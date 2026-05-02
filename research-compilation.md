# Research Compilation: LLM-Augmented Strategic Technology Foresight

Stand: 2026-04-22. Alles was wir gefunden haben, kompakt zusammengefasst.

---

## 1. Was existiert bereits auf GitHub?

### Direkt nutzbar als Dependency

| Repo | Stars | Lizenz | Was es tut | Nutzbar? |
|------|-------|--------|-----------|----------|
| **Metaculus/forecasting-tools** | 69 | MIT | Production-ready LLM-Forecasting-Toolkit. GeneralLlm (litellm-Wrapper), SmartSearcher (Exa.ai + Pydantic-Output), KeyFactorsResearcher, Benchmarking, PyPI-Package. | **JA -- beste Dependency.** GeneralLlm, SmartSearcher, KeyFactors direkt nutzbar. |
| **ag-ross/PyCIB** | 3 | AGPL-3.0 | Vollst. CIB-Engine: deterministisch + Monte Carlo + Uncertainty + Dynamic Multi-Period + Feasibility Constraints. Akademisch rigoros (Zenodo DOI). | **Vielleicht -- AGPL ist Copyleft-Blocker.** Algorithmus gut dokumentiert, ggf. Kern selbst implementieren unter MIT. |

### Patterns klauen, nicht als Dependency nutzen

| Repo | Was klauen? |
|------|------------|
| **dannyallover/llm_forecasting** (NeurIPS 2024, 59 stars) | 5-Stufen-Pipeline: Search -> Filter -> Summarize -> Reason -> Aggregate. State-of-the-art-Muster. Keine Lizenz = rechtlich nicht nutzbar. |
| **MagnovaAI/foresight** (0 stars, MIT) | Multi-Agent-Szenario-Simulation mit CrewAI. Klauen: Entity Discovery (neue Akteure zwischen Runden entdecken), Directional Influence Matrix, Structured Agent Output. |
| **defidaddydavid/polyswarm** (1 star, MIT) | 12 AI-Personas debattieren, 26 Aggregationsmethoden, Plugin-Architektur fuer Datenquellen (`@register_source`), Kalibrations-Tracking. |
| **JulietteGoldstein/AI-Forecasting** | Delphi-LLM mit iterativen Runden + 5 weitere Forecasting-Methoden + Ensemble. Nutzt Kalshi-Daten. |
| **Paralogosai/ai-horizon-scanning-prototype** (4 stars) | FAISS-Embeddings, PESTLE-Klassifikation, Weak-Signal-Detection, Streamlit-Dashboard. |
| **isanthoshgandhi/foresight-intelligence** | IFTF-Methodik als Claude-Plugin: Cross-Impact, STEEEP-Matrix, Backcasting. LLM-geschaetzt, nicht algorithmisch. |
| **JohannesBuchner/zwicky-morphological-analysis** (16 stars) | Einzige Python Zwicky-Implementierung. Depth-first search mit Pruning. |

### Weitere relevante Tools

| Tool | Relevanz |
|------|---------|
| **setrf/forecasterarena** (11 stars) | 7 LLMs traden wöchentlich auf Polymarket. Live-Tracking. |
| **alastair-JL/StochasticCIB** | R-Package fuer stochastische CIB-Erweiterung. |
| **ScenarioWizard** (cross-impact.org) | Referenz-CIB-Tool (web-basiert, nicht open-source). |

---

## 2. Die drei Methoden im Detail

### A. Cross-Impact Balance (CIB)

**Was:** Mathematischer Konsistenzcheck fuer Szenarien. Jedes Szenario = Kombination von Treiber-Zustaenden. CIB prueft: Ist diese Kombination in sich konsistent?

