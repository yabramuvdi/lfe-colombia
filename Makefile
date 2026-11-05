# Paper 4 replication package. `make` rebuilds every table and figure from the
# committed inputs; nothing here needs network access or an API key except
# the optional `pipeline` target.

PY        := .venv/bin/python
CITEGRAPH := .venv/bin/citegraph
OUT       := citegraph_out

# LLM used for metadata and reference extraction (stages 2-3 of `pipeline`).
MODEL     := gemini-3.1-flash-lite

.PHONY: all env tables figures workbook export pipeline clean

all: tables figures workbook export

env: $(PY)
$(PY): requirements.txt
	python3.11 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt
	touch $(PY)

# Career base: base_institucional.xlsx + crosswalks -> institutional/out/*.csv
tables: $(PY)
	cd institutional && ../$(PY) build_clean_base.py

# Every manuscript figure, written to institutional/out/figures/ and
# citegraph_out/figures/. paper4_figures also writes citegraph_out/author_centrality.csv.
figures: tables
	$(PY) run_notebooks.py notebooks/paper4_institutional_figures.ipynb notebooks/paper4_figures.ipynb

# One workbook of everything known about the authors of the core papers.
workbook: tables figures
	$(CITEGRAPH) export-authors --out $(OUT) \
	  --extra-csv Institutional=institutional/out/base_institucional_clean.csv \
	  --extra-csv Career_Positions=institutional/out/career_positions.csv \
	  --extra-csv Supervision=institutional/out/supervision.csv \
	  --master-column Institutional=affiliation_institution \
	  --master-column Institutional=affiliation_department \
	  --master-column Institutional=affiliation_field \
	  --master-column Institutional=affiliation_country \
	  --master-column Institutional=phd_institution \
	  --master-column Institutional=phd_year_end \
	  --master-column Institutional=phd_field

# A read-only Excel view of the 93 core papers and their annotations, for
# reviewing. Edit citegraph_out/work_annotations.csv, never this workbook.
export: $(PY)
	cd annotations && ../$(PY) make_core_papers_xlsx.py

# Optional: re-derive citegraph_out/ from its per-paper caches. Stages 2-3 are
# served from metadata/ and references/ without calling the LLM; enrichment
# queries CrossRef/OpenAlex for any work whose cached result is missing or was a
# transient failure. Converting PDFs (stage 1) needs data/ and is not part of it.
pipeline: $(PY)
	$(CITEGRAPH) metadata   --out $(OUT) --model $(MODEL)
	$(CITEGRAPH) references --out $(OUT) --model $(MODEL) --yes
	$(CITEGRAPH) dedup      --out $(OUT)
	$(CITEGRAPH) enrich     --out $(OUT) --enrich-max-workers 2
	$(CITEGRAPH) authors    --out $(OUT)
	$(CITEGRAPH) jel        --out $(OUT)

clean:
	rm -rf institutional/out $(OUT)/figures $(OUT)/core_authors.xlsx core_papers_export.xlsx
