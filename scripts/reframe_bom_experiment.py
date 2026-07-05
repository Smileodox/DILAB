"""DECISIVE TEST — can the BOM be REFRAMED to produce scenario structure? (Delphi option C)

The claim on trial: "BOM is bad because components are complementary sliders." The systems
engineer argued this is an artifact of extracting components WITHOUT their architectural forks —
add the budget-driven competing directions and BOM should behave like the functional path.

This re-extracts the SAME datasheet-grounded BOM/component drivers as competing ARCHITECTURAL
directions (product-pool RAG + the functional DIRECTIONS_EXTRACT prompt that forbids levels and
demands mutually-exclusive paradigms), then runs the EXACT referees the functional path faced:
absolute+contrastive CCA -> auto-calibrated sampling -> null-model structure test -> the
axis-DIRECTION-stability test.

Decision rule (a priori):
  >= 2 direction-stable axes (|cos|>=0.7 across elicitations) -> BOM IS fixable (option C works).
  <= 1                                                        -> confirms diffuse futures (3rd method).
"""
import json, os, random, sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.llm import safe_chat_json
from src.models.morphological import DriverManifestation, MorphologicalBox
from src.pipeline import domain, functional, structure
from src.pipeline.clustering import config_matrix
from src.prompts.functional import DIRECTIONS_EXTRACT
from src.rag import format_rag_chunks, get_collection, retrieve

D = "data/outputs/"
profile = domain.load_profile()
pkw = profile.prompt_kwargs()
coll = get_collection()

# 1. Datasheet-grounded BOM/component drivers.
md = json.load(open(D + "merge_state.json"))["unified_drivers"]
comps = [d for d in md if d.get("origin") in ("bom", "both")
         or d.get("dimension_type") in ("hardware", "software")][:12]
print(f"Reframing {len(comps)} datasheet-grounded BOM/component drivers into architectural directions\n", flush=True)


def reframe(d):
    """Extract competing architectural DIRECTIONS for one BOM component (product-pool grounded)."""
    q = f"{d['name']} {d['description'][:100]} competing architectures paradigms alternatives design trade-offs"
    rag = ""
    try:
        rag = format_rag_chunks(retrieve(coll, q, pool="product", n=5))
    except Exception:
        pass
    res = safe_chat_json(DIRECTIONS_EXTRACT.format(
        function_name=d["name"], function_description=d["description"][:300], rag_chunks=rag, **pkw),
        temperature=0.5, model="gpt-5.4")
    out = []
    for x in res.get("directions", []):
        if x.get("label"):
            out.append(DriverManifestation(driver_id=d["id"], label=x["label"],
                       description=x.get("description", ""),
                       plausibility=x.get("plausibility", "medium") if x.get("plausibility") in ("high", "medium", "low") else "medium"))
    return d, out


manifs, allm, kept = {}, [], []
with ThreadPoolExecutor(max_workers=6) as pool:
    for f in as_completed([pool.submit(reframe, d) for d in comps]):
        d, dirs = f.result()
        if len(dirs) >= 2:  # a real morphological dimension needs >=2 competing directions
            manifs[d["id"]] = [m.id for m in dirs]
            allm.extend(dirs)
            kept.append(d)

morph = MorphologicalBox(drivers=[d["id"] for d in kept], manifestations=manifs, all_manifestations=allm)
name_by = {d["id"]: d["name"] for d in kept}
manif_by = {m.id: m for m in allm}
rawbox = {"drivers": morph.drivers, "manifestations": morph.manifestations,
          "all_manifestations": [m.model_dump(mode="json") for m in allm]}
json.dump(rawbox, open(D + "morphbox_bom_reframe.json", "w"), indent=2)
print(f"{len(kept)}/{len(comps)} components yielded >=2 competing directions; {len(allm)} directions total")
for d in kept:
    print(f"  {name_by[d['id']][:34]:34s}: " + " | ".join(manif_by[m].label[:26] for m in manifs[d['id']]))
if len(kept) < 3:
    print("\nToo few forking components — BOM cannot even be reframed into a morphological field. Verdict: NOT fixable.")
    sys.exit(0)

