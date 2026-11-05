"""Import hand-curated core-paper metadata into citegraph's annotation surface.

`core_papers.xlsx` (sheet `LFEs_COL`, 93 rows) is the legacy record of what
Maria coded by hand about the core papers. This imports two of its columns --
`Tema` and `Type of publication` -- into `citegraph_out/work_annotations.csv`,
keyed on the persistent citegraph work id, where `citegraph.annotations` can
validate them and `CitationGraph` can join them onto every ring view.

`works.csv` is NOT the place for this: stage 4 regenerates it, so a column
typed in there survives until the next `citegraph dedup` and no longer.

Two jobs, both auditable:

1. **Crosswalk.** The sheet keys on the title as the PDF printed it, citegraph
   on the work id. Titles are matched fuzzily (OCR breaks words: 'R ESOURCE A
   LLOCATION', 'Cooperativenessand competitiveness inchildrenR') and the result
   is written to `crosswalk_papers.csv` with its score, worst first. The
   assignment must be one-to-one across all 93 or the script refuses to write.
2. **Vocabulary.** The raw columns carry case and trailing-space noise -- 13
   spellings of 9 themes, 6 of 4 publication types -- so each folded key maps
   to one declared value. An unmapped value raises rather than passing through;
   a silent new category would show up as a lone bar in a figure.

Non-destructive: re-running keeps every value already in the CSV (a human's
edit outranks this import) and preserves columns this script knows nothing
about. Delete a cell to have the import refill it.

Usage:  python make_work_annotations.py [--dry-run]
"""
from __future__ import annotations

import csv
import html
import re
import sys
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz

HERE = Path(__file__).resolve().parent
XLSX = HERE.parent / "core_papers.xlsx"
SHEET = "LFEs_COL"
OUT_DIR = HERE.parent / "citegraph_out"
WORKS_CSV = OUT_DIR / "works.csv"
ANNOTATIONS_CSV = OUT_DIR / "work_annotations.csv"
SCHEMA_CSV = OUT_DIR / "annotation_schema.csv"
CROSSWALK_CSV = HERE / "crosswalk_papers.csv"

# Context columns: written so the file is readable and editable by hand, and
# dropped again on load. `citegraph.annotations` treats any column works.csv
# already has as context, so these never overwrite pipeline metadata.
CONTEXT = ["source_file", "Title", "Authors", "Year"]
ANNOTATIONS = ["Tema", "Publication_Type"]

# A match below this is not a spelling difference, it is the wrong paper.
MIN_SCORE = 70.0

# Folded key -> the one declared spelling. `None` means the cell records no
# theme: for six book chapters and two working papers the sheet repeats the
# publication type here, which the `temas` sheet allows but which says nothing
# the Publication_Type column does not already say. Those eight were assigned a
# theme by hand in work_annotations.csv, with the reasoning in Tema_evidence;
# blanking them here is what let that happen, and the import leaves them alone.
TEMA = {
    "economics": "Economics",
    "environmental economics": "Environmental Economics",
    "experimental economics/behavioral economics": (
        "Experimental and Behavioural Economics"
    ),
    "interdisciplinary": "Interdisciplinary",
    "development": "Development",
    "development economics": "Development Economics",
    "conflict/peace": "Peace and Conflict Studies",
    "book chapter": None,
    "working paper": None,
}

# Sentence case throughout, including 'paper', which the sheet writes lowercase
# 77 times: a legend mixing 'paper' with 'Book chapter' reads as a mistake.
PUBLICATION_TYPE = {
    "paper": "Paper",
    "book chapter": "Book chapter",
    "working paper": "Working paper",
    "phd dissertation": "PhD dissertation",
}

_NON_ALNUM = re.compile(r"[^a-z0-9 ]")
_SPACES = re.compile(r"\s+")


