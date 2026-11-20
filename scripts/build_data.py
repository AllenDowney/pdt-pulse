#!/usr/bin/env python3
"""Write the Household Pulse Survey data in the common format (STANDARD.md §8).

    python scripts/build_data.py [RELEASE ...]      (make data RELEASES="week01 week02")

For each release (cycle) named, or every release when none is named, reads the PUF and the
replicate-weight CSV inside the cycle's zip (pdt.readers.read_csv_zip) and writes
data/processed/pulse-<release>-puf.parquet and -repwgt.parquet with the variables this repo has
records for. pdt.release compares every cell with the CSV's. Run one release per process under a
memory cap; the files are large.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))

try:
    from pdt.readers import read_csv_zip
    from pdt.release import data_source, write_release
except ImportError:
    sys.exit("Needs the PublicDataToolkit library: pip install -e ../PublicDataToolkit, or run through `make data`.")
import hps  # noqa: E402


def read(release, table, names):
    source = data_source(ROOT, release, table)
    path = ROOT / source["path"]
    if not path.exists():
        return None
    return read_csv_zip(path, hps.zip_members(path)[table], names), source["id"]


if __name__ == "__main__":
    write_release(ROOT, read, releases=sys.argv[1:] or None)
