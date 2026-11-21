"""Write the data files the explorer pages load (site/data/*.js).

Reads the frozen corpus (citegraph_out/) and the career base (institutional/out/;
run `make tables` first). Outputs are committed so GitHub Pages can serve the
site without running the pipeline. Each file is a plain <script> assignment so
the pages also open straight from disk.
"""

import json
import math
from pathlib import Path

import networkx as nx
import pandas as pd
from citegraph import CitationGraph

ROOT = Path(__file__).resolve().parent.parent
CG = ROOT / "citegraph_out"
INST = ROOT / "institutional" / "out"
DATA = ROOT / "site" / "data"

# Same construction as the co-citation map in notebooks/paper4_figures.ipynb (Figure 18).
CENTRALITY_MIN_PAPERS, MAP_AUTHORS, MAP_TIES_PER_AUTHOR = 3, 28, 3
NEIGHBOURHOODS = {  # the paper's hand-drawn reading of the map, matched on surname
    "Commons governance": ["Cardenas", "Gardner", "Hardin", "Janssen", "Ledyard", "Lopez",
                           "Murphy", "Ostrom", "Stranlund", "Velez", "Walker", "Willis"],
    "Social preferences": ["Andreoni", "Bowles", "Camerer", "Falk", "Fehr", "Fischbacher",
                           "Gintis", "Gneezy", "Gächter", "Henrich", "Kahneman", "McCabe"],
    "Experimental methods and public goods": ["Carpenter", "Croson", "Harrison", "List"],
}


