#!/usr/bin/env python3
"""Write the Household Pulse Survey data in the common format (STANDARD.md §8).

    python scripts/build_data.py [RELEASE ...]      (make data RELEASES="week01 week02")

For each release (cycle) named, or every release when none is named, reads the PUF and the
replicate-weight CSV inside the cycle's zip (pdt.readers.read_csv_zip; for week 55, the
SAS files, pdt.readers.read_sas) and writes
data/processed/pulse-<release>-puf.parquet and -repwgt.parquet with the variables this repo has
records for, and in -repwgt the replicate weights PWEIGHT1-80 that dataset.yaml's design names. pdt.release compares every cell with the CSV's. Run one release per process under a
memory cap; the files are large.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))

try:
    from pdt.readers import read_csv_zip, read_sas
    from pdt.release import data_source, write_release
except ImportError:
    sys.exit("Needs the PublicDataToolkit library: pip install -e ../PublicDataToolkit, or run through `make data`.")
import hps  # noqa: E402


def read(release, table, names):
    source = data_source(ROOT, release, table)
    path = ROOT / source["path"]
    if not path.exists():
        return None
    member = hps.zip_members(path)[table]
    if member.endswith(".sas7bdat"):            # week 55: Census serves only its SAS zip
        import zipfile
        out = ROOT / "data" / "interim" / release / member
        if not out.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(path) as z:
                out.write_bytes(z.read(member))
        return read_sas(out, names), source["id"]
    return read_csv_zip(path, member, names), source["id"]


if __name__ == "__main__":
    write_release(ROOT, read, releases=sys.argv[1:] or None)
