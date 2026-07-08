# Differentiation-Fix — gemessene Ergebnisse (2026-07-07/08)

**Branch:** `feature/combinatorial-landscape` · **Config des Runs:** 4 Driving-Achsen, CIB absolute +
dissent-preserving (`CIB_DISSENT_PRESERVING=1`), gpt-5.4 gepoolt über 4 Endpoints. Nichts committed.

## 1. Was implementiert wurde
- **Parts 1–3** (Plan): `trends.py` dimension-bucketed Extraction · `merge.py` cross-dimension Merge-Guard ·
  `cib.py` dissent-preserving Aggregation (Flag `CIB_DISSENT_PRESERVING`).
- **4. Driving-Achse `technological`** (Enum + Anker + `_DRIVING_DIMENSIONS` + Test). KB-verifiziert:
  406 Orphan-Chunks echten AI/ML-Contents (arXiv), kein Regulatory-Bleed.
- **Infra/Model-Fix:** `AZURE_OPENAI_CHAT_DEPLOYMENT` gpt-4.1-mini → **gpt-5.4**; `llm._get_client`
  pooled jetzt nach dem *effektiven* Model → General-Chat round-robinnt über alle 4 Endpoints.

## 2. Pipeline-Run — gemessen vs. Baseline
| Metrik | Baseline | Nach Fix |
|---|---|---|
| Driving axes | 1 | **11** |
| Driving-Dimensionen | 1 (regulatory) | **4** (reg 3 · market 4 · geo 2 · tech 2) |
| Response-Achsen (Tech-BOM) | 18 | 24 (hw 19 · sw 5) |
| CIB Negativ-Anteil | ~0–11 % (Warnung) | **22 %** (Weimer-Jehle 20–30 %-Band, Warnung weg) |
| Fixpunkte | — | 421 → 6 Szenario-Seeds |
| Manifestations-Zeit | 789 s | **64 s** (gpt-5.4 gepoolt) |
| 429-Errors | Storm | **0** |
| MCDA impact / probability | flach | **weiterhin flach** (alle 7.0 / 6.0) |
| grounding_strength | alle „moderate" | alle „moderate" |
| Szenario-Narrative Cosine-Ähnlichkeit | — | 0.885–0.949 (mean **0.92**) |
| Kombinatorische Silhouette | 0.076 | **0.067** (unverändert, < 0.25-Floor) |

## 3. Engine-Soundness-Validierung (`scripts/validate_engine_soundness.py` → `data/outputs/engine_validation.json`)
Drei Felder durch **denselben** Struktur-Test (`structure.analyze`, Null-Modell-Vergleich):

| Feld | Verdict | Silhouette | PC1 | eff_dim | z(silhouette) |
|---|---|---|---|---|---|
| **Positiv-Kontrolle** (gekoppelt S=3) | **usable structure** | **0.721** | 0.611 | 2.53 | **8.6** |
| **Negativ-Kontrolle** (ungekoppelt S=0) | ≈ uniform random | 0.224 | 0.151 | 7.83 | −0.69 |
| **Echtes 4-Achsen-Spektrum** | ≈ uniform random | **0.067** | 0.058 | 29.99 | 1.4 |

**Interpretation:** Die Engine findet nachweislich saubere Cluster (Silhouette 0.72, z=8.6), *wenn*
echte Kopplung vorliegt, und meldet ehrlich „uniform random", wenn nicht. Unser Spektrum-Feld matcht
die **Negativ-Kontrolle** (0.067, z=1.4 = über Null, aber nicht signifikant). → Der flache Wert ist ein
**Kopplungs-/Korpus-Defizit, kein Engine-Defekt.** Format-passend zu unserer (vereinfachten,
driver-level ordinalen) CIB — siehe Scope-Hinweis unten.

## 4. Ehrliche Schlussfolgerung
- **Root-Cause auf Input-Ebene GEFIXT & beweisbar:** Achsen-Anzahl 1→11, 4 Dimensionen, CIB-Bias
  89 %→22 % negativ. Infra sauber (gpt-5.4 gepoolt, kein 429-Storm, ~2× schneller).
