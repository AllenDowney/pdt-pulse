"""Build the Household Pulse Survey records: one release per cycle (week01-week63, cycle01-cycle09).

Usage:
    python build/build_records.py        (make build; needs the PublicDataToolkit library)

Reads build/slice.yaml, dataset.yaml (the releases, in order) and each cycle's data dictionary,
which is inside its CSV zip in data/raw/. Writes metadata/releases/<release>/{puf,repwgt}/
variables.jsonl, metadata/groups.jsonl, metadata/links.jsonl and build/report.md.

Where each field comes from (STANDARD.md §3):
- label, description, question text, universe, notes, values: the cycle's data dictionary
  (Description, Question Wording, Values, Universe, Internal Notes). Text is copied with Excel's
  escaped carriage returns and line breaks removed (rule hps_strip_x000d).
- which codes are valid: the dictionary's Range ("1:4"). Codes the Values list outside the
  Range (-99, -88) are missing; their types are by rule hps_missing_types, from the label.
  A Range that spans values rather than codes (a birth year, "1:40" people) is a valid_range.
- measure, variable_type: build/slice.yaml (hand), by kind.
- the replicate weights PWEIGHT1-80: the dictionary describes them once (or not at all);
  their records are made by rule hps_replicate_series.
- links between consecutive cycles: rule hps_same_name_same_dictionary, or Census's user notes
  where they state a change (slice.yaml `documented_changes`).
"""

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from pdt.compare import compare_text, is_change
    from pdt.release import data_source
except ImportError:
    sys.exit("Needs the PublicDataToolkit library on PYTHONPATH (make build sets it).")
import hps  # noqa: E402

META = ROOT / "metadata"
DATASET = "pulse"
RULES = {"strip": ("hps_strip_x000d", "0.1"), "missing": ("hps_missing_types", "0.1"),
         "series": ("hps_replicate_series", "0.1"), "links": ("hps_same_name_same_dictionary", "0.1")}
# Missing types by the dictionary's label (rule hps_missing_types).
TYPES = {"question seen but category not selected": ["skipped"], "missing / did not report": ["no_answer"]}


def jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def types_of(label):
    return TYPES.get(" ".join(label.lower().split()), ["unspecified"])


def strip_note():
    rule, version = RULES["strip"]
    return {"origin": "rule", "rule": rule, "rule_version": version,
            "note": "The dictionary's text with Excel's escaped carriage returns (_x000D_) and line breaks removed."}


