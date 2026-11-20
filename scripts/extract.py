#!/usr/bin/env python3
"""Write an extract of this dataset from the common-format files in data/processed (STANDARD.md §8).

Run `make data` first. Then, for example:

    python scripts/extract.py --release 2024 --vars AGE,SEX,WEIGHT --out extract.csv
    python scripts/extract.py --release 2024 --table person --vars @vars.txt \\
        --missing dk=DK refused=DK --codes --out extract.parquet

You name the variables, the release (and the table, for a release with several),
the waves, and what to do with each missing type: `--missing dk=DK refused=DK`
replaces those types, and every other missing value is null. Unresolved codes
are null too, unless you pass --unresolved. --codes keeps each variable's code
column. The extract makes no analysis choices of its own.

The releases and tables are dataset.yaml's; a wrong or missing --release or --table
gets the list. What the extract relied on goes to stderr, including every code
classified, or made valid, only by an `inferred` correction (STANDARD.md §5.3).

Uses the PublicDataToolkit library (pdt.extract) with its data extra:
`pip install -e "../PublicDataToolkit[data]"`, or run with PYTHONPATH=../PublicDataToolkit/lib.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
NEEDS = ("Needs the PublicDataToolkit library with its data extra: "
         "pip install -e \"../PublicDataToolkit[data]\", or run with PYTHONPATH=../PublicDataToolkit/lib.")


def releases():
    """[(release id, [table ids])] from dataset.yaml; a release without tables has [None]."""
    import yaml
    with open(ROOT / "dataset.yaml") as f:
        dataset = yaml.safe_load(f)
    return dataset["id"], [(str(r["id"]), [str(t["id"]) for t in r.get("tables") or []] or [None])
                           for r in dataset.get("releases") or []]


def listing(rels):
    return "\n".join(f"  {rel}" + (f"  tables: {', '.join(tabs)}" if tabs != [None] else "")
                     for rel, tabs in rels)


def preflight(argv):
    """Refuse, with the fix, before reading anything: no data, an unknown release or table."""
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--release")
    p.add_argument("--table")
    p.add_argument("-h", "--help", action="store_true")
    args, _ = p.parse_known_args(argv)
    dataset_id, rels = releases()
    if args.help:
        return f"Releases in dataset.yaml:\n{listing(rels)}"
    if not PROCESSED.is_dir() or not any(PROCESSED.glob("*.parquet")):
        sys.exit(f"{PROCESSED.relative_to(ROOT)}/ has no data files. Run `make data` first "
                 "(it needs the source files in data/raw/: `make download`).")
    tables = dict(rels)
    if args.release is None or args.release not in tables:
        what = "Name a release with --release" if args.release is None else f"No release {args.release!r}"
        sys.exit(f"{what}. Releases in dataset.yaml:\n{listing(rels)}")
    if args.table not in tables[args.release]:
        what = ("Release {} has several tables; name one with --table" if args.table is None
                else "Release {} has no table " + repr(args.table))
        sys.exit(what.format(args.release) + f". Releases in dataset.yaml:\n{listing(rels)}")
    from pdt.common_format import file_name
    path = PROCESSED / file_name(dataset_id, args.release, args.table)
    if not path.exists():
        sys.exit(f"{path.relative_to(ROOT)} doesn't exist. Run `make data` "
                 f"(or `make data RELEASES={args.release}`, where the Makefile takes it).")
    return None


def main(argv):
    try:
        import pdt.common_format  # noqa: F401  (the base install: the checks below need no pandas)
    except ImportError:
        sys.exit(NEEDS)
    help_text = preflight(argv)
    try:
        from pdt.extract import main as extract_main
    except ImportError as e:
        sys.exit(f"{NEEDS} ({e})")
    if help_text:
        print(help_text + "\n")
    return extract_main([str(ROOT), *argv])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
