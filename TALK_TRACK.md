# Talk Track — Final-Präsi 13.07. (~14:10 + Puffer, 13 Szenen)

Regieanweisungen deutsch in [Klammern], Sprechtext englisch. → = Klick (Pfeiltaste/Clicker).
Nach der letzten Szene: Esc = Dashboard (Q&A). Literatur-Fragen → Methodology-Tab.

---

## 1 · Hook — 1:00
[Ruhig starten, Titel wirken lassen]
„How do you see 2035 coming — before your competitors do? That is the question Rohde & Schwarz
gave us, for one concrete product: a spectrum monitoring receiver."
→ [Zahlenkette läuft]
„Our answer is a pipeline. It reads 70 documents, distills them into 14 key factors, spans
268 million possible futures, keeps the 120 that are internally consistent, and names five
archetypes. In the next fifteen minutes I will walk you through it twice: once following a
single driver from a paragraph to a strategy, and once asking the harder question — can we
trust it?"
→

## 2 · Station 1: Source — 0:45
„Everything begins as text. These are real excerpts from the corpus: OECD, the EU Radio
Spectrum Policy Group, ENISA. No model has touched them yet."
→ [Treiberkarte zoomt rein]
„Out of this corpus one driver emerges: the shift to dynamic, shared and harmonised spectrum
access. It rests on 416 chunks from 14 sources. And that is the principle of the whole
pipeline: nothing is invented — every driver keeps its source IDs for life. We will follow
THIS driver through every station."
→

## 3 · Station 2: Mechanism (Punktwolke) — 1:15
„How does a driver like that get found? Every dot here is a real text chunk — the entire
trend corpus, 3,693 chunks, embedded as vectors."
→ [Coverage-Fade]
„First, a coverage check: everything the product itself already explains fades out. What
stays are 2,424 orphans — content the product does NOT cover. That gap is where external
drivers live."
→ [Dimensions-Farben]
„Each orphan is assigned to its driving dimension: regulatory, market, geopolitical,
technological."
→ [Cluster + Chips, unser Cluster pulsiert]
„Then we cluster inside each dimension, and one focused LLM call reads the five most central
chunks of each cluster and names the force behind them. Nineteen clusters, nineteen named
drivers — the pulsing one is ours. And note: no hardcoded search queries anywhere. The
knowledge base itself decides what a trend is."
→

## 4 · Station 3: Selection (41 Chips) — 0:45
„Together with 24 drivers from the product's own component tree we get 41 candidates."
→ [14 leuchten, unserer pulsiert]
„An evidence-weighted selection keeps the 14 best-supported ones as our scenario axes.
Our driver sails through — it carries the most evidence of all."
→

## 5 · Station 4: Futures — 0:40
„For every factor the pipeline drafts four futures, optimistic to pessimistic — again
grounded in the sources. For our driver they range from cross-border shared-spectrum
observatories down to hot-spot policing of sharing failures."
→ [268M-Stempel]
„Fourteen factors, four states each: 268 million possible futures. Most of them contradict
themselves. We need a filter."
→

## 6 · Station 5: CIB — 1:15
„The filter is Cross-Impact Balance — Weimer-Jehle, 2006. Five LLM expert personas — an
engineer, a regulator, a strategist, a researcher, a disruption analyst — score how every
future of our driver pushes or blocks every other driver."
[MAUS: die amber pulsierende Kante klicken — das +2/−2-Paar]
„And here is the part I want you to see: we keep their disagreement. Our driver promotes
this one — plus two — while it pushes back, minus two. The pipeline preserves that
contradiction. It is signal, not noise to average away."
→ [Stat-Leiste]
„In total: 182 judgments, 29 percent inhibiting — right inside the 20-to-30-percent band
Weimer-Jehle reports for real systems. LLMs are naturally too agreeable; the
dissent-preserving panel is what fixes that. Contradictory futures die here."
→

## 7 · Station 6: Field — 0:50
„What survives: 120 internally consistent scenarios out of 268 million. Every diamond is
one complete 14-factor future."
→ [Farb-Split]
„Colored by what each scenario assumes for OUR driver. No single future wins — but
fragmentation survives most often, 47 of 120."
→ [Verteilungs-Panel]
„That skew is honest: consistency leans pessimistic here. Worth knowing before you write
a strategy."
→

