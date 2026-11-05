"""Export the 93 core papers as one shareable Excel sheet.

Everything recorded about the papers Maria selected, in one file someone
outside the project can open: the bibliographic record the pipeline extracted
and enriched, the two hand-curated columns, and two counts that say how each
paper sits in the corpus.

This is an **export**, not a source. Edit `citegraph_out/work_annotations.csv`
(annotations) or fix the PDF metadata upstream (bibliography), then re-run.
Nothing reads this workbook back, and it is deliberately named so it cannot be
mistaken for `core_papers.xlsx`, which is the legacy curated source.

Metadata comes from `enriched_works.csv` rather than `works.csv`: it is the
same 3,277 works with the provider's title, journal, year and DOI where a
match was found, and the extracted values where it was not.

Usage:  python make_core_papers_xlsx.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from citegraph.annotations import load_annotations

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE.parent / "citegraph_out"
XLSX = HERE.parent / "core_papers_export.xlsx"
SHEET = "Core papers"

# (column, width, wrap) in reading order: what the paper is, then how it was
# coded, then where it sits in the corpus, then the provenance a reader only
# needs when they question a row.
LAYOUT = [
    ("Year", 7, False),
    ("Title", 62, True),
    ("Authors", 34, True),
    ("Journal", 30, True),
    ("Journal_Canonical", 26, False),
    ("DOI", 26, False),
    ("Tema", 24, False),
    ("Publication_Type", 15, False),
    ("Cited_by_corpus", 10, False),
    ("N_references", 10, False),
    ("Tema_evidence", 40, False),
    ("work_id", 34, False),
    ("source_file", 30, False),
]
NUMERIC = {"Year", "Cited_by_corpus", "N_references"}


def build() -> pd.DataFrame:
    works = pd.read_csv(OUT_DIR / "enriched_works.csv", index_col="id")
    edges = pd.read_csv(OUT_DIR / "citation_graph.csv")
    annotations = load_annotations(
        OUT_DIR / "work_annotations.csv",
        works=works,
        schema_path=OUT_DIR / "annotation_schema.csv",
    )

    core = works[works["ring"] == 0].join(annotations)
    # Distinct citing bibliographies, not raw edges: a work cited twice by one
    # paper is cited by one paper. The edge table is already deduplicated, but
    # counting distinct citers says what the number means.
    core["Cited_by_corpus"] = (
        edges.groupby("cited_id")["citing_id"].nunique().reindex(core.index).fillna(0)
    )
    core["N_references"] = (
        edges.groupby("citing_id")["cited_id"].nunique().reindex(core.index).fillna(0)
    )
    core = core.rename(columns={"doi": "DOI"}).reset_index(names="work_id")

    for column in NUMERIC:
        core[column] = pd.to_numeric(core[column], errors="coerce").astype("Int64")
    missing = [name for name, _, _ in LAYOUT if name not in core.columns]
    if missing:
        raise SystemExit(f"enriched_works.csv is missing {missing}; re-run the pipeline")
    return core.sort_values(["Year", "Title"])[[name for name, _, _ in LAYOUT]]


def write(table: pd.DataFrame) -> None:
    with pd.ExcelWriter(XLSX, engine="openpyxl") as writer:
        table.to_excel(writer, sheet_name=SHEET, index=False)
        sheet = writer.sheets[SHEET]
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for position, (name, width, wrap) in enumerate(LAYOUT, start=1):
            letter = get_column_letter(position)
            sheet.column_dimensions[letter].width = width
            header = sheet[f"{letter}1"]
            header.font = Font(bold=True)
            header.alignment = Alignment(vertical="center")
            for row in range(2, len(table) + 2):
                sheet[f"{letter}{row}"].alignment = Alignment(
                    wrap_text=wrap, vertical="top",
                    horizontal="center" if name in NUMERIC else "left",
                )


def main() -> None:
    table = build()
    write(table)
    blank = {name: int(table[name].isna().sum()) for name, _, _ in LAYOUT}
    print(f"{len(table)} core papers -> {XLSX}")
    print("  years " f"{table['Year'].min()}-{table['Year'].max()}, "
          f"{blank['DOI']} without a DOI, {blank['Tema']} without a Tema")
    print(f"  cited within the corpus: {(table['Cited_by_corpus'] > 0).sum()} of {len(table)}")


if __name__ == "__main__":
    main()
