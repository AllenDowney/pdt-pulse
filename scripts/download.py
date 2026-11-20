#!/usr/bin/env python3
"""Fetch the files this repo is built from, as sources.yaml lists them.

    python scripts/download.py --check            # what is present; no network
    python scripts/download.py --accept-terms     # fetch what's missing

Read the publisher's terms before downloading:

    https://www.census.gov/about/policies/open-gov.html

The script won't fetch anything until you pass --accept-terms. PDF codebooks are
converted with `pdftotext -layout` (poppler-utils). Sources with
`acquisition: manual` print their manual steps instead.

Uses the PublicDataToolkit library (pdt.download); `make download` sets PYTHONPATH.
"""

import sys
from pathlib import Path

try:
    from pdt.download import main
except ImportError:
    sys.exit("Needs the PublicDataToolkit library: pip install -e ../PublicDataToolkit, "
             "or run through `make download`.")

ROOT = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    sys.exit(main([str(ROOT), *sys.argv[1:]]))
