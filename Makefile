PYTHON ?= python3
PAPERS_DIR ?= ..

.PHONY: build serve test

build:
	$(PYTHON) scripts/build_graph.py --papers-dir "$(PAPERS_DIR)"

serve:
	$(PYTHON) -m http.server 8000 --directory web

test:
	$(PYTHON) -m unittest discover -s tests -v
