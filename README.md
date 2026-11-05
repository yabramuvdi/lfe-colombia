# Paper 4 — replication package

Code and data that reproduce every table and figure of paper 4. The analysis
library, [citegraph](https://github.com/yabramuvdi/citegraph), is a separate
repository; this package pins the exact commit it was run with.

## Reproduce

Requires Python 3.11 and `make`.

```bash
make env    # create .venv from requirements.txt (pinned versions)
make        # tables, figures and the core-author workbook
```

`make` needs no network access and no API key. It writes:

| Output | Made by |
| --- | --- |
| `institutional/out/*.csv` | `institutional/build_clean_base.py`: the cleaned career base and supervision ties |
| `institutional/out/figures/` | `notebooks/paper4_institutional_figures.ipynb`: careers, doctoral lineages, supervision × co-citation |
| `citegraph_out/figures/` | `notebooks/paper4_figures.ipynb`: corpus, citation and co-citation figures |
| `citegraph_out/core_authors.xlsx` | `citegraph export-authors`: everything known about the authors of the core papers |
| `core_papers_export.xlsx` | `annotations/make_core_papers_xlsx.py`: the 93 core papers with their topic and publication type, for review |

Each figure is saved as PDF + PNG, with a grayscale proof under `gray/` and its
caption and notes in `<stem>.caption.md`. Two runs produce byte-identical PNGs.
PDFs differ only in their embedded creation date.

## What is in here

```
base_institucional.xlsx   hand-collected careers of the 58 core authors (raw; never edited by code)
core_papers.xlsx          legacy curated sheet of the 93 core papers; Tema / Publication_Type were imported
                          from it once and are now edited in citegraph_out/work_annotations.csv
institutional/            cleaning pipeline for the career base; crosswalks and corrections are curated inputs
annotations/              one-time import of core_papers.xlsx into citegraph_out/work_annotations.csv
citegraph_out/            the citation corpus, frozen (see below)
notebooks/                the two figure notebooks, and paper4_pipeline.ipynb: the stage-by-stage
                          walkthrough that built citegraph_out/, with its inspection cells
docs/                     NETWORK_METHODOLOGY.md, DATA_QUALITY_NOTES.md
```

`institutional/README.md` and `annotations/README.md` describe those steps
and the curated files in detail.

### `citegraph_out/`: the frozen corpus

This holds the output of the citegraph pipeline over the 93 core papers, plus the
curated files that steer it (`journal_aliases.csv`, `author_aliases.csv`,
`author_external_ids.csv`, `work_annotations.csv`, `annotation_schema.csv`). The
CSVs are the inputs to the analysis and are committed as they were when the
figures were made.

They are frozen because two pipeline steps cannot be repeated exactly:
extracting metadata and references uses an LLM, and enrichment queries CrossRef
and OpenAlex, whose records change. So the per-paper results are committed as
well: `metadata/`, `references/` and `enrichment/`.

`make pipeline` re-derives the CSVs from those caches. Stages 2–4 (sources,
raw citations, works and the citation graph) reproduce the committed files
byte for byte, offline. Enrichment queries the providers for any work without a
usable cached result.

**`authors.csv` and `author_citations.csv` do not reproduce exactly, and are
kept frozen on purpose.** They were built with an earlier citegraph version.
Under the pinned version, 409 of the 3,277 enrichment results were cached in a
format it no longer accepts without re-querying the providers. Without
those provider author identifiers, a rebuild resolves 5 author identities
differently (T. K. Ahn is split three ways; Lam, Lobo and Shivakoti change
id) and carries about 59 fewer OpenAlex ids. The two `a-ahn-tk-*` rows of
`author_aliases.csv` then name ids that no longer exist, and the stage stops
on them. Every figure and number in the paper uses the frozen files.

## Data availability and rights

- **The 93 core papers** are copyrighted and are not included. Neither is the
  full-text markdown converted from them (`citegraph_out/markdown/`). Each
  paper is listed in `citegraph_out/sources.csv`. To re-run the pipeline from
  the PDFs, place them under `data/` (one folder per author, as listed in
  `citegraph_out/input_manifest.json`) and run `citegraph convert data --out
  citegraph_out --recursive --ocr-auto` before `make pipeline`.
- **`base_institucional.xlsx`** was compiled by hand from public sources
  (CVs, university pages, dissertation records). It contains career information on
  named researchers.
- **Bibliographic metadata** from CrossRef and OpenAlex is openly licensed.

## Software

Python 3.11.10. `requirements.txt` pins every package, including citegraph's
commit. The LLM used for extraction is set by `MODEL` in the `Makefile`.
