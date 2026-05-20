# Methodology Summary — Sprint Report

## What Are We Building?

We are building a prototype that uses AI (Large Language Models) to automate parts of **Strategic Technology Foresight** — the practice of systematically exploring what technologies might emerge in the next 5–15 years and what that means for a company's products.

Our focus domain is **regulatory frequency monitoring** — this is the field where government agencies use specialized equipment (made by Rohde & Schwarz) to scan radio spectrum, detect illegal transmitters, and enforce spectrum regulations. Think of it as "traffic enforcement, but for radio waves."

The core question the pipeline answers: **"What technologies could change this domain by 2035, how do they interact, and what future scenarios should R&S prepare for?"**

## How Does the Pipeline Work?

The pipeline has 7 steps, each implemented as a Jupyter Notebook. Each step reads the output of the previous step and produces structured JSON data that feeds into the next.

### Step 1: Knowledge Base Construction

Before we can ask an LLM anything useful, we need to give it domain-specific knowledge. We build a **Knowledge Base (KB)** from two types of sources:

- **KB-Product** (what exists today): R&S product pages and datasheets describing their current spectrum monitoring receivers (ESMD, ESMW, UMS300) — what frequencies they cover, what components they use, what their specifications are.
- **KB-Trends** (what might come tomorrow): Research papers and trend reports about emerging technologies — AI in spectrum management, quantum sensing, 6G networks, satellite-based monitoring, etc.

Each source document is split into smaller chunks (~500 words each), converted into numerical vectors (embeddings) using Azure OpenAI, and stored in a vector database (ChromaDB). This allows us to later retrieve only the most relevant chunks for any given question — a technique called **Retrieval-Augmented Generation (RAG)**.

### Step 2: Bottom-Up BOM Decomposition

Starting from a specific R&S product (the ESMW Ultra Wideband Monitoring Receiver), we ask the LLM to decompose it level by level — like peeling an onion:

```
ESMW Receiver
├── RF Frontend
│   ├── Wideband Antenna System
│   ├── Tunable Bandpass Filters        ← technology driver?
│   └── Low Noise Amplifier
├── Signal Processing
│   ├── Photonic ADC                    ← technology driver!
│   ├── Digital Downconversion
│   └── Real-Time Bandwidth Processing
├── Direction Finding
│   ├── AoA Error Correction            ← technology driver!
│   └── TDOA Measurement
...
```

At each level, the LLM only sees 3 relevant chunks from KB-Product (not the entire knowledge base). This keeps the prompts focused and ensures we can trace every component back to its source document.

The leaf nodes (the deepest components) are then classified: is this a **technology driver** (meaning it has active R&D, is evolving, could be disrupted) or a **passive component** (stable, commodity, not changing)?

### Step 3: Top-Down Trend Scanning

In parallel to the bottom-up product analysis, we scan the trend literature for technology megatrends that could impact spectrum monitoring. We use 5 different search queries to cover different angles:

- AI/ML for spectrum monitoring
- Quantum sensing and RF detection
- 6G and cognitive radio
- Space/satellite-based monitoring
- Edge computing and distributed sensors

For each trend found, we assess: **how specifically does this impact regulatory frequency monitoring?** Only trends with high or medium impact are kept as "trend-derived drivers."

### Step 4: Driver Merge and Confidence Scoring

Now we have two lists of technology drivers — one from the product (bottom-up) and one from trends (top-down). We merge them:

- **Validated** (appears in BOTH lists) → high confidence. Example: "Photonic Signal Processing" found in both R&S product specs and research papers. This means the technology is both commercially relevant and academically active.
- **Incremental** (BOM-only) → medium confidence. Found in current products but not flagged as a major trend. Likely to see steady improvements.
- **Speculative** (trend-only) → low confidence. Appears in research but not yet in products. Could be disruptive if it matures.

Near-duplicate drivers (e.g., "Photonic Signal Processing for Ultra-Wideband Receivers" and "Photonic Signal Processing for Spectrum Analysis") are automatically consolidated using embedding similarity — if two driver descriptions are more than 82% similar in vector space, they get merged.

### Step 5: Cross-Impact Balance (CIB) Matrix

This is where it gets interesting. We evaluate every pair of drivers: **"If Driver A makes a breakthrough, how does that affect Driver B?"**

For example:
- "If AI-native spectrum sensing breaks through, does that help or hurt quantum RF sensing?" (Maybe it reduces the need for quantum sensors → inhibiting)
- "If edge computing advances, does that help distributed monitoring?" (Yes, directly enables it → promoting)

The LLM scores each pair on two separate dimensions:
- **Promoting score** (0–3): How much does A help B?
- **Inhibiting score** (0–3): How much does A hinder B? (resource competition, obsolescence, etc.)

