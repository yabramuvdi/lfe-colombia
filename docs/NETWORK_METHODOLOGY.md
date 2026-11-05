# Paper 4 — Network methodology, in plain words

Companion note to section 7 of `notebooks/paper4_figures.ipynb`. It explains what the
network we analyse is, how it is built, what each number means, and what we deliberately
leave out. It is written so that a co-author can lift paragraphs straight into the paper's
methods section and so that a reviewer's likely objections are already answered.

Written 11 September 2026, alongside the notebook changes it describes. Corpus figures
below are from the artifacts of that date and drift slightly whenever a pipeline stage is
re-run; re-check them against the notebook output before they go into the manuscript.

**Decisions taken (11 September 2026).** Each was weighed in the assessment that preceded
this note; the alternative is described in the text where it matters.

| # | Decision | Implemented in the notebook |
| - | -------- | --------------------------- |
| D1 | Which single centrality measure to report | Freeman degree centrality is the reported measure and the ranking figure. Normalised strength was tried first and reverted the same day: it selects the same top 20, is no less compressed, and costs the reader a definition. It stays as a check in the exported table and one sentence in the notes |
| D2 | Whether to claim algorithmic "communities" | No. The map caption offers three groupings as our reading, and prints the modularity of the unpruned normalised ties so the claim stays honest. Reaffirmed 13 September 2026: the neighbourhood map now *shades* by that hand reading too, because the 28-author partition collapsed to two communities at modularity 0.06 after the corpus repair. The 60-author partition still recovers the three groups (modularity 0.10) |
| D3 | Whether to bring back the "centre of gravity by period" figure | Yes, rewritten as notebook section 8 |
| D4 | Whether the ego network stays in the main text | Moved to an appendix |

---

## 1. What question the network answers

The citation counts in sections 4 to 6 tell us *who* the corpus cites and *how often*. The
network in section 7 asks a different question: *how are the authors the corpus cites
arranged relative to one another?* Do they form one conversation or several? Which authors
are read together? Where does the focal author sit?

That is a question about **position in a structure**, not about totals. It needs a network,
and the first methodological decision is which network.

**Why not the citation graph itself.** The pipeline extracts the bibliography of each of
the 93 source publications. That gives a graph in which source publications point to the
works they cite. The graph is one hop deep by construction: only the 93 sources have
outgoing arrows, and every cited work is a dead end whether or not it cites anything in the
real world. Path-based measures such as betweenness, closeness or PageRank computed on this
graph would describe *our sampling design* (which PDFs we happened to process), not the
literature. We therefore do not compute centrality on it.

**What we use instead.** The standard answer in the sociology of science and in
bibliometrics is to turn the citation data into an **author co-citation network** (Small
1973 for documents; White and Griffith 1981 for authors). It is the tool that the
"mapping a discipline" literature has used for forty years (McCain 1990; White and McCain
1998), and every measure we report is defined on it.

---

## 2. The object: an author co-citation network

**In one sentence.** Two authors are connected when the same bibliography cites both of
them, and the connection is as strong as the number of bibliographies that do so.

**A toy example.** Suppose three source publications have these bibliographies:

| Source | Cites works by |
| ------ | -------------- |
| P1 | Ostrom, Cardenas, Fehr |
| P2 | Ostrom, Cardenas |
| P3 | Fehr, Gächter, Cardenas |

Then Ostrom–Cardenas are co-cited by two bibliographies (P1, P2), Fehr–Cardenas by two
(P1, P3), Ostrom–Fehr by one (P1), Fehr–Gächter by one (P3), Cardenas–Gächter by one (P3),
and Ostrom–Gächter by none. Cardenas is tied to everyone; Gächter is tied to two authors.
That is the whole construction. The corpus network is the same thing with 92 bibliographies
instead of three.

