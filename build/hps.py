"""Read the Census Bureau's Household Pulse Survey files: the per-cycle zips and their data dictionaries.

    zip_members(zip)          {"dictionary": name, "puf": name, "repwgt": name} inside a cycle's CSV zip
    dictionary(zip)           {variable: entry} from the cycle's data dictionary (xlsx)
    values_of(text)           [(code, label)] from a dictionary's Values cell ("1) Male\\n2) Female")
    valid_codes(range_text)   the codes the Range column allows ("1:4", "1,2", "<blank>,1"), or None

A dictionary lists each variable in a block of rows: the question number, the name,
"Description" with the description, the question wording, the Range; then "Values",
"Universe" and "Internal Notes" rows. Excel's escaped carriage return (_x000D_) is a
layout artifact and is removed (rule hps_strip_x000d), as are line breaks inside a cell.
"""

import io
import re
import zipfile

X000D = re.compile(r"_x000D_\s*")


def clean(text):
    """A dictionary cell as text: _x000D_ removed, runs of whitespace (line breaks) made one space."""
    if text is None:
        return None
    return " ".join(X000D.sub(" ", str(text)).split())


def zip_members(path):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
    pick = lambda pat: next((n for n in names if re.search(pat, n, re.I)), None)  # noqa: E731
    return {"dictionary": pick(r"dictionary.*\.xlsx$"), "puf": pick(r"_puf_\d+\.csv$|puf_?\d*\.csv$"),
            "repwgt": pick(r"repwgt.*\.csv$")}


def values_of(text):
    """[(code, label)] from a Values cell: one "code) label" per line. A range "1-10) ..." is one entry."""
    out = []
    for line in X000D.sub("\n", str(text or "")).split("\n"):
        m = re.match(r"^\s*(-?\d+(?:-\d+)?)\)\s*(.*?)\s*$", line)
        if m:
            code = m.group(1)
            out.append((int(code) if re.fullmatch(r"-?\d+", code) else code, " ".join(m.group(2).split())))
    return out


def valid_codes(range_text):
    """The codes the Range column allows: "1:4" -> {1..4}; "1,2" -> {1, 2}; "<blank>,1" -> {1};
    "Varying" or a year range -> None (not a list of codes)."""
    t = clean(range_text) or ""
    codes = set()
    for part in t.split(","):
        part = part.strip()
        m = re.fullmatch(r"(-?\d+):(-?\d+)", part)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            if hi - lo > 50:
                return None
            codes.update(range(lo, hi + 1))
        elif re.fullmatch(r"-?\d+", part):
            codes.add(int(part))
        elif part.lower() in ("<blank>", ""):
            continue
        else:
            return None
    return codes or None


def dictionary(zip_path):
    """{variable: {qnum, description, question, range, values, universe, notes, row}} for one cycle."""
    import openpyxl
    name = zip_members(zip_path)["dictionary"]
    with zipfile.ZipFile(zip_path) as z:
        book = openpyxl.load_workbook(io.BytesIO(z.read(name)), read_only=True)
    rows = list(book[book.sheetnames[0]].iter_rows(values_only=True))
    out, current = {}, None
    for i, row in enumerate(rows, start=1):
        row = list(row) + [None] * 7
        label = clean(row[2]) or ""
        if row[1] and label.lower().startswith("description"):
            current = out.setdefault(clean(row[1]), {
                "qnum": clean(row[0]), "description": clean(row[3]), "question": clean(row[4]),
                "range": clean(row[5]), "values_text": None, "universe": None, "notes": None, "row": i,
                "sheet": book.sheetnames[0], "file": name})
        elif current is not None and label.lower().startswith("values"):
            current["values_text"] = row[3]
        elif current is not None and label.lower().startswith("universe"):
            current["universe"] = clean(row[3])
        elif current is not None and label.lower().startswith("internal notes"):
            current["notes"] = clean(row[3])
    for entry in out.values():
        entry["values"] = values_of(entry.pop("values_text"))
    return out