The net score (promoting minus inhibiting) goes into the matrix. We use this **split-scoring** technique because LLMs have a well-documented positivity bias — if you just ask "what's the impact?", they almost always say positive. By forcing a separate inhibiting score, we get more realistic assessments.

The result is a matrix that shows which technologies reinforce each other and which ones compete.

### Step 6: Scenario Generation

Using the drivers and their CIB relationships, we construct four future scenarios:

| Scenario | Type | Drivers Used | Assumption |
|---|---|---|---|
| Evolutionary Optimistic | evolutionary | validated + incremental | all breakthrough |
| Evolutionary Conservative | evolutionary | validated + incremental | all steady progress |
| Disruptive Transformation | disruptive | speculative + validated | all breakthrough |
| Mixed Stagnation + Disruption | disruptive | incremental + speculative | hardware stagnates, AI/space break through |

Before generating each scenario, a **CIB consistency check** verifies that the driver-state assumptions don't contradict the cross-impact matrix. For example, if the CIB says "A breakthrough in X strongly inhibits Y," then a scenario cannot assume both X and Y break through simultaneously.

Each scenario is generated with RAG context — the LLM receives relevant source chunks so the narrative stays grounded in real data rather than pure hallucination.

### Step 7: Comparative Scenario Assessment

Finally, all four scenarios are evaluated **side by side in a single prompt** on:
- **Impact** (1–10): How much would this change the domain?
- **Probability** (1–10): How likely is this scenario by 2035?
- **Confidence** (0–1): Derived from the underlying driver confidence scores.

We use **forced ranking** — the LLM must assign different scores to each scenario and receives calibration anchors (e.g., "5 = notable change requiring product adaptation, 9 = major paradigm shift"). This prevents the common failure mode where the LLM rates everything as "9/10 very impactful."

The results are visualized as an Impact vs. Probability scatter plot, where dot size represents confidence and color represents scenario type (blue = evolutionary, orange = disruptive).

## Traceability — The Red Thread

A core requirement from R&S (Product Owner: Dr. Andrew Schaefer) is **Nachvollziehbarkeit** — every claim must be traceable back to its source. The pipeline achieves this by propagating `source_chunk_ids` through every step:

```
Scenario: "Quantum-Enhanced AI-Native Spectrum Monitoring"
  └── Assumption: "Quantum RF Sensing: breakthrough"
      └── Driver: Quantum RF Sensing with Rydberg Atoms (confidence: low, origin: trend)
          └── Trend Impact Assessment (chunk: 554b9cd597f5)
              └── Source: "Quantum Sensing and Space-Based Spectrum Monitoring Trends"
                  └── URL: [original source]
```

The final traceability report in Notebook 07 prints this complete chain for every scenario.

## LLM Bias Mitigation

LLMs tend to be overly positive and agreeable (known as "sycophancy bias"). This is problematic for foresight, where you need honest assessments of trade-offs and risks. We address this with two techniques:

1. **CIB Split-Scoring**: Instead of asking "what's the net impact of A on B?" (which always comes back positive), we ask for separate promoting (0–3) and inhibiting (0–3) scores. The LLM must commit to an inhibiting score, even if small. Net = promoting - inhibiting.

2. **Batch Assessment with Forced Ranking**: Instead of evaluating each scenario independently (which leads to everything scoring 9/10), we present all scenarios in one prompt and require distinct scores with calibration anchors. This forces differentiation.

## Tech Stack

| Component | Technology | Purpose |
|---|---|---|
| LLM | Azure OpenAI gpt-4.1-mini | All reasoning, classification, generation |
| Embeddings | Azure OpenAI text-embedding-3-small | Semantic search, deduplication |
| Vector DB | ChromaDB (local, persistent) | RAG retrieval with pool filtering |
| Data Models | Pydantic v2 | Type-safe traceability chain |
| Orchestration | Jupyter Notebooks (7 sequential) | Executable, inspectable pipeline |
| State Passing | JSON files (data/outputs/) | Each notebook reads previous, writes next |
| Package Mgmt | uv | Python dependency management |

## Key Findings

### Driver Landscape

The pipeline identified **29 unique technology drivers** from two independent sources:

- **3 validated** (confirmed by both product analysis AND trend literature): These are technologies that R&S already uses and that are simultaneously flagged as active research areas. They represent the highest-confidence evolution paths. Examples: Photonic Signal Processing, Software-Defined Radio evolution, Edge Computing for distributed monitoring.
- **10 incremental** (product BOM only): Technologies present in current R&S products but not highlighted as major trends. These will likely see steady, predictable improvement. Examples: TDOA measurement, AoA error correction, tunable bandpass filters, GNSS modules.
- **16 speculative** (trend literature only): Emerging technologies not yet in current products. These carry the highest disruption potential but also the lowest confidence. Examples: Quantum RF sensing with Rydberg atoms, AI-native 6G networks, federated learning for spectrum management, LEO satellite constellations.

