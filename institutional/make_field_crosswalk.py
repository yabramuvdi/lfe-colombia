"""Seed / refresh crosswalk_fields.csv.

Maps the free-text `affiliation_department` and `PhD_title` strings onto a small
set of research fields, so the two can be counted. 59 people hold 31 distinct
department strings and 18 distinct PhD titles; counting the raw strings produces
a long tail of singletons rather than a distribution.

Non-destructive: existing rows are kept, only new raw strings are appended.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
CLEAN = HERE / "out" / "base_institucional_clean.csv"
FIELD_CW = HERE / "crosswalk_fields.csv"

# Ordered: the first pattern that matches wins, so put the specific ones first.
RULES: list[tuple[str, str]] = [
    (r"\banthropolog|human evolutionary biology|human evolution and social change|"
     r"sociology and anthropology", "Anthropology"),
    (r"\bneuroscience|behavioral sciences|psycholog", "Psychology & Neuroscience"),
    (r"applied mathematics|\bmathematics\b|\bengineering\b|system dynamics|"
     r"energy modelling", "Engineering, Mathematics & Systems"),
    (r"political science|public policy|public and environmental affairs|"
     r"school of government|poverty and equity", "Political Science & Public Policy"),
    (r"environment|sustainab|rural studies|geoscience|natural resources|"
     r"natural sciences|agricultural (development|technology)|forestry|ecolog|"
     r"geography", "Environment & Sustainability"),
    (r"\beconom", "Economics"),
    (r"\bmanagement\b|business|organizational behavior|financial research",
     "Management & Business"),
    # NB: a French "Doctorat en Sciences" is a doctorate in *science*, not in social
    # science, and is not classifiable from the string alone -- see crosswalk_fields.csv.
    (r"social research|social sciences", "Other social science"),
    (r"labour organization|world bank|technical advisor|hospital|public health",
     "Non-academic / applied"),
]


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def classify(raw: str) -> tuple[str, str]:
    """-> (field, the rule that matched) for one raw string."""
    s = strip_accents(raw).lower()
    for pattern, field in RULES:
        if re.search(pattern, s):
            return field, pattern
    return "Unclassified", ""


def main() -> int:
    w = pd.read_csv(CLEAN).fillna("")
    seen: dict[tuple[str, str], int] = {}
    for kind, col in (("department", "affiliation_department"), ("phd_title", "phd_title")):
        for v in w[col]:
            v = str(v).strip()
            if v:
                seen[(kind, v)] = seen.get((kind, v), 0) + 1

    existing = pd.read_csv(FIELD_CW, dtype=str).fillna("") if FIELD_CW.exists() else pd.DataFrame()
    known = set(zip(existing.get("kind", []), existing.get("raw_string", [])))
    new = [(k, v, n) for (k, v), n in sorted(seen.items()) if (k, v) not in known]
    print(f"{len(seen)} distinct raw strings ({len(new)} new)")

    rows = []
    for kind, raw, n in new:
        field, rule = classify(raw)
        rows.append({
            "kind": kind, "raw_string": raw, "n_people": n, "field": field,
            "matched_rule": rule,
            "needs_review": "1" if field == "Unclassified" else "0",
            "notes": "",
        })

    out = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True) if len(existing) \
        else pd.DataFrame(rows)
    out.sort_values(["kind", "field", "raw_string"]).to_csv(FIELD_CW, index=False)
    if rows:
        m = pd.DataFrame(rows)
        print(m.groupby("field")["n_people"].sum().sort_values(ascending=False).to_string())
        unc = m[m.field == "Unclassified"]
        if len(unc):
            print(f"\nUNCLASSIFIED ({len(unc)}):")
            print(unc[["kind", "raw_string"]].to_string(index=False))
    print(f"wrote {FIELD_CW} ({len(out)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