def build_puf(release, wave, source, book, cfg, report):
    hand = {"origin": "hand", "author": cfg["author"], "date": cfg["date"]}
    records = []
    for name, facts in cfg["puf"].items():
        e = book.get(name)
        if not e:
            continue
        loc = f"{e['file']}, row {e['row']}"
        pub = {"origin": "publisher", "source": source, "location": loc}
        rec = {"dataset": DATASET, "release": release, "table": "puf", "name": name}
        fields = {}
        if e["description"]:
            rec["label"] = e["description"]
        if e["question"] and e["question"] != "-":
            rec["questions"] = [{"text": e["question"], **({"number": e["qnum"]} if e["qnum"] not in ("-", None) else {})}]
            fields["questions"] = {**pub, "note": strip_note()["note"]}
        if e["universe"]:
            rec["universe"] = e["universe"]
        if e["notes"]:
            rec["notes"] = e["notes"]
        valid = hps.valid_codes(e["range"])
        values, ranges = [], []
        for code, label in e["values"]:
            if isinstance(code, str):                       # "1-10) number of people": a range, not a code
                ranges.append((code, label))
            elif valid is not None and code not in valid:
                rule, version = RULES["missing"]
                values.append({"code": code, "label": label, "kind": "missing", "missing_types": types_of(label),
                               "origin": {**pub, "note": f"Outside the dictionary's Range ({e['range']}). Types by "
                                                         f"rule {rule} {version}, from the label."}})
            else:
                values.append({"code": code, "label": label, "kind": "valid"})
        if values:
            rec["values"] = values
            fields["values"] = {**pub, "note": strip_note()["note"]}
        m = re.fullmatch(r"(-?\d+):(-?\d+)", e["range"] or "")
        if valid is None and m:
            rec["valid_range"] = {"min": int(m.group(1)), "max": int(m.group(2)),
                                  **({"note": e["notes"]} if e["notes"] and "code" in e["notes"].lower() else {})}
            fields["valid_range"] = {**pub, "note": f"The dictionary's Range, {e['range']}."}
        elif ranges and valid:
            rec["valid_range"] = {"min": min(valid), "max": max(valid)}
            fields["valid_range"] = {**pub, "note": f"The dictionary's Range, {e['range']} ({ranges[0][1]})."}
        rec["storage_type"] = ("string" if facts["kind"] == "id" else "float" if facts["kind"] == "weight"
                               else "integer")
        kind = cfg["kinds"][facts["kind"]]
        rec["variable_type"] = kind["variable_type"]
        fields["variable_type"] = {**hand, "note": f"By kind ({facts['kind']}) in build/slice.yaml."}
        if kind.get("measure"):
            rec["measure"] = kind["measure"]
            fields["measure"] = dict(fields["variable_type"])
        rec["availability"] = [{"wave": wave}]
        fields["availability"] = {"origin": "publisher", "source": source,
                                  "note": "Each cycle is one release; the variable is in its dictionary."}
        rec["source_location"] = {"source": source, "upstream_id": name}
        rec["provenance"] = {"record": pub, "fields": fields}
        records.append(rec)
    return records


def build_repwgt(release, wave, source, book, cfg, puf_names):
    rule, version = RULES["series"]
    series = {"origin": "rule", "rule": rule, "rule_version": version, "source": source,
              "note": f"The replicate-weight file's columns {cfg['repwgt']['prefix']}1-{cfg['repwgt']['n']}, which "
                      "the dictionary doesn't list one by one."}
    hand = {"origin": "hand", "author": cfg["author"], "date": cfg["date"]}
    out = []
    for name in ["SCRAM"] + [n for n in ("WEEK", "CYCLE") if n in puf_names]:
        e = book.get(name, {})
        out.append({"dataset": DATASET, "release": release, "table": "repwgt", "name": name,
                    **({"label": e["description"]} if e.get("description") else {}),
                    "storage_type": "string" if name == "SCRAM" else "integer",
                    "variable_type": "administrative", "measure": "identifier",
                    "availability": [{"wave": wave}],
                    "provenance": {"record": {"origin": "publisher", "source": source},
                                   "fields": {"variable_type": hand, "measure": hand}}})
    for i in range(1, cfg["repwgt"]["n"] + 1):
        out.append({"dataset": DATASET, "release": release, "table": "repwgt", "name": f"{cfg['repwgt']['prefix']}{i}",
                    "label": f"Person replicate weight {i}", "storage_type": "float",
                    "variable_type": "weight", "measure": "weight", "availability": [{"wave": wave}],
                    "provenance": {"record": series}})
    return out