**Why co-citation says something.** A co-citation is a statement made by the *citing*
authors, not by us. When a bibliography cites Ostrom and Fehr together, its authors are
telling us that they treat those two bodies of work as belonging to the same conversation.
Aggregating those statements across the corpus recovers the intellectual map that the field
itself holds in its head (White and Griffith 1981 call this "intellectual structure";
Persson 1994 calls the set of cited authors the corpus's "intellectual base").

**Construction rules we apply, and why.**

1. *Every author of a cited work counts* ("all-author" co-citation, Zhao and Strotmann
   2008), not only the first author. First-author counting would erase co-authors and
   misattribute team work; it dates from when citation indexes recorded only first authors.
2. *One mention per bibliography.* If a source cites three works by Ostrom, Ostrom appears
   once in that bibliography's author set. The tie weight counts bibliographies, never
   individual references, so long bibliographies do not get more than one vote per pair.
3. *No self-ties.* An author is never co-cited with themself.
4. *Inclusion threshold.* An author enters the network only if at least **3** source
   bibliographies cite them. This removes the long tail of once-cited names, which would
   otherwise dominate the node count while telling us nothing about structure. The top-20
   ranking is unchanged at thresholds of 2, 3 or 5 (19 to 20 of the same names); the
   threshold matters only for the size of the network and the percentage scale of degree.
5. *Author identities* come from the pipeline's author-normalisation stage, which merges
   name variants ("Cardenas, J.C.", "Juan Camilo Cardenas") into one canonical author and
   keeps genuinely different people apart. Remaining splits among the authors that matter
   here are negligible (one or two citations each).

**What the corpus network looks like** (re-measured 13 September 2026, after the
thesis-series records were removed from the corpus itself).

| Quantity | Value |
| -------- | ----- |
| Source publications (bibliographies) | 93 |
| References per bibliography | median 39, range 14 to 157 (after excluding the thesis-series records) |
| Authors cited by at least 3 bibliographies | 564 |
| Co-citation ties | 48,556 |
| Density (share of all author pairs that are tied) | 0.31 |
| Largest set of most-cited authors in which every pair is tied | the 30 most-cited authors |

One known data problem is gone. One dissertation's back matter added 180 spurious
"references" (see `DATA_QUALITY_NOTES.md`). **As of 13 September 2026 those records are
removed from the corpus itself**, not filtered in the notebook; the notebook now only
carries a guard that fails loudly if they ever return. They never reached the network
anyway: they are cited by that one document only, so their authors fall below the
3-bibliography threshold, and the four Gothenburg environmental economists who remain are
genuinely cited elsewhere in the corpus.

---

## 3. Reading the structure: one conversation, not several

The first result is not a ranking but a shape.

**Density 0.31** means that three of every ten pairs of authors in the network have been
cited together by at least one source publication. For 564 authors, that is a very
connected network.

**The 30 most-cited authors form a clique**: every one of them has been co-cited with
every other at least once. In plain words, there is no author in the top thirty whom the
corpus reads in isolation from the rest. The literature the corpus builds on is a single
integrated conversation, with the classic look of an **invisible college** (Price 1965;
Crane 1972): a small, densely interconnected set of authors that everyone in the field
reads together.

**Sub-schools are visible but faint.** When we let a standard community-detection
algorithm (modularity maximisation, Newman 2006; Blondel et al. 2008) partition the
normalised network among the 60 most central authors, it finds three consistent groups,
and they are readable:

- a *commons-governance* group around Ostrom, Walker, Gardner, Stranlund, Willis, Ledyard,
  Cardenas, Lopez, Janssen;
- a *social-preferences and cultural-evolution* group around Fehr, Bowles, Henrich,
  Fischbacher, Carpenter, Camerer, Gintis, Falk;
- a *field-experimental methodology and public-goods* group around Gächter, List,
  Harrison, Croson, Gneezy, Andreoni, Herrmann, Eckel.

But the separation is weak: the modularity of that partition is about 0.10, where values
near zero mean the groups are barely more connected internally than a random division
would be. (An earlier draft figure reported modularity 0.47; that number was computed on
the pruned "backbone" drawn in the map, and pruning creates apparent structure by
construction, so it overstated the finding.) **This is why the map caption offers the
three groupings as our reading of the map rather than as an algorithmic result, and prints
the modularity of the unpruned ties next to them (D2).** The honest headline is
integration, not fragmentation.

---

## 4. Drawing the map

A network this dense cannot be drawn as it is: with almost every pair tied, a layout
algorithm has nothing to separate and produces a blob. Two steps that are standard in
author co-citation mapping turn it into a readable picture.

**Step 1, normalise the ties.** Raw co-citation counts mostly reproduce citation frequency:
two authors cited by many bibliographies will be co-cited often just by arithmetic. We
therefore divide each tie by the square root of the product of the two authors' own citing
counts (the **cosine**, or Salton, measure; Salton and McGill 1983; see van Eck and Waltman
2009 on why co-occurrence data should be normalised this way). In the toy example,
Ostrom–Cardenas is 2 / √(2 × 3) = 0.82 while Fehr–Gächter is 1 / √(2 × 1) = 0.71. The
normalised tie asks: *given how often each author is cited at all, how often are they cited
together?* It rewards distinctive pairing and discounts mere frequency.

**Step 2, keep the backbone.** For each of the 28 most-cited authors (the selection rule of
classical author co-citation mapping) we keep only their 3 strongest normalised ties. What remains is the skeleton of the strongest affinities, which
a force-directed layout can resolve.

**How to read the map figure.** Node area is the number of source publications citing the
author. A line means the tie is among one of the two authors' three strongest normalised
ties. Positions come from a force-directed layout with a fixed random seed: near means
strongly tied, but the axes carry no units and distances are not measurements. The three groupings named in the caption are
those of section 3. They are stated by hand in the notebook, not re-derived per run. At the
60-author scale the algorithm does recover them (three groups, modularity 0.10), but the
unpruned normalised ties among the *28 mapped authors alone* separate into only **two**
communities, at modularity 0.06, merging commons governance with the field-experimental
group. A partition that weak should not decide what a figure claims, so the notebook prints
it beside the reading instead of drawing from it.

**A second drawing of the same map** (`cocitation_network_map_neighbourhoods`) is built to
be read rather than to stay close to the drawn ties. It keeps the same 28 authors and the
same backbone lines but takes positions from a stress layout over the normalised ties among
*all* pairs, which is the modern form of the multidimensional-scaling maps that author
co-citation analysis has used since McCain (1990): two authors sit close when the corpus
cites them together relative to how often it cites each, whether or not a line joins them.
The three neighbourhoods are shaded and named, and node fill follows them so the grouping
survives grayscale print. Both the grouping and its names are ours; the caption says so and
reports the modularity of the algorithmic partition of the same ties beside it. Because membership follows all of an author's
ties while the lines show only the three strongest, an author can sit inside one
neighbourhood while their lines reach another (Andreoni, in the social-preferences region,
is drawn tied to the commons experimentalists). That is a faithful feature, not a drawing
error, and the caption explains it.

---

## 5. Measuring position: one centrality measure

Centrality is any number that summarises how well placed a node is. The classic menu is
Freeman's (1979): degree, closeness, betweenness; plus Bonacich's (1972) eigenvector
measure. We report **one**, degree, and compute a second only as a check.

**Degree centrality, the measure we report (D1).** Degree centrality is the share of the
other authors in the network with whom an author is co-cited at least once. It is the
simplest possible statement of centrality and needs no definition beyond that sentence:
"co-cited with 97% of the authors in the network" is plain language. In the toy example of
section 2, Cardenas has degree 1 (tied to all three others) and Gächter 2/3.

**What degree shows here, and what it cannot.** On this network degree **saturates** at
the top: the focal author scores 0.97, the next ten score between 0.81 and 0.95, and the
thirty most-cited authors form a clique. Once every frequently-cited author is tied to
nearly everyone, the top of the degree ranking is close to the citation ranking of section
5 (rank correlation 0.86 with citation counts among the 50 most-cited authors, 0.76 over
all 564). The paper should say this plainly, because it is the finding of section 3 seen
from the individual author's side: the literature the corpus draws on is one conversation,
and its most-cited authors are read alongside everyone. The ranking figure is therefore a
supporting figure; the structural claims rest on the density, the clique and the map.

**Normalised strength, computed as a check.** The weighted generalisation of degree
(Barrat et al. 2004; Opsahl, Agneessens and Skvoretz 2010) is the sum of an author's tie
weights. Computed on the cosine-normalised ties of section 4 it discounts citation
frequency and asks how strongly an author is paired with the rest of the network. It was
the first candidate for the headline measure and was reverted: it selects 19 of the same
twenty authors as degree (rank correlation 0.84 across all authors), is no less compressed
at the top, and costs the reader a definition that "share of authors co-cited with" does
not. It reorders a few names in a way that is informative but not needed for the paper's
argument: authors whose citations cluster in one sub-literature rise (Lopez from 10th to
4th), authors cited broadly but diffusely fall (Gächter from 4th to 7th). It is kept as a
column in the exported table (`author_centrality.csv`) and as one sentence in the figure
notes, which turns it into a free robustness statement.

**Dropped, and why.**

- *Eigenvector centrality* (Bonacich 1972) on the raw ties ranks almost identically to
  degree here (rank correlation 0.88) and even more closely to citation counts (0.80).
  Reporting it alongside degree adds a second number that says the same thing. On the
  normalised ties it becomes unstable, favouring small tight groups.
- *Betweenness and closeness* (Freeman 1979) measure bridging and reach along shortest
  paths. In a network where three in ten pairs are directly tied and the top thirty are a
  clique, almost every shortest path has length one or two, there are few structural holes
  to bridge, and both measures collapse into noisy versions of degree. We checked a
  related bridging statistic (the participation coefficient across the three groups of
  section 3) and it is essentially identical for every author in the top twenty, at about
  0.65: nobody is a distinctive broker, because everybody is tied to everybody.
- *PageRank* is a directed-graph prestige measure; the co-citation network is undirected,
  and on the citation graph it would measure sampling design (section 1).

---

## 6. The self-citation check

**The objection.** The focal author wrote a large share of the source publications, and
his own bibliographies cite him. He could be central because he cites himself.

**The check.** Rebuild the entire network from only the source publications he did *not*
author (54 of 93) and recompute every measure. No tie in that network can come from his own
bibliographies.

**The result.** He remains cited by 36 of those 54 publications and keeps rank 1 by degree
centrality; the rest of the top fifteen moves by a few places at most. On the repaired
corpus he now keeps rank 1 under the normalised-strength check as well — before the
thesis-series records were removed he fell to second behind Ostrom, so this reading has
strengthened, not weakened. Read plainly: his position does not depend on his own
bibliographies. The figure notes report both measures.

**The check's limit.** The 54 remaining sources are still, in large part, written by his
students and co-authors. The check removes mechanical self-citation; it cannot remove the
fact that the corpus was assembled around a research programme he started. The paper
should say so.

---

## 7. Whom the focal author is read alongside (D4: appendix)

The ego-network figure shows the 15 authors most often co-cited with the focal author,
with tie width proportional to the raw number of shared bibliographies (Ostrom 53, Walker
44, Fehr 38, Stranlund 37, Gardner 34 at the time of writing). The light ties among the
other 15 show that they are all tied to one another too. It is a descriptive figure and
readers like it, but its content is largely the top of the citation ranking in section 5,
drawn as a star. It belongs in an appendix rather than the main text.

---

## 8. Limitations to state in the paper

1. **One-hop data.** We see what the 93 sources cite, not what the cited works cite. The
   network describes the corpus's intellectual base, not the field at large.
2. **Corpus definition drives centrality.** A corpus assembled around a research programme
   will find that programme's founder central. Section 6 handles self-citation, not
   selection.
3. **Long bibliographies weigh more.** Each bibliography casts one vote per author pair,
   but a 200-reference dissertation casts votes on far more pairs than a 20-reference
   article. This is inherent to co-citation counting and standard practice; we do not
   correct for it.
4. **Author disambiguation is automated.** Residual splits (an initial-only variant not
   merged into its full-name cluster) lower an author's counts slightly. We checked the
   top authors by hand; remaining splits are one or two citations.
5. **Normalisation is a choice, and not every normalisation can be summed into a
   centrality.** Cosine is one of several accepted normalisations of co-occurrence data
   (association strength, Jaccard, inclusion; van Eck and Waltman 2009). For the map they
   give similar pictures. For the strength measure they do not: association strength and
   Jaccard divide by products or sums of the two citing counts, so a pair of authors cited
   three times each and co-cited once scores higher than Cardenas–Ostrom, and the summed
   ranking is taken over by rarely-cited, initial-only names. Cosine (and the inclusion
   index, which agrees with it on nine of the top ten) scales by the square root of the
   product and stays anchored to authors the corpus actually reads. That, and its
   simplicity, is why the map and the check use cosine. A reviewer who asks for association strength
   should be pointed to the map, where it is appropriate, not to the ranking.
6. **Layout positions are not measurements.** Distances in the map figures are a visual
   aid with a fixed seed, not coordinates in a metric space.

---

## 9. What we deliberately did not do

- **Bibliographic coupling** (Kessler 1963): link two *source* publications when they
  share references. It is the mirror image of co-citation and describes the corpus's
  research front rather than its intellectual base. We computed it as a check: all 92
  sources connect, density 0.42, and modularity-based grouping (about 0.18) separates
  early commons experiments, co-management studies, regulation and enforcement, and the
  later social-preferences work, roughly by period. It is a second network with a second
  set of concepts to explain, and the paper's question is about the intellectual base, so
  we leave it out. It is a natural extension if a reviewer asks how the corpus itself is
  organised.
- **Any path-based or prestige measure** (betweenness, closeness, PageRank, k-cores,
  structural holes), for the reasons in sections 1 and 5.
- **Temporal networks.** With 93 sources spread over 26 years, per-period networks are
  too small to compare structurally. The one historical figure worth keeping (D3) is
  descriptive: the share of each period's sources that cite a given author, which shows the
  corpus's centre of gravity moving from Hardin to Ostrom to social preferences to the
  economics of conflict. That figure is section 8 of the notebook
  (`centre_of_gravity_by_period`); the six tracked authors are Hardin, Ostrom, the focal
  author, Fehr, List and Blattman, each resolved to a canonical author cluster.

---

## 10. A methods paragraph to adapt

> To describe the intellectual structure of the literature the corpus draws on, we build
> an author co-citation network (Small 1973; White and Griffith 1981). For each of the 93
> source publications we take the set of authors of the works its bibliography cites,
> counting every co-author of a cited work once per bibliography. Two authors are linked
> when at least one bibliography cites both, and the tie is weighted by the number of
> bibliographies that do. Authors cited by fewer than three bibliographies are excluded,
> leaving 564 authors and 48,556 ties. The network is dense (0.31): the thirty most-cited
> authors are each co-cited with every other, so the corpus rests on a single integrated
> intellectual base rather than on separate schools. To map it we normalise each tie by
> the geometric mean of the two authors' citing counts (cosine; van Eck and Waltman 2009)
> and draw, for the 28 most-cited authors, each author's three strongest normalised ties.
> We summarise an author's position by Freeman's (1979) degree centrality, the share of
> the other authors with whom the author is co-cited at least once. In a network this dense
> the measure saturates at the top, so the ranking of the most-cited authors is close to
> their citation ranking; we report this as a finding rather than a nuisance. As a check we
> also compute normalised strength, the sum of an author's cosine-normalised ties (Barrat et
> al. 2004; Opsahl et al. 2010), which selects the same twenty authors. Because [focal
> author] authored 39 of the source publications, we rebuild the network from the 53 he did
> not author and recompute every measure; he keeps the first rank by degree and is second,
> behind Ostrom, by normalised strength. Path-based measures such as betweenness are not
> reported: in a network this dense they reduce to noisy restatements of degree, and on the
> raw citation graph, which is one hop deep by construction, they would measure our
> sampling design rather than the literature.

