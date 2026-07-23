"""Backfill the PCA projection into landscape_state_combi.json.

The 2026-07-08 full run's projection step failed and run_combinatorial.py swallowed the
traceback, so the combinatorial landscape shipped without axes/parcoords/structure-verdict.
This re-runs src.pipeline.projection.project_config on the persisted artifacts and merges
the result in WITHOUT touching structure.lenses/floor (written by the multi-method stage).

Usage: uv run python scripts/backfill_projection.py
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipeline import projection  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "data" / "outputs"


def main() -> None:
    scenarios = json.loads((OUT / "scenario_state_combi.json").read_text())["scenarios"]
    morph = json.loads((OUT / "morphbox_state.json").read_text())
    merge = json.loads((OUT / "merge_state.json").read_text())
    dnames = {d["id"]: d.get("name", d["id"]) for d in merge.get("unified_drivers", [])}

    proj = projection.project_config(scenarios, morph, driver_names=dnames, seed=42)

    landscape_path = OUT / "landscape_state_combi.json"
    shutil.copy2(landscape_path, landscape_path.with_suffix(".json.bak"))
    landscape = json.loads(landscape_path.read_text())

    for pt in landscape.get("points", []):
        xy = proj["coords"].get(pt["scenario_id"])
        if xy:
            pt["cx"], pt["cy"] = xy

    # Preserve the multi-method lens comparison already in the artifact.
    old_structure = landscape.get("structure", {})
    merged_structure = {**proj["structure"]}
    for key in ("lenses", "floor"):
        if key in old_structure:
            merged_structure[key] = old_structure[key]
    landscape["structure"] = merged_structure
    landscape["axes"] = proj["axes"]
    landscape["parcoords"] = proj["parcoords"]

    landscape_path.write_text(json.dumps(landscape, indent=2))

    n_cx = sum(1 for p in landscape["points"] if "cx" in p)
    print(f"backfilled: {n_cx}/{len(landscape['points'])} points with PCA coords")
    print(f"axes: pc1={proj['axes']['pc1']['label']!r} ({proj['axes']['pc1']['share']:.0%}), "
          f"pc2={proj['axes']['pc2']['label']!r} ({proj['axes']['pc2']['share']:.0%})")
    print(f"structure verdict: {proj['structure'].get('verdict')} "
          f"(pc1_share={proj['structure'].get('pc1_share')}, "
          f"silhouette={proj['structure'].get('best_silhouette')})")
    print(f"parcoords rows: {len(proj['parcoords'].get('rows', []))}, "
          f"lenses preserved: {'lenses' in landscape['structure']}")


if __name__ == "__main__":
    main()
