PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
PAPERS_DIR ?= ..

.PHONY: start build update discover discover-shared accept reject preview serve test mac-app

start:
	$(PYTHON) scripts/start_app.py

build:
	$(PYTHON) scripts/build_graph.py --papers-dir "$(PAPERS_DIR)"

update:
	$(PYTHON) scripts/update_library.py --papers-dir "$(PAPERS_DIR)"
	$(PYTHON) scripts/capture_preview.py

discover:
	$(PYTHON) scripts/discover_papers.py --skip-shared

discover-shared:
	$(PYTHON) scripts/discover_papers.py --skip-arxiv

accept:
	$(PYTHON) scripts/manage_candidate.py accept --id "$(ID)" --category "$(CATEGORY)" --papers-dir "$(PAPERS_DIR)"
	$(PYTHON) scripts/update_library.py --papers-dir "$(PAPERS_DIR)"

reject:
	$(PYTHON) scripts/manage_candidate.py reject --id "$(ID)"

preview:
	$(PYTHON) scripts/capture_preview.py

serve:
	$(PYTHON) scripts/serve_graph.py --papers-dir "$(PAPERS_DIR)"

test:
	$(PYTHON) -m unittest discover -s tests -v

mac-app:
	platform/macos/build_app.sh