Adjust the counts to the notebook output of the day the figures are finalised.

---

## References

Barrat, A., Barthélemy, M., Pastor-Satorras, R., and Vespignani, A. (2004). The
architecture of complex weighted networks. *Proceedings of the National Academy of
Sciences* 101(11), 3747–3752.

Blondel, V. D., Guillaume, J.-L., Lambiotte, R., and Lefebvre, E. (2008). Fast unfolding of
communities in large networks. *Journal of Statistical Mechanics: Theory and Experiment*,
P10008.

Bonacich, P. (1972). Factoring and weighting approaches to status scores and clique
identification. *Journal of Mathematical Sociology* 2(1), 113–120.

Crane, D. (1972). *Invisible Colleges: Diffusion of Knowledge in Scientific Communities*.
University of Chicago Press.

Freeman, L. C. (1979). Centrality in social networks: Conceptual clarification. *Social
Networks* 1(3), 215–239.

Kessler, M. M. (1963). Bibliographic coupling between scientific papers. *American
Documentation* 14(1), 10–25.

McCain, K. W. (1990). Mapping authors in intellectual space: A technical overview.
*Journal of the American Society for Information Science* 41(6), 433–443.

Newman, M. E. J. (2006). Modularity and community structure in networks. *Proceedings of
the National Academy of Sciences* 103(23), 8577–8582.

