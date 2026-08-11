PYTHON ?= python3
PAPERS_DIR ?= ..

.PHONY: build update preview serve test

build:
	$(PYTHON) scripts/build_graph.py --papers-dir "$(PAPERS_DIR)"

update:
	$(PYTHON) scripts/update_library.py --papers-dir "$(PAPERS_DIR)"
	$(PYTHON) scripts/capture_preview.py

preview:
	$(PYTHON) scripts/capture_preview.py

serve:
	$(PYTHON) scripts/serve_graph.py --papers-dir "$(PAPERS_DIR)"

test:
	$(PYTHON) -m unittest discover -s tests -v