**Wie:**
1. Definiere N Treiber (z.B. "6G-Entwicklung"), je 2-4 Zustaende ("verzoegert / planmaessig / beschleunigt")
2. Bewerte paarweise: Wie beeinflusst Zustand X von Treiber A den Treiber B? (-3 bis +3)
3. Fuer jede Szenario-Kombination: Berechne Impact-Summe pro Treiber
4. Konsistent = kein einzelner Treiber-Wechsel verbessert die Gesamt-Impact-Summe (Nash-Equilibrium-Logik)
5. Von z.B. 10.000 Kombinationen -> filtern auf 10-30 konsistente Szenarien

**Staerke:** Mathematisch beweisbar konsistent, skalierbar, publizierbar.
**Schwaeche:** Qualitaet = Qualitaet der Cross-Impact-Matrix. Wer befuellt die?

**Referenzen:**
- Weimer-Jehle (2006): Foundational paper
- Weimer-Jehle (2023): Springer-Buch
- cross-impact.org: Algorithmus-Details + ScenarioWizard
- PyCIB: Python-Implementierung

### B. LLM-Delphi

**Was:** Klassische Delphi-Methode (iterative Expertenrunden) simuliert mit LLM-Personas.

**Wie (Best Practice aus Literatur):**
1. 5-7 diverse Personas definieren (z.B. Technologe, Oekonom, Regulierer, Militaer-Analyst, Startup-Gruender)
2. Jede Persona bekommt eigenen Kontext + explizit widersprüchliche Perspektiven (sonst konvergieren sie sofort!)
3. Runde 1: Jede Persona bewertet unabhaengig
4. Mediator-Phase: Anonymisierte Zusammenfassung, Dissens hervorheben (nicht nur Konsens!)
5. Runde 2: Personas revidieren mit Feedback
6. Aggregation: Gewichteter Durchschnitt oder Extremisierung

**Schluesselfinding:** "Scalable Delphi" (Lorenz & Fritz, 2026): Pearson r=0.87-0.95 mit Ground Truth. Die **Struktur** (iterativ + Mediator), nicht die Persona-Expertise, treibt die Qualitaet.

**Echo-Chamber-Problem und Loesungen:**
- Problem: Alle Personas kommen vom selben Modell -> kuenstliche Konvergenz
- Loesung 1: Verschiedene LLMs nutzen (GPT-4o, Claude, Llama) = "Wisdom of the Silicon Crowd"
- Loesung 2: Explizit widersprüchliche Priors pro Persona zuweisen (DelphAI-Ansatz)
- Loesung 3: Mediator der Dissens bewahrt, nicht nur Konsens extrahiert
- Loesung 4: Semantische Konvergenz quantitativ tracken (Embedding-Distanzen)

**Referenzen:**
- Scalable Delphi: arXiv:2602.08889
- DelphAI: Dazeley-Gaist (2025), Wolfram + Claude
- Argyle et al. (2023): "Out of One, Many" -- LLM-Persona-Simulation (foundational)
- Wisdom of the Silicon Crowd: Schoenegger et al., Science Advances 2024

### C. Prediction Markets als Kalibrierung

**Was:** Markt-Wahrscheinlichkeiten (Polymarket, Metaculus, Kalshi) als Ground-Truth-Anker fuer LLM-Forecasts.

**Warum das funktioniert:**
- Prediction Markets: Brier ~0.09 (random = 0.25, exzellent = <0.10)
- Polymarket: 2,847 resolved markets, Overall Brier 0.187, 1 Monat vor Schluss: 0.09
- Kalshi: Brier oft <0.10
- Superforecasters: 0.081
- Bestes LLM (GPT-4.5): 0.101 -- Gap schliesst sich, Paritaet erwartet ~Nov 2026

**Konkrete APIs:**
- **Polymarket**: Gamma API (kein Auth, `gamma-api.polymarket.com`), PyPI: `polymarket-apis`, 4000 req/10s
- **Metaculus**: Python-Framework `forecasting-tools` (pip-installbar!), Community Brier 0.10-0.20
- **Kalshi**: REST + WebSocket, public data frei
- **Manifold**: Open-source, `api.manifold.markets`, 500 req/min