Opsahl, T., Agneessens, F., and Skvoretz, J. (2010). Node centrality in weighted networks:
Generalizing degree and shortest paths. *Social Networks* 32(3), 245–251.

Persson, O. (1994). The intellectual base and research fronts of JASIS 1986–1990. *Journal
of the American Society for Information Science* 45(1), 31–38.

Price, D. J. de Solla (1965). Networks of scientific papers. *Science* 149(3683), 510–515.

Salton, G., and McGill, M. J. (1983). *Introduction to Modern Information Retrieval*.
McGraw-Hill.

Small, H. (1973). Co-citation in the scientific literature: A new measure of the
relationship between two documents. *Journal of the American Society for Information
Science* 24(4), 265–269.

van Eck, N. J., and Waltman, L. (2009). How to normalize cooccurrence data? An analysis of
some well-known similarity measures. *Journal of the American Society for Information
Science and Technology* 60(8), 1635–1651.

White, H. D., and Griffith, B. C. (1981). Author cocitation: A literature measure of
intellectual structure. *Journal of the American Society for Information Science* 32(3),
163–171.

White, H. D., and McCain, K. W. (1998). Visualizing a discipline: An author co-citation
analysis of information science, 1972–1995. *Journal of the American Society for
Information Science* 49(4), 327–355.

Zhao, D., and Strotmann, A. (2008). Comparing all-author and first-author co-citation
analyses of information science. *Journal of Informetrics* 2(3), 229–239.
