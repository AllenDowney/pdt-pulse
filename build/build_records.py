"""Build the Household Pulse Survey (HPS) metadata records from the publisher's documentation and the data file.

Usage:
    python build/build_records.py

Reads build/slice.yaml and the sources in data/raw/ (sources.yaml). Writes
metadata/releases/<release>/variables.jsonl and build/report.md.

Where each field comes from (keep this list current; STANDARD.md §3):
- label, question text, codes and labels, availability: TODO, the documentation
- which codes occur, availability counts: the data file
- measure: build/slice.yaml (hand)
- missing types, storage type: rules in this file, each named and versioned

To fill in parse_documentation() and read_data(), use the skill for the source
format in PublicDataToolkit/skills/, and follow
PublicDataToolkit/instructions/03-parse-documentation.md to 05-availability.md.
The data checks below (C3-C5) run here until `pdt check` runs them.
"""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
META = ROOT / "metadata"
DATASET = "pulse"

RULE_VERSION = "0.1"


# ---------------------------------------------------------------- inputs

def load_slice():
    return yaml.safe_load((ROOT / "build" / "slice.yaml").read_text())


def parse_documentation(names):
    """Return {name: entry} for the wanted names, from the documentation in data/raw/.

    Probe the source first (skills/from-*/SKILL.md). Strip layout, never content:
    page-break headers, running headers, line breaks from page width.
    """
    raise NotImplementedError("write the parser for this dataset's documentation")


def read_data(names):
    """Return (all column names, {name: {code: count}}, {name: {wave: n}}) from the data file.

    Keep the publisher's missing tokens (Stata: convert_missing=True; see
    skills/from-data-labels/SKILL.md).
    """
    raise NotImplementedError("write the reader for this dataset's data file")


# ---------------------------------------------------------------- build

def build_variable(name, spec, entry, release):
    """One record (STANDARD.md §4). Every field not from the record's source gets its origin."""
    record = {"dataset": DATASET, "release": release, "name": name}
    # record["label"] = ...; record["questions"] = [...]; record["values"] = [...]
    # record["availability"] = [{"wave": ...}, ...]
    if spec.get("measure"):
        record["measure"] = spec["measure"]
    record["provenance"] = {
        "record": {"origin": "publisher", "source": "TODO"},
        "fields": {"measure": {"origin": "hand", "author": "TODO", "date": "TODO"}} if spec.get("measure") else {},
    }
    return record


# ---------------------------------------------------------------- checks against the data

def check_coverage(documented, columns):
    """C3: names in the data without documentation, and the other way, compared case-insensitively."""
    doc = {n.upper() for n in documented}
    data = {n.upper() for n in columns}
    return sorted(data - doc), sorted(doc - data)


def check_codes(record, occurring):
    """C4: codes that occur in the data but aren't in the record's values."""
    listed = {str(v["code"]) for v in record.get("values", [])}
    return sorted((c, n) for c, n in occurring.items() if str(c) not in listed)


def check_availability(record, counts):
    """C5: waves in availability with no data, and waves with data not in availability."""
    recorded = {a["wave"] for a in record.get("availability", [])}
    with_data = {w for w, n in counts.items() if n}
    return sorted(recorded - with_data), sorted(with_data - recorded)


# ---------------------------------------------------------------- main

def main():
    spec = load_slice()
    release = spec["release"]
    names = list(spec.get("variables") or {})
    records, report = [], []
    if names:
        docs = parse_documentation(names)
        columns, codes, counts = read_data(names)
        undocumented, missing = check_coverage(docs, columns)
        report += ["## C3: coverage", "",
                   f"- In the data but not the documentation: {undocumented or 'none'}",
                   f"- In the documentation but not the data: {missing or 'none'}", ""]
        to_look_at = []
        for name in names:
            rec = build_variable(name, spec["variables"][name] or {}, docs[name], release)
            for code, n in check_codes(rec, codes.get(name, {})):
                to_look_at.append(f"- `{name}` code {code}: occurs {n} times, not documented")
            extra, absent = check_availability(rec, counts.get(name, {}))
            if extra or absent:
                to_look_at.append(f"- `{name}`: waves without data {extra}; waves with data not recorded {absent}")
            records.append(rec)
        report += ["## Values, labels and waves to look at", ""] + (to_look_at or ["None."])
    write_jsonl(META / "releases" / release / "variables.jsonl", records)
    write_report(release, records, report)


def write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def write_report(release, records, body):
    lines = [f"# Build report: {DATASET}, release {release}", "",
             "Generated by `build/build_records.py`. Do not edit.", "",
             f"- Variables: {len(records)}", ""] + body
    (ROOT / "build" / "report.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