The low overlap (only 3/29 = 10% validated) is itself a finding: **the current product portfolio and the research frontier operate at very different abstraction levels.** BOM drivers are concrete hardware components (filters, ADCs, downconverters), while trend drivers describe system-level paradigms (cognitive radio, digital twins, federated AI). This gap is where strategic risk lives — disruption doesn't come from a better bandpass filter, it comes from an entirely different approach to spectrum monitoring.

### Cross-Impact Analysis

The CIB matrix (15 selected drivers, 210 pairwise evaluations) reveals that **most technology drivers in this domain are mutually reinforcing** — the mean cross-impact score is +0.76 on a -3 to +3 scale, with 71% positive, 29% neutral, and 0% negative relationships.

Top influencers (drivers that most strongly affect others):
1. **Photonic Signal Processing** (+15) — enables wider bandwidth capture, which cascades into better AI training data, better direction finding, and better edge processing
2. **Edge Computing + I/Q Streaming** (+14) — the "connective tissue" that ties distributed sensors together
3. **Real-Time Bandwidth Processing** (+14) — foundational capability that most other drivers build on

This pattern suggests that the spectrum monitoring technology ecosystem is **synergistic rather than competitive** — advancing one technology tends to help, not hurt, the others. The main competitive dynamic is indirect: **R&D budget and engineering talent are finite**, so heavy investment in AI may slow progress on hardware-level innovations (captured by the split-scoring inhibiting factors).

### Scenario Assessment

The four generated scenarios span distinct quadrants of the Impact vs. Probability space:

| Scenario | Impact | Probability | Confidence | Quadrant |
|---|---|---|---|---|
| **Evolutionary Breakthrough** | 7.0 | 9.0 | 0.75 | HIGH PRIORITY — likely and impactful |
| **Evolutionary Conservative** | 5.0 | 8.0 | 0.75 | EXPECTED — baseline future |
| **Quantum + AI Disruption** | 10.0 | 4.0 | 0.30 | MONITOR — high impact but uncertain |
| **AI + Space (Hardware Stagnation)** | 8.0 | 6.0 | 0.45 | STRATEGIC RISK — plausible disruption |

**Most actionable scenario: "AI-Driven Federated Spectrum Oversight from Space"** (Impact 8, Probability 6). This scenario models a concrete strategic risk for R&S: what happens if AI-based approaches and space-based monitoring become dominant while traditional hardware techniques (TDOA, AoA, tunable filters) — R&S's current core competencies — stagnate? The moderate probability (6/10) makes this neither dismissible nor certain, which is exactly the kind of scenario that should drive strategic planning.

**Highest-impact scenario: "Quantum-Enhanced AI-Native Spectrum Monitoring"** (Impact 10, Probability 4). Quantum RF sensing with Rydberg atoms replacing classical RF frontends would be a complete paradigm shift. Low probability by 2035, but worth monitoring as a long-horizon wildcard.

**Baseline scenario: "Evolutionary Conservative"** (Impact 5, Probability 8). The "nothing dramatic changes" scenario — steady progress in photonics, SDR, edge computing. This is the most likely future and R&S's current product roadmap likely already accounts for it. Low strategic value from a foresight perspective, but useful as a comparison baseline.

### Strategic Implications for R&S

1. **The transition from hardware-defined to software-defined monitoring is the central theme** across all scenarios. R&S should ensure its SDR architectures are flexible enough to absorb AI-based signal classification without hardware changes.
2. **Space-based monitoring is an emerging competitive dimension.** LEO satellite constellations appear in 3 of 4 scenarios. R&S should evaluate whether to participate or risk being disrupted by space-first competitors.
3. **Quantum sensing is a low-probability, high-impact wildcard.** No immediate action needed, but maintaining awareness and research partnerships is advisable.
4. **The biggest risk is not a single technology but a shift in approach** — from R&S's traditional hardware-centric, ground-based model to a distributed, AI-driven, cloud/space-based model where the hardware becomes commodity.

### Limitations

- **Small knowledge base** (7 sources, 24 chunks) — results would improve significantly with more domain-specific sources. The pipeline is designed to scale.
- **No negative CIB scores** — despite split-scoring, the LLM (gpt-4.1-mini) still avoids giving truly inhibiting assessments. A stronger model or human-in-the-loop validation would improve CIB quality.
- **Evolutionary scenarios lack diversity** — driver assumptions are too uniform (all breakthrough or all steady-progress). Future iterations should explore mixed states within evolutionary scenarios.
- **Single product focus** — BOM decomposition currently covers only the ESMW receiver. Extending to the full R&S monitoring portfolio would broaden the driver landscape.
