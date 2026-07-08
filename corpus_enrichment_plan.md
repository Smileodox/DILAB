# Corpus-Enrichment-Plan — gegensätzliche Driving-Quellen

**Date:** 2026-07-07 · **Branch:** `feature/combinatorial-landscape` · **Status:** Roadmap (nach dem Differentiation-Fix)

## Warum (Problem)
Der Differentiation-Fix hat den **Root-Cause auf der Treiber-Ebene** behoben (driving axes 1 → 11, 4 Dimensionen
regulatory/market/geopolitical/technological, CIB-Bias 89 %→22 % negativ). Die **End-to-End-Szenario-Differenzierung
bleibt aber begrenzt**, weil der Korpus thematisch schief ist:

- ~50 % der 2875 Chunks stammen aus **zwei deskriptiven Mega-Docs** (WRC-23 Final Acts + ITU-Handbuch).
- Forward-looking Policy nur ~10.5 %; 18/19 der ursprünglichen Treiber kamen aus dem 7.4 %-Produkt-Pool.
- Folge: Selbst die **market/geopolitical/technological**-Buckets surfacen regulatory-lastigen Content — die
  extrahierten Treiber heißen z.B. „Regulatory Mandates for Dynamic Spectrum Access" obwohl sie im market-Bucket sitzen.
- Messbar: die 6 Szenario-Narrative embedden bei **0.885–0.949 Cosine** (mean 0.92) → thematische Monokultur.

**Ziel:** *gegensätzliche* (opposed), nicht-regulatorische Driving-Quellen einspeisen, damit die 4 Driving-Dimensionen
**inhaltlich distinkt** werden — nicht nur im `dimension_type`-Stempel, sondern im tatsächlichen Chunk-Content. Das ist
der Hebel, um die 0.92-Homogenität zu brechen (der Treiber-Fix allein ist notwendig, aber nicht hinreichend).

## Wonach genau (Quell-Ziele pro Dimension)
Bewusst so gewählt, dass sie **Trade-offs artikulieren** (füttert zusätzlich die CIB-Dissent-Aggregation):

| Dimension | Gesuchter Content (nicht-regulatorisch) | Beispiel-Quelltypen |
|---|---|---|
| **market** | Nachfrage, Adoption, Preis, Wettbewerb, Capex | Analyst-/Marktreports (SDR-/Spectrum-Monitoring-Equipment-Markt, Telco-Capex), Industrie-Adoptionsstudien |
| **geopolitical** | Souveränität, Blocktensionen, Export-/Handelskontrollen, Defense-Doktrin | Nationale Spektrum-Positionen, ITU-R-Regionalblöcke, RF-/Halbleiter-Exportkontrollen, Sicherheits-/Defense-Papiere |
| **technological** | *externe* Tech-Push-Trends (schon ok via arXiv) | Halbleiter-Roadmaps, Edge-AI, Quantum-Sensing, 6G-**Tech**-Roadmaps (nicht Policy) |
| **Tension/Contra** | explizite Zielkonflikte | Privacy-vs-Surveillance, Cost-vs-Capability, Zentral-vs-Edge, Open-vs-Proprietär |

Der `technological`-Bucket ist bereits am gesündesten (406 Chunks echter AI/ML-Content aus dem arXiv-Ingester —
verifiziert 2026-07-07). Fokus also auf **market** und **geopolitical**, wo der Content am dünnsten/regulatory-verseucht ist.

## Wie (Mechanik — bestehende Muster wiederverwenden)
1. **arXiv-Ingester erweitern** (`src/pipeline/arxiv_ingest.py`): dimensions-gezielte Queries statt eines generischen
   Strings. Der Ingester hält bereits den **Traceability-Contract** (`source_id` + `year` in Metadaten) und mappt in die KB.
2. **PDF-/Report-Ingester** (neu, nach demselben Muster): Markt-/Geopolitik-Reports (PDF) → Chunks → **Pool `trend`**
   taggen (damit sie als Orphan-Kandidaten in die Driving-Extraktion fallen). Semantic Chunking wie bestehende Pipeline.
3. **Pool-Tagging:** neue Chunks in den `trend`-Pool (nicht `product`), damit sie über die Coverage-Gap-Logik als
   Orphans zu Driving-Treibern werden. `dimension_type` wird dann vom Bucketing gestempelt (kein manueller Eingriff).
4. **Domain-Agnostik wahren:** die *Methode* (gezielte Queries pro Driving-Dimension) ist generisch — **keine**
   spektrum-spezifischen Quellen hart in den Code. Quell-Listen in Config/CLI-Args, nicht in `src/`.

## Balance-Ziel
- Anteil der 2 Mega-Docs: **50 % → < 30 %**.
- market-/geopolitical-Bucket-Content: von „regulatory-flavored" → thematisch eigenständig
  (messbar: Top-Sources pro Bucket sind NICHT mehr WRC-23/ITU-Handbuch).

## Verifikation (nach Enrichment)
- **Bucket-Content-Distinktheit:** `/tmp/kb_tech_probe.py`-Muster auf alle 4 Anker anwenden → Top-`source_title`
  pro Bucket prüfen (regulatory-Bleed weg?).
- **Szenario-Homogenität:** Narrative-Embedding-Ähnlichkeit von **0.92 runter** (Ziel < 0.85).
- **Silhouette:** kombinatorische Struktur (`run_combinatorial.py`) — steigt sie Richtung 0.25-Floor?
- **CIB-Negativ-Anteil:** bleibt/steigt im 20–30 %-Band (mehr echte Trade-offs → mehr starke Negative).
- **Traceability (Andrew):** jeder neue Chunk trägt `source_id` + `year`; Provenienz bleibt prüfbar.

## Abgrenzung
- **Kein** Ersatz für den Score-Anchoring-Fix der MCDA-Kompression (separater Eval-Hebel).
- Enrichment ist **Roadmap**, nicht Deadline-kritisch für die Mon-Präsentation — dort wird es als *nächster Schritt*
  mit klarem Mechanismus und Balance-Ziel präsentiert (nicht als offener Punkt).
