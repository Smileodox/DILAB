"""Multi-lens geometry check — are we measuring the scenario field's structure the wrong way?

The default verdict (structure.py) uses KMeans + silhouette on the ONE-HOT config space. That
assumes spherical clusters. This script looks through additional windows on the SAME 120
combinatorial configs + their narratives (no new pipeline run) to test whether structure exists
that the default lens misses:

  A. one-hot config  + KMeans-silhouette      (the current default — baseline)
  B. ORDINAL config  + KMeans-silhouette      (keeps manifestation ordering; gradient-friendly)
  C. one-hot config  + UMAP->HDBSCAN          (density-based; non-spherical/manifold clusters)
  D. ordinal config  + UMAP->HDBSCAN
  E. narrative embeddings + UMAP->HDBSCAN      (BERTopic's clustering core; semantic space)
     + raw pairwise cosine (the "same-domain text collapses to ~0.9" check)

If every lens says "no clusters", the continuum verdict is multi-method robust. If one disagrees,
we've found structure the default hides.

Run:  uv run python scripts/geometry_triangulation.py
"""
from __future__ import annotations

import json
import os
import sys
import warnings

import numpy as np

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import hdbscan
import umap
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

CONFIGS = json.load(open("data/outputs/combinatorial_state.json"))["configs"]
MB = json.load(open("data/outputs/morphbox_state.json"))
DRIVERS = MB["drivers"]
MANIFS = MB["manifestations"]  # driver_id -> [manifestation_id, ...] ordered optimistic→pessimistic
VOCAB = [m for d in DRIVERS for m in MANIFS[d]]
VIDX = {m: i for i, m in enumerate(VOCAB)}


def onehot(cfg):
    v = np.zeros(len(VOCAB))
    for mid in cfg["configuration"].values():
        if mid in VIDX:
            v[VIDX[mid]] = 1.0
    return v


def ordinal(cfg):
    v = np.zeros(len(DRIVERS))
    for i, d in enumerate(DRIVERS):
        mid = cfg["configuration"].get(d)
        ms = MANIFS[d]
        if mid in ms:
            v[i] = ms.index(mid) / (len(ms) - 1) if len(ms) > 1 else 0.5
    return v


def kmeans_sil(X, krange=(2, 10)):
    best, bestk = -1.0, None
    for k in range(krange[0], min(krange[1], len(X) - 1) + 1):
        lab = KMeans(k, n_init=10, random_state=42).fit_predict(X)
        if len(set(lab)) > 1:
            s = silhouette_score(X, lab)
            if s > best:
                best, bestk = s, k
    return round(best, 4), bestk


def umap_hdbscan(X, min_cluster_size=5, n_components=5):
    emb = umap.UMAP(n_neighbors=15, n_components=min(n_components, X.shape[1]),
                    metric="euclidean", random_state=42).fit_transform(X)
    lab = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size).fit_predict(emb)
    n_clusters = len(set(lab)) - (1 if -1 in lab else 0)
    n_noise = int((lab == -1).sum())
    mask = lab != -1
    sil = None
    if n_clusters > 1 and mask.sum() > n_clusters:
        sil = round(float(silhouette_score(emb[mask], lab[mask])), 4)
    return n_clusters, n_noise, sil


X1 = np.array([onehot(c) for c in CONFIGS])
Xo = np.array([ordinal(c) for c in CONFIGS])

print(f"n_configs={len(CONFIGS)}  vocab={len(VOCAB)}  drivers={len(DRIVERS)}\n")

print("=== CONFIG-SPACE LENSES ===")
s1, k1 = kmeans_sil(X1)
print(f"A. one-hot + KMeans  : best_silhouette={s1} (k={k1})   [current default]")
so, ko = kmeans_sil(Xo)
print(f"B. ordinal + KMeans  : best_silhouette={so} (k={ko})")
c1 = umap_hdbscan(X1)
print(f"C. one-hot + UMAP/HDBSCAN : clusters={c1[0]} noise={c1[1]} silhouette={c1[2]}")
co = umap_hdbscan(Xo)
print(f"D. ordinal + UMAP/HDBSCAN : clusters={co[0]} noise={co[1]} silhouette={co[2]}")

print("\n=== NARRATIVE / SEMANTIC LENS (BERTopic core) ===")
try:
    scen = json.load(open("data/outputs/scenario_state_combi.json"))["scenarios"]
    texts = [s.get("narrative", "")[:2000] for s in scen if s.get("narrative")]
    from src.llm import embed
    E = np.array(embed(texts))
    # raw same-domain cosine
    En = E / (np.linalg.norm(E, axis=1, keepdims=True) + 1e-10)
    sim = En @ En.T
    off = sim[np.triu_indices(len(E), k=1)]
    print(f"narratives={len(E)}  pairwise cosine: mean={off.mean():.3f} min={off.min():.3f} max={off.max():.3f}")
    e = umap_hdbscan(E, n_components=5)
    print(f"E. narrative embed + UMAP/HDBSCAN : clusters={e[0]} noise={e[1]} silhouette={e[2]}")
except Exception as ex:  # noqa: BLE001
    print(f"narrative lens skipped: {ex}")

print("\nFloor for 'usable clusters' = 0.25 silhouette. Synthetic coupled control = 0.72.")
