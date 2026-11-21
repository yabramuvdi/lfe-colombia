"""Seed / refresh the two hand-editable crosswalks for base_institucional.xlsx.

Re-runnable and non-destructive: rows already present in a crosswalk are kept
exactly as they are (so hand edits survive), and only raw strings that are new
to the spreadsheet get appended. Run this after Maria adds authors; then run
build_clean_base.py.

Institution canonical names and countries come from ROR (https://ror.org) where
a confident match exists, so aggregation can key on a stable identifier rather
than a string.
"""
from __future__ import annotations

import sys
import time
import unicodedata
from pathlib import Path

import httpx
import pandas as pd
from rapidfuzz import fuzz

HERE = Path(__file__).resolve().parent
XLSX = HERE.parent / "base_institucional.xlsx"
AUTHORS_CSV = HERE.parent / "citegraph_out" / "authors.csv"
INST_CW = HERE / "crosswalk_institutions.csv"
PEOPLE_CW = HERE / "crosswalk_people.csv"

INSTITUTION_COLS = [
    "affiliation_university_or_institution",
    "PhD_institution",
    "postdoc_university",
]
MISSING = {"", "no", "not found", "nan", "none", "n/a", "-"}

# the country columns that sit beside each institution column, used to keep ROR
# from matching a same-named institution on the wrong continent
COUNTRY_FOR = {
    "affiliation_university_or_institution": "affiliation_university_country",
    "PhD_institution": "PhD_country",
    "postdoc_university": "postdoc_country",
}
ISO_NAME = {
    "US": "United States", "GB": "United Kingdom", "CO": "Colombia",
    "ES": "Spain", "SE": "Sweden", "IT": "Italy", "DE": "Germany",
    "FR": "France", "DK": "Denmark", "CH": "Switzerland", "NL": "Netherlands",
    "NO": "Norway", "CA": "Canada", "PT": "Portugal", "TH": "Thailand",
    "AU": "Australia",
}
COUNTRY_ISO = {
    "usa": "US", "united states": "US", "uk": "GB", "united kingdom": "GB",
    "colombia": "CO", "spain": "ES", "sweden": "SE", "italy": "IT",
    "germany": "DE", "france": "FR", "denmark": "DK", "switzerland": "CH",
    "netherlands": "NL", "the netherlands": "NL", "norway": "NO",
    "canada": "CA", "portugal": "PT", "thailand": "TH", "australia": "AU",
}

# ROR ids pinned by hand where the API cannot be trusted to pick right
ROR_OVERRIDE = {
    "Conservation Strategy Fund": ("", "no ROR record; CSF is a US 501(c)(3), "
                                       "distinct from The Conservation Fund"),
}

