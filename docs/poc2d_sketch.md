# PoC 2d: Hypothesis-First Foresight

## Problem mit poc2c

Citation Graph RAG findet nur was in der akademischen Nachbarschaft der Seeds liegt. "Blind Spots" sind per Definition nicht dort. Prompt-Tuning und Seed-Diversifizierung ändern das nicht — es ist ein Architekturproblem.

## Idee: Umkehrung der Pipeline

**poc2c**: Corpus → Retrieval → Extraction → "Was ist überraschend?" (Bottom-up)
**poc2d**: LLM generiert Hypothesen → Quellen validieren/falsifizieren (Top-down)

### Warum das funktionieren könnte

Andrews Regel: "Exploit LLM **capabilities**, not its **knowledge**."

Das LLM hat breites Wissen über Industrien, Technologien, Disruption-Patterns. Dieses Wissen ist unverifiziert — genau das was Andrew nicht will. ABER: wenn wir das Wissen nur als **Hypothesengenerator** nutzen und dann mit echten Quellen validieren, exploiten wir die Fähigkeit (kreatives Querdenken) ohne dem Wissen zu vertrauen.

### Pipeline

```
┌─────────────────────────────────────────────────────┐
│ 1. HYPOTHESENGENERATION (LLM Capability)            │
│                                                      │
│    Input: R&S Profil + Disruption-Frameworks         │
│    Prompt: "Welche Technologien/Trends aus ANDEREN   │
│    Industrien könnten R&S in 5-10 Jahren betreffen?" │
│                                                      │
│    → 30-50 unvalidierte Hypothesen                   │
│    → Jede mit: Disruption-These, Suchstrategie,      │
│      erwarteter Evidenztyp                           │
└──────────────┬──────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────┐
│ 2. MULTI-SOURCE EVIDENCE SEARCH                      │
│                                                      │
│    Pro Hypothese automatisch suchen in:              │
│    - OpenAlex (akademisch)                           │
│    - Patent-APIs (Google Patents, Lens.org)          │
│    - News/Industry (Event Registry, GDELT)           │
│    - Startup-Daten (Crunchbase API, optional)        │
│                                                      │
│    → Evidence Bundle pro Hypothese                   │
│    → "Keine Evidenz gefunden" = auch ein Signal      │
└──────────────┬──────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────┐
│ 3. VALIDATION (LLM Capability, nicht Knowledge)      │
│                                                      │
│    Pro Hypothese:                                    │
│    - Evidenz gefunden? → Faithfulness Check (poc2c)  │
│    - Keine Evidenz? → "Speculative" Flag             │
│    - Widersprüchliche Evidenz? → Markieren           │
│                                                      │
│    → Validated Drivers (mit Quellen)                 │
│    → Speculative Drivers (LLM-only, transparent)     │
│    → Falsified Hypotheses (auch wertvoll)            │
└──────────────┬──────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────┐
│ 4. SURPRISE + AUDIT (reuse poc2c)                    │
│                                                      │
│    - LLM Surprise Assessment                         │
│    - Full Audit Trail                                │
│    - Aber jetzt auch: "Speculative" Kategorie        │
│    - Scatter: Validated vs. Speculative Drivers      │
└─────────────────────────────────────────────────────┘
```

### Warum "Speculative" Drivers wertvoll sind

Wenn das LLM eine Hypothese generiert die plausibel klingt aber KEINE akademische Evidenz hat, ist das potenziell der interessanteste Fall:
- Vielleicht ist es zu neu für Papers (Weak Signal)
- Vielleicht ist es ein Cross-Domain Transfer den noch niemand erforscht
- Vielleicht ist es Bullshit

Alle drei Fälle sind für einen Strategen relevant. Der Audit Trail macht transparent WELCHER Fall es ist.

### Disruption-Frameworks für den Hypothesen-Prompt

Statt "generiere Hypothesen" (zu vage) nutze bewährte Foresight-Frameworks:
- **Christensen Disruption**: Was ist "good enough" Tech die von unten kommt?
- **Adjacent Possible**: Welche Kombinationen existierender Tech werden jetzt erst möglich?
- **Regulatory Shock**: Welche Policy-Änderungen könnten den Markt umstrukturieren?
- **Platform Shift**: Wo verschieben sich Wertschöpfungsketten?
- **Convergence**: Welche bisher getrennten Industrien verschmelzen?

### Konkrete APIs

| Quelle | API | Kosten | Was es bringt |
|--------|-----|--------|---------------|
| OpenAlex | api.openalex.org | Free | Akademische Papers + Citation Graph |
| Lens.org | lens.org/api | Free (non-commercial) | Patents + Scholarly combined |
| Event Registry | eventregistry.org | Free tier (500/day) | News aus 150k Quellen |
| Google Patents | SerpAPI wrapper | Free tier | Patent-Trends |
| Crunchbase | crunchbase.com/api | Paid ($) | Startup-Funding als Signal |

### Was wir aus poc2c übernehmen

- `src/models.py` — Observable Models (SourceEvidence, FaithfulnessResult, etc.)
- Faithfulness Check Logik
- LLM Surprise Assessment
- Audit Report + Visualisierung
- Dedup via Agglomerative Clustering

### Was neu ist

- Hypothesengeneration als eigener Step mit Pydantic Model
- Multi-Source Evidence Search (nicht nur OpenAlex)
- Drei Driver-Kategorien: Validated / Speculative / Falsified
- Disruption-Framework-basierter Prompt statt generischer Foresight-Queries

### Risiken

- LLM-Hypothesen könnten generisch sein ("AI disrupts everything")
  → Fix: Framework-basierte Prompts + R&S-spezifischer Kontext
- Zu viele Hypothesen, zu wenig Evidenz pro Hypothese
  → Fix: Batch-Validierung, Top-N nach LLM-Confidence
- Patent/News APIs haben Limits
  → Fix: Stufenweise — erst OpenAlex-only, dann Sources hinzufügen
- "Speculative" Kategorie könnte als License für Bullshit missbraucht werden
  → Fix: Transparent labeln, nie als "validated" darstellen

## MVP: Was ist das Minimum für poc2d?

1. LLM generiert 30 Hypothesen (mit Disruption-Frameworks)
2. OpenAlex-only Evidence Search (keine neuen APIs nötig)
3. Validation: Faithfulness Check aus poc2c
4. Drei Kategorien: Validated / Speculative / Falsified
5. Audit Trail aus poc2c

→ Neues Notebook, ~1 Tag Arbeit, reused 60% von poc2c