## 8 · Station 7: Archetypes — 0:50
„Same 120 scenarios — drawn in the space where the clustering actually runs. Five patterns
pop out as islands: five named archetypes, from an Algorithmic Spectrum Commons to a
State-Orchestrated Sharing Grid. The grey points are the honest continuum — 40 scenarios
that simply blend."
→ [Haltungs-Karten]
„Each archetype takes a stance on our driver. State-Orchestrated picks automated
enforcement, ten of twenty. And two archetypes genuinely refuse to decide — we show the tie
instead of faking a majority. Our OECD paragraph is now a defining trait of five futures,
still traceable by ID."
→

## 9 · Validation — 2:30 [WICHTIGSTE SZENE, langsam sprechen]
„Now the second walk: can we trust any of this? Before you search a beach with a metal
detector, you test the detector. It must beep on a coin — and stay silent on empty sand."
→ [Panel 1]
„The coin: a prefabricated ground-truth CIB — you can see the matrix — two blocks that
promote inside and inhibit across. Fed through the SAME engine, the detector beeps:
silhouette 0.72, z-score 8.6."
→ [Panel 2]
„Empty sand: the same field with the coupling zeroed out. The detector stays silent —
z minus 0.7."
→ [Panel 3 + Takeaway]
„The real spectrum field, on our first run: also silent. And that is the finding — this
engine does not hallucinate clusters. A flat result is a property of the data. So we fixed
the data — never the verdict."
→

## 10 · Improvement: 3 Hebel — 1:15
„Three levers, three measurements. We never touched the outputs; we fixed the inputs."
→ [Karten animieren]
„The dissent-preserving panel took the inhibiting share from zero to 29 percent — and this
is the real matrix, every red cell one judgment where the panel said no. The structure
signal rose from z 1.4 to 3.55 — across the significance line, and you can see the field
gain shape. And targeted enrichment grew the corpus from 2,875 to 3,905 chunks."
→

## 11 · Improvement: Linsen — 1:15
„And one lever costs nothing: the lens. Same 120 scenarios, identical coordinates."
→ → → [zügig durch die 4 Linsen]
„One-hot k-means: silhouette 0.07 — a blob. Ordinal encoding respects that our states are
ordered: 0.17. HDBSCAN, which may honestly leave points unassigned: 0.34. Ordinal plus
HDBSCAN: 0.38 — past the 0.25 floor."
→ [Punchline]
„The structure was always there. We changed the lens."
→

## 12 · 3D — 0:50
„The result space in three dimensions — shown in the space where the archetypes were found.
You can see the islands."
→ [EINMAL sliden, nicht spielen]
„And it is a working instrument, not a picture: slice anywhere, and you get the residents
of that slice and its dominant factor recipe. That is strategy raw material."
→

## 13 · Closing — 1:00
„So that is the pipeline: knowledge base, drivers, morphology and cross-impact, scenario
field, archetypes, strategy."
→ [Ketten-Recap]
„70 sources. 14 factors. 268 million futures. 120 consistent scenarios. Five archetypes.
Every step traceable by ID, from source chunk to strategy. And the real point: swap the
knowledge base — same pipeline, new map. Spectrum monitoring was only the test case.
Thank you."

---

## Q&A-Spickzettel
- **Esc** → Dashboard. Scenarios/Traceability = Beleg-Munition; **Methodology-Tab** = jede
  Methode mit Paper-Quelle + Warum.
- „Warum 2.875 hier, 3.693 da?" → 2.875 Basis-Korpus + 1.030 arXiv-Enrichment = 3.905 gesamt,
  davon 3.693 im Trend-Pool.
- „Graue Punkte in den Insel-Kernen?" → eigener 2D-Fit desselben ordinalen Raums, nicht das
  5D-Embedding selbst — erwartbar und ehrlich.
- „19 of 53 chunks resolved?" → Korpus nach den Runs angereichert; ehrlich angezeigt statt
  still gedroppt.
- 3D-Szene: Toggle oben rechts = PCA-Sicht („Strategie-Karte mit interpretierbaren Achsen").
