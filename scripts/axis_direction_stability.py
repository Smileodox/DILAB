"""Decisive experiment (red-team's proposal): is the scenario AXIS DIRECTION elicitation-stable,
or only its magnitude? The invariance test (robust_cca_confirm.py) checked scalar stats stay above
null; it never checked that the PC loading vector (WHICH drivers define the axis) is stable across
elicitations. If the field is near-isotropic (pc1~=pc2), the leading PCs are degenerate and their
direction is ill-defined — so a 'central<->edge axis' interpretation would be a reseed/elicitation
artifact, not a robust finding. Offline, no LLM, |cos| (sign-invariant), a-priori bar |cos|>=0.7.
"""
import json, os, random, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.models.morphological import DriverManifestation, MorphologicalBox
from src.pipeline import functional
from src.pipeline.clustering import config_matrix

D = "data/outputs/"
raw = json.load(open(D + "morphbox_zwicky_state.json"))
morph = MorphologicalBox(drivers=raw["drivers"], manifestations=raw["manifestations"],
    all_manifestations=[DriverManifestation(**m) for m in raw["all_manifestations"]])
vocab = [m["id"] for m in raw["all_manifestations"]]
absolute = json.load(open(D + "cca_state.json"))["cca"]
contrastive = json.load(open(D + "cca_state_contrastive.json"))["cca"]

def hard_set(cca):
    return {frozenset((a, b)) for a, row in cca.items() for b, v in row.items() if v <= -2}
abs_hard = hard_set(absolute)
robust = {a: dict(row) for a, row in contrastive.items()}          # contrastive minus fabricated hard pairs
for a, row in list(robust.items()):
    for b, v in list(row.items()):
        if v <= -2 and frozenset((a, b)) not in abs_hard:
            robust[a][b] = 0

def loadings(cca, seed, k=3):
    """Top-k PC loading vectors (unit, 36-dim) of the sampled one-hot config field."""
    cfgs = functional.sample_consistent(morph, cca, 120, reject_threshold=None, seed=seed)
    scens = [{"assumptions": [{"manifestation_id": m} for m in c.configuration.values()]} for c in cfgs]
    x = config_matrix(scens, vocab).astype(float)
    xc = x - x.mean(axis=0, keepdims=True)
    _, sv, vt = np.linalg.svd(xc, full_matrices=False)
    shares = (sv**2) / (sv**2).sum()
    return vt[:k], shares[:k]

Lc1, sh = loadings(contrastive, 42);  Lc2, _ = loadings(contrastive, 7)   # reseed = the ceiling
Lr, shr = loadings(robust, 42)
La, sha = loadings(absolute, 42)

def cosrow(A, B):
    return [round(abs(float(A[i] @ B[i])), 3) for i in range(len(A))]

print("PC variance shares: contrastive", [round(float(s),3) for s in sh],
      "| robust", [round(float(s),3) for s in shr], "| absolute", [round(float(s),3) for s in sha])
print("(pc1~=pc2 => near-degenerate leading PCs => direction ill-defined)\n")
print("|cos| of PC loading vectors (a-priori 'same axis' bar = 0.70):   PC1    PC2    PC3")
print(" within-contrastive (reseed 42 vs 7)  = CEILING :", cosrow(Lc1, Lc2))
print(" contrastive vs robust (strip fabricated)        :", cosrow(Lc1, Lr))
print(" robust vs absolute (vs honest elicitation)      :", cosrow(Lr, La))
print(" contrastive vs absolute                         :", cosrow(Lc1, La))
n_pass = sum(1 for i in range(3) if abs(float(Lc1[i] @ Lr[i])) >= 0.7 and abs(float(Lr[i] @ La[i])) >= 0.7)
print(f"\nAxes passing direction-stability across BOTH elicitation steps at |cos|>=0.7: {n_pass}")
print("Decision rule: >=2 pass -> multi-axis D earned | exactly 1 -> B | 0 clean -> B with caveats")