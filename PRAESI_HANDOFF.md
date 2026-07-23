# Präsi-Handoff — Final-Präsentation Mo 2026-07-13

Alles, was für die Präsi gebaut wurde. Stand: Sa 2026-07-12, Branch `feature/combinatorial-landscape`,
**alles UNCOMMITTED**. Geschrieben als Wiedereinstiegs-Doku nach Context-Clear.

---

## 1. Das Konzept

15-Minuten-Präsi läuft **komplett im Dashboard** — keine PowerPoint. Eigener Präsentationsmodus
unter **`/present`** (Sidebar-Eintrag „Present"): 12 Szenen im Design-System des Dashboards,
mit Pfeiltasten durchblätterbar, alle Visuals aus den echten Pipeline-Artefakten des finalen
Laufs vom 08.07. Drei inhaltliche Kapitel:

1. **Journey** — EIN echter Treiber durch alle Pipeline-Stationen (verständlich machen)
2. **Validierung** — Null-Modell + synthetischer CIB-Kontrolltest („Metalldetektor", Rigor)
3. **Verbesserung** — messbare Hebel + Linsen-Wechsel (Ergebnisverbesserung)

### Bedienung
- Start: `uv run uvicorn web.app:app --port 8000` → `http://127.0.0.1:8000/present`
- **→ / Space / PageDown** = nächster Step/Szene · **←/PageUp** = zurück · **Esc** = Dashboard
  · **Home** = Anfang · Dots unten = Szenen-Direktsprung · Presenter-Clicker funktioniert
- Escape funktioniert IMMER (auch wenn der 3D-Slider Fokus hat — bewusst so gefixt)

### Timing-Anker (15 min)
Hook 1 min → Journey (jetzt 7 Szenen inkl. NEUER Mechanismus-Szene) ~6,5 min → Validierung 3 min
→ Verbesserung (3 Szenen) 3 min → Closing 1,5 min. Die neue Station 2 kostet ~1 min — bei
Zeitdruck in Journey-Szenen 4–6 (Futures/Coupling) straffen. Dashboard-Live-Seiten
(Scenarios/Traceability!) = Q&A-Munition via Esc + Sidebar.

---

## 2. Die 13 Szenen (`web/frontend/src/present/scenes/`)

Registry + Reihenfolge: `scenes/index.js`. Kontrakt: jede Szene exportiert `STEPS` (Reveal-Steps)
+ Default-Komponente `({ data, step })`; `data` = das komplette `/api/present`-Bundle.

Entschieden 12.07.: Station 2 = Punktwolken-Variante; die Funnel-Alternative (JourneyFunnelScene)
wurde gelöscht. In der Mechanismus-Szene wird „BOM" bewusst NICHT benannt (Formulierung:
„the product's own technology") — der Begriff fällt erst gar nicht, die Chips-Legende in Station 3
sagt nur „from the component tree".

| # | Szene | Steps | Inhalt |
|---|---|---|---|
| 1 | HookScene | 2 | Zahlenkette 70 Quellen → 14 Faktoren → 268.435.456 → 120 → 5, animierte Count-Ups |
| 2 | JourneySourceScene | 2 | 8 echte Chunk-Ausschnitte (OECD/RSPG/ENISA, serverseitig gereinigt) → Treiberkarte: 416 Chunks · 14 Quellen |
| 3 | **JourneyMechanismScene (NEU 12.07.)** | 4 | Extraktions-Mechanismus als echte Punktwolke: 601 echte Chunk-Punkte (PCA über Chroma-Embeddings) → Coverage-Fade (2.424 Orphans) → 4 Dimensions-Farben (432/1156/168/668) → Cluster ziehen sich zusammen, 19 Treiber, unser Cluster pulsiert |
| 4 | JourneyExtractionScene | 2 | 41 Treiber-Chips (24 BOM sky / 17 Trend violet) → 14 selektierte leuchten, unser Treiber pulsiert |
| 5 | JourneyFuturesScene | 2 | 4 Manifestations-Karten (optimistisch→pessimistisch) → „= 268,435,456"-Stempel |
| 6 | JourneyCouplingScene | 2 | Radiales CIB-Netz um den Treiber; **Klick auf Kante → 5 Persona-Votes mit echten Begründungen**; +2/−2-Paar pulsiert amber („preserved dissent"); negative Kanten gestrichelt |
| 7 | JourneyFieldScene | 3 | 120 Punkte bauen sich auf → Farb-Split nach Treiber-Wahl (47/35/21/17) → Verteilungs-Panel. **Seit 12.07. im Cluster-Raum (`ox/oy`, ordinal UMAP)** — Layout anders als frühere Proben! |
| 8 | JourneyArchetypeScene | 2 | Feld färbt nach Archetypen → 5 Haltungs-Karten (3 klar: 8/15, 10/20, 7/12 · 2 ehrliche Ties: „deliberately undecided"). **Cluster-Raum: 5 Inseln mit Hüllen, Continuum gedimmt** (endlich sichtbare Cluster statt Blob) |
| 9 | ValidationScene | 4 | Metalldetektor-Triptychon: 3 echte Punktwolken (gekoppelt/ungekoppelt/real), je mit **Input-CIB-Matrix-Thumbnail** (vorgefertigte 8×8-Block-Matrix · genullte Matrix · echte 14×14) — „same engine, three inputs"; Stempel-Verdicts (0,72/z8,6 · 0,22/z−0,7 · 0,067/z1,4), z-Skalen mit Signifikanzlinie, Takeaway + 29%-Weimer-Jehle-Chip (live aus cib_state). Matrix-Daten: `standard_matrix_signs` in engine_validation_fields.json (13.07. ergänzt) |
| 10 | ImprovementLeversScene | 2 | 3 Hebel-Karten animieren: CIB 0→**29 %** mit ECHTER 14×14-Matrix (53 negative Zellen flippen gestaffelt rot) + Band-Gauge; z 1,4→3,55 (kreuzt Signifikanz) + Vorher/Nachher-Feld-Thumbnails; Chunks 2.875→3.905 |
| 11 | LensMorphScene | 4 | Dieselben 120 Punkte, 4 Linsen-Buttons, Silhouette-Thermometer 0,07→0,38 kreuzt 0,25-Floor mit Blitz; Cluster-Farben = Majority-Archetyp (konsistent mit Szene 8+12); Punchline erst am letzten Deck-Step |
| 12 | Slice3DScene | 2 | Rotierbarer 3D-Raum, **Default = Cluster-Raum (UMAP 1–3 ordinal, Archetyp-Inseln)**; Toggle oben rechts = PCA-Rückweg für Q&A („Strategie-Karte mit interpretierbaren Achsen"). Slab-Slider (rAF-throttled) sliced entlang der Achse der aktiven Projektion (UMAP 1 bzw. PC1), rechts: Bewohner + Rezept-Streifen |
| 13 | ClosingScene | 2 | Pipeline-Blöcke (OHNE Namen — Team-Bylines am 12.07. auf Pauls Wunsch entfernt, Konstante heißt jetzt `STAGES`) + Ketten-Recap + „Swap the KB: same pipeline" |

**Zahlen-Narration Station 2↔3**: Station 2 spricht über den TREND-Pool in Chroma (3.693, inkl.
arXiv-Enrichment; 3.905 gesamt = 212 product + 3.693 trend), Station 3-Titel nutzt `kb_state`
(2.875 = Korpus VOR Enrichment). Beides echt — bei Rückfrage: „2.875 Basis-Korpus, +1.030
arXiv-Enrichment = 3.905, davon 3.693 im Trend-Pool."

Shell: `web/frontend/src/present/PresentShell.jsx` (Fullscreen, Keyboard, Dots, Fehler-/Lade-Zustände).
Gemeinsames Chrome: `scenes/SlideFrame.jsx`. Route in `App.jsx` (ohne Shell-Chrome, mit ErrorBoundary).

---

## 3. Daten-Ebene

### `/api/present` (web/app.py)
Ein gecachtes Bundle (~117 KB), Cache invalidiert über mtime von `landscape_state_combi.json`.
Beispiel-Treiber: `_PRESENT_DRIVER_ID = "f33ab61e5a83"` („Shift to dynamic shared and harmonised
spectrum access"). Enthält: `meta` (Zahlenkette) · `journey` (Treiber, gereinigte chunk_previews,
41 Treiber, 4 Manifestationen, 13 Kopplungen MIT `persona_scores` [5 Objekte mit promoting/
inhibiting/net + Reasoning], Verteilung, `scenario_manif`-Map, Archetyp-Haltungen mit Tie-Flag) ·
`field` (120 Punkte x/y/cx/cy/cz/archetype) · `lenses` (Summary + per-Punkt-Labels + floor) ·
`validation` (synthetische Felder + Stats) · `improvement` (Hebel-Zahlen, Lens-Progression) ·
`parcoords`. Preview-Reinigung: PUA-Glyphen raus, Start am ersten Prosa-Satz (Seitenköpfe weg).

### `scripts/prepare_present_data.py` (einmalig gelaufen, idempotent)
1. **PC3 (`cz`)** an alle 120 Punkte in `landscape_state_combi.json` (gleiche Geometrie/Vorzeichen-
   Konvention wie cx/cy)
2. **Per-Punkt-Lens-Labels** in `structure.lens_labels` (Silhouetten exakt reproduziert:
   0,074 / 0,17 / 0,3365 / 0,3799)
3. **`data/outputs/engine_validation_fields.json`**: 2D-Punktwolken der synthetischen Kontrollfelder
   (gekoppelt S=3: 18 Configs, PC1 61 % · ungekoppelt S=0: 150 Configs, isotrop)

`scripts/backfill_projection.py` (früher gelaufen): parcoords/axes/structure-Verdict in
`landscape_state_combi.json` zurückgeholt (Backup: `.json.bak`).

### `scripts/backfill_cluster_space.py` (anderer Claude, 12.07.)
Stampt `ox/oy` (2D) + `ox3/oy3/oz3` (3D) in `landscape_state_combi.json` — UMAP-Fits der
ORDINALEN Matrix mit den Parametern des Archetyp-Clusterings (n_neighbors=15, euklidisch,
seed 42). Das ist der Raum, in dem HDBSCAN die Archetypen wirklich gefunden hat; Stationen 6/7
und die 3D-Szene zeigen ihn seit 12.07. als Default (Fallback auf x/y bzw. PCA, wenn Felder
fehlen). ⚠️ Nach frischem Pipeline-Lauf NEU ausführen (nicht in run_full.py verdrahtet).
**Ehrlicher Caveat für Q&A**: eigene 2D/3D-Fits desselben Raums, NICHT das 5D-Embedding selbst
(UMAP-Komponenten sind ungeordnet) — einzelne graue Continuum-Punkte in den Insel-Kernen sind
erwartbar, kein Bug. Folien-Zahlen: Archetypen 20/20/15/13/12 + 40 Continuum (33 %, bewusst
ehrlich), HDBSCAN-Silhouette 0,3799. Vergleichs-Screenshotquelle:
`viz_preview/cluster_space_preview.html`.

### `scripts/prepare_present_extraction.py` (NEU 12.07., einmalig gelaufen, idempotent)
Füttert die neuen Mechanismus-Szenen → `data/outputs/present_extraction.json`, im Bundle als
`extraction` (fehlt die Datei, wird `extraction: null` — Deck stirbt nicht). KEINE Reproduktion,
keine LLM/Embed-Calls: Cluster-Mitgliedschaften kommen direkt aus `trend_state.json`
(`source_chunk_ids` je Trend-Treiber = exakt die KMeans-Cluster-Member des finalen Laufs), Layout
= PCA über die in Chroma persistierten Chunk-Embeddings, Sample 601 Punkte (150 covered + 451
Orphans, stratifiziert je Cluster, seed 42). Alle Konsistenz-Checks gegen `trend_state.metadata`
grün (3.693 Chunks / 2.424 Orphans / Buckets 432·1156·168·668 / 19 Cluster). Erster Versuch über
Azure-Anker-Re-Embedding scheiterte übrigens: Azure-Embeddings sind nicht bit-stabil →
Bucket-Grenzen verschoben. Artefakt-basiert ist strenger „nothing is invented".

---

## 4. Faktengecheckte Zahlen (gegen Artefakte verifiziert — slide-sicher)

- Treiber: **416 Quell-Chunks aus 14 Quellen** (239 resolven in aktueller KB), Top-Quelle OECD
  „Road to 5G" (76). ⚠️ NICHT „13 Chunks" (alter Claude-Vorschlag war falsch)
- Dimension: **market** (⚠️ nicht regulatory), Origin trend, driving axis
- Extraktion: 41 unified (24 BOM + 17 Trend) → **Top-14** via `select_top_drivers`
  (evidenzgewichtet-stratifiziert; `SUBSET_N=14` in `scripts/run_subset.py`, per `--n-drivers`
  überschreibbar; die 41 sind KB-abhängig, die 14 sind Pipeline-Default)
- CIB: 182 Judgments, **29 % inhibiting** (53/182, seit 13.07. LIVE aus cib_state berechnet —
  die früher zitierten 22 % waren die historische Fix-Messung; beides im
  Weimer-Jehle-Band 20–30 %), Kopplungen des Treibers:
  +2 → „Regulatory shift to dynamic shared-spectrum enforcement", −1 → „affordable licensing";
  asymmetrisches Paar +2/−2 mit „International shift toward dynamic and shared spectrum governance"
- Verteilung über 120 Szenarien: **47 Fragmented / 35 Automated / 21 Cross-border / 17 Hot-spot**
- Archetyp-Haltungen: State-Orchestrated → Automated **10/20**, Certified Patchwork → Fragmented
  **8/15**, Algorithmic Commons → Fragmented **7/12**; ⚠️ Policing (4/4/4) und Federated (6/6)
  sind ECHTE Gleichstände — als „deliberately undecided" zeigen, nicht als Entscheidung
- Validierung: gekoppelt 0,72/z8,6 „usable" · ungekoppelt 0,22/z−0,7 „random" · real 0,067/z1,4
  „random" → Engine halluziniert nicht; Verbesserung: z 1,4→3,55, CIB-Bias 0→29 %, Korpus
  2.875→3.905 Chunks, Linsen 0,07→0,17→0,34→**0,38** (ordinal HDBSCAN → 5 Archetypen + 33 % Kontinuum)

---

## 5. Vorher schon erledigt (Kontext)

- **UI-Audit-Schwarm** (82 Agents): 62 bestätigte Findings, Plan in `ui_audit_fixplan.json`
- **Alle 15 Fix-Punkte umgesetzt** (Details in Memory `project_ui_demo_fixes.md`): ErrorBoundary,
  CIB-Crash, Fake-Zahlen auf PipelinePage raus (+2 neue Stages), /archetypes in Pfeilnavigation,
  Landscape-Money-Shot, Traceability ehrlich (19/53 resolved wird angezeigt), BOM-Highlight-Bug
  (27/27), Farbsystem vereinheitlicht (`archetypeColor` in `colors.js`)
- **Präsi-Bau**: 5 Szenen-Bauer-Agents parallel + 2 adversariale Review-Agents; alle kritischen
  Review-Findings gefixt (Escape-vor-Input-Guard, Slider-Blur+Throttle, Farbvertrag LensMorph,
  projektortaugliche Ordinal-Palette, Step-Rückwärts-Regressionen, Chunk-Preview-Junk)

## 6. Status + offene Punkte

**Gebaut & smoke-getestet:** aktuelles Bundle siehe `web/static/assets/` (Stand 12.07.), alle
Endpoints 200, `/present` in KB-Views registriert, Previews sauber, 120/120 Punkte mit cz.
Am 12.07. zusätzlich: alle Em-Dashes aus den sichtbaren Slide-Texten entfernt (Platzhalter „—"
für fehlende Werte bewusst belassen) + Team-Bylines aus ClosingScene raus.

**TODO vor Montag (Paul):**
1. ⚠️ **Visueller Durchklick** aller Szenen im Browser — Mechanismus/Closing sind per
   Screenshot verifiziert, Rest: Kanten-Klick Coupling, Linsen-Buttons, 3D-Slider
2. Nach JEDER Frontend-Änderung: `cd web/frontend && npm run build` (FastAPI serviert `web/static`!)
3. **Beamer-Probe**: unter 1080p können hohe Szenen scrollen statt passen (bekannt, akzeptiert)
4. **Committen** (kein Co-Authored-By!) — 30+ geänderte Dateien + present/-Verzeichnis + Skripte
6. Q&A-Antworten parat: „19 of 53 chunks resolved" = Korpus nach Runs angereichert, ehrlich
   angezeigt statt still gedroppt; MCDA-Rohscores flach = Differenzierung via TOPSIS (Caption
   steht auf StrategyPage)
7. **Methodology-Tab (NEU 13.07.)**: Sidebar „Methodology" = jede Methode mit Paper-Quelle
   (Zwicky 1969, Weimer-Jehle 2006, Sharma 2023, McInnes 2018, Campello 2013, Rousseeuw 1987,
   Saaty 1980, Hwang & Yoon 1981, Lewis 2020, Schwartz 1991 …) + „Why this way"-Begründung +
   eigene Pipeline-Figuren. Bei Literatur-/Methodik-Rückfragen: Esc → Methodology.

**Bewusst offen (post-demo):** stale chunk-ids echt heilen (final_analysis re-run), Lint-Altbestand,
Code-Splitting (5,4-MB-Chunk), Combi-Szenarien im Scenarios-Browser, Slice3D-Rezept-Tooltips
sichtbar statt hover-only.
