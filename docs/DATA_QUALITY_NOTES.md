# Paper 4 — known data quality problems

Written 2026-09-09, updated 2026-09-13. **Problem 1 is fixed in the current
`citegraph_out/` artifacts; problem 2 is not.** Account for problem 2 before publishing
journal-level counts from this corpus.

Corpus as of 2026-09-13: 93 source publications, 3,277 works, 4,532 citation edges.
(It was 92 / 3,461 / 4,686 before the problem-1 repair and the addition of the 93rd paper.)

---

## 1. One source document contributed 180 fake references — FIXED 2026-09-13

**What it was.** The work `w-palacio-2010-formal-and-informal-regulations-and` (Clara
Villegas Palacio's 2010 PhD dissertation, University of Gothenburg, source file
`base2026_Claude2__Villegas__PhD dissertation Villegas.md`) had an out-degree of 337, of
which 180 were spurious: the department's back-matter list of *previous doctoral theses in
the series Ekonomiska Studier*, going back to 1911, which the extractor read as a
bibliography. All 180 carried `Journal == "Ekonomiska Studier"`.

**Root cause.** The references stage splits a document into bibliography sections by `##`
headers. A non-final section stopped at the next same-or-higher-level header, but the final
section deliberately ran to end of file — and in this document `## References` (line 1885)
was followed by `## Previous doctoral theses in the Department of Economics, Gothenburg`
(line 1913) with no header in between, so the bibliography swallowed the back matter.

**The fix.** `split_reference_sections` now ends the final section at a same-or-higher-level
header that opens recognised back matter (`_BACKMATTER_HEADER_RE`: appendices, supporting
information, notes, previous doctoral theses, and similar). It is deliberately a *denylist*
so the splitter fails closed, because headers interrupting a real reference list are common:
running page heads (`## 94 ECONOMIA, Spring 2009`, `## A. Pfaff et al.`) appear mid-list in
two source papers, and in `Cardenas__MarketsReligionCommunity-2010.md` the only header the
regex matches is JSTOR front-matter boilerplate while the real bibliography sits behind an
unmatched header — so "stop at the next same-level header" would have silently dropped
references from three papers. An offline diff over all 92 markdown files before the repair
showed 17 changing, every one a pure suffix trim at a genuine back-matter header.

**Result.** 0 Ekonomiska works (was 180). The thesis now has out-degree 138 and keeps all
six of its chapter bibliographies. Corpus-wide this took works 3,461 → 3,277 and edges
4,686 → 4,532. **No exclusion filter is needed any more** — section 7 of
`notebooks/paper4_figures.ipynb` still carries one and it can be removed.

**Verify:**

```python
from citegraph import CitationGraph
g = CitationGraph.from_out_dir("citegraph_out")
bad = g.works[g.works["Journal"].astype(str).str.contains("Ekonomiska", na=False)]
len(bad)  # expect 0
```

## 2. Journal names are not normalised

**What.** Journal strings are stored exactly as the extractor found them, with no
canonicalisation. There are **1,603 distinct journal spellings across 3,393 non-empty
values**, and much of that is the same venue written several ways.

| Venue | Spellings | Rows | Largest split |
| --- | --- | --- | --- |
| American Economic Review | 4 | 111 | 69 full name, 25 `Am. Econ. Rev.`, 14 with a leading "The" |
| Ecological Economics | 3 | 80 | 41 full name, 36 `Ecol. Econ.`, 3 `Ecol Econ` |

**Impact.** Any count of "most-cited journals" is currently wrong, and wrong in a
predictable direction: it *understates* concentration, because the leading venues are the
ones most often abbreviated. Ecological Economics is nearly halved by the split. This
affects the corpus in both directions, since the same problem exists for the source
publications and for the cited works.

**Note.** `citegraph enrich` returns a canonical container title from CrossRef and
OpenAlex for matched works, so `enriched_works.csv` is a better basis for journal-level
analysis than `works.csv`. That only helps for works that matched; check
`enrichment_summary.json` for the match rate before relying on it.

**Verify:**

```python
j = g.works["Journal"].dropna().astype(str)
j[j.str.lower().str.startswith("ecol")].value_counts()
```

---

## Minor, noticed in passing

The dissertation above is filed under first-author surname `palacio`, from "Clara
Villegas Palacio". The compound surname "Villegas Palacio" was not attested elsewhere in
the corpus, so the author stage kept the conservative last-token reading. This is the
documented behaviour rather than a bug, but the work id and the author display name read
oddly. It can be corrected by hand in `citegraph_out/author_aliases.csv`.