def clean(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


def write(name, var, obj):
    DATA.mkdir(exist_ok=True)
    (DATA / f"{name}.js").write_text(
        f"const {var} = " + json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + ";\n",
        encoding="utf-8")


# ---- corpus: every work, who wrote it, who cites what -------------------------------------
works = pd.read_csv(CG / "works.csv").set_index("id")
doi = pd.read_csv(CG / "enriched_works.csv").set_index("id")["doi"]
ann = pd.read_csv(CG / "work_annotations.csv").set_index("id")
jel = pd.read_csv(CG / "jel_codes.csv").set_index("id")["JEL_Codes"]
occ = pd.read_csv(CG / "author_citations.csv").sort_values(["record_id", "position"])
authors = pd.read_csv(CG / "authors.csv").set_index("id")
names = authors["display_name"]
edges = pd.read_csv(CG / "citation_graph.csv")

core = works.index[works.ring == 0]
wa = occ.groupby("record_id", sort=False)["author_id"].apply(lambda s: list(dict.fromkeys(s)))
corpus = {"works": {}, "cites": edges[["citing_id", "cited_id"]].values.tolist(), "names": {}}
for wid, r in works.iterrows():
    year = clean(r.Year)
    w = {"t": clean(r.Title), "a": wa.get(wid, []), "y": int(year) if year is not None and str(year).isdigit() else clean(year),
         "j": next((j for j in (clean(r.Journal_Canonical), clean(r.Journal)) if j and j != "Unknown"), None), "doi": clean(doi.get(wid))}
    if not w["a"] and clean(r.Authors):
        w["ar"] = r.Authors  # no canonical author link: keep the raw string to show
    if r.ring == 0:
        w.update(core=True, tema=clean(ann.Tema.get(wid)), type=clean(ann.Publication_Type.get(wid)),
                 jel=clean(jel.get(wid)))
    corpus["works"][wid] = {k: v for k, v in w.items() if v not in (None, [], "")}
used = {a for w in corpus["works"].values() for a in w.get("a", [])}
corpus["names"] = {a: names[a] for a in sorted(used) if a in names}

# ---- people: the 58 core authors' profiles, plus their advisors, plus doctoral ties --------
base = pd.read_csv(INST / "base_institucional_clean.csv")
sup = pd.read_csv(INST / "supervision.csv")
core_ids = set(base.author_id)
people = {}
for r in base.itertuples():
    year = "" if pd.isna(r.phd_year_end) else f", {int(r.phd_year_end)}"
    people[r.author_id] = {k: v for k, v in {
        "name": r.display_name, "core": True, "advisors": r.phd_supervisor_status,
        "phd": "" if pd.isna(r.phd_institution) else f"{r.phd_institution}{year}",
        "phd_field": clean(r.phd_field), "phd_title": clean(r.phd_title),
        "aff": clean(r.affiliation_institution), "dept": clean(r.affiliation_department),
        "aff_field": clean(r.affiliation_field), "country": clean(r.affiliation_country),
    }.items() if v not in (None, "")}
ties = []
for r in sup.itertuples():
    key = lambda aid, name: aid if isinstance(aid, str) and aid in core_ids else name
    a, s = key(r.advisor_author_id, r.advisor), key(r.advisee_author_id, r.advisee)
    people.setdefault(a, {"name": r.advisor, "core": False})
    people.setdefault(s, {"name": r.advisee, "core": False})
    ties.append([a, s])

# ---- network: Figure 18's 28 authors and their co-citation ties ------------------------------
g = CitationGraph.from_out_dir(CG)
net = g.author_cocitation_network(min_papers=CENTRALITY_MIN_PAPERS)
ncite = nx.get_node_attributes(net, "n_citing_papers")
cos = lambda u, v: net[u][v]["weight"] / math.sqrt(ncite[u] * ncite[v]) if net.has_edge(u, v) else 0.0
strength = {u: sum(cos(u, v) for v in net[u]) for u in net}
top = sorted(net, key=lambda u: (-ncite[u], -strength[u]))[:MAP_AUTHORS]
drawn = set()
for u in top:
    for v in sorted((v for v in top if v != u), key=lambda v: -cos(u, v))[:MAP_TIES_PER_AUTHOR]:
        drawn.add(tuple(sorted((u, v))))
# Stress layout over the normalised ties among all pairs, as in the paper's neighbourhood map:
# two authors sit close when the corpus cites them together relative to how often it cites each.
dist = {u: {v: 1 - cos(u, v) for v in top if v != u} for u in top}
lay = nx.complete_graph(sorted(top))
pos = nx.kamada_kawai_layout(lay, dist=dist)
fold = lambda s: s.replace("á", "a").replace("é", "e").replace("ó", "o")
group = {fold(n): grp for grp, ns in NEIGHBOURHOODS.items() for n in ns}
network = {
    "nodes": {u: {"name": net.nodes[u]["display_name"], "n": ncite[u], "x": round(float(pos[u][0]), 4),
                  "y": round(float(pos[u][1]), 4), "group": group.get(fold(authors.surname[u]))} for u in top},
    "ties": [[u, v, net[u][v]["weight"], round(cos(u, v), 4), (u, v) in drawn]
             for u in sorted(top) for v in sorted(top) if u < v and net.has_edge(u, v)],
}

# ---- checks against the paper's numbers -----------------------------------------------------
assert len(core) == 93 and len(corpus["cites"]) == 4532
assert set(edges.citing_id) <= set(core) and set(edges.cited_id) <= set(works.index)
assert sum(p["core"] for p in people.values()) == 58 and len(ties) == len(sup)
assert core_ids <= set(corpus["names"]), "every core author must be linked to their works"
unplaced = [n["name"] for n in network["nodes"].values() if not n["group"]]
assert len(network["nodes"]) == MAP_AUTHORS and not unplaced, f"not in any neighbourhood: {unplaced}"

write("corpus", "CORPUS", corpus)
write("people", "PEOPLE", {"people": people, "ties": ties})
write("network", "NETWORK", network)
print(f"site/data: {len(corpus['works'])} works, {len(corpus['cites'])} citations, "
      f"{len(people)} people, {len(ties)} doctoral ties, {len(network['nodes'])} network authors")