def links_between(old, new, recs_old, recs_new, cfg):
    rule, version = RULES["links"]
    by_new = {r["name"]: r for r in recs_new}
    out, report = [], []
    documented = {(d["first"], v): d for d in cfg["documented_changes"] for v in d["variables"]}
    for r in recs_old:
        s = by_new.get(r["name"])
        if s is None:
            continue
        relations, notes = ["same_item"], []
        qa = (r.get("questions") or [{}])[0].get("text")
        qb = (s.get("questions") or [{}])[0].get("text")
        if is_change(compare_text(qa, qb)):
            relations.append("wording_changed")
            notes.append("question wording changed")
        va = {str(v["code"]): v.get("label") for v in r.get("values", [])}
        vb = {str(v["code"]): v.get("label") for v in s.get("values", [])}
        if set(va) != set(vb) or r.get("valid_range") != s.get("valid_range"):
            relations.append("codes_changed")
            notes.append(f"codes or range: {sorted(set(va) ^ set(vb)) or ''} "
                         f"{r.get('valid_range')} -> {s.get('valid_range')}".strip())
        changed = [c for c in va if c in vb and is_change(compare_text(va[c], vb[c]))]
        if changed or is_change(compare_text(r.get("label"), s.get("label"))):
            relations.append("labels_changed")
            notes += [f"code {c} {va[c]!r} -> {vb[c]!r}" for c in changed]
            if is_change(compare_text(r.get("label"), s.get("label"))):
                notes.append(f"label {r.get('label')!r} -> {s.get('label')!r}")
        doc = documented.get((new, r["name"]))
        if doc:
            if doc["relation"] not in relations:
                report.append(f"- `{r['name']}` {old}->{new}: Census documents {doc['relation']}, "
                              "but the dictionaries don't show it")
                relations.append(doc["relation"])
            origin = {"origin": "publisher", "source": doc["source"], "location": doc["location"],
                      "note": f"\"{doc['quote']}\""}
        else:
            origin = {"origin": "rule", "rule": rule, "rule_version": version, "source": s["provenance"]["record"]["source"]}
        out.append({"from": {"release": old, "table": "puf", "name": r["name"]},
                    "to": {"release": new, "table": "puf", "name": r["name"]}, "relations": relations,
                    "origin": origin,
                    "note": "The same name in consecutive cycles; their dictionaries compared."
                            + (" Changed: " + "; ".join(notes) + "." if notes else "")})
    return out, report


def main():
    cfg = yaml.safe_load((ROOT / "build" / "slice.yaml").read_text())
    ds = yaml.safe_load((ROOT / "dataset.yaml").read_text())
    report, groups, links, built = [], [], [], []
    for r in ds["releases"]:
        release = r["id"]
        src = data_source(ROOT, release, "puf")
        path = ROOT / src["path"]
        if not path.exists():
            report.append(f"- {release}: {path.name} is missing")
            continue
        book = hps.dictionary(path)
        wave = release
        puf = build_puf(release, wave, src["id"], book, cfg, report)
        rep = build_repwgt(release, wave, src["id"], book, cfg, {x["name"] for x in puf})
        jsonl(META / "releases" / release / "puf" / "variables.jsonl", puf)
        jsonl(META / "releases" / release / "repwgt" / "variables.jsonl", rep)
        rule, version = RULES["series"]
        groups.append({"id": f"{release}.replicate-weights", "kind": "other", "label": "Person replicate weights",
                       "releases": [release], "ordered": True,
                       "members": [{"release": release, "table": "repwgt", "name": x["name"]} for x in rep
                                   if x["name"].startswith(cfg["repwgt"]["prefix"])],
                       "origin": {"origin": "rule", "rule": rule, "rule_version": version, "source": src["id"]},
                       "note": "The 80 replicate weights of successive difference replication (dataset.yaml design)."})
        missing = [n for n in cfg["puf"] if n not in book]
        report.append(f"- {release}: {len(puf)} puf records; not in this cycle: {', '.join(missing) or 'none'}")
        built.append((release, puf))
    for (old, a), (new, b) in zip(built, built[1:]):
        more, lines = links_between(old, new, a, b, cfg)
        links += more
        report += lines
    jsonl(META / "groups.jsonl", groups)
    jsonl(META / "links.jsonl", links)
    from collections import Counter
    rels = Counter(tuple(l["relations"]) for l in links)
    head = ["# Build report: pulse", "", "Generated by `build/build_records.py`. Do not edit.", "",
            f"- {len(built)} releases; {sum(len(p) for _, p in built)} puf records; {len(groups)} groups; "
            f"{len(links)} links", "- Link relations: " + "; ".join(f"{', '.join(k)}: {v}" for k, v in rels.most_common()),
            ""]
    (ROOT / "build" / "report.md").write_text("\n".join(head + report) + "\n")
    print("\n".join(head + report[-12:]))


if __name__ == "__main__":
    main()
