# Mapping the History of Lab-in-the-Field Experiments in Colombia

Data and code for the chapter *Mapping the History of Lab in the Field
Experiments in Colombia: Origins, Networks and Institutions*. The chapter
studies the 93 publications derived from lab-in-the-field experiments (LFEs)
conducted in Colombia between 1998 and 2024, and the 58 core authors who wrote
them. It combines two quantitative methods:

- **Bibliometrics**, on the papers: when and where they were published, their
  themes, whom they cite, and which authors are cited together.
- **Prosopography**, on the people: where the core authors trained and work,
  and the doctoral supervision ties that link them into academic families.

This repository reproduces every figure and number in the chapter from
committed inputs.

## Explore the data

**[mariagutierrezruan.github.io/lfe-colombia](https://mariagutierrezruan.github.io/lfe-colombia/)**
lets you browse the data without installing anything:

| Page | What it shows |
| --- | --- |
| [Papers](https://mariagutierrezruan.github.io/lfe-colombia/) | The 93 core papers, with their metadata, bibliography, and the core papers that cite them |
| [Authors](https://mariagutierrezruan.github.io/lfe-colombia/authors.html) | Profiles of the 58 core authors: affiliation, doctorate, papers and co-authors |
| [Lineages](https://mariagutierrezruan.github.io/lfe-colombia/lineages.html) | The doctoral family tree of any core author, including those not plotted in the chapter |
| [Cited authors](https://mariagutierrezruan.github.io/lfe-colombia/citations.html) | Every author cited by the corpus, ranked, with the works cited and who cites them |
| [Co-citation network](https://mariagutierrezruan.github.io/lfe-colombia/network.html) | The 28 most-cited authors and how often the corpus cites them together |

## The data

- **The corpus.** A publication enters the corpus if it reports a
  lab-in-the-field experiment (incentivised economic games, payments to
  participants, a relevant population rather than a convenience sample)
  conducted at least partly in Colombia. Journal articles, book chapters,
  working papers and PhD dissertations in English or Spanish all count. Each
  paper's theme and publication type are hand-coded.
- **The core authors.** Authors listed on at least two papers in the corpus,
  or sole author of one. One further author, César Mantilla, co-authored a
  single paper and is included as a named exception: he was advised by Juan
  Camilo Cárdenas, which lets the Bowles lineage be traced to a third
  generation. Their current (or last) affiliation and doctoral training
  (institution, year, field, advisors) were collected by hand from public
  sources.
- **The references.** The bibliographies of the 93 papers were extracted from
  the full texts with a language model constrained to a fixed schema,
  reconciled into distinct works, and enriched with CrossRef and OpenAlex
  metadata. This is done with
  [citegraph](https://github.com/yabramuvdi/citegraph), a separate library
  pinned here by commit.

## Reproduce

Requires Python 3.11 and `make`.

```bash
make env    # create .venv from requirements.txt (pinned versions)
make        # tables, figures, workbooks and the explorer's data
```

`make` needs no network access and no API key. It writes:

| Output | Made by |
| --- | --- |
| `institutional/out/*.csv` | `institutional/build_clean_base.py`: the cleaned career base and supervision ties |
| `institutional/out/figures/` | `notebooks/institutional_figures.ipynb`: affiliations, doctoral training, lineages |
| `citegraph_out/figures/` | `notebooks/figures.ipynb`: publications, themes, citations and the co-citation network |
| `citegraph_out/core_authors.xlsx` | `citegraph export-authors`: everything known about the authors of the core papers |
| `core_papers_export.xlsx` | `annotations/make_core_papers_xlsx.py`: the 93 core papers with their theme and publication type |
| `site/data/*.js` | `site/build_data.py`: the data behind the explorer pages |

Each figure is saved as PDF and PNG, with a grayscale proof under `gray/` and
its caption and notes in `<stem>.caption.md`. Two runs produce byte-identical
PNGs; PDFs differ only in their embedded creation date.

## Repository layout

```
base_institucional.xlsx   hand-collected careers of the 58 core authors (raw; never edited by code)
core_papers.xlsx          legacy curated sheet of the 93 core papers; themes and publication types were
                          imported from it once and are now edited in citegraph_out/work_annotations.csv
institutional/            cleaning pipeline for the career base; crosswalks and corrections are curated inputs
annotations/              one-time import of core_papers.xlsx into citegraph_out/work_annotations.csv
citegraph_out/            the citation corpus, frozen (see below)
notebooks/                the two figure notebooks, and pipeline.ipynb: the stage-by-stage
                          walkthrough that built citegraph_out/
site/                     the explorer pages, published to GitHub Pages on every push to main
docs/                     NETWORK_METHODOLOGY.md, DATA_QUALITY_NOTES.md
```

`institutional/README.md` and `annotations/README.md` describe those steps and
their curated files in detail.

### `citegraph_out/`: the frozen corpus

This holds the output of the citegraph pipeline over the 93 core papers, plus
the curated files that steer it (`journal_aliases.csv`, `author_aliases.csv`,
`author_external_ids.csv`, `work_annotations.csv`, `annotation_schema.csv`).
The CSVs are the inputs to the analysis, committed as they were when the
figures were made.

They are frozen because two pipeline steps cannot be repeated exactly:
extraction uses a language model, and enrichment queries CrossRef and
OpenAlex, whose records change. So the per-paper results are committed too:
`metadata/`, `references/` and `enrichment/`.

`make pipeline` re-derives the CSVs from those caches. Stages 2–4 (sources,
raw citations, works and the citation graph) reproduce the committed files
byte for byte, offline. Enrichment queries the providers for any work without
a usable cached result.

**`authors.csv` and `author_citations.csv` do not reproduce exactly, and are
kept frozen on purpose.** They were built with an earlier citegraph version.
Under the pinned version, 409 of the 3,277 enrichment results were cached in a
format it no longer accepts without re-querying the providers. Without those
provider author identifiers, a rebuild resolves 5 author identities
differently (T. K. Ahn is split three ways; Lam, Lobo and Shivakoti change id)
and carries about 59 fewer OpenAlex ids. The two `a-ahn-tk-*` rows of
`author_aliases.csv` then name ids that no longer exist, and the stage stops on
them. Every figure and number in the chapter uses the frozen files.

## Data availability and rights

- **The 93 core papers** are copyrighted and are not included, nor is the
  full-text markdown converted from them (`citegraph_out/markdown/`). Each
  paper is listed in `citegraph_out/sources.csv`. To re-run the pipeline from
  the PDFs, place them under `data/` (one folder per author, as listed in
  `citegraph_out/input_manifest.json`) and run
  `citegraph convert data --out citegraph_out --recursive --ocr-auto` before
  `make pipeline`.
- **`base_institucional.xlsx`** was compiled by hand from public sources (CVs,
  university pages, dissertation records). It contains career information on
  named researchers.
- **Bibliographic metadata** from CrossRef and OpenAlex is openly licensed.

## Software

Python 3.11.10. `requirements.txt` pins every package, including citegraph's
commit. The language model used for extraction is set by `MODEL` in the
`Makefile`.
