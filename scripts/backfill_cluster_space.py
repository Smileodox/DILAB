"""Backfill cluster-space UMAP coordinates onto the combinatorial landscape — additive only.

Computes fresh 2D and 3D UMAP fits on the ORDINAL config matrix (the exact space the archetype
HDBSCAN clusters, same params: n_neighbors=15, euclidean, seed 42) and stamps them as NEW point
fields ox/oy (2D) and ox3/oy3/oz3 (3D) into landscape_state_combi.json. Existing fields
(x/y, cx/cy/cz, archetype, ...) are untouched; a backup copy is written first.

Run:  uv run python scripts/backfill_cluster_space.py  [--outputs-dir data/outputs]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import warnings
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.models.morphological import DriverManifestation, MorphologicalBox  # noqa: E402
from src.pipeline.archetypes import _ordinal_matrix  # noqa: E402

UMAP_PARAMS = {"n_neighbors": 15, "metric": "euclidean", "seed": 42}


def umap_project(x, n_components: int, seed: int = 42):
    # same params as the clustering step (src/pipeline/clustering.py hdbscan_cluster)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import umap
        return umap.UMAP(n_neighbors=UMAP_PARAMS["n_neighbors"], n_components=n_components,
                         metric=UMAP_PARAMS["metric"], random_state=seed).fit_transform(x)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--outputs-dir", type=Path, default=REPO / "data" / "outputs")
    args = ap.parse_args()
    out = args.outputs_dir

    landscape_path = out / "landscape_state_combi.json"
    landscape = json.loads(landscape_path.read_text())
    configs = json.loads((out / "combinatorial_state.json").read_text())["configs"]
    mb = json.loads((out / "morphbox_state.json").read_text())
    box = MorphologicalBox(
        drivers=mb["drivers"],
        manifestations=mb["manifestations"],
        all_manifestations=[DriverManifestation(**m) for m in mb["all_manifestations"]],
    )

    points = landscape["points"]
    if len(points) != len(configs) or any(
        p.get("seed_id") != c.get("id") for p, c in zip(points, configs)
    ):
        raise SystemExit("landscape points and combinatorial configs are not index-aligned — abort")

    x = _ordinal_matrix(configs, box)
    emb2 = umap_project(x, 2)
    emb3 = umap_project(x, 3)
    print(f"ordinal matrix {x.shape} -> UMAP 2D {emb2.shape} + 3D {emb3.shape}")

    backup = landscape_path.with_suffix(".json.bak-preordinal")
    shutil.copy2(landscape_path, backup)
    print(f"backup: {backup}")

    for i, p in enumerate(points):
        p["ox"] = round(float(emb2[i, 0]), 4)
        p["oy"] = round(float(emb2[i, 1]), 4)
        p["ox3"] = round(float(emb3[i, 0]), 4)
        p["oy3"] = round(float(emb3[i, 1]), 4)
        p["oz3"] = round(float(emb3[i, 2]), 4)

    landscape.setdefault("metadata", {})["ordinal_umap"] = {
        **UMAP_PARAMS,
        "source": "ordinal config matrix (same space as archetype HDBSCAN, fresh 2D/3D fits)",
        "fields": ["ox", "oy", "ox3", "oy3", "oz3"],
    }
    landscape_path.write_text(json.dumps(landscape, indent=2))
    print(f"stamped ox/oy + ox3/oy3/oz3 on {len(points)} points -> {landscape_path}")


if __name__ == "__main__":
    main()