- **Struktureller Output NICHT verbessert:** Silhouette 0.067 ≈ 0.076, Narrative 0.92, MCDA flach.
  Die Achsen-*Anzahl* stieg, aber die Achsen sind **nicht unabhängig genug** — der schiefe Korpus
  lässt market/geo/tech-Treiber regulatory-gefärbten Content tragen → korrelierte CIB-Kopplungen →
  Config-Space rekollabiert zum Kontinuum.
- **Der bindende Constraint ist jetzt der KORPUS** (`corpus_enrichment_plan.md`), plus ein **separater**
  MCDA-Eval-Kompressions-Hebel (Score-Anchoring in `SCENARIO_ASSESS`).
- **Präsentations-Verkaufspunkt:** Die Engine misst das Input-Property korrekt und **halluziniert keine
  Cluster** — Integrität als Feature, extern belegt durch die 3-Wege-Validierung.

## Scope-Hinweis: kein externer CIB-Benchmark möglich
Unsere Engine nutzt eine **vereinfachte, driver-level ordinale CIB** (`support_score`,
`morphological.py`), **nicht** Weimer-Jehles volle state×state-Judgment-Matrix. Eine publizierte
CIB-Matrix (state-level) passt daher nicht 1:1 rein. Die synthetische Positiv-Kontrolle oben ist das
format-passende, deterministische, offline-reproduzierbare Äquivalent zum Gold-Standard-Check.

## 5. Corpus-Enrichment (2026-07-08) — Cap + gezielte Quellen
**Was:** (a) **Source-Cap** in `trends.py` (`MAX_CHUNKS_PER_SOURCE=150`) bricht die Mega-Doc-Dominanz;
(b) **arXiv** dimensions-gezielt (`scripts/enrich_corpus.py`): market/geo + massiv technological (RIS, SDR/FPGA,
RL, LLM-für-Wireless, Edge, mmWave-MIMO, Quantum); (c) **Report-PDFs** (`scripts/enrich_corpus_reports.py`):
OECD/GSMA (market) + NTIA/DoD-EMS/Brookings (geopolitical). KB 2875 → **3905 Chunks** (+1030).