**Wie nutzen:**
1. Fuer jeden Technologie-Treiber: Relevante Prediction-Market-Fragen suchen
2. Markt-Wahrscheinlichkeiten als Bayesian Prior fuer Treiber-Zustaende
3. Divergenz >20pp zwischen LLM-Einschaetzung und Markt flaggen
4. Kalibrations-Feedback-Loop: Eigene Predictions vs. Market-Resolution tracken

---

## 3. Grounding & Evaluation (Andrews Kernforderung)

### Faithfulness (Quellenbeleg)

**RAGAS-Methode:** Aus dem generierten Text atomare Claims extrahieren -> jeden Claim gegen Retrieved Context pruefen -> Ratio supported/total = Faithfulness Score. >0.8 = gut.

**Enforcement:** Pydantic-Schema mit mandatory SourceReference (inkl. exaktem Zitat-Excerpt, nicht nur Dokument-ID). Jede Behauptung braucht min. 1 Quelle.

### Konsistenz (CIB)

CIB-Algorithmus = mathematische Garantie: Szenario ist intern widerspruchsfrei. Staerkster Differentiator vs. "einfach LLM fragen".

### Kalibrierung

- LLMs sind systematisch overconfident nach RLHF
- Ensemble von 12 LLMs ≈ 925-Personen-Crowd (Brier 0.20 vs 0.19)
- Human+Machine Averaging = bestes Ergebnis (Brier 0.12)
- Post-hoc Kalibrierung (Isotonic Regression, Temperature Scaling) hilft

### Backtesting

**Achtung:** Li et al. (2026, arXiv:2601.13717) "Simulated Ignorance Fails" -- LLMs koennen NICHT zuverlaessig so tun als wuessten sie die Zukunft nicht. 52% Performance-Gap bleibt. Reasoning-Models sind sogar schlechter (post-hoc Rationalisierung).

**Besser:** Prozess-Validierung statt Ergebnis-Validierung:
- Identifiziert das Tool die richtigen Treiber? (vs. Experten-Benchmark)
- Ist CIB korrekt implementiert? (deterministic, testbar)
- Sind Quellen korrekt zugeordnet? (RAGAS Faithfulness)
- Cohen's Kappa: Tool vs. R&S-Experten bei Cross-Impact-Bewertung

### Was R&S beeindrucken wuerde

1. **Audit Trail**: Jeder Claim -> spezifische Quellenpassage (kein Consulting-Bullshit)
2. **Experten-Vergleich**: Tool vs. R&S-Experten, Cohen's Kappa berichten
3. **Visualisierungen**: Impact-Uncertainty Matrix, Cross-Impact Heatmap, Szenario-Dashboard
4. **Reproduzierbarkeit**: Deterministisch wo moeglich (CIB), Varianz berichten wo nicht (LLM)
5. **Updatebarkeit**: Neue Quellen rein -> neue Szenarien raus (kein One-Shot-Consulting)

---

## 4. Die Luecke -- Was NIEMAND gebaut hat

Einzelteile existieren ueberall. Was fehlt:

1. **CIB + LLM**: PyCIB braucht handgefuellte Matrizen. Niemand hat LLMs die Matrix befuellen lassen.
2. **LLM-Delphi -> CIB**: Niemand kombiniert iterative LLM-Expertenrunden mit formaler Konsistenzpruefung.
3. **Prediction-Market-Kalibrierung fuer Foresight**: Niemand nutzt Marktdaten als Anker fuer Szenario-Wahrscheinlichkeiten.
4. **End-to-End Pipeline**: Horizon Scanning + Treiber-Extraktion + Cross-Impact + Konsistenz + Narrative + Evaluation = nicht vorhanden als System.

---

## 5. Datenfluss-Skizze: Wie alles zusammenpasst