def fold(value: object) -> str:
    """Case- and whitespace-fold one cell, including the sheet's nbsp."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).replace("\xa0", " ")
    return _SPACES.sub(" ", text).strip().casefold()


def title_key(value: object) -> str:
    """Reduce a title to what survives OCR: lowercase alphanumerics."""
    text = html.unescape(str(value)).lower()
    return _SPACES.sub(" ", _NON_ALNUM.sub(" ", text)).strip()


def declared(value: object, mapping: dict[str, str | None], column: str, row: int) -> str:
    """Map a raw cell onto its declared value, refusing anything unmapped."""
    key = fold(value)
    if key not in mapping:
        raise SystemExit(
            f"{SHEET} row {row}: {column}={str(value)!r} is not a known value. "
            f"Add it to the {column} map and to annotation_schema.csv, or fix "
            "the spreadsheet."
        )
    return mapping[key] or ""


def crosswalk(sheet: pd.DataFrame, core: pd.DataFrame) -> list[dict]:
    """Assign each sheet row to one core work, best matches claimed first."""
    keys = {title_key(t): wid for wid, t in core["Title"].items()}
    scored = []
    for position, row in enumerate(sheet.itertuples(), start=2):
        key = title_key(getattr(row, "Titulo"))
        for candidate, work_id in keys.items():
            scored.append((fuzz.token_set_ratio(key, candidate), position, work_id))
    scored.sort(key=lambda item: (-item[0], item[1], item[2]))

    taken_rows: dict[int, tuple[str, float]] = {}
    taken_works: set[str] = set()
    for score, position, work_id in scored:
        if position in taken_rows or work_id in taken_works or score < MIN_SCORE:
            continue
        taken_rows[position] = (work_id, score)
        taken_works.add(work_id)

    rows = []
    for position, row in enumerate(sheet.itertuples(), start=2):
        work_id, score = taken_rows.get(position, ("", 0.0))
        rows.append(
            {
                "sheet_row": position,
                "score": round(score, 1),
                "xlsx_title": _SPACES.sub(" ", str(getattr(row, "Titulo"))).strip(),
                "work_id": work_id,
                "work_title": core.at[work_id, "Title"] if work_id else "",
                "needs_review": "" if score == 100 else "yes",
            }
        )
    return rows


def merge_existing(records: dict[str, dict[str, str]]) -> tuple[dict[str, dict], list[str]]:
    """Let anything already written to disk win over this import."""
    extra: list[str] = []
    if not ANNOTATIONS_CSV.exists():
        return records, extra
    with ANNOTATIONS_CSV.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            work_id = (row.get("id") or "").strip()
            if work_id not in records:
                raise SystemExit(
                    f"{ANNOTATIONS_CSV} annotates {work_id!r}, which this import does "
                    "not cover. Resolve by hand rather than letting the import drop it."
                )
            for column, value in row.items():
                if column in (None, "id") or not (value or "").strip():
                    continue
                if column not in CONTEXT + ANNOTATIONS and column not in extra:
                    extra.append(column)
                records[work_id][column] = value.strip()
    return records, extra


def write_schema() -> None:
    """Declare the two columns; never clobber a hand-edited schema."""
    if SCHEMA_CSV.exists():
        return
    def values(mapping: dict[str, str | None]) -> str:
        return "|".join(dict.fromkeys(v for v in mapping.values() if v))

    with SCHEMA_CSV.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["column", "type", "allowed", "description"])
        writer.writerow([
            "Tema", "enum", values(TEMA),
            "Broad research theme, as coded by hand from the paper",
        ])
        writer.writerow([
            "Publication_Type", "enum", values(PUBLICATION_TYPE),
            "What kind of publication this is",
        ])
    print(f"wrote {SCHEMA_CSV}")


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    sheet = pd.read_excel(XLSX, SHEET)
    sheet.columns = [str(c).replace("\xa0", " ").strip() for c in sheet.columns]
    # itertuples renames anything that is not an identifier positionally
    # (`_6`), so give the two columns we read real names first.
    sheet = sheet.rename(columns={"Título": "Titulo",
                                  "Type of publication": "Type_raw"})

    works = pd.read_csv(WORKS_CSV, index_col="id")
    core = works[works["ring"] == 0]

    rows = crosswalk(sheet, core)
    matched = [r for r in rows if r["work_id"]]
    if len(matched) != len(sheet) or len(matched) != len(core):
        unmatched = [r for r in rows if not r["work_id"]]
        raise SystemExit(
            f"Crosswalk is not one-to-one: {len(matched)} of {len(sheet)} sheet rows "
            f"matched {len(core)} core works. Unmatched: "
            + "; ".join(f"row {r['sheet_row']} {r['xlsx_title'][:60]!r}" for r in unmatched)
        )

    records: dict[str, dict[str, str]] = {}
    for row, match in zip(sheet.itertuples(), rows, strict=True):
        work_id = match["work_id"]
        work = core.loc[work_id]
        records[work_id] = {
            "source_file": str(work.get("source_file") or ""),
            "Title": str(work.get("Title") or ""),
            "Authors": str(work.get("Authors") or ""),
            "Year": "" if pd.isna(work.get("Year")) else str(int(work["Year"])),
            "Tema": declared(row.Tema, TEMA, "Tema", match["sheet_row"]),
            "Publication_Type": declared(
                row.Type_raw, PUBLICATION_TYPE, "Type of publication",
                match["sheet_row"],
            ),
        }
    records, extra = merge_existing(records)

    blank = [wid for wid, r in records.items() if not r["Tema"]]
    worst = sorted(matched, key=lambda r: r["score"])[:5]
    print(f"{len(records)} core works annotated from {SHEET}")
    print(f"crosswalk: {sum(1 for r in matched if r['score'] == 100)} exact, "
          f"{len(matched)} total, lowest score {worst[0]['score']}")
    for r in worst:
        if r["score"] < 100:
            print(f"  {r['score']:5} {r['xlsx_title'][:55]!r} -> {r['work_id']}")
    print(f"{len(blank)} works have no Tema (a publication type was recorded instead):")
    for wid in blank:
        print(f"  {wid}  {records[wid]['Title'][:65]}")

    if dry_run:
        print("\n--dry-run: nothing written")
        return

    columns = ["id"] + CONTEXT + ANNOTATIONS + extra
    with ANNOTATIONS_CSV.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for work_id in sorted(records):
            writer.writerow({"id": work_id, **records[work_id]})
    print(f"wrote {ANNOTATIONS_CSV}")

    with CROSSWALK_CSV.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: (r["score"], r["sheet_row"])))
    print(f"wrote {CROSSWALK_CSV}")

    write_schema()


if __name__ == "__main__":
    main()