**Effekt (Full-Run auf angereichertem Korpus, Cap ON):**
- Source-Cap: Orphans 3375 → **2186** (Mega-Doc-Überhang gekappt).
- Buckets (post-cap): market 1155, technological 668, regulatory 429, **geopolitical 169**.
- Treiber-Content: market hat jetzt *echte* Ökonomie-Treiber („Economic-value-driven spectrum reallocation",
  „Spectrum pricing and licence obligation reform"); technological AI/software; geopolitical **weiterhin nur 1**
  ITU-flavored Treiber.
- CIB Negativ-Anteil: 12.6 % (dissent-preserving; niedriger als die 22 % im Vor-Enrichment-Run).
- MCDA: leichter Spread (impact 7–8, probability 5–6) vs. vorher flach (7/6). actionability/risk noch flach.

**Kombinatorische Struktur — der Kern-Befund:**
| Run | Silhouette | z(silhouette) | eff_dim | Verdict |
|---|---|---|---|---|
| Baseline | 0.076 | — | — | continuum |
| 4-Achsen (vor Enrichment) | 0.067 | 1.4 (n.s.) | 29.99 | ≈ uniform random |
| **Angereichert** | **0.074** | **3.55** (signifikant) | 29.66 | above null, but no usable clusters |

→ Silhouette bleibt < 0.25-Floor (keine sauberen Cluster), **aber z-Score 1.4 → 3.55**: das Feld ist jetzt
*statistisch signifikant über dem Zufall*, wo es vorher zufalls-ununterscheidbar war. Enrichment hat **echte,
messbare Struktur** hinzugefügt — nur noch nicht genug für Archetyp-Cluster.

**Verbleibende Engpässe (nächste Hebel):**
1. **Geopolitical bleibt 1 Treiber** — Bucket zu klein (169) + Anker („international coordination") zieht ITU-Content;
   die DoD/Brookings-National-Security-Chunks sind Minderheit. → mehr/gezieltere geo-Quellen ODER Anker schärfen.
2. **Extraktions-Granularität**: `k_dim` klein (tech=3) → 668 Chunks über RIS/FPGA/Quantum kollabieren zu 3×
   „AI dynamic spectrum sharing". Minderheiten-Themen bekommen keinen eigenen Treiber. → k_dim erhöhen.
3. **MCDA-Eval-Kompression** (separater Hebel, Score-Anchoring).
4. **Bug**: gpt-5.4-Requests hängen gelegentlich am Ende von CIB/Narrative-Phasen; lösen sich erst per SDK-600s-Timeout
   (~8 min Verlust/Run). → Client-`timeout=` in `src/llm.py` setzen.

## 6. Granularität + Hang-Fix (2026-07-08)
**Was:** (a) `trends.py` k_dim jetzt **pro Bucket nach dessen Richness** (`bucket_size / TARGET_CHUNKS_PER_DRIVER`,
Cap `MAX_DRIVERS_PER_DIM=6`) statt globalem Budget → reiche Buckets liefern distinkte Sub-Themen-Treiber.
(b) `llm.py`: Client-`timeout=120s` → hängende gpt-5.4-Requests scheitern schnell + retryen (statt 600s-Stall).

**Effekt:**
- Trend-Treiber 12 → **19**; technological liefert jetzt DISTINKTE Achsen: „6G reconfigurable intelligent
  surfaces (RIS)", „Privacy-preserving edge AI", „5G softwarization" statt 3× „AI dynamic spectrum sharing". ✓
- Merge: **18 driving-Achsen** (war 11) über 4 Dimensionen (reg 5, market 5, geo 2, tech 6).
- CIB in **517s** durch (vs. ~1000s mit Hang) — Hang-Fix bestätigt. CIB-Negativ **24.2 %** (zurück im 20–30 %-Band).
- Consistency: **429 Fixpunkte**.

**Kombinatorische Struktur:** Silhouette **0.071** (z 2.87) — weiter < 0.25-Floor, „above null, no usable clusters".
MCDA weiter flach (impact 7–8, Rest flach).

**Der entscheidende Struktur-Befund:** Die evidence-gewichtete `SUBSET_N=14`-Selektion für CIB/Szenarien pickt
jetzt **14 Treiber, ALLE driving** (market 5, tech 6, reg 2, geo 1; **0 Response/BOM**). Das Feld ist damit **nicht
mehr das 1-D-degenerierte Kontinuum vom Baseline**, sondern **isotrop** (eff_dim ~29, pc1 ~0.06): 14 diverse,
weitgehend UNABHÄNGIGE driving-Achsen. Deshalb keine Cluster — **Cluster bräuchten antagonistische Blöcke**
(Positiv-Kontrolle: ±3-Kopplung → Silhouette 0.72). Diese Domäne hat *unabhängige, nicht gegensätzliche*
Unsicherheiten → 429 diverse Szenarien statt 3–4 Archetypen. Faithfully gemessen, kein Engine-Artefakt.

**Offene Entscheidung:** Die 14er-Selektion droppt jetzt ALLE Response/BOM-Achsen. Für die morphologische
Methode evtl. einen driving+response-**Mix** erzwingen (driving spannt Szenarien, response = Outcomes) statt
rein evidence-gewichtet. + weiterhin: geo-Schwäche, MCDA-Score-Anchoring.

## Enrichment-Skripte (reproduzierbar)
- `scripts/enrich_corpus.py` — dimensions-gezielte arXiv-Ingestion (TREND-Pool, idempotent).
- `scripts/enrich_corpus_reports.py` — Download + Ingestion kuratierter Report-PDFs (10 Quellen, verifiziert).
- Source-Cap: `trends.py` `MAX_CHUNKS_PER_SOURCE` / `run(max_chunks_per_source=...)`.

## Reproduzieren
- Pipeline: `CIB_DISSENT_PRESERVING=1 uv run python run_full.py --skip-arxiv`
- Silhouette (kombinatorisch): `uv run python run_combinatorial.py --skip-rag --skip-eval`
- Engine-Validierung: `uv run python scripts/validate_engine_soundness.py`
- Logs/Artefakte: `data/outputs/_e2e_fix.log`, `_combi_structure.log`, `engine_validation.json`
