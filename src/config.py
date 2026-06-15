import os
from dotenv import load_dotenv

load_dotenv()

AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_CHAT_DEPLOYMENT = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4.1-mini")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", ".chroma")

MAX_RAG_CHUNKS = 5
BOM_MAX_DEPTH = 5
CIB_SCALE = (-3, 3)
CIB_MODEL = os.environ.get("AZURE_OPENAI_CIB_MODEL", "gpt-4.1")
CIB_MC_SAMPLES = int(os.environ.get("CIB_MC_SAMPLES", "2000"))
CIB_MC_RESTARTS = int(os.environ.get("CIB_MC_RESTARTS", "100"))

EVAL_MODEL = os.environ.get("AZURE_OPENAI_EVAL_MODEL", "gpt-4.1")
SCENARIO_MODEL = os.environ.get("AZURE_OPENAI_SCENARIO_MODEL", "gpt-4.1")
SCENARIO_N_SEEDS = int(os.environ.get("SCENARIO_N_SEEDS", "6"))

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
