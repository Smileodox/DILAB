# Implementation Plan: Two PoC Notebooks for LLM-Augmented Strategic Technology Foresight

## Status: COMPLETE

---

## 1. Project Skeleton

### Directory Structure

```
DILAB/
  pyproject.toml
  .env                          # AZURE_OPENAI_API_KEY, AZURE_OPENAI_BASE_URL, AZURE_OPENAI_MODEL
  .env.example                  # Template without secrets
  .gitignore
  notebooks/
    poc1_cib.ipynb              # PoC 1: LLM -> CIB Matrix
    poc2_rag_surprise.ipynb     # PoC 2: RAG + Surprise Scoring
  src/
    cib.py                      # CIB algorithm (pure functions + numpy)
    models.py                   # Pydantic models shared by both PoCs
    llm.py                      # Thin Azure OpenAI client wrapper
  data/
    arxiv_papers/               # Downloaded PDFs (gitignored)
    chroma_db/                  # ChromaDB persistent store (gitignored)
  CLAUDE.md
  research-compilation.md
```

### pyproject.toml

```toml
[project]
name = "dilab-foresight"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    # --- Shared ---
    "openai>=1.42",
    "pydantic>=2.8",
    "python-dotenv>=1.0",

    # --- PoC 1: CIB ---
    "numpy>=1.26",
    "pandas>=2.1",
    "tabulate>=0.9",           # Pretty-print tables in notebooks

    # --- PoC 2: RAG + Surprise ---
    "arxiv>=2.1",
    "llama-index>=0.12",
    "llama-index-vector-stores-chroma>=0.4",
    "llama-index-embeddings-openai>=0.5",
    "llama-index-llms-openai>=0.6",
    "chromadb>=1.0",

    # --- Notebook ---
    "jupyter>=1.0",
    "matplotlib>=3.8",
    "seaborn>=0.13",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### Bootstrap Commands

```bash
cd DILAB
uv init                        # Creates pyproject.toml scaffold
# Then paste dependencies into pyproject.toml
uv sync                        # Installs everything into .venv
uv run jupyter notebook        # Launch notebooks
```

### .env File

```
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_BASE_URL=https://your-resource.openai.azure.com/openai/v1/
AZURE_OPENAI_MODEL=gpt-4o
```

### .gitignore Additions

```
.env
data/arxiv_papers/
data/chroma_db/
.venv/
__pycache__/
*.pyc
.ipynb_checkpoints/
```

---

## 2. Shared Module: src/llm.py

A thin wrapper so both notebooks use identical Azure OpenAI setup.

```python
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