```
[Knowledge Base / RAG]
  Quellen: Papers, Patents, Standards, R&S-Website, Sci-Fi, Industry Reports
  Tools: LlamaIndex + Chroma, Unstructured.io fuer Parsing
      |
      v
[1. Treiber-Identifikation]
  LLM extrahiert Tech-Treiber aus Dokumenten
  STEEP-Kategorisierung, TRL-Schaetzung
  -> KeyFactorsResearcher (forecasting-tools) nutzbar
  -> Ergebnis: Liste von ~15-25 Treibern mit je 2-4 Zustaenden
      |
      v
[2. LLM-Delphi fuer Cross-Impact-Bewertung]
  5-7 Personas (Technologe, Oekonom, Regulierer, Militaer, Startup)
  2 Runden + Mediator, explizit widersprüchliche Priors
  Multi-Model (GPT-4o + Claude + Llama) gegen Echo Chamber
  -> Ergebnis: Cross-Impact-Matrix (N×N, -3 bis +3)
      |
      v
[3. Prediction-Market-Kalibrierung]
  Polymarket/Metaculus/Kalshi APIs abfragen
  Relevante Markt-Fragen zu Treibern matchen
  Markt-Wahrscheinlichkeiten als Priors einbauen
  Divergenzen >20pp flaggen
  -> Ergebnis: Kalibrierte Treiber-Wahrscheinlichkeiten
      |
      v
[4. CIB Konsistenzpruefung]
  Cross-Impact-Matrix -> PyCIB (oder eigene Impl.)
  Alle Kombinationen durchrechnen
  Konsistente Szenarien filtern (Nash-Equilibrium)
  -> Ergebnis: 10-30 konsistente Szenario-Konfigurationen
      |
      v
[5. Szenario-Narrative]
  Fuer jedes konsistente Szenario: LLM generiert Narrativ
  RAG-grounded, jeder Claim mit Quellenbeleg
  Pydantic-Schema erzwingt Struktur + Citations
  -> Ergebnis: "Ein Tag im Leben eines Spectrum Monitoring Operators 2035"
      |
      v
[6. Quantitative Analyse]
  Monte Carlo ueber Treiber-Verteilungen (SALib)
  Sobol Sensitivity: Welche Treiber sind entscheidend?
  Clustering in Szenario-Archetypen (k-means)
  Impact-Probability-Matrix
      |
      v
[7. Strategische Implikationen]
  Szenarien gegen R&S-Strategie "wind-tunneln"
  Welche Investitionen sind robust ueber alle Szenarien?
  Welche Szenarien erfordern strategische Pivots?
```

---

## 6. Schluessel-Referenzen (geordnet nach Relevanz)

**Methodik:**
- Weimer-Jehle (2006): "Cross-Impact Balances" -- CIB-Algorithmus
- Weimer-Jehle (2023): CIB for Scenario Analysis (Springer Buch)
- Lorenz & Fritz (2026): "Scalable Delphi" -- arXiv:2602.08889
- Argyle et al. (2023): "Out of One, Many" -- LLM-Persona-Simulation
- Schoenegger et al. (2024): "Wisdom of the Silicon Crowd" -- Science Advances
- Halawi et al. (2024): "Approaching Human-Level Forecasting" -- NeurIPS 2024

**Evaluation:**
- RAGAS: docs.ragas.io -- Faithfulness-Metrik
- Li et al. (2026): "Simulated Ignorance Fails" -- arXiv:2601.13717 (Backtesting-Warnung)
- Schoemaker (2020): Historical Analysis + Scenario Planning
- ForecastBench: forecastbench.org (ICLR 2025)
- SALib: salib.readthedocs.io -- Sobol Sensitivity

**Tools:**
- Metaculus/forecasting-tools: github.com/Metaculus/forecasting-tools (MIT, PyPI)
- ag-ross/PyCIB: github.com/ag-ross/PyCIB (AGPL)
- ScenarioWizard: cross-impact.org

**Policy/Foresight Community:**
- European Parliament (2025): "Augmented Foresight" Briefing
- EU JRC Foresight: knowledge4policy.ec.europa.eu/foresight
- BCG (2025): "Navigating the Future with Strategic Foresight"
