# Cleaning `base_institucional.xlsx`

The spreadsheet is never modified. Everything here reads it and writes to `out/`.

## Run order

```bash
python make_crosswalks.py        # institutions: raw string -> canonical name + ROR id
python make_people_crosswalk.py  # people: raw name -> canonical name + citegraph author_id
python build_clean_base.py       # apply both + corrections.csv, write out/
```

All three are re-runnable and non-destructive. The two `make_*` scripts keep every row
that already exists in a crosswalk exactly as it is and only append raw strings that are
new, so hand edits survive. After Maria adds authors, run all three again.

## The files you edit

| File | What it decides |
| --- | --- |
| `crosswalk_institutions.csv` | One row per raw institution string. Change `canonical_name` / `ror_id` to change how that string is grouped. |
| `crosswalk_people.csv` | One row per raw person name (author *and* supervisor). `author_id` is the join key to the citation data. |
| `corrections.csv` | Row-level factual fixes, with evidence. Can also fill columns the spreadsheet does not have. |
| `crosswalk_fields.csv` | Maps department strings and PhD titles onto research fields. Drives the field figures. |
| `supervision_seed.csv` | Postdoc / visiting supervision ties. **Empty on purpose** — see below. |
| `HAND` / `CANONICAL` dicts in the `make_*` scripts | Seeds for new raw strings. Editing the CSVs is usually enough. |

`corrections.csv` is guarded: each row states the `old_value` it expects. If the
spreadsheet has since changed, the correction is **not** applied and a `correction_stale`
flag is raised instead of silently overwriting newer data.

## The outputs

| File | Shape |
| --- | --- |
| `out/base_institucional_clean.csv` | 58 rows, one per author — the familiar wide shape, cleaned |
| `out/career_positions.csv` | 138 rows, one per (author, position) — tidy; this is the one to aggregate over |
| `out/supervision.csv` | 62 advisor → advisee edges, all doctoral |
| `out/advisors.csv` | the PhD subset, kept for compatibility |
| `out/review_flags.csv` | Everything changed on evidence, and everything still unresolved |

## Four decisions worth knowing about

**`No` and `Not found` are not merged.** `"No"` means *this person had no postdoc* — real
information. `"Not found"` means *we could not determine it*. The source spreadsheet used
both, plus blanks, in the same columns. Collapsing them all to NA would put 7 unknown
authors into the denominator of the postdoc rate. Instead each block carries a
three-valued `*_status` of `present` / `none` / `unknown`, and `has_postdoc` is
`True` / `False` / `NA`. Use `has_postdoc.notna()` as your denominator.

**Institutions group by ROR id, not by string.** 89 raw strings resolve to 83
institutions (82 with a ROR id, plus one without). ROR matching cross-checks the country the spreadsheet records, because
several institutions share a name across countries — the first pass matched *Northwestern
University* to the Philippine university of that name with a perfect string score. One
institution (Conservation Strategy Fund) has no ROR record and is flagged.

Universidad Nacional de Colombia's campuses share one ROR id, so `campus` is kept as a
separate column. Group on `institution_ror` for the university, on
`(institution, campus)` for the campus.

**Visiting positions are not postdocs.** Two entries describe visiting appointments —
Méndez at Indiana and Castillo at ASU, both in `postdoc_2`. They are typed
`position_type='visiting'` in `career_positions.csv` and excluded from `has_postdoc` and
`n_postdocs`, so postdoc rates are not inflated.

The `\bvisiting\b` test is a heuristic, and it cannot tell a postdoc that happens to carry a
"Visiting Scholar" title from a mid-career visit. Fix those at source by recording the real
title, as was done for Cárdenas on 2026-09-13. `build_clean_base.py` also loads an optional
`exclusions.csv` (`display_name,reason`) for anyone who has to leave the frame for a reason
worth recording; the file is absent because nobody currently does.

## Who is in the base

58 authors, drawn from the 146 authors of the core corpus. **The selection criterion is
the manuscript's to state — nothing in this pipeline derives it.** The base is simply
whichever people the workbook holds. As audited on 2026-11-22 the 58 are:

- 53 with two or more core works;
- 4 with one core work that is sole-authored (Moya, Ramos-Toro, Guerra Forero, Agneman);
- 1 with one co-authored core work, kept as a named exception rather than under a
  general rule (César Mantilla, advised by Juan Camilo Cárdenas, so the Bowles lineage
  reaches a third generation). Supervisors were only collected for authors in the base,
  so other single-paper co-authors were not checked for advisors among the core authors.

Changes on 2026-11-22: Julia Seither (one co-authored work, advisor outside the core) was
removed. Cleve E. Willis (three core works) was restored — he had been dropped on
2026-09-13 for having an empty row. His record: PhD in Agricultural Economics, University
of California, Davis, 1972, dissertation chair Gordon C. Rausser (UC Davis ARE programme
history, 2023, Appendix E); Professor of Resource Economics and later Dean at the
University of Massachusetts Amherst. He is deceased, so the affiliation is his last one,
as for Ostrom and Marlowe. His postdoc fields are `Not found`.

## Known limits

- One fully blank row is dropped (`dropped` flag).
- Eva Ranehill's PhD year and two second-postdoc institutions (Anderies/CSIRO,
  Dreber/SIFR) are `medium` confidence — see `corrections.csv` for the reasoning.
- Hoja2 of the spreadsheet is a stale citegraph export: 4 of its 151 `author_id`s no
  longer exist, having been merged by `citegraph_out/author_aliases.csv`. Nothing here
  reads Hoja2 — the person crosswalk resolves against the live `citegraph_out/authors.csv`.

**Supervision is doctoral only.** Maria decided on 2026-09-12 not to model postdoc
supervision: the spreadsheet has no postdoc supervisor column, and public sources document
postdoc advisors too patchily to be worth it. `supervision.csv` keeps its `relation_type`
column and `supervision_seed.csv` keeps its header, so the layer can be switched back on by
filling that file — seven researched ties are parked in `supervision_seed.parked.csv`.
Removing them fragments the network noticeably (the largest component drops from 19 people
to 9), because two of them were Ostrom's ties into the Colombian group.

## Figures

`make figures` from the repository root — or open
`notebooks/institutional_figures.ipynb` in Jupyter. It writes to `out/figures/`, each figure as PDF + PNG + `<stem>.caption.md`,
following the economics-journal conventions in the repo's `styling-econ-figures` skill.

Seven figures carry the plain `figN_` stems and are the ones the manuscript points at:

| Stem | Shows |
| --- | --- |
| `fig1_affiliation_field` | field of current affiliation |
| `fig2_affiliation_country` | country of current affiliation |
| `fig3_phd_field` | field of the doctorate |
| `fig4_phd_field_by_decade` | field of the doctorate by decade, stacked |
| `fig5_doctoral_lineages` | doctoral lineages of five or more people, as a tidy tree |
| `fig6_supervision_over_time` | ties inside the 59-author list, one band per chain, on a year axis |
| `fig7_phd_institutions` | institutions that trained two or more of the authors |

Stems containing `alt` are competing versions of the figure they are named after, kept so
the choice can be made by eye and not written into the manuscript:
`fig5alt_lineages_in_time`, `fig5alt_lineage_tree_min3`, `fig6alt_tie_rows`, and
`fig7alt_outside_advisors`. Deleting an `alt` cell from the notebook is all it takes to
drop one once it has lost.
