"""Run the cross-function collinearity diagnostic on the functional/Zwicky morphbox.

Cause-side test: does the functional field's weak continuum come from the functions being
collinear (one latent axis measured N times)? Prints latent-axis count + collinear groups.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.pipeline.collinearity import analyze_collinearity

DATA = "data/outputs"
morph = json.load(open(os.path.join(DATA, "morphbox_zwicky_state.json")))
try:
    merge = json.load(open(os.path.join(DATA, "functional_merge_state.json")))
    name_by_fid = {d["id"]: d.get("name", d["id"]) for d in merge.get("unified_drivers", [])}
except Exception:
    name_by_fid = {}

n_funcs = len(morph["drivers"])
n_manif = len(morph["all_manifestations"])
print(f"Functional morphbox: {n_funcs} functions, {n_manif} directions\n", flush=True)

stats = analyze_collinearity(morph, name_by_fid=name_by_fid, sim_threshold=0.5)

print(f"latent_axes (participation ratio): {stats['latent_axes']}  of {stats['kept_functions']} functions")
print(f"mean |cos| between function axes:  {stats['mean_abs_cos']}")
print(f"axis groups (|cos|>=0.5): {stats['n_axis_groups']}  | largest collinear group: {stats['largest_group']}\n")
if stats["group_names"]:
    print("Collinear function groups (collapse onto one axis):")
    for g in stats["group_names"]:
        print(f"  - {g}")
else:
    print("No collinear groups at threshold 0.5 — functions are distinct axes.")

print("\nINTERPRETATION:")
la, nf = stats["latent_axes"], stats["kept_functions"]
if nf and la < 0.35 * nf:
    print(f"  latent_axes {la} << {nf} functions → STRONG collinearity: the field is ~{round(la)} axis(es)")
    print("  measured many times. The weak continuum is (partly) this artifact → act on it (Part A step 2).")
elif nf and la > 0.7 * nf:
    print(f"  latent_axes {la} ≈ {nf} functions → functions are genuinely distinct concerns.")
    print("  Collinearity is NOT the artifact; the continuum (if any) is closer to the domain truth.")
else:
    print(f"  latent_axes {la} vs {nf} functions → partial collinearity; some functions collapse.")
