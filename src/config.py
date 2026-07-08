import os
from dotenv import load_dotenv

load_dotenv()

AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_CHAT_DEPLOYMENT = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-5.4")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", ".chroma")

MAX_RAG_CHUNKS = 5
BOM_MAX_DEPTH = 5
CIB_SCALE = (-3, 3)
CIB_MODEL = os.environ.get("AZURE_OPENAI_CIB_MODEL", "gpt-4.1")
CIB_MC_SAMPLES = int(os.environ.get("CIB_MC_SAMPLES", "2000"))
CIB_MC_RESTARTS = int(os.environ.get("CIB_MC_RESTARTS", "100"))
# Elicitation mode for the CIB matrix. "absolute" is the legacy prompt (mildly positive-biased).
# "contrastive" is a de-biased, SYMMETRIC prompt that weighs competition and enablement equally.
# Default stays "absolute" until the de-biased variant is validated downstream on the null-model
# structure verdict (an earlier tension-primed draft over-corrected to ~71% negative).
CIB_MODE = os.environ.get("CIB_MODE", "absolute")
# When on, CIB panel aggregation preserves a strong minority dissent (net <= -2) instead of
# median-washing trade-offs to ~0/positive — a low-cost backstop against the positivity bias.
# Default OFF so the test suite and legacy runs are unchanged; enable via CIB_DISSENT_PRESERVING=1.
CIB_DISSENT_PRESERVING = os.environ.get("CIB_DISSENT_PRESERVING", "").lower() in ("1", "true", "yes", "on")

EVAL_MODEL = os.environ.get("AZURE_OPENAI_EVAL_MODEL", "gpt-4.1")
SCENARIO_MODEL = os.environ.get("AZURE_OPENAI_SCENARIO_MODEL", "gpt-4.1")
SCENARIO_N_SEEDS = int(os.environ.get("SCENARIO_N_SEEDS", "6"))

# --- Domain abstraction (KB-agnostic foresight) ---
# The pipeline derives a DomainProfile from the docked KB and injects it into neutral
# prompt templates (no hardwired domain). These optionally OVERRIDE the derived framing
# (hybrid: derive first, then let the user pin values per domain). "" = derive from KB.
DOMAIN_PROFILE_PATH = os.path.join("data", "outputs", "domain_profile.json")
DOMAIN_LABEL = os.environ.get("DOMAIN_LABEL", "")          # force the domain label
DOMAIN_HORIZON = os.environ.get("DOMAIN_HORIZON", "")      # e.g. "2035"
DOMAIN_ACTOR = os.environ.get("DOMAIN_ACTOR", "")          # e.g. "Rohde & Schwarz"
DOMAIN_MODEL = os.environ.get("AZURE_OPENAI_DOMAIN_MODEL", "gpt-5.4")  # profiling model

# --- Combinatorial scenario method (Soft-CIB + embedding clustering) ---
# Alternative to the CIB fixed-point path: sample the morphological field broadly,
# use the CIB matrix only as a soft consistency filter (reject only strongly
# contradictory combinations), generate short narratives, cluster them in embedding
# space and pick one representative per cluster. Coexists with the baseline path.
COMBI_N_SAMPLES = int(os.environ.get("COMBI_N_SAMPLES", "120"))          # target kept combinations
COMBI_OVERSAMPLE_FACTOR = float(os.environ.get("COMBI_OVERSAMPLE_FACTOR", "4.0"))  # draw N x this before rejection
# Calibrated on the real 14-driver CIB: random configs have a contradiction_ratio of
# ~0.19..0.60 (median ~0.42). 0.40 keeps the more-consistent ~38% (rejects the
# contradictory majority) and reaches the N target with the oversample factor above.
COMBI_REJECT_THRESHOLD = float(os.environ.get("COMBI_REJECT_THRESHOLD", "0.40"))   # max contradiction_ratio to keep
COMBI_N_CLUSTERS = int(os.environ.get("COMBI_N_CLUSTERS", "0"))          # 0 = auto-select k by silhouette
COMBI_CLUSTER_K_MIN = int(os.environ.get("COMBI_CLUSTER_K_MIN", "4"))
COMBI_CLUSTER_K_MAX = int(os.environ.get("COMBI_CLUSTER_K_MAX", "10"))
COMBI_CLUSTER_K_RANGE = (COMBI_CLUSTER_K_MIN, COMBI_CLUSTER_K_MAX)
COMBI_NARRATIVE_WORDS = os.environ.get("COMBI_NARRATIVE_WORDS", "250-300")
COMBI_SEED = int(os.environ.get("COMBI_SEED", "42"))