def get_client() -> OpenAI:
    return OpenAI(
        base_url=os.environ["AZURE_OPENAI_BASE_URL"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
    )

def get_model() -> str:
    return os.environ.get("AZURE_OPENAI_MODEL", "gpt-4o")
```

Key point: Azure AI Foundry uses the standard `openai.OpenAI` client (NOT `AzureOpenAI`) when using the `/openai/v1/` base URL path. This was confirmed in the Microsoft docs. The `client.beta.chat.completions.parse()` method works with Pydantic models for structured output.

---

## 3. PoC 1: LLM -> CIB Matrix (Detailed Design)

### 3a. Pydantic Models (src/models.py)

```python
from pydantic import BaseModel, Field

class DriverState(BaseModel):
    driver_name: str
    state_name: str
    state_index: int        # 0-based index within this driver

class Driver(BaseModel):
    name: str
    description: str
    states: list[str]       # e.g. ["delayed", "on-track", "accelerated"]

class CrossImpactEntry(BaseModel):
    source_driver: str
    source_state: str
    target_driver: str
    impact: int = Field(ge=-3, le=3)
    rationale: str

class CrossImpactRow(BaseModel):
    source_driver: str
    source_state: str
    impacts: list[CrossImpactEntry]

class CrossImpactMatrix(BaseModel):
    """Full LLM response: all impacts from one source driver-state to all target drivers."""
    rows: list[CrossImpactRow]
```

### 3b. Hardcoded R&S Domain Drivers

Seven drivers, each with 2-3 states. This yields a manageable combination space (2*3*3*3*3*3*2 = 972 scenarios, well within brute-force range).

```python
DRIVERS = [
    Driver(
        name="6G Development",
        description="Timeline and progress of 6G standardization and deployment",
        states=["delayed", "on-track", "accelerated"]
    ),
    Driver(
        name="Spectrum Policy",
        description="Regulatory approach to spectrum allocation and sharing",
        states=["restrictive", "status-quo", "liberalized"]
    ),
    Driver(
        name="AI-Native Wireless",
        description="Integration of AI/ML into wireless PHY/MAC layers",
        states=["niche-adoption", "mainstream", "pervasive"]
    ),
    Driver(
        name="Space-Based Sensing",
        description="LEO satellite constellations for spectrum monitoring and comms",
        states=["limited", "operational", "dominant"]
    ),
    Driver(
        name="Electronic Warfare Demand",
        description="Military/security demand for EW and signal intelligence capabilities",
        states=["stable", "growing", "surge"]
    ),
    Driver(
        name="T&M Automation",
        description="Automation level in test & measurement workflows",
        states=["manual-dominant", "semi-automated", "fully-automated"]
    ),
    Driver(
        name="Open RAN Adoption",
        description="Market penetration of O-RAN disaggregated network architecture",
        states=["marginal", "significant"]
    ),
]
```

Total combinations: 3*3*3*3*3*3*2 = 1,458 scenarios. Brute-force is trivially fast.

### 3c. CIB Algorithm (src/cib.py)

Implement as pure functions operating on numpy arrays. No classes needed for a PoC.

**Data structure**: The cross-impact matrix is a 2D numpy array where:
- Rows = all (driver, state) pairs (source of influence)
- Columns = all drivers (targets of influence)
- Cell [i, j] = impact of source state i on target driver j

For 7 drivers with states above, that is 20 source rows and 7 target columns.

```python
import numpy as np
from itertools import product

def build_state_index(drivers: list) -> tuple[list[tuple[int,int]], list[int]]:
    """
    Returns:
      state_list: [(driver_idx, state_idx), ...] for all states across all drivers
      driver_sizes: [num_states_for_driver_0, num_states_for_driver_1, ...]
    """
    state_list = []
    driver_sizes = []
    for d_idx, driver in enumerate(drivers):
        n = len(driver.states)
        driver_sizes.append(n)
        for s_idx in range(n):
            state_list.append((d_idx, s_idx))
    return state_list, driver_sizes

def compute_impact_sums(scenario: tuple[int,...], matrix: np.ndarray,
                         state_list: list, driver_sizes: list) -> np.ndarray:
    """
    For a given scenario (tuple of state indices, one per driver),
    compute the impact sum received by EACH state of EACH driver.

    Returns: 1D array of length len(state_list), where entry k is
    the total impact received by state k from all active states
    in the scenario (excluding the driver that state k belongs to).
    """
    n_drivers = len(driver_sizes)
    n_states_total = len(state_list)
    impact_sums = np.zeros(n_states_total)

    # Find which rows in state_list are "active" in this scenario
    active_rows = []
    offset = 0
    for d_idx, size in enumerate(driver_sizes):
        active_rows.append(offset + scenario[d_idx])
        offset += size

    # For each target state k, sum impacts from all active source states
    # EXCEPT the one from the same driver as k
    for k in range(n_states_total):
        target_driver = state_list[k][0]
        total = 0.0
        for d_idx in range(n_drivers):
            if d_idx == target_driver:
                continue  # No self-impact
            row = active_rows[d_idx]
            total += matrix[row, k]
        impact_sums[k] = total

    return impact_sums

def is_consistent(scenario: tuple[int,...], matrix: np.ndarray,
                   state_list: list, driver_sizes: list) -> bool:
    """
    A scenario is consistent if for every driver, the active state
    has the highest (or tied-highest) impact sum among all states
    of that driver.

    This is the Nash equilibrium condition from Weimer-Jehle (2006).
    """
    impact_sums = compute_impact_sums(scenario, matrix, state_list, driver_sizes)

    offset = 0
    for d_idx, size in enumerate(driver_sizes):
        active_state = scenario[d_idx]
        active_sum = impact_sums[offset + active_state]
        for s_idx in range(size):
            if impact_sums[offset + s_idx] > active_sum:
                return False
        offset += size
    return True

def find_consistent_scenarios(drivers: list, matrix: np.ndarray) -> list[tuple[int,...]]:
    """Brute-force: enumerate all combinations, return consistent ones."""
    state_list, driver_sizes = build_state_index(drivers)
    ranges = [range(s) for s in driver_sizes]
    consistent = []
    for scenario in product(*ranges):
        if is_consistent(scenario, matrix, state_list, driver_sizes):
            consistent.append(scenario)
    return consistent
```

**Why brute-force**: With ~1,500 combinations and a 20x20 matrix, this runs in under a second. No optimization needed.

### 3d. LLM Prompt for Cross-Impact Matrix

The prompt asks the LLM to fill impacts **one source driver at a time** to stay within output token limits. Loop over each driver's states as source, ask for impacts on all other drivers.

**System prompt**:
```
You are an expert in strategic technology foresight for the wireless communications,
spectrum monitoring, and test & measurement industries. You are helping build a
Cross-Impact Balance (CIB) matrix for scenario analysis.

You will be given a SOURCE driver-state and a list of TARGET drivers. For each target
driver, rate the influence of the source state on each state of the target driver on
a scale from -3 to +3:
  -3 = strongly inhibits this state
  -2 = moderately inhibits
  -1 = weakly inhibits
   0 = no significant influence
  +1 = weakly promotes
  +2 = moderately promotes
  +3 = strongly promotes

Rules:
- Consider direct causal influences, not correlations
- Impacts are on the TARGET states, not the source
- For each target driver, the impacts across its states should reflect relative
  preference shifts (if one state is promoted, another is typically inhibited)
- Provide a brief rationale for each impact score
```

**User prompt** (called in a loop for each source driver-state):
```
SOURCE: Driver "{source_driver}" in state "{source_state}"
({source_description})

Rate the impact on each state of EVERY other driver listed below:

{for each target driver:}
TARGET DRIVER: "{target_name}" ({target_description})
  States: {list of states}

Return your response as structured JSON.
```

**Structured output Pydantic model** for each call:
```python
class ImpactAssessment(BaseModel):
    target_driver: str
    target_state: str
    impact: int = Field(ge=-3, le=3)
    rationale: str

class SourceStateImpacts(BaseModel):
    source_driver: str
    source_state: str
    assessments: list[ImpactAssessment]
```

**Call pattern**: `client.beta.chat.completions.parse(model=model, messages=[...], response_format=SourceStateImpacts)`

With 7 drivers and 20 total states, there are 20 source-state calls. Each returns impacts on ~17 target states (excluding own driver). This is ~20 API calls, each fast with structured output. Total cost: roughly 20 calls * ~1000 tokens each = ~20K tokens, well under $1.

### 3e. Matrix Assembly

After all LLM calls, assemble into the numpy matrix:

```python
def assemble_matrix(drivers, all_responses):
    state_list, driver_sizes = build_state_index(drivers)
    n = len(state_list)
    matrix = np.zeros((n, n))

    # Create lookup: (driver_name, state_name) -> state_list index
    lookup = {}
    idx = 0
    for d in drivers:
        for s in d.states:
            lookup[(d.name, s)] = idx
            idx += 1

    for response in all_responses:
        src_idx = lookup[(response.source_driver, response.source_state)]
        for a in response.assessments:
            tgt_idx = lookup[(a.target_driver, a.target_state)]
            matrix[src_idx, tgt_idx] = a.impact

    return matrix
```

### 3f. Display Results

1. **Cross-impact heatmap**: `seaborn.heatmap()` with state labels on both axes, diverging colormap (RdBu_r), annotated with values.

2. **Consistent scenarios table**: `pandas.DataFrame` where each row is a consistent scenario, columns are driver names, cells are state names. Use `tabulate` for notebook display.

3. **Scenario count summary**: Print total combinations vs. consistent count.

```python
# Heatmap
fig, ax = plt.subplots(figsize=(14, 10))
labels = [f"{d.name}: {s}" for d in drivers for s in d.states]
sns.heatmap(matrix, xticklabels=labels, yticklabels=labels,
            cmap="RdBu_r", center=0, vmin=-3, vmax=3,
            annot=True, fmt=".0f", ax=ax)
ax.set_title("Cross-Impact Matrix (LLM-generated)")
plt.tight_layout()

# Scenarios table
rows = []
for sc in consistent:
    row = {}
    for d_idx, d in enumerate(drivers):
        row[d.name] = d.states[sc[d_idx]]
    rows.append(row)
df = pd.DataFrame(rows)
print(f"\n{len(consistent)} consistent scenarios out of {total} combinations\n")
display(df)
```

### 3g. Notebook Cell Structure (poc1_cib.ipynb)

| Cell | Content |
|------|---------|
| 1 | Imports, path setup, `sys.path.insert` for src/ |
| 2 | Load .env, initialize OpenAI client |
| 3 | Define DRIVERS list (hardcoded) |
| 4 | LLM loop: for each source state, call structured output, collect responses |
| 5 | Assemble numpy matrix from responses |
| 6 | Display heatmap |
| 7 | Run CIB consistency check |
| 8 | Display consistent scenarios table |
| 9 | (Optional) Save matrix + results to JSON for reproducibility |

---

## 4. PoC 2: RAG + Surprise Scoring (Detailed Design)

### 4a. ArXiv Paper Fetching

Use the `arxiv` package (v2.1+). Fetch ~50 papers across R&S-relevant topics.

```python
import arxiv

QUERIES = [
    "spectrum monitoring machine learning",
    "6G wireless communications",
    "test measurement 5G NR",
    "signal processing cognitive radio",
    "open RAN O-RAN testing",
    "electronic warfare signal detection",
    "satellite LEO spectrum sensing",
]

client = arxiv.Client(page_size=10, delay_seconds=3.0)

papers = []
for q in QUERIES:
    search = arxiv.Search(query=q, max_results=8, sort_by=arxiv.SortCriterion.Relevance)
    for result in client.results(search):
        papers.append({
            "title": result.title,
            "abstract": result.summary,
            "url": result.pdf_url,
            "published": result.published,
            "arxiv_id": result.entry_id,
        })
```

No need to download PDFs for the PoC. Abstracts are sufficient for RAG and driver extraction. This keeps things fast and avoids PDF parsing complexity.

### 4b. LlamaIndex + ChromaDB Setup

Use abstracts as documents. Embed with OpenAI embeddings (text-embedding-3-small via Azure). Store in ChromaDB.

```python
import chromadb
from llama_index.core import VectorStoreIndex, Document, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI as LlamaOpenAI

# Configure LlamaIndex to use Azure OpenAI
Settings.embed_model = OpenAIEmbedding(
    model_name="text-embedding-3-small",
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_base=os.environ["AZURE_OPENAI_BASE_URL"],
)
Settings.llm = LlamaOpenAI(
    model=os.environ.get("AZURE_OPENAI_MODEL", "gpt-4o"),
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_base=os.environ["AZURE_OPENAI_BASE_URL"],
)

# Build documents
documents = [
    Document(
        text=f"Title: {p['title']}\n\nAbstract: {p['abstract']}",
        metadata={"arxiv_id": p["arxiv_id"], "title": p["title"]},
    )
    for p in papers
]

# ChromaDB persistent store
chroma_client = chromadb.PersistentClient(path="data/chroma_db")
chroma_collection = chroma_client.get_or_create_collection("arxiv_papers")
vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

# Build index
index = VectorStoreIndex.from_documents(documents, vector_store=vector_store)
query_engine = index.as_query_engine(similarity_top_k=5)
```

**Important note on Azure embedding models**: The user needs to verify their Azure AI Foundry deployment includes an embedding model. If `text-embedding-3-small` is not deployed, they can either:
- Deploy it in Azure AI Foundry
- Use ChromaDB's default embedding (all-MiniLM-L6-v2, runs locally, no API needed) by omitting `Settings.embed_model`

The fallback with ChromaDB default embeddings is simpler for a PoC:
```python
# Simpler fallback: let ChromaDB handle embeddings locally
# Just remove Settings.embed_model entirely
# ChromaDB uses sentence-transformers all-MiniLM-L6-v2 by default
```

### 4c. Driver Extraction via LLM

Use RAG context + direct LLM structured output to extract technology drivers from the indexed papers.

**Extraction prompt** (system):
```
You are a technology foresight analyst specializing in wireless communications,
spectrum monitoring, and test & measurement (T&M) for Rohde & Schwarz.

Given a set of research paper abstracts, extract TECHNOLOGY DRIVERS that could
significantly shape the industry over the next 5-10 years.

A technology driver is a specific technology, capability, or trend (NOT a product
or company). Each driver should have:
- A concise name (3-5 words)
- A one-sentence description of what it is
- A STEEP category (Social, Technological, Economic, Environmental, Political)
- An estimated TRL range (1-9)
- The source paper titles it was derived from

Extract 10-20 distinct drivers. Avoid generic drivers like "AI" or "5G" --
be specific (e.g., "AI-based spectrum anomaly detection" not "artificial intelligence").
```

**Pydantic model**:
```python
class ExtractedDriver(BaseModel):
    name: str
    description: str
    steep_category: str = Field(description="One of: Social, Technological, Economic, Environmental, Political")
    trl_low: int = Field(ge=1, le=9)
    trl_high: int = Field(ge=1, le=9)
    source_papers: list[str]

class DriverExtractionResult(BaseModel):
    drivers: list[ExtractedDriver]
```

**Two-pass approach**:
1. Query the RAG index with broad queries like "emerging technologies spectrum monitoring", "novel approaches 6G testing", "future wireless communications capabilities" to get relevant context chunks.
2. Feed the retrieved chunks into `client.beta.chat.completions.parse()` with the extraction prompt and `response_format=DriverExtractionResult`.

### 4d. Surprise Scoring Algorithm

The core idea: compute the embedding of each extracted driver, find the centroid of all embeddings, and rank drivers by their cosine distance from the centroid. Drivers far from the centroid represent "outlier" or "blind spot" topics.

```python
import numpy as np

def compute_surprise_scores(driver_names: list[str], embeddings: np.ndarray) -> list[tuple[str, float]]:
    """
    Args:
        driver_names: list of driver name strings
        embeddings: numpy array of shape (n_drivers, embedding_dim)
    Returns:
        list of (driver_name, surprise_score) sorted descending by score
    """
    # Compute centroid (mean embedding = "industry consensus")
    centroid = embeddings.mean(axis=0)

    # Cosine distance from centroid for each driver
    scores = []
    for i, name in enumerate(driver_names):
        vec = embeddings[i]
        cos_sim = np.dot(vec, centroid) / (np.linalg.norm(vec) * np.linalg.norm(centroid))
        surprise = 1.0 - cos_sim  # Higher = more surprising
        scores.append((name, float(surprise)))

    # Sort descending by surprise
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores
```

**How to get embeddings**: Use the same embedding model from the RAG setup. Embed the driver name + description as a single string.

```python
# Using openai SDK directly for embeddings
response = client.embeddings.create(
    model="text-embedding-3-small",  # or deployment name
    input=[f"{d.name}: {d.description}" for d in extracted_drivers]
)
embeddings = np.array([e.embedding for e in response.data])
```

If using ChromaDB default embeddings (local model), use the sentence-transformers library directly:
```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("all-MiniLM-L6-v2")
texts = [f"{d.name}: {d.description}" for d in extracted_drivers]
embeddings = model.encode(texts)
```

### 4e. Display Results

1. **Ranked surprise table**: DataFrame with columns [Rank, Driver, Description, STEEP, TRL, Surprise Score, Sources]. Color-code by surprise score.

2. **Bar chart**: Horizontal bar chart of surprise scores, sorted descending. Color gradient from green (low surprise = consensus) to red (high surprise = blind spot).

3. **2D projection**: UMAP or PCA of driver embeddings, with centroid marked. Color by surprise score. Labels on each point.

```python
# Bar chart
fig, ax = plt.subplots(figsize=(10, 8))
names = [s[0] for s in scores]
values = [s[1] for s in scores]
colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(scores)))
ax.barh(names[::-1], values[::-1], color=colors[::-1])
ax.set_xlabel("Surprise Score (cosine distance from centroid)")
ax.set_title("Technology Drivers by Surprise Score\n(Higher = Potential Blind Spot)")
plt.tight_layout()
```

For the 2D projection (optional but visually compelling):
```python
from sklearn.decomposition import PCA

