PYTHON ?= python
# A PublicDataToolkit checkout. Or `pip install -e $(PDT)` and run `pdt check`.
PDT ?= ../PublicDataToolkit

.PHONY: download build data views check export-daaf

## Fetch the sources into data/raw. Read the publisher's terms first, then: make download ARGS=--accept-terms
download:
	PYTHONPATH=$(PDT)/lib $(PYTHON) scripts/download.py $(ARGS)

## Build metadata records from data/raw (build/build_records.py writes build/report.md)
build:
	PYTHONPATH=$(PDT)/lib $(PYTHON) build/build_records.py

## Write the data in the common format, data/processed/, one release at a time (scripts/build_data.py)
data:
	PYTHONPATH=$(PDT)/lib $(PYTHON) scripts/build_data.py $(RELEASES)

## Generate agent/, docs/ and export/ from the records (pdt views)
## VIEWS_ARGS="--only site" builds docs/ alone, as the Pages workflow does.
views:
	PYTHONPATH=$(PDT)/lib $(PYTHON) -m pdt views . $(VIEWS_ARGS)

## Check the repo against the PublicDataToolkit standard (pdt check)
check:
	PYTHONPATH=$(PDT)/lib $(PYTHON) -m pdt check .

## On request: export/daaf/, this dataset as a DAAF data-source skill (pdt export daaf).
## The skill's name starts with dataset.yaml's `domain`; ARGS="--domain health" overrides it.
export-daaf:
	PYTHONPATH=$(PDT)/lib $(PYTHON) -m pdt export daaf . $(ARGS)
