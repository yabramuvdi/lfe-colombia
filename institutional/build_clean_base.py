"""Build the analysis-ready tables from base_institucional.xlsx.

Reads the raw spreadsheet plus three hand-editable files -- crosswalk_institutions.csv,
crosswalk_people.csv and corrections.csv -- and writes four tables to out/.
The spreadsheet is never modified.

    out/base_institucional_clean.csv  one row per author, wide (the familiar shape)
    out/career_positions.csv          one row per (author, position), tidy/long
    out/supervision.csv               advisor -> advisee edges, PhD *and* postdoc
    out/advisors.csv                  the PhD subset of the above (kept for compatibility)
    out/review_flags.csv              everything changed on evidence, and everything unresolved

Run make_crosswalks.py and make_people_crosswalk.py first if the spreadsheet has
gained rows since the crosswalks were last refreshed.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
XLSX = HERE.parent / "base_institucional.xlsx"
OUT = HERE / "out"
INST_CW = HERE / "crosswalk_institutions.csv"
PEOPLE_CW = HERE / "crosswalk_people.csv"
CORRECTIONS = HERE / "corrections.csv"
EXCLUSIONS = HERE / "exclusions.csv"
FIELD_CW = HERE / "crosswalk_fields.csv"
SUPERVISION_SEED = HERE / "supervision_seed.csv"
SHORT_NAMES = HERE / "institution_short_names.csv"

# 'No' is a fact (this person had no postdoc). 'Not found' is an absence of
# evidence. Blank is neither recorded nor looked for. Collapsing all three to
# NA would destroy the denominator for any "what share did X?" statistic, so
# they are kept apart and surfaced as a three-valued flag.
NO_TOKENS = {"no"}
UNKNOWN_TOKENS = {"not found", "n/a", "-", "none"}

def attach_short_names(frames, problems):
    """Add a printable institution label beside every canonical institution.

    Figures that put an institution inside a box cannot carry "London School of
    Economics and Political Science", so ``institution_short_names.csv`` gives
    each one a printed form. It is keyed on ROR id rather than on a raw string
    because several raw spellings resolve to one institution, and a label
    attached to the spelling would let the same university print two ways.

    Two failures are reported rather than silently absorbed, following the rule
    the journal aliases already follow in the package: a curated row that
    matches nothing is a typo, and an institution with no curated row falls back
    to its canonical name so the gap shows up as a long label rather than a
    blank one.
    """
    if not SHORT_NAMES.exists():
        problems.append(f"{SHORT_NAMES.name} is missing; institutions keep their full names")
        return
    cur = pd.read_csv(SHORT_NAMES, dtype=str).fillna("")
    by_ror = {r.ror_id: r.short_name for r in cur.itertuples(index=False) if r.ror_id}
    by_name = {r.canonical_name: r.short_name for r in cur.itertuples(index=False)}

    def short_of(name, ror):
        if ror and ror in by_ror:
            return by_ror[ror]
        return by_name.get(name, name)

    seen_rors, seen_names = set(), set()
    for frame, name_col, ror_col in frames:
        if name_col not in frame.columns:
            continue
        rors = frame[ror_col] if ror_col and ror_col in frame.columns else pd.Series("", index=frame.index)
        names = frame[name_col].fillna("")
        rors = rors.fillna("")
        seen_names.update(n for n in names if n)
        seen_rors.update(r for r in rors if r)
        frame[f"{name_col}_short"] = [
            short_of(n, r) if n else "" for n, r in zip(names, rors, strict=True)
        ]

    dead = [
        r.canonical_name
        for r in cur.itertuples(index=False)
        if (r.ror_id not in seen_rors) and (r.canonical_name not in seen_names)
    ]
    if dead:
        problems.append(
            f"{len(dead)} short-name row(s) match no institution in the base: "
            + ", ".join(sorted(dead)[:5])
        )
    uncurated = sorted(n for n in seen_names if n not in by_name)
    if uncurated:
        problems.append(
            f"{len(uncurated)} institution(s) have no curated short name: "
            + ", ".join(uncurated[:5])
        )
    print(f"short names: {len(cur)} curated, {len(seen_names)} institutions in the base")


SPLIT_NAMES = re.compile(r",| y | and |;")

# A supervisor cell fragment is a person if it has two whitespace tokens -- or if
# it is an initial glued to a surname with no space after the period. The source
# has 'J.Rotmans' beside 'O.J. Vrieze' in one cell; a bare `len(split()) >= 2`
# test keeps the second and silently drops the first. Keep this in step with the
# identical guard in make_people_crosswalk.py.
GLUED_INITIALS = re.compile(r"^(?:[A-Za-z]\.){1,3}[A-Za-z]{2,}")


def looks_like_person(name: str) -> bool:
    return len(name.split()) >= 2 or bool(GLUED_INITIALS.match(name))


# ROR's spelling of each country the spreadsheet names, so the one institution
# with no ROR record (Conservation Strategy Fund) does not arrive in the figures
# as a second country called 'USA' beside ROR's 'United States'.
COUNTRY_NAME = {
    "usa": ("United States", "US"), "united states": ("United States", "US"),
    "uk": ("United Kingdom", "GB"), "united kingdom": ("United Kingdom", "GB"),
    "colombia": ("Colombia", "CO"), "spain": ("Spain", "ES"),
    "sweden": ("Sweden", "SE"), "italy": ("Italy", "IT"),
    "germany": ("Germany", "DE"), "france": ("France", "FR"),
    "denmark": ("Denmark", "DK"), "switzerland": ("Switzerland", "CH"),
    "netherlands": ("The Netherlands", "NL"),
    "the netherlands": ("The Netherlands", "NL"),
    "norway": ("Norway", "NO"), "canada": ("Canada", "CA"),
    "portugal": ("Portugal", "PT"), "thailand": ("Thailand", "TH"),
    "australia": ("Australia", "AU"),
}

# columns the source spreadsheet does not have; created empty so corrections.csv
# can populate them (see the postdoc_2/postdoc_3 note below)
DERIVED_COLS = ["postdoc_2_university", "postdoc_3_university",
                "postdoc_2_position", "postdoc_3_position"]

# a position recorded in the postdoc block that is not actually a postdoc
VISITING = re.compile(r"\bvisiting\b", re.I)

POSITION_BLOCKS = [
    # (label, department_col, institution_col, country_col, start_col, end_col)
    ("affiliation", "affiliation_department", "affiliation_university_or_institution",
     "affiliation_university_country", None, None),
    ("phd", "PhD_title", "PhD_institution", "PhD_country", None, "PhD_year_end"),
    ("postdoc_1", "postdoc_department", "postdoc_university", "postdoc_country",
     "postdoc_year_start", "postdoc_year_end"),
    # postdoc 2 and 3 have no university column in the source schema -- the
    # institution sits inside the department text. DERIVED_COLS adds the column
    # so corrections.csv can fill it, which restores the symmetry.
    ("postdoc_2", "postdoc_2_department", "postdoc_2_university", "postdoc_2_country",
     "postdoc_2_year_start", "postdoc_2_year_end"),
    ("postdoc_3", "postdoc_3_department", "postdoc_3_university", "postdoc_3_country",
     "postdoc_3_year_start", "postdoc_3_year_end"),
]

flags: list[dict] = []


def flag(display_name, kind, column, value, message):
    flags.append({"display_name": display_name, "kind": kind, "column": column,
                  "value": value, "message": message})


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def clean_cell(v) -> str:
    """NBSP, en-dash, curly quote, collapsed whitespace, NFC, trimmed."""
    if pd.isna(v):
        return ""
    s = str(v).replace("\xa0", " ").replace("–", "-").replace("’", "'")
    return unicodedata.normalize("NFC", " ".join(s.split())).strip()


def status_of(raw: str) -> str:
    """'none' | 'unknown' | 'present' for a cleaned cell."""
    low = raw.strip().lower()
    if low in NO_TOKENS:
        return "none"
    if low in UNKNOWN_TOKENS or low == "":
        return "unknown"
    return "present"


def parse_year(raw: str, who: str, col: str):
    """-> (Int64-able year or pd.NA, ongoing flag)."""
    low = raw.strip().lower()
    if low in ("in progress", "current", "ongoing", "present"):
        return pd.NA, True
    m = re.search(r"(1[89]\d{2}|20\d{2})", raw)
    if m:
        return int(m.group(1)), False
    if status_of(raw) == "present":
        flag(who, "unparsed_year", col, raw, "value is not a year and not a known sentinel")
    return pd.NA, False


def main() -> int:
    OUT.mkdir(exist_ok=True)
    h1 = pd.read_excel(XLSX, sheet_name="Hoja1")
    inst = pd.read_csv(INST_CW, dtype=str).fillna("")
    people = pd.read_csv(PEOPLE_CW, dtype=str).fillna("")
    corr = pd.read_csv(CORRECTIONS, dtype=str).fillna("")
    fields = pd.read_csv(FIELD_CW, dtype=str).fillna("") if FIELD_CW.exists() else pd.DataFrame()
    field_of = {(r.kind, r.raw_string): r.field for r in fields.itertuples(index=False)} \
        if len(fields) else {}

    inst_by_key = {r.raw_key: r for r in inst.itertuples(index=False)}
    person_by_raw = {r.raw_name: r for r in people.itertuples(index=False)}

    # ---- clean every cell, then apply the row-level corrections -------------
    h1 = h1.map(clean_cell)
    n_source_rows = len(h1)          # not a constant: the sheet gains and loses rows
    h1 = h1[h1["display_name"] != ""].reset_index(drop=True)
    for c in DERIVED_COLS:
        if c not in h1.columns:
            h1[c] = ""
    n_blank = n_source_rows - len(h1)
    if n_blank:
        flag("(blank rows)", "dropped", "display_name", "",
             f"{n_blank} row(s) with no display_name dropped from the clean table")

    # People deliberately removed from the analysis frame. Kept as a file rather
    # than deleted from the spreadsheet so the sampling frame stays auditable: the
    # paper has to be able to say who was in scope and why they left.
    if EXCLUSIONS.exists():
        excl = pd.read_csv(EXCLUSIONS, dtype=str).fillna("")
        for e in excl.itertuples(index=False):
            mask = h1["display_name"] == e.display_name
            if not mask.any():
                flag(e.display_name, "exclusion_unmatched", "display_name", e.display_name,
                     "exclusions.csv names someone not in the spreadsheet -- already gone?")
                continue
            h1 = h1[~mask].reset_index(drop=True)
            flag(e.display_name, "excluded", "display_name", e.display_name, e.reason)

    applied = 0
    for c in corr.itertuples(index=False):
        mask = h1["display_name"] == c.display_name
        if not mask.any():
            flag(c.display_name, "correction_unmatched", c.column, c.new_value,
                 "corrections.csv names an author not present in the spreadsheet")
            continue
        before = h1.loc[mask, c.column].iloc[0]
        if before != c.old_value:
            flag(c.display_name, "correction_stale", c.column, before,
                 f"corrections.csv expected {c.old_value!r}; spreadsheet now holds {before!r} "
                 "-- correction NOT applied")
            continue
        h1.loc[mask, c.column] = c.new_value
        applied += 1
        flag(c.display_name, "corrected", c.column, f"{c.old_value} -> {c.new_value}",
             f"[{c.confidence} confidence] {c.evidence}")
    print(f"applied {applied}/{len(corr)} corrections")

    # ---- resolve names -----------------------------------------------------
    rows, positions, advisor_edges = [], [], []
    for r in h1.itertuples(index=False):
        who = r.display_name
        p = person_by_raw.get(who)
        if p is None:
            flag(who, "unknown_person", "display_name", who,
                 "not in crosswalk_people.csv -- re-run make_people_crosswalk.py")
            canonical, author_id = who, ""
        else:
            canonical, author_id = p.canonical_name, p.author_id
        if not author_id:
            flag(who, "no_author_id", "display_name", who,
                 "no citegraph author_id -- this author cannot be joined to the citation data")

        rec = {"author_id": author_id, "display_name": canonical, "raw_display_name": who}
        visiting_blocks: set[str] = set()

        # ---- one block per career position --------------------------------
        for label, dept_c, inst_c, ctry_c, start_c, end_c in POSITION_BLOCKS:
            dept_raw = getattr(r, dept_c, "") or ""
            inst_raw = getattr(r, inst_c, "") if inst_c else ""
            ctry_raw = getattr(r, ctry_c, "") or ""
            # a block's status is driven by the institution where there is one,
            # otherwise by the department cell
            driver = inst_raw if inst_c else dept_raw
            st = status_of(driver)
            rec[f"{label}_status"] = st

            canon = ror = country = iso2 = campus = secondary = ""
            if st == "present" and inst_c:
                surname_key = strip_accents(who).lower().split()[-1]
                k = f"{inst_raw}|{surname_key}" if inst_raw == "University of California" else inst_raw
                m = inst_by_key.get(k)
                if m is None:
                    flag(who, "unknown_institution", inst_c, inst_raw,
                         "not in crosswalk_institutions.csv -- re-run make_crosswalks.py")
                else:
                    canon, ror = m.canonical_name, m.ror_id
                    country, iso2, campus = m.country, m.country_iso2, m.campus
                    secondary = m.secondary_canonical_name
                    if m.needs_review == "1":
                        flag(who, "institution_needs_review", inst_c, inst_raw,
                             f"mapped to {canon!r}: {m.notes}")
            elif st == "present" and not inst_c:
                flag(who, "institution_in_department_cell", dept_c, dept_raw,
                     f"{label} has no university column in the source schema; the institution "
                     "is inside the department text and was not canonicalised")

            # the country the spreadsheet asserts, where ROR did not supply one.
            # Spelled ROR's way, or the country ends up as its own extra category
            # ('USA' beside 'United States') the moment anything counts by country.
            if not country and status_of(ctry_raw) == "present":
                country, fallback_iso2 = COUNTRY_NAME.get(
                    ctry_raw.lower(), (ctry_raw, ""))
                iso2 = iso2 or fallback_iso2
                if ctry_raw.lower() not in COUNTRY_NAME:
                    flag(who, "country_not_normalised", ctry_c, ctry_raw,
                         "no ROR country for this institution and the spreadsheet's "
                         "spelling is not in COUNTRY_NAME -- it will count as its own "
                         "category; add it to the map")
            if st == "present" and status_of(ctry_raw) == "present" and iso2:
                asserted = COUNTRY_NAME.get(ctry_raw.lower(), ("", ""))[1]
                if asserted and asserted != iso2:
                    flag(who, "country_disagreement", ctry_c, ctry_raw,
                         f"spreadsheet says {ctry_raw}, ROR places {canon} in {country}")

            start, start_ongoing = parse_year(getattr(r, start_c, "") if start_c else "", who, start_c or "")
            end, ongoing = parse_year(getattr(r, end_c, "") if end_c else "", who, end_c or "")

            rec[f"{label}_department"] = dept_raw if status_of(dept_raw) == "present" else ""
            rec[f"{label}_institution"] = canon
            rec[f"{label}_institution_ror"] = ror
            rec[f"{label}_institution_2"] = secondary
            rec[f"{label}_campus"] = campus
            rec[f"{label}_country"] = country
            rec[f"{label}_country_iso2"] = iso2
            rec[f"{label}_year_start"] = start
            rec[f"{label}_year_end"] = end
            rec[f"{label}_ongoing"] = ongoing or start_ongoing

            if st == "present":
                kind = label.split("_")[0]
                pos_col = "postdoc_position" if label == "postdoc_1" else f"{label}_position"
                if kind == "postdoc" and VISITING.search(dept_raw + " " +
                                                         (getattr(r, pos_col, "") or "")):
                    kind = "visiting"
                    visiting_blocks.add(label)
                    flag(who, "not_a_postdoc", dept_c, dept_raw[:80],
                         f"{label} describes a visiting position, not a postdoc; "
                         "classified as position_type='visiting' so postdoc rates stay honest")
                positions.append({
                    "author_id": author_id, "display_name": canonical,
                    "position_type": kind,
                    "seq": int(label.split("_")[1]) if "_" in label else 1,
                    "department": rec[f"{label}_department"],
                    "institution": canon, "institution_ror": ror,
                    "institution_2": secondary, "campus": campus,
                    "country": country, "country_iso2": iso2,
                    "year_start": start, "year_end": end,
                    "ongoing": ongoing or start_ongoing,
                    "raw_institution": inst_raw or dept_raw,
                })

        # convenience booleans over the three-valued statuses. `visiting_blocks`
        # holds block labels, not column names: block 1's department column is
        # `postdoc_department`, not `postdoc_1_department`, so matching on the
        # column name silently failed to exclude a visiting first postdoc.
        pd_states = [rec[f"postdoc_{i}_status"] for i in (1, 2, 3)
                     if f"postdoc_{i}" not in visiting_blocks]
        pd_states = pd_states or ["unknown"]
        rec["has_postdoc"] = (True if "present" in pd_states
                              else (False if "none" in pd_states else pd.NA))
        rec["n_postdocs"] = sum(s == "present" for s in pd_states)
        rec["has_phd"] = {"present": True, "none": False, "unknown": pd.NA}[rec["phd_status"]]
        rec["phd_title"] = r.PhD_title if status_of(r.PhD_title) == "present" else ""
        rec["affiliation_field"] = field_of.get(("department", rec["affiliation_department"]), "")
        rec["phd_field"] = field_of.get(("phd_title", rec["phd_title"]), "")
        if rec["phd_year_end"] is not pd.NA and pd.notna(rec["phd_year_end"]):
            d = (int(rec["phd_year_end"]) // 10) * 10
            rec["phd_decade"] = f"{d}s"
        else:
            rec["phd_decade"] = ""
        for lbl, raw in (("affiliation_field", rec["affiliation_department"]),
                         ("phd_field", rec["phd_title"])):
            if raw and not rec[lbl]:
                flag(who, "unknown_field", lbl, raw,
                     "not in crosswalk_fields.csv -- re-run make_field_crosswalk.py")
        rec["phd_in_progress"] = rec["phd_ongoing"]

        # ---- supervisors ---------------------------------------------------
        sup_raw = r.PhD_supervisor
        sup_names = []
        if status_of(sup_raw) == "present":
            for part in SPLIT_NAMES.split(sup_raw):
                n = clean_cell(part)
                if status_of(n) != "present" or not looks_like_person(n):
                    continue
                sp = person_by_raw.get(n)
                cname = sp.canonical_name if sp else n
                sup_names.append(cname)
                advisor_edges.append({
                    "advisor_name": cname,
                    "advisor_author_id": sp.author_id if sp else "",
                    "advisor_in_frame": None,   # filled below, once the frame is known
                    "advisee_name": canonical,
                    "advisee_author_id": author_id,
                    "phd_institution": rec["phd_institution"],
                    "phd_year_end": rec["phd_year_end"],
                    "raw_advisor_name": n,
                })
        rec["phd_supervisors"] = "; ".join(sup_names)
        rec["n_phd_supervisors"] = len(sup_names)
        rec["phd_supervisor_status"] = status_of(sup_raw)
        rows.append(rec)

    wide = pd.DataFrame(rows)
    for c in wide.columns:
        if c.endswith(("_year_start", "_year_end")):
            wide[c] = wide[c].astype("Int64")
    pos = pd.DataFrame(positions)
    for c in ("year_start", "year_end"):
        pos[c] = pos[c].astype("Int64")
    adv = pd.DataFrame(advisor_edges)
    # True when the advisor is themselves one of the authors in this base. The old
    # `advisor_in_corpus` asked whether the advisor matched *any* citegraph author, so
    # it turned on how the corpus happened to spell the name -- Samuel Bowles resolved,
    # Robert Boyd did not, and neither is in this base.
    frame_names = set(wide["display_name"])
    adv["advisor_in_frame"] = adv["advisor_name"].isin(frame_names)
    # one table for both levels of supervision. PhD edges come from the
    # spreadsheet's own PhD_supervisor column; postdoc edges come from
    # supervision_seed.csv, which is hand-maintained because the spreadsheet has
    # no postdoc supervisor column at all.
    sup = adv.rename(columns={"advisor_name": "advisor", "advisee_name": "advisee",
                              "phd_institution": "institution"}).copy()
    sup["relation_type"] = "phd"
    sup["year_start"] = pd.NA
    sup["year_end"] = sup["phd_year_end"]
    sup["confidence"] = "high"
    sup["evidence"] = "PhD_supervisor column of base_institucional.xlsx"
    sup = sup[["advisor", "advisee", "relation_type", "institution", "year_start",
               "year_end", "confidence", "evidence", "advisor_author_id",
               "advisee_author_id", "advisor_in_frame"]]

    if SUPERVISION_SEED.exists():
        # the seed carries leading `#` explanation lines; drop them by line rather
        # than with pandas' comment=, which would also truncate any field holding a '#'
        import io
        body = "".join(ln for ln in SUPERVISION_SEED.read_text().splitlines(keepends=True)
                       if not ln.lstrip().startswith("#"))
        seed = pd.read_csv(io.StringIO(body), dtype=str).fillna("")
        canon_by_name = {}
        for rr in people.itertuples(index=False):
            canon_by_name[rr.raw_name] = (rr.canonical_name, rr.author_id)
            canon_by_name[rr.canonical_name] = (rr.canonical_name, rr.author_id)
        extra = []
        for e in seed.itertuples(index=False):
            adv_c, adv_id = canon_by_name.get(e.advisor_name, (e.advisor_name, ""))
            ade_c, ade_id = canon_by_name.get(e.advisee_name, (e.advisee_name, ""))
            if not ade_id:
                flag(e.advisee_name, "supervision_seed_unmatched", "advisee_name",
                     e.advisee_name, "supervision_seed.csv names someone not in the author list")
            extra.append({
                "advisor": adv_c, "advisee": ade_c, "relation_type": e.relation_type,
                "institution": e.institution,
                "year_start": int(e.year_start) if e.year_start else pd.NA,
                "year_end": int(e.year_end) if e.year_end else pd.NA,
                "confidence": e.confidence, "evidence": e.evidence,
                "advisor_author_id": adv_id, "advisee_author_id": ade_id,
                "advisor_in_frame": adv_c in frame_names,
            })
            if e.confidence in ("medium", "low"):
                flag(e.advisee_name, f"{e.relation_type}_advisor_{e.confidence}_confidence",
                     "supervision_seed.csv", f"{adv_c} -> {ade_c}", e.evidence)
        sup = pd.concat([sup, pd.DataFrame(extra)], ignore_index=True)

    # coverage of the postdoc side, which is the weak part of this table
    n_pd_positions = int((pos["position_type"] == "postdoc").sum())
    n_pd_edges = int((sup["relation_type"] == "postdoc").sum())
    flag("(coverage)", "postdoc_supervision_coverage", "supervision.csv",
         f"{n_pd_edges}/{n_pd_positions}",
         "postdoc advisors are rarely recorded publicly; the rest are unresolved. "
         "Add rows to supervision_seed.csv as they are confirmed.")

    # ---- verification ------------------------------------------------------
    print("\n--- verification ---")
    problems = []
    attach_short_names(
        [
            (pos, "institution", "institution_ror"),
            (sup, "institution", None),
            (adv, "phd_institution", None),
            *[
                (wide, f"{p}_institution", f"{p}_institution_ror")
                for p in ("affiliation", "phd", "postdoc_1", "postdoc_2", "postdoc_3")
            ],
        ],
        problems,
    )
    if wide["display_name"].str.contains("\xa0").any():
        problems.append("non-breaking space survived into display_name")
    for c in wide.columns:
        if wide[c].dtype == object and wide[c].astype(str).str.contains("\xa0").any():
            problems.append(f"non-breaking space survived in {c}")
    unmatched = wide[wide["author_id"] == ""]
    if len(unmatched):
        problems.append(f"{len(unmatched)} author(s) with no citegraph author_id")
    unknown_inst = [f for f in flags if f["kind"] == "unknown_institution"]
    if unknown_inst:
        problems.append(f"{len(unknown_inst)} institution string(s) missing from the crosswalk")
    dupe_ids = wide[wide["author_id"] != ""]["author_id"].duplicated().sum()
    if dupe_ids:
        problems.append(f"{dupe_ids} duplicated author_id(s) in the clean table")
    for c in wide.columns:
        if c.endswith(("_year_start", "_year_end")) and str(wide[c].dtype) != "Int64":
            problems.append(f"{c} is not a nullable integer column")
    print("PASS: all checks" if not problems else "FAIL:\n  " + "\n  ".join(problems))

    OUT.mkdir(exist_ok=True)
    wide.to_csv(OUT / "base_institucional_clean.csv", index=False)
    pos.to_csv(OUT / "career_positions.csv", index=False)
    adv.to_csv(OUT / "advisors.csv", index=False)
    sup.to_csv(OUT / "supervision.csv", index=False)
    pd.DataFrame(flags).to_csv(OUT / "review_flags.csv", index=False)
    print(f"\nwrote {len(wide)} authors, {len(pos)} positions, "
          f"{len(sup)} supervision edges ({(sup.relation_type=='phd').sum()} phd / "
          f"{(sup.relation_type=='postdoc').sum()} postdoc / "
          f"{(sup.relation_type=='visiting').sum()} visiting), "
          f"{len(flags)} review flags to {OUT}/")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
