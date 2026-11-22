# Core-paper annotations

Hand-curated facts about the 93 core papers — things read off the PDF by a
person, not extracted by the pipeline. Today: `Tema` and `Publication_Type`.

## Where the data lives

| File | What it is |
| ---- | ---------- |
| `../citegraph_out/work_annotations.csv` | **The annotations.** Authoritative, one row per core work, keyed on the citegraph work `id`. Edit this by hand. |
| `../citegraph_out/annotation_schema.csv` | Declares each column and its allowed values. `citegraph` validates against it on load. |
| `crosswalk_papers.csv` | Audit of the one-time title match from `core_papers.xlsx` onto work ids, worst score first. |
| `make_work_annotations.py` | The importer that produced both, from `core_papers.xlsx` sheet `LFEs_COL`. |
| `make_core_papers_xlsx.py` | Builds `../core_papers_export.xlsx`, the shareable one-sheet view of all 93 papers. |

## How `Tema` is assigned

A journal article takes the theme of its journal in Maria's journal-to-theme
table (received 2026-11-01): the journal is classified, not the paper, whatever
the paper is about. Four journals the table did not originally list were added
on 2026-11-22 -- *Ecology and Society* (Environmental and Ecological Economics),
*Ecosystem Services* (Interdisciplinary), *Journal of Public Economics* and
*American Economic Review* (both Economics). Chapters, working papers and
dissertations were coded from the paper. Match journals on the sheet's `Revista`
column, not on the provider's `Journal_Canonical`, which names repositories (LA
Referencia, SSRN) for some papers. Every theme that is not the sheet's original
value says why in `Tema_evidence`.

Open, from the table: it lists *Journal of Agribusiness in Developing and
Emerging Economies*, which no core paper is in, and asks to verify whether both
Peace and Conflict papers are in *Peace Economics, Peace Science and Public
Policy* (only one is; the other is HiCN Working Paper 379). Neither changes a
theme.

## How `Publication_Type` differs from the legacy sheet

`core_papers.xlsx` types 77 rows "paper"; `work_annotations.csv` has 71 `Paper`
(11 working papers, 7 book chapters, 4 PhD dissertations). Six rows were
retyped in commit `58780b2` because the document in the corpus is not a journal
article -- the sheet's own `Revista` column already says so for the first five:

| Work | Document in the corpus | Now |
| ---- | ---------------------- | --- |
| Cárdenas 2008, *Social Preferences Among the People of Sanquianga* | Documento CEDE 2008-11 | Working paper |
| Cárdenas et al. 2008, *Discrimination in the Provision of Social Services to the Poor* | IDB Research Network Working Paper R-544 | Working paper |
| Maldonado & Moreno-Sánchez 2008, *Does scarcity exacerbate the tragedy of the commons?* | Documento CEDE 2009-22 | Working paper |
| Moreno-Sánchez & Maldonado 2009, *Can Co-Management Improve the Governance of a Common-Pool Resource?* | Documento CEDE 2009-15 | Working paper |
| Bernal Escobar et al. 2013, *Derretimiento y Retroceso Glaciar* | Documento CEDE 2013-16 | Working paper |
| Fatas et al. 2021, *The Behavioral Consequences of Conflict Exposure on Risk Preferences* | Oxford Research Encyclopedia entry | Book chapter |

The importer keeps what is already in `work_annotations.csv`, so re-running it
does not bring the 77 back.

**Not `works.csv`.** Stage 4 regenerates it, so anything typed in there is
destroyed by the next `citegraph dedup`.

## Using them in a figure

```python
from citegraph import CitationGraph

g = CitationGraph.from_out_dir(OUT_DIR)
g.has_annotations                    # True once work_annotations.csv exists
g.core["Publication_Type"].value_counts()
g.core.groupby("Tema").size()
```

The columns join onto every ring view, so `g.core`, `g.ring(n)` and `g.works`
all carry them. Works nobody annotated (every ring-1 reference) hold a missing
value, so `groupby` and `value_counts` drop them the way they should.

## The shareable Excel export

```bash
python make_core_papers_xlsx.py     # -> ../core_papers_export.xlsx
```

One sheet, 93 rows, sorted by year: `Year, Title, Authors, Journal,
Journal_Canonical, DOI, Tema, Publication_Type, Cited_by_corpus, N_references,
Tema_evidence, work_id, source_file`. Frozen header, autofilter, ready to send.

Bibliography comes from `enriched_works.csv` -- the provider's title, journal,
year and DOI where CrossRef or OpenAlex matched, the extracted values where they
did not. `Cited_by_corpus` counts how many of the 93 bibliographies cite that
paper; `N_references` counts the references extracted from it.

It is an **export and nothing reads it back.** To change a value, edit
`work_annotations.csv` (annotations) or fix the record upstream (bibliography),
then re-run. The name is deliberately not `core_papers.xlsx` -- that is the
legacy curated source, and the two must never be confused.

Known blanks, all honest: 15 papers have no DOI, and 3 have no journal -- a 1998
book chapter, a 2014 Uniandes mimeo, and "Capital social y territorio", which
neither provider matched.

## Adding a column

1. Add a row to `annotation_schema.csv`: `column,type,allowed,description`.
   `type` is `enum` (list the values, `|`-separated) or `text`. The description
   is the instruction to whoever fills the column in — a person or an agent — so
   write it as one.
2. Add the column to `work_annotations.csv` and fill it.

An undeclared column is carried through untouched, so step 1 is optional for
free text. A declared `enum` is checked on every load and a value outside the
list raises, naming the work.

## The eight assigned themes

Eight papers -- six book chapters and two working papers -- have a *publication
type* in the spreadsheet's `Tema` cell ("Book chapter", "Working paper"),
duplicating the neighbouring column and recording no theme. Maria's `temas`
sheet lists those as allowed themes, so it is her fallback, not a typo; the four
PhD dissertations got real themes even so.

The import blanks them, and a theme was then assigned for each by reading the
paper and matching it to a paper Maria had already coded. The reasoning is in
the `Tema_evidence` column, one line per work, naming the paper each assignment
follows. Seven are Environmental Economics or Interdisciplinary commons work;
the 1998 Cárdenas/Stranlund/Willis chapter is marked a judgement call, coded
Development to match the same team's *World Development* article making the same
crowding-out argument, with Environmental Economics the defensible alternative.

Re-check them if the theme figure matters to a claim: they are 8 of 93.

## Re-running the import

```bash
python make_work_annotations.py --dry-run   # report, write nothing
python make_work_annotations.py
```

Non-destructive: any value already in `work_annotations.csv` wins over the
spreadsheet, and unknown columns survive. Clear a cell to have the import refill
it. The script refuses to write unless all 93 sheet rows match all 93 core works
one-to-one, and refuses any `Tema` / `Type of publication` spelling it has not
been taught to fold.

`core_papers.xlsx` is the legacy source, not the working surface. Its other
columns (`Is it a LFE?`, `¿Cita a Ostrom?`, …) mix a verdict with the prose
justifying it, so importing them means splitting each into a verdict column and
an evidence column — see the W4 section of
`citegraph/docs/superpowers/specs/2026-09-13-enrichment-and-downstream-design.md`.
