# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Replication package for paper 4: reproduces every table and figure from committed inputs. The analysis library, [citegraph](https://github.com/yabramuvdi/citegraph), lives in a separate repo and is pinned by commit in `requirements.txt` (installed into `.venv`, so read its source under `.venv/lib/python3.11/site-packages/citegraph/`).

## Commands

```bash
make env        # .venv from requirements.txt (Python 3.11.10, fully pinned)
make            # tables + figures + workbook + export; offline, no API key
make tables     # institutional/out/*.csv only
make figures    # runs both figure notebooks via run_notebooks.py (fails on first cell error)
make export     # core_papers_export.xlsx
make pipeline   # optional: re-derive citegraph_out/ CSVs from per-paper caches (enrich may hit network)
make clean
```

Run one notebook: `.venv/bin/python run_notebooks.py notebooks/paper4_figures.ipynb`. Notebooks execute with `notebooks/` as cwd. There is no test suite; verification is re-running `make` and checking outputs — two runs must give byte-identical PNGs (PDFs differ only in creation date).

## Architecture

Three independent input streams feed the figures:

1. **Career base** — `base_institucional.xlsx` (raw, hand-collected, **never edited by code**) → `institutional/build_clean_base.py` applies curated crosswalks (`crosswalk_institutions.csv`, `crosswalk_people.csv`, `crosswalk_fields.csv`) and guarded `corrections.csv` → `institutional/out/`. The `make_*crosswalk*.py` scripts only append new raw strings; existing rows (hand edits) are preserved. See `institutional/README.md` for the run order and modelling decisions (`No` vs `Not found` three-valued status, ROR-id grouping, visiting ≠ postdoc, doctoral-only supervision).
2. **Citation corpus** — `citegraph_out/` is **frozen**: output of the citegraph pipeline over the 93 core papers plus the curated steering files (`journal_aliases.csv`, `author_aliases.csv`, `author_external_ids.csv`, `work_annotations.csv`, `annotation_schema.csv`). LLM extraction and CrossRef/OpenAlex enrichment are not repeatable, so per-paper caches (`metadata/`, `references/`, `enrichment/`) are committed. `authors.csv` and `author_citations.csv` do **not** reproduce under the pinned citegraph and must not be regenerated — all paper numbers use the frozen files.
3. **Core-paper annotations** — `citegraph_out/work_annotations.csv` is the authoritative, hand-edited source for `Tema`/`Publication_Type`, validated against `annotation_schema.csv` on load. `core_papers.xlsx` is the legacy source it was imported from once (`annotations/make_work_annotations.py`); `core_papers_export.xlsx` is a read-only export. Never edit `works.csv` (stage 4 regenerates it).

Figures load the corpus via `CitationGraph.from_out_dir(OUT_DIR)` (annotations join onto `g.core`, `g.ring(n)`, `g.works`). Each figure is written as PDF + PNG, a grayscale proof under `gray/`, and `<stem>.caption.md`. In the institutional notebook, plain `figN_` stems are what the manuscript cites; `*alt*` stems are competing candidates.

## Constraints

- Copyrighted inputs are excluded: the PDFs (`data/`) and `citegraph_out/markdown/`. Don't add them.
- `base_institucional.xlsx` contains career data on named researchers.
- `docs/DATA_QUALITY_NOTES.md` lists an unfixed issue affecting journal-level counts; `docs/NETWORK_METHODOLOGY.md` explains the co-citation network choices.
- The extraction LLM is set by `MODEL` in the `Makefile`.