# --- Evidence-grounded pointwise evaluation (scenario auditor) ---
# The evaluation stage scores each scenario in its own bounded prompt against a per-scenario
# evidence budget (its own chunks + driver chunks + "stress" RAG chunks), extracting facts
# before scoring to counter LLM positivity bias. These knobs cap the evidence context (fixed
# per scenario so narrative length cannot bias the score) and the CIB relationships injected.
MAX_EVIDENCE_CHUNKS_PER_SCENARIO = int(os.environ.get("MAX_EVIDENCE_CHUNKS_PER_SCENARIO", "6"))
MAX_EVIDENCE_CHARS_PER_CHUNK = int(os.environ.get("MAX_EVIDENCE_CHARS_PER_CHUNK", "700"))
TARGET_SCENARIO_EVIDENCE_CHUNKS = int(os.environ.get("TARGET_SCENARIO_EVIDENCE_CHUNKS", "2"))
TARGET_DRIVER_EVIDENCE_CHUNKS = int(os.environ.get("TARGET_DRIVER_EVIDENCE_CHUNKS", "2"))
TARGET_STRESS_EVIDENCE_CHUNKS = int(os.environ.get("TARGET_STRESS_EVIDENCE_CHUNKS", "2"))
CIB_RELEVANCE_THRESHOLD = int(os.environ.get("CIB_RELEVANCE_THRESHOLD", "2"))     # |score| >= this counts
MAX_CIB_RELATIONSHIPS_PER_SCENARIO = int(os.environ.get("MAX_CIB_RELATIONSHIPS_PER_SCENARIO", "6"))

MCDA_CRITERIA = ["impact", "probability", "actionability", "time_horizon", "risk_severity"]

# AHP pairwise comparison matrix (5x5).
# Order matches MCDA_CRITERIA. Value a[i][j] = importance of criterion i vs j.
# 1=equal, 3=moderate, 5=strong, 7=very strong, 9=extreme. a[j][i] = 1/a[i][j].
# Encodes: Impact > Probability >= Risk Severity > Time Horizon > Actionability.
MCDA_PAIRWISE_DEFAULT: list[list[float]] = [
    [1,     2,     3,     2,     2    ],  # impact
    [1/2,   1,     2,     2,     1    ],  # probability
    [1/3,   1/2,   1,     1,     1/2  ],  # actionability
    [1/2,   1/2,   1,     1,     1    ],  # time_horizon
    [1/2,   1,     2,     1,     1    ],  # risk_severity
]

MCDA_CR_THRESHOLD = 0.10

# Multi-endpoint pool for rate limit distribution
AZURE_ENDPOINTS: list[dict] = []

def _build_endpoint_pool():
    pool = []
    if AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY:
        pool.append({
            "endpoint": AZURE_OPENAI_ENDPOINT,
            "api_key": AZURE_OPENAI_API_KEY,
            "api_version": AZURE_OPENAI_API_VERSION,
        })
    i = 2
    while True:
        ep = os.environ.get(f"AZURE_OPENAI_ENDPOINT_{i}", "")
        key = os.environ.get(f"AZURE_OPENAI_API_KEY_{i}", "")
        if not ep or not key:
            break
        pool.append({
            "endpoint": ep,
            "api_key": key,
            "api_version": os.environ.get(f"AZURE_OPENAI_API_VERSION_{i}", AZURE_OPENAI_API_VERSION),
        })
        i += 1
    return pool

AZURE_ENDPOINTS = _build_endpoint_pool()
