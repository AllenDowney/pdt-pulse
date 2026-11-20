PYTHON ?= python
# A PublicDataToolkit checkout. Or `pip install -e $(PDT)` and run `pdt check`.
PDT ?= ../PublicDataToolkit

.PHONY: download build views check

## Fetch the sources into data/raw. Read the publisher's terms first, then: make download ARGS=--accept-terms
download:
	PYTHONPATH=$(PDT)/lib $(PYTHON) scripts/download.py $(ARGS)

## Build metadata records from data/raw (build/build_records.py writes build/report.md)
build:
	$(PYTHON) build/build_records.py

## Generate agent/, docs/ and export/ from the records (pdt views)
views:
	PYTHONPATH=$(PDT)/lib $(PYTHON) -m pdt views .

## Check the repo against the PublicDataToolkit standard (pdt check)
check:
	PYTHONPATH=$(PDT)/lib $(PYTHON) -m pdt check .
