# Plan A: Bottom-Up Rigorous

## Philosophie
Von den Produkten aus nach unten graben. Alles was wir über Tech Drivers wissen, leiten wir aus der realen Produktstruktur ab. Maximale Nachvollziehbarkeit, methodisch sauber.

## Pipeline

### 1. Knowledge Base
- Öffentliche R&S Produktseiten, Datenblätter, Applikationsberichte für Regulatory Frequency Monitoring
- Technische Papers zu Spectrum Monitoring (IEEE, ITU)
- RAG mit ChromaDB, jeder Chunk hat Source-Metadaten

### 2. Tech Driver Identification: Iterative BOM Decomposition
- Produkte Level für Level zerlegen (Produkt → Subsystem → Komponente → Technologie → Material)
- Jede Ebene ein fokussierter LLM-Call mit nur relevanten RAG-Chunks
- Am Ende: Blatt-Knoten klassifizieren — ist das ein Tech Driver (aktive Forschung, Entwicklungspotenzial) oder passiv (Kupferdraht)?

### 3. Tech Driver Evaluation: CIB (Cross-Impact-Bilanzanalyse)
- Für identifizierte Tech Drivers eine Cross-Impact-Matrix aufbauen
- LLM bewertet paarweise: "Wie beeinflusst Fortschritt in Driver A die Entwicklung von Driver B?" (Skala: -3 bis +3)
- Jede Bewertung mit Begründung + Source-Referenz
- CIB-Konsistenzalgorithmus: nur Kombinationen von Driver-Ausprägungen zulassen, die sich nicht widersprechen

### 4. Scenario Generation: Morphologische Analyse
- Für jeden Driver 3 Ausprägungen definieren: Durchbruch / Stetiger Fortschritt / Stagnation
- CIB-konsistente Kombinationen als Szenario-Skelette
- LLM reichert jedes Skelett mit Narrativ an ("Ein Tag im Leben...")
- Jedes Szenario ist direkt rückverfolgbar auf Driver-Ausprägungen und deren Quellen

### 5. Analysis: Strukturierte Bewertung
- Impact-Bewertung: Wie stark verändert das Szenario die Produktdomäne? (1-10)
- Probability: Aggregiert aus den einzelnen Driver-Wahrscheinlichkeiten
- Robustness: Wie sensitiv ist das Szenario gegenüber Änderungen einzelner Driver?
- Output: Impact vs. Probability Matrix + Traceability-Report

## Traceability
Lückenlos: Quelle → Chunk → BOM-Knoten → Tech Driver → CIB-Bewertung → Szenario-Skelett → Narrativ → Assessment. Jeder Schritt referenziert seine Inputs.

## Stärken
- Höchste Nachvollziehbarkeit (jede Aussage bis zur Quelle rückverfolgbar)
- Methodisch fundiert (CIB ist etablierte Foresight-Methode)
- Konsistente Szenarien (keine widersprüchlichen Annahmen)
- Sehr gut für Andrew präsentierbar (strukturiert, wissenschaftlich)

## Schwächen
- Tunnel Vision: Findet nur Drivers, die schon in heutigen Produkten stecken
- Verpasst potentiell disruptive Technologien von außen (Quantum Sensing, Satellite-based Monitoring...)
- BOM-Decomposition braucht gute Produktdaten — bei öffentlichen Quellen evtl. limitiert
- Viele LLM-Calls (iterative Decomposition + paarweise CIB-Bewertung)

## Komplexität
Mittel-Hoch. Die iterative BOM-Decomposition und die CIB-Matrix sind aufwändig, aber jeder Schritt ist klar definiert und einzeln testbar.