# --- hand-authored resolution of every raw string that is not already the
# --- institution's own name. Values are (canonical, secondary_or_None, note).
# --- Anything absent here is passed to ROR as-is.
# Retired 2026-09-13 when the source was corrected, and deliberately NOT kept:
# "PSU" and "Leipzig University" are ordinary names of other institutions, so an
# unscoped mapping here would silently misroute a future row. The rest are kept
# even when unreferenced -- they are abbreviations or misspellings that can only
# mean one thing.
HAND: dict[str, tuple[str, str | None, str]] = {
    # Colombian shorthand
    "Uniandes": ("Universidad de los Andes", None, "local shorthand"),
    "Javeriana": ("Pontificia Universidad Javeriana", None, "local shorthand"),
    "UNAL Medellin": ("Universidad Nacional de Colombia", None, "campus: Medellin"),
    "UNAL Bogota": ("Universidad Nacional de Colombia", None, "campus: Bogota"),
    # abbreviations
    "UCL": ("University College London", None, "abbreviation"),
    "UCLA": ("University of California, Los Angeles", None, "abbreviation"),
    "MIT": ("Massachusetts Institute of Technology", None, "abbreviation"),
    "Caltech": ("California Institute of Technology", None, "abbreviation"),
    "UC Santa Barbara": ("University of California, Santa Barbara", None, "abbreviation"),
    # bare 'University of California' - campus resolved per person by lookup
    "University of California|mcelreath": (
        "University of California, Los Angeles", None,
        "campus resolved by lookup: PhD 2001 under Robert Boyd at UCLA"),
    "University of California|stranlund": (
        "University of California, Santa Barbara", None,
        "campus resolved by lookup: PhD Economics UCSB 1992"),
    "University of California|murphy": (
        "University of California, Davis", None,
        "campus resolved by lookup: PhD Agricultural & Resource Economics UC Davis 1999"),
    # same institution, several strings
    "Indiana University": ("Indiana University Bloomington", None, "campus implied"),
    "Indiana University - Bloomington, USA": ("Indiana University Bloomington", None, "trailing country"),
    "Indiana University Bloomington, Arizona State University": (
        "Indiana University Bloomington", "Arizona State University", "two institutions in one cell"),
    "Washington University": ("Washington University in St. Louis", None, "short form"),
    "Columbia University, New York City": ("Columbia University", None, "trailing city"),
    "Boise State University in Boise": ("Boise State University", None, "trailing city"),
    "College of DuPage (Illinois).": ("College of DuPage", None, "trailing state + period"),
    "Max Planck Institute (Berlin)": (
        "Max Planck Institute for Human Development", None,
        "Barrett's postdoc unit (Center for Adaptive Behavior and Cognition) sits at MPI-HD Berlin"),
    "Max-Planck-Gesellschaft": (
        "Max Planck Institute for Human Development", None,
        "McElreath's postdoc unit (Center for Adaptive Behavior and Cognition) sits at MPI-HD Berlin"),
    # sub-unit given instead of the parent institution
    "Andrew Young School of Policy Studies": (
        "Georgia State University", None, "school within Georgia State University"),
    "St. Antony's College, University of Oxford": (
        "University of Oxford", None, "college within Oxford"),
    "Institute of Sciences and Technology (ICTA), Universitat Autonoma de Barcelona": (
        "Universitat Autonoma de Barcelona", None,
        "ICTA = Institut de Ciencia i Tecnologia Ambientals, a UAB institute"),
    # wrong language / wrong accent
    "Universidad de Pavia": ("Universita di Pavia", None, "Spanish spelling of an Italian university"),
    "Universitat Autonoma de Barcelona": ("Universitat Autonoma de Barcelona", None, ""),
    "University of gottingen": ("University of Gottingen", None, "lowercase g"),
    "University of Lugano": ("Universita della Svizzera italiana", None, "official name"),
    "Universite Paris Ouest Nanterre La Defense": (
        "Universite Paris Nanterre", None, "renamed in 2017"),
    "Universite Lyon 1": ("Universite Claude Bernard Lyon 1", None, "official name"),
    "Vrije Universiteit": ("Vrije Universiteit Amsterdam", None, "disambiguated from VU Brussel"),
    "Osnabruck University": ("Universitat Osnabruck", None, ""),
    # two institutions in one cell, Spanish connector
    "Brigham and Women's Hospital y la Harvard T.H. Chan School of Public Health.": (
        "Brigham and Women's Hospital", "Harvard T.H. Chan School of Public Health",
        "Ariadne Labs is a joint centre of both; Spanish connector and trailing period removed"),
}


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def clean_cell(v) -> str:
    """Normalise a raw spreadsheet cell: NBSP, newlines, NFC, trim."""
    if pd.isna(v):
        return ""
    s = str(v).replace("\xa0", " ").replace("–", "-").replace("’", "'")
    s = " ".join(s.split())
    return unicodedata.normalize("NFC", s).strip()


def is_missing(s: str) -> bool:
    return s.strip().lower() in MISSING


def ror_lookup(name: str, client: httpx.Client, expect_iso2: str = "") -> dict:
    """Best ROR match for `name`, or empty dict if nothing is confident.

    `expect_iso2` is the country the spreadsheet records for this affiliation.
    A candidate in the wrong country is rejected outright: several institutions
    share a name across countries (Northwestern University exists in both
    Evanston and Laoag), so a perfect string score proves nothing on its own.
    """
    try:
        r = client.get("https://api.ror.org/v2/organizations",
                       params={"query": name}, timeout=30)
        r.raise_for_status()
        items = r.json().get("items", [])
    except Exception as exc:  # network trouble is recorded, never fatal
        return {"ror_error": str(exc)[:120]}
    best, best_score, rejected = None, 0.0, 0
    for it in items[:15]:
        loc = (it.get("locations") or [{}])[0].get("geonames_details", {})
        if expect_iso2 and loc.get("country_code") and loc["country_code"] != expect_iso2:
            rejected += 1
            continue
        names = [n["value"] for n in it.get("names", [])]
        score = max((fuzz.token_sort_ratio(strip_accents(name).lower(),
                                           strip_accents(n).lower()) for n in names),
                    default=0.0)
        if score > best_score:
            best, best_score = it, score
    if best is None or best_score < 80:
        return {"ror_score": round(best_score, 1),
                "ror_error": f"{rejected} candidate(s) rejected on country" if rejected else ""}
    display = next((n["value"] for n in best["names"] if "ror_display" in n["types"]),
                   best["names"][0]["value"])
    loc = (best.get("locations") or [{}])[0].get("geonames_details", {})
    return {
        "ror_id": best["id"].rsplit("/", 1)[-1],
        "ror_display": display,
        "country": loc.get("country_name", ""),
        "country_iso2": loc.get("country_code", ""),
        "org_type": ";".join(best.get("types", [])),
        "ror_score": round(best_score, 1),
        "ror_error": f"{rejected} candidate(s) rejected on country" if rejected else "",
    }