pca = PCA(n_components=2)
coords = pca.fit_transform(embeddings)
centroid_2d = coords.mean(axis=0)

fig, ax = plt.subplots(figsize=(10, 8))
scatter = ax.scatter(coords[:, 0], coords[:, 1], c=values, cmap="RdYlGn_r", s=100, zorder=5)
ax.scatter(*centroid_2d, marker="X", s=200, c="black", label="Centroid (consensus)")
for i, name in enumerate(names):
    ax.annotate(name, (coords[i,0], coords[i,1]), fontsize=8, ha="left")
ax.legend()
ax.set_title("Driver Embedding Space (PCA)")
plt.colorbar(scatter, label="Surprise Score")
plt.tight_layout()
```

### 4f. Notebook Cell Structure (poc2_rag_surprise.ipynb)

| Cell | Content |
|------|---------|
| 1 | Imports, path setup, load .env |
| 2 | Fetch arxiv papers (arxiv package) |
| 3 | Build LlamaIndex + ChromaDB index from abstracts |
| 4 | Test RAG: query the index with a sample question |
| 5 | Extract technology drivers via LLM structured output |
| 6 | Compute embeddings for extracted drivers |
| 7 | Compute surprise scores |
| 8 | Display ranked table |
| 9 | Display bar chart |
| 10 | Display 2D PCA projection |

---

## 5. Verification Plan

### PoC 1 Verification

1. **Smoke test the LLM client**: Single API call with a trivial structured output (e.g., return a CalendarEvent). Confirms Azure connection + structured output works.

2. **Matrix sanity check**: After LLM fills the matrix, verify:
   - No cell outside [-3, +3]
   - Diagonal blocks (self-impacts within same driver) are zero or correctly handled
   - Print raw matrix and spot-check 2-3 entries against common sense

3. **CIB algorithm unit test**: Create a tiny 2-driver, 2-state matrix by hand where the consistent scenarios are known. Verify `find_consistent_scenarios` returns exactly the expected set.
   ```python
   # Trivial test: 2 drivers, 2 states each
   # Driver A: [a0, a1], Driver B: [b0, b1]
   # Matrix (4 source states x 4 target states):
   # a0->b0=+2, a0->b1=-1, a1->b0=-1, a1->b1=+2
   # b0->a0=+2, b0->a1=-1, b1->a0=-1, b1->a1=+2
   # Consistent: (0,0) and (1,1) -- mutually reinforcing
   ```

4. **Scenario count reasonableness**: With 7 drivers, expect 10-50 consistent scenarios out of ~1,458. If 0 or all are consistent, something is wrong.

5. **Heatmap visual check**: The heatmap should show clear structure (not random noise). Within each target driver's columns, impacts from a source state should show opposing signs (if one state is promoted, another should be inhibited).

### PoC 2 Verification

1. **ArXiv fetch check**: Print count and sample titles. Verify >30 papers fetched, no duplicates.

2. **ChromaDB index check**: After indexing, run `chroma_collection.count()` and verify it matches paper count.

3. **RAG query test**: Ask "What are emerging techniques for spectrum monitoring?" and verify the response cites actual paper titles from the index.

4. **Driver extraction check**: Verify 10-20 drivers returned. Check names are specific (not generic). Check source_papers match actual titles in the index.

5. **Surprise score distribution**: Scores should range from ~0.01 to ~0.15 (not all identical, not wildly spread). If all scores are nearly identical, embeddings might not be diverse enough.

6. **Centroid interpretation**: The lowest-surprise drivers should be "obvious" topics (e.g., "6G channel modeling"). The highest-surprise should be unexpected (e.g., something from the satellite or EW papers that is less mainstream).

---

## 6. Dependencies Between PoCs

The two PoCs are fully independent. Neither requires the other. They share only:
- `src/llm.py` (Azure client wrapper)
- `src/models.py` (Pydantic models -- but each PoC uses different models from this file)
- `.env` (credentials)

They can be developed and tested in any order.

---

## 7. Key Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Azure embedding model not deployed | Use ChromaDB default local embeddings (all-MiniLM-L6-v2) as fallback |
| LLM returns inconsistent impact scores | Add retry logic; validate Pydantic parsing catches malformed responses automatically |
| Too few / too many consistent scenarios | Adjust number of drivers or states; 7 drivers is a sweet spot |
| ArXiv rate limiting | `delay_seconds=3.0` in arxiv client; cache results locally after first fetch |
| LlamaIndex + Azure integration issues | LlamaIndex OpenAI integration uses same base_url pattern; test in cell 1 before building full index |
| Structured output not supported on deployment | Requires gpt-4o version 2024-08-06 or later; check deployment version in Azure portal |

---

## 8. Implementation Sequence

**Phase 1** (get the skeleton running):
1. Create pyproject.toml, .env, .gitignore
2. `uv sync`
3. Write src/llm.py, verify Azure connection works

**Phase 2** (PoC 1 -- can start immediately):
4. Write src/models.py (CIB Pydantic models)
5. Write src/cib.py (algorithm)
6. Unit test CIB with hand-crafted 2x2 matrix
7. Build poc1_cib.ipynb: LLM calls -> matrix -> heatmap -> consistency -> table

**Phase 3** (PoC 2 -- can start immediately, parallel to Phase 2):
8. Build poc2_rag_surprise.ipynb: arxiv fetch -> index -> RAG test -> driver extraction -> surprise scoring -> visualizations

Each phase is ~2-3 hours of focused work for someone familiar with the stack.