# 2. CCA under both elicitations.
print("\nScoring CCA (absolute + contrastive) ...", flush=True)
cca_abs = functional.assess_cca(morph, manif_by, name_by, model="gpt-5.4", mode="absolute", profile=profile)
cca_con = functional.assess_cca(morph, manif_by, name_by, model="gpt-5.4", mode="contrastive", profile=profile)
json.dump({"absolute": cca_abs, "contrastive": cca_con}, open(D + "cca_bom_reframe.json", "w"), indent=2)


def hard_set(c):
    return {frozenset((a, b)) for a, row in c.items() for b, v in row.items() if v <= -2}
abs_hard = hard_set(cca_abs)
robust = {a: dict(row) for a, row in cca_con.items()}
for a, row in list(robust.items()):
    for b, v in list(row.items()):
        if v <= -2 and frozenset((a, b)) not in abs_hard:
            robust[a][b] = 0


def cca_stats(c):
    seen, sc = set(), []
    for a, row in c.items():
        for b, v in row.items():
            k = frozenset((a, b))
            if k not in seen:
                seen.add(k); sc.append(v)
    return len(sc), sum(1 for s in sc if s < 0), sum(1 for s in sc if s <= -2), round(sum(sc) / len(sc), 3)
for lbl, c in [("absolute", cca_abs), ("contrastive", cca_con)]:
    n, neg, hard, mean = cca_stats(c)
    print(f"  {lbl}: {n} pairs | neg {neg} ({100*neg/n:.0f}%) | hard(-2) {hard} | mean {mean:+.2f}")

# 3. Null-model structure test on the contrastive field.
cfgs = functional.sample_consistent(morph, cca_con, 120, reject_threshold=None, seed=42)
scens = structure.configs_to_scenarios([c.model_dump(mode="json") for c in cfgs])
res = structure.analyze(scens, rawbox, null_trials=30, seed=42)
o, z = res["observed"], res["z_scores"]
print(f"\nNULL TEST (contrastive, auto-calibrated): kept {len(cfgs)}")
print(f"  silhouette={o['best_silhouette']} (z={z['best_silhouette']}) | eff_dim={o['effective_dim']} (z={z['effective_dim']}) | pc1={o['pc1']} (z={z['pc1']})")
print(f"  -> {res['verdict']}")

# 4. Axis-DIRECTION stability (the referee that broke the functional axis).
vocab = [m["id"] for m in rawbox["all_manifestations"]]


def loadings(cca, seed, k=3):
    cf = functional.sample_consistent(morph, cca, 120, reject_threshold=None, seed=seed)
    sc = [{"assumptions": [{"manifestation_id": m} for m in c.configuration.values()]} for c in cf]
    x = config_matrix(sc, vocab).astype(float)
    xc = x - x.mean(axis=0, keepdims=True)
    _, _, vt = np.linalg.svd(xc, full_matrices=False)
    return vt[:k]


Lc1, Lc2 = loadings(cca_con, 42), loadings(cca_con, 7)
Lr, La = loadings(robust, 42), loadings(cca_abs, 42)
cos = lambda A, B: [round(abs(float(A[i] @ B[i])), 3) for i in range(min(len(A), len(B)))]
print("\nAXIS-DIRECTION STABILITY (|cos| of PC loadings, bar 0.70):   PC1   PC2   PC3")
print("  within-contrastive reseed (CEILING) :", cos(Lc1, Lc2))
print("  contrastive vs robust               :", cos(Lc1, Lr))
print("  robust vs absolute                  :", cos(Lr, La))
npass = sum(1 for i in range(3) if len(Lr) > i and abs(float(Lc1[i] @ Lr[i])) >= 0.7 and abs(float(Lr[i] @ La[i])) >= 0.7)
print(f"\nDirection-stable axes (|cos|>=0.7 across BOTH elicitation steps): {npass}")
print("VERDICT:", ">=2 -> BOM IS FIXABLE (option C works, I was wrong)" if npass >= 2
      else "<=1 -> BOM reframe does NOT rescue structure; confirms DIFFUSE futures from a 3rd method")