def collect_raw_institutions(h1: pd.DataFrame) -> list[tuple[str, tuple[str, str]]]:
    """Every distinct key -> (raw_string, expected_iso2) needing a canonical name."""
    seen: dict[str, tuple[str, str]] = {}
    for _, row in h1.iterrows():
        surname_key = strip_accents(clean_cell(row["display_name"])).lower().split()[-1] \
            if clean_cell(row["display_name"]) else ""
        for col in INSTITUTION_COLS:
            raw = clean_cell(row.get(col))
            if is_missing(raw):
                continue
            # bare 'University of California' needs a per-person campus
            key = f"{raw}|{surname_key}" if raw == "University of California" else raw
            ctry = clean_cell(row.get(COUNTRY_FOR[col]))
            iso = "" if is_missing(ctry) else COUNTRY_ISO.get(ctry.lower(), "")
            prev = seen.get(key)
            # keep the first non-empty country hint we see for this string
            seen[key] = (raw, prev[1] or iso) if prev else (raw, iso)
    return sorted(seen.items())


def main() -> int:
    h1 = pd.read_excel(XLSX, sheet_name="Hoja1")
    # corrections.csv can introduce institution strings the spreadsheet never
    # held (and can add whole columns), so fold it in before collecting keys
    corr_path = HERE / "corrections.csv"
    if corr_path.exists():
        corr = pd.read_csv(corr_path, dtype=str).fillna("")
        for c in corr.itertuples(index=False):
            if c.column not in h1.columns:
                h1[c.column] = ""
            mask = h1["display_name"].map(clean_cell) == c.display_name
            if mask.any() and clean_cell(h1.loc[mask, c.column].iloc[0]) == c.old_value:
                h1.loc[mask, c.column] = c.new_value
        for col in ("postdoc_2_university", "postdoc_3_university"):
            if col in h1.columns and col not in INSTITUTION_COLS:
                INSTITUTION_COLS.append(col)
                COUNTRY_FOR[col] = col.replace("_university", "_country")
    keys = collect_raw_institutions(h1)
    print(f"{len(keys)} distinct institution keys in the spreadsheet")

    existing = pd.read_csv(INST_CW, dtype=str).fillna("") if INST_CW.exists() else pd.DataFrame()
    known = set(existing["raw_key"]) if len(existing) else set()
    new_keys = [(k, v) for k, v in keys if k not in known]
    print(f"{len(new_keys)} new; {len(known)} already in {INST_CW.name} (kept as-is)")
    unused = known - {k for k, _ in keys}
    if unused:
        print(f"{len(unused)} crosswalk row(s) no longer referenced by the spreadsheet "
              f"(harmless, kept for history): {', '.join(sorted(unused))}")
    if not new_keys:
        return 0

    rows = []
    with httpx.Client(headers={"User-Agent": "citegraph-lfe-colombia/1.0"}) as client:
        for i, (key, (raw, expect_iso2)) in enumerate(new_keys, 1):
            # HAND is keyed on the accent-stripped string so it survives the
            # accent problems the raw data has.
            hand_key = strip_accents(key)
            canonical, secondary, note = HAND.get(hand_key, (raw, None, ""))
            src = "hand" if hand_key in HAND else "verbatim"
            if canonical in ROR_OVERRIDE:
                pinned, why = ROR_OVERRIDE[canonical]
                info = {"ror_id": pinned, "ror_score": "", "ror_error": why}
            else:
                info = ror_lookup(canonical, client, expect_iso2)
            # prefer ROR's official display name, which is the point of using ROR
            final = info.get("ror_display") or canonical
            rows.append({
                "raw_key": key,
                "raw_string": raw,
                "canonical_name": final,
                "ror_id": info.get("ror_id", ""),
                "campus": note.split("campus: ")[1] if "campus: " in note else "",
                "country": info.get("country", "") or ISO_NAME.get(expect_iso2, ""),
                "country_iso2": info.get("country_iso2", "") or expect_iso2,
                "org_type": info.get("org_type", ""),
                "secondary_canonical_name": secondary or "",
                "secondary_ror_id": "",
                "resolved_from": src if not info.get("ror_id") else f"{src}+ror",
                "ror_match_score": info.get("ror_score", ""),
                "needs_review": "1" if (not info.get("ror_id") or info.get("ror_score", 0) < 90) else "0",
                "notes": "; ".join(x for x in (note, info.get("ror_error", "")) if x),
            })
            print(f"  [{i:2d}/{len(new_keys)}] {raw[:48]:50s} -> {final[:45]:47s} "
                  f"{info.get('ror_id','(no ror)')}")
            time.sleep(0.15)

    # second pass: ROR ids for the secondary institutions
    with httpx.Client(headers={"User-Agent": "citegraph-lfe-colombia/1.0"}) as client:
        for r in rows:
            if r["secondary_canonical_name"]:
                info = ror_lookup(r["secondary_canonical_name"], client, r["country_iso2"])
                r["secondary_ror_id"] = info.get("ror_id", "")
                if info.get("ror_display"):
                    r["secondary_canonical_name"] = info["ror_display"]
                time.sleep(0.15)

    out = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True) if len(existing) \
        else pd.DataFrame(rows)
    out.sort_values("raw_string").to_csv(INST_CW, index=False)
    print(f"\nwrote {INST_CW} ({len(out)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
