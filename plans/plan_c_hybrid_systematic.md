# Plan C: Hybrid — Meet in the Middle

## Philosophie
Zwei Perspektiven gleichzeitig: Bottom-Up (BOM) und Top-Down (Trends). Wo sie sich treffen, sind die wirklich relevanten Tech Drivers. Das Beste aus beiden Welten, aber aufwändiger.

## Pipeline

### 1. Knowledge Base (zwei Pools)
- **KB-Product**: R&S Produktseiten, Datenblätter, Applikationsberichte (wie Plan A)
- **KB-Trends**: Forschungspapers, Trend Reports, Regulatorische Entwicklungen, Tech Magazines (wie Plan B)
- Beide in ChromaDB, aber mit Pool-Tag (product vs. trend) für gezielte Retrieval

### 2. Tech Driver Identification: Dual-Source
- **Bottom-Up Arm**: Iterative BOM Decomposition (wie Plan A)
  - Produkt → Subsystem → Komponente → Grundtechnologie
  - Ergebnis: Liste von "Product-grounded Drivers"
- **Top-Down Arm**: Trend Scanning (wie Plan B, aber fokussierter)
  - Nur Trends scannen die Relevanz für RF/Spectrum/Monitoring haben
  - Ergebnis: Liste von "Trend-derived Drivers"
- **Merge**: LLM mapped die beiden Listen aufeinander:
  - Match: BOM-Driver "GaN Transistors" ↔ Trend "Wide-bandgap Semiconductors" → Hohe Konfidenz
  - Nur Bottom-Up: "PCB Substrat" → wahrscheinlich kein strategischer Driver
  - Nur Top-Down: "Quantum RF Sensing" → Disruptionspotenzial, noch nicht in Produkten
  - Output: Unified Driver List mit Herkunfts-Tag und Konfidenz

### 3. Tech Driver Evaluation: Gewichtete CIB
- CIB Cross-Impact-Matrix (wie Plan A)
- Zusätzlich: jeder Driver bekommt Gewichte aus dem Merge:
  - Beide Quellen → höheres Gewicht (validiert)
  - Nur Trend → mittleres Gewicht (Disruptionspotenzial)
  - Nur BOM → niedrigeres Gewicht (inkrementell)
- CIB-Konsistenzprüfung für Szenario-Skelette

### 4. Scenario Generation: Structured + Narrative
- CIB-konsistente Skelette (wie Plan A)
- Narrative Anreicherung mit breiterem Kontext (wie Plan B)
- Zwei Szenario-Typen:
  - **Evolutionäre Szenarien**: basierend auf BOM-Drivers (wie entwickeln sich heutige Produkte weiter?)
  - **Disruptive Szenarien**: basierend auf Trend-only-Drivers (was passiert wenn etwas Neues kommt?)

### 5. Analysis: Multi-Kriterien
- Impact + Probability (wie Plan A)
- Actionability + Preparedness (wie Plan B)
- Zusätzlich: "Confidence Score" basierend auf Quellenlage
  - Szenario basiert auf validierten Drivers (beide Quellen) → höhere Confidence
  - Szenario basiert auf Trend-only Drivers → niedrigere Confidence, aber potentiell höherer Impact
- Output: 2D-Matrix (Impact vs. Probability) + Confidence-Overlay + Traceability

## Traceability
Tiefste Traceability von allen drei Plänen: jeder Driver hat zwei Herkunftsketten (BOM + Trend), jede CIB-Bewertung hat Begründung, jedes Szenario referenziert seine Driver-Ketten. Merge-Entscheidungen sind dokumentiert.

## Stärken
- Comprehensive: fängt sowohl inkrementelle als auch disruptive Entwicklungen ein
- Validierung durch zwei unabhängige Quellen
- Confidence Scoring — man weiß was gut belegt ist und was spekulativ
- Erfüllt Andrews BOM-Anforderung UND geht darüber hinaus
- Methodisch am stärksten (für Präsentation/Report)

## Schwächen
- Höchste Komplexität (zwei parallele Pipelines + Merge)
- Merge-Schritt ist nicht-trivial und potentiell fehleranfällig
- Mehr Quellen nötig (braucht gute Trend-Quellen zusätzlich zu Produktdaten)
- Risiko von Over-Engineering für einen PoC
- Deutlich mehr LLM-Calls und damit Kosten/Zeit

## Komplexität
Hoch. Jede Komponente ist einzeln machbar, aber die Integration (besonders der Merge) ist anspruchsvoll. Für einen PoC eventuell zu viel — könnte aber als Zielarchitektur dienen, während der PoC mit Plan A startet.
