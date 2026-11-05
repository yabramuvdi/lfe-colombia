"""Seed / refresh crosswalk_people.csv.

Puts the two person namespaces in the spreadsheet -- `display_name` (the author)
and `PhD_supervisor` (free text, several names per cell) -- into one table, and
attaches the citegraph `author_id` where the person is in the corpus.

Non-destructive: existing rows are kept verbatim, only new raw names are added.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz

HERE = Path(__file__).resolve().parent
XLSX = HERE.parent / "base_institucional.xlsx"
AUTHORS_CSV = HERE.parent / "citegraph_out" / "authors.csv"
PEOPLE_CW = HERE / "crosswalk_people.csv"

MISSING = {"", "no", "not found", "nan", "none", "n/a", "-"}
SPLIT = re.compile(r",| y | and |;")

# A supervisor cell fragment is a person if it has two whitespace tokens -- or if
# it is an initial glued to a surname with no space after the period. The source
# has 'J.Rotmans' beside 'O.J. Vrieze' in one cell; a bare `len(split()) >= 2`
# test keeps the second and silently drops the first. Keep this in step with the
# identical guard in build_clean_base.py.
GLUED_INITIALS = re.compile(r"^(?:[A-Za-z]\.){1,3}[A-Za-z]{2,}")


def looks_like_person(name: str) -> bool:
    return len(name.split()) >= 2 or bool(GLUED_INITIALS.match(name))

# Accented / fuller forms for names the spreadsheet records without diacritics.
# The join key is always `author_id`, never the string, so these only affect how
# a name is displayed -- but a manuscript should still spell people correctly.
CANONICAL = {
    "Juan Camilo Cardenas": "Juan Camilo Cárdenas",
    "Maria Alejandra Velez": "María Alejandra Vélez",
    "María Alejandra Velez": "María Alejandra Vélez",
    "Maria Claudia Lopez": "María Claudia López",
    "Luz Ángela Rodriguez": "Luz Ángela Rodríguez",
    "Lina Maria Restrepo-Plaza": "Lina María Restrepo-Plaza",
    "Rocío del Pilar Moreno-Sanchez": "Rocío del Pilar Moreno-Sánchez",
    "Jose Alberto Guerra Forero": "José Alberto Guerra Forero",
    "Clara Villegas-Palacio": "Clara Inés Villegas-Palacio",
    "Enrique Fatas": "Enrique Fatás",
    "Diego Ramos": "Diego Ramos-Toro",
    "Rachel T.A. Croson": "Rachel T. A. Croson",
    "Santiago Arango Aramburo": "Santiago Arango-Aramburo",
    "Clara Inés Villegas Palacio": "Clara Inés Villegas-Palacio",
    "Juan Camilo Cárdenas": "Juan Camilo Cárdenas",
    "María Alejandra Vélez": "María Alejandra Vélez",
    "J.Rotmans": "Jan Rotmans",
    "O.J. Vrieze": "O. J. Vrieze",
}


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def clean_cell(v) -> str:
    if pd.isna(v):
        return ""
    s = str(v).replace("\xa0", " ").replace("–", "-").replace("’", "'")
    return unicodedata.normalize("NFC", " ".join(s.split())).strip()


def is_missing(s: str) -> bool:
    return s.strip().lower() in MISSING


def key(name: str) -> str:
    """Comparison key: accent-free, lowercase, punctuation-free tokens."""
    s = strip_accents(name).lower()
    s = re.sub(r"[.\-']", " ", s)
    return " ".join(sorted(s.split()))


def match_author(name: str, authors: pd.DataFrame) -> tuple[str, float]:
    """Best citegraph author_id for `name`, requiring the surname to agree."""
    surname = strip_accents(name).lower().split()[-1] if name.split() else ""
    best_id, best = "", 0.0
    for aid, disp, sur in authors[["id", "display_name", "surname"]].itertuples(index=False):
        sur_n = strip_accents(str(sur)).lower()
        # surname must appear in the query name -- guards against high fuzzy
        # scores between unrelated people who share given names
        if surname and sur_n and sur_n not in strip_accents(name).lower():
            continue
        score = fuzz.token_sort_ratio(key(name), key(str(disp)))
        if score > best:
            best_id, best = aid, score
    return (best_id, round(best, 1)) if best >= 85 else ("", round(best, 1))


def main() -> int:
    h1 = pd.read_excel(XLSX, sheet_name="Hoja1")
    authors = pd.read_csv(AUTHORS_CSV).fillna("")

    roles: dict[str, set[str]] = {}
    for v in h1["display_name"]:
        n = clean_cell(v)
        if not is_missing(n):
            roles.setdefault(n, set()).add("author")
    for v in h1["PhD_supervisor"]:
        cell = clean_cell(v)
        if is_missing(cell):
            continue
        for part in SPLIT.split(cell):
            n = clean_cell(part)
            if n and not is_missing(n) and looks_like_person(n):
                roles.setdefault(n, set()).add("supervisor")

    existing = pd.read_csv(PEOPLE_CW, dtype=str).fillna("") if PEOPLE_CW.exists() else pd.DataFrame()
    known = set(existing["raw_name"]) if len(existing) else set()
    new = sorted(n for n in roles if n not in known)
    print(f"{len(roles)} distinct person names ({len(new)} new)")

    rows = []
    for raw in new:
        canonical = CANONICAL.get(raw, raw)
        aid, score = match_author(canonical, authors)
        if not aid:  # try the raw spelling too, in case CANONICAL over-corrected
            aid, score = match_author(raw, authors)
        rows.append({
            "raw_name": raw,
            "canonical_name": canonical,
            "author_id": aid,
            "role": "+".join(sorted(roles[raw])),
            "in_corpus": "1" if aid else "0",
            "match_score": score,
            "resolved_from": "hand" if raw in CANONICAL else "verbatim",
            "needs_review": "1" if (not aid or score < 95 or raw in CANONICAL) else "0",
            "notes": "",
        })

    out = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True) if len(existing) \
        else pd.DataFrame(rows)
    out.sort_values(["role", "canonical_name"]).to_csv(PEOPLE_CW, index=False)
    if rows:
        m = pd.DataFrame(rows)
        print(f"matched to an author_id: {(m['author_id'] != '').sum()}/{len(m)}")
    print(f"wrote {PEOPLE_CW} ({len(out)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
