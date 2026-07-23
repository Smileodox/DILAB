"""Cluster-space preview — standalone HTML, side-by-side check of viz geometry vs clustering geometry.

The archetype step clusters HDBSCAN on a 5D UMAP of the ORDINAL config matrix, but the official
landscape views plot a different geometry (PCA / legacy UMAP of the one-hot matrix). This script
renders both next to each other so the gap can be judged by eye, WITHOUT touching any official
artifact or frontend code:

  Panel A  official 2D PCA (cx/cy)                — what the app shows today
  Panel B  fresh 2D UMAP on the ordinal matrix    — the space HDBSCAN actually clustered
  Panel C  official 3D PCA (cx/cy/cz)
  Panel D  fresh 3D UMAP on the ordinal matrix

Panels B/D dim the Continuum halo, draw convex hulls (2D) and median centroids with archetype
names. Reads data/outputs/ read-only; writes a single self-contained HTML.

Run:  uv run python scripts/make_cluster_space_preview.py
      [--outputs-dir data/outputs] [--out viz_preview/cluster_space_preview.html]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import warnings
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.models.morphological import DriverManifestation, MorphologicalBox  # noqa: E402
from src.pipeline.archetypes import _ordinal_matrix  # noqa: E402

PLOTLY_JS = REPO / "web/frontend/node_modules/plotly.js-dist-min/plotly.min.js"
PLOTLY_CDN = "https://cdn.plot.ly/plotly-3.6.0.min.js"

# mirror web/frontend/src/utils/colors.js — color index = position in the SORTED label set
ARCHETYPE_PALETTE = ["#5B8FF9", "#61DDAA", "#F6BD16", "#F08BB4", "#7262FD",
                     "#78D3F8", "#F6903D", "#008685", "#D95040", "#9FB40F"]
CONTINUUM = "Continuum"
CONTINUUM_COLOR = "#6b7280"
FONT = "Inter, system-ui, sans-serif"
GRID = "rgba(161,161,170,0.1)"
ZEROLINE = "rgba(161,161,170,0.2)"
HOVERLABEL = {"bgcolor": "#18181b", "bordercolor": "#3f3f46",
              "font": {"color": "#e4e4e7", "family": FONT, "size": 12}}


def load_artifacts(outputs_dir: Path):
    landscape = json.loads((outputs_dir / "landscape_state_combi.json").read_text())
    configs = json.loads((outputs_dir / "combinatorial_state.json").read_text())["configs"]
    mb = json.loads((outputs_dir / "morphbox_state.json").read_text())
    box = MorphologicalBox(
        drivers=mb["drivers"],
        manifestations=mb["manifestations"],
        all_manifestations=[DriverManifestation(**m) for m in mb["all_manifestations"]],
    )
    points = landscape["points"]
    if len(points) != len(configs):
        raise SystemExit(f"points ({len(points)}) and configs ({len(configs)}) differ in length")
    misaligned = [i for i, (p, c) in enumerate(zip(points, configs)) if p.get("seed_id") != c.get("id")]
    if misaligned:
        raise SystemExit(f"landscape points and combinatorial configs are not index-aligned "
                         f"(first mismatch at index {misaligned[0]})")
    return landscape, points, configs, box


def umap_project(x: np.ndarray, n_components: int, seed: int = 42) -> np.ndarray:
    # same params as the clustering step (src/pipeline/clustering.py hdbscan_cluster)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import umap
        return umap.UMAP(n_neighbors=15, n_components=n_components,
                         metric="euclidean", random_state=seed).fit_transform(x)


def hex_to_rgba(hex_color: str, alpha: float) -> str:
    n = int(hex_color.lstrip("#"), 16)
    return f"rgba({(n >> 16) & 255},{(n >> 8) & 255},{n & 255},{alpha})"


def group_by_archetype(points: list[dict]):
    named = sorted({p.get("archetype") for p in points
                    if p.get("archetype") and p.get("archetype") != CONTINUUM})
    groups: dict[str, list[int]] = {label: [] for label in [CONTINUUM, *named]}
    for i, p in enumerate(points):
        label = p.get("archetype") or CONTINUUM
        groups.setdefault(label if label in groups else CONTINUUM, []).append(i)
    return named, groups


def color_for(label: str, named: list[str]) -> str:
    if label == CONTINUUM or label not in named:
        return CONTINUUM_COLOR
    return ARCHETYPE_PALETTE[named.index(label) % len(ARCHETYPE_PALETTE)]


def finite_coords(points: list[dict], keys: tuple[str, ...]) -> dict[int, tuple[float, ...]]:
    out: dict[int, tuple[float, ...]] = {}
    for i, p in enumerate(points):
        vals = [p.get(k) for k in keys]
        if all(isinstance(v, (int, float)) and math.isfinite(v) for v in vals):
            out[i] = tuple(float(v) for v in vals)
    return out


def hover_text(p: dict, label: str) -> str:
    cons = p.get("consistency_score")
    cons = f"{cons:g}" if isinstance(cons, (int, float)) else "–"
    return f"<b>{p.get('title', '?')}</b><br>{label}<br>Konsistenz: {cons}"


def hull_trace(xy: np.ndarray, color: str):
    if len(xy) < 3:
        return None
    from scipy.spatial import ConvexHull, QhullError
    try:
        hull = ConvexHull(xy)
    except QhullError:
        return None
    vx = xy[hull.vertices, 0].tolist()
    vy = xy[hull.vertices, 1].tolist()
    return {"type": "scatter", "x": vx + [vx[0]], "y": vy + [vy[0]],
            "mode": "lines", "fill": "toself",
            "fillcolor": hex_to_rgba(color, 0.08),
            "line": {"color": hex_to_rgba(color, 0.35), "width": 1},
            "hoverinfo": "skip", "showlegend": False}


def traces_2d(coords: dict[int, tuple], points: list[dict], groups: dict[str, list[int]],
              named: list[str], *, dim_noise: bool, hulls: bool) -> list[dict]:
    traces: list[dict] = []
    order = [CONTINUUM, *named]

    if hulls:
        for label in named:
            idxs = [i for i in groups[label] if i in coords]
            t = hull_trace(np.array([coords[i][:2] for i in idxs]), color_for(label, named)) \
                if len(idxs) >= 3 else None
            if t:
                traces.append(t)

    for label in order:
        idxs = [i for i in groups.get(label, []) if i in coords]
        if not idxs:
            continue
        color = color_for(label, named)
        if label == CONTINUUM:
            alpha, size = (0.18, 4) if dim_noise else (0.35, 4)
        else:
            alpha, size = (0.9, 9) if dim_noise else (0.9, 6)
        traces.append({
            "type": "scatter", "mode": "markers", "name": label,
            "x": [coords[i][0] for i in idxs], "y": [coords[i][1] for i in idxs],
            "marker": {"size": size, "color": hex_to_rgba(color, alpha),
                       "line": {"width": 0}},
            "text": [hover_text(points[i], label) for i in idxs],
            "hoverinfo": "text", "hoverlabel": HOVERLABEL,
        })
    return traces


def traces_3d(coords: dict[int, tuple], points: list[dict], groups: dict[str, list[int]],
              named: list[str], *, dim_noise: bool) -> list[dict]:
    traces: list[dict] = []
    for label in [CONTINUUM, *named]:
        idxs = [i for i in groups.get(label, []) if i in coords]
        if not idxs:
            continue
        color = color_for(label, named)
        if label == CONTINUUM:
            alpha, size = (0.15, 3.5) if dim_noise else (0.35, 3.5)
        else:
            alpha, size = (0.9, 6) if dim_noise else (0.9, 5)
        # scatter3d has no per-point opacity array — the fade lives in rgba colors
        traces.append({
            "type": "scatter3d", "mode": "markers", "name": label,
            "x": [coords[i][0] for i in idxs],
            "y": [coords[i][1] for i in idxs],
            "z": [coords[i][2] for i in idxs],
            "marker": {"size": size, "color": [hex_to_rgba(color, alpha)] * len(idxs),
                       "opacity": 1, "line": {"width": 0}},
            "text": [hover_text(points[i], label) for i in idxs],
            "hoverinfo": "text", "hoverlabel": HOVERLABEL,
        })
    return traces


def _axis2d(label: str) -> dict:
    return {"title": {"text": label, "font": {"size": 11, "color": "#a1a1aa"}},
            "gridcolor": GRID, "zerolinecolor": ZEROLINE}


def layout_2d(xlab: str, ylab: str) -> dict:
    return {"paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
            "font": {"color": "#a1a1aa", "family": FONT, "size": 12},
            "margin": {"t": 10, "r": 10, "b": 45, "l": 50},
            "xaxis": _axis2d(xlab), "yaxis": _axis2d(ylab),
            "legend": {"orientation": "h", "y": -0.16, "font": {"size": 10}},
            "hovermode": "closest"}


def _axis3d(label: str) -> dict:
    return {"title": {"text": label, "font": {"size": 10}},
            "gridcolor": GRID, "zerolinecolor": ZEROLINE,
            "backgroundcolor": "rgba(0,0,0,0)", "color": "#a1a1aa"}


def layout_3d(titles: tuple[str, str, str]) -> dict:
    return {"paper_bgcolor": "rgba(0,0,0,0)",
            "font": {"color": "#a1a1aa", "family": FONT, "size": 12},
            "margin": {"t": 0, "r": 0, "b": 0, "l": 0},
            "scene": {"xaxis": _axis3d(titles[0]), "yaxis": _axis3d(titles[1]),
                      "zaxis": _axis3d(titles[2])},
            "legend": {"orientation": "h", "y": -0.04, "font": {"size": 10}}}


PAGE_INTRO = (
    "Panels A/C zeigen die offizielle Projektion der App (PCA der One-Hot-Matrix). "
    "Panels B/D zeigen dieselben 120 Konfigurationen als frische UMAP-Projektion der "
    "<b>ordinalen</b> Matrix — also des Raums, auf dem HDBSCAN die Archetypen tatsächlich "
    "gefunden hat (gleiche Parameter wie im Clustering-Schritt: n_neighbors=15, euklidisch, "
    "Seed 42; eigener 2D/3D-Fit, da UMAP-Komponenten anders als PCA nicht geordnet sind — "
    "es ist NICHT das 5D-Embedding selbst, einzelne Continuum-Punkte innerhalb der Hüllen "
    "sind daher erwartbar). Archetyp-Namen erscheinen beim Hovern und in der Legende. "
    "Farben identisch zur App. Es wurde kein offizielles Artefakt verändert."
)

PANEL_META = [
    ("panel-a", "A — Offiziell: PCA (One-Hot), 2D", "Was der Landscape-Tab heute zeigt (cx/cy)."),
    ("panel-b", "B — NEU: UMAP (ordinal), 2D", "Cluster-Raum-Sicht: Noise abgedimmt, Hüllen je Archetyp; Namen beim Hovern."),
    ("panel-c", "C — Offiziell: PCA (One-Hot), 3D", "Die Present-Mode-3D-Sicht (cx/cy/cz)."),
    ("panel-d", "D — NEU: UMAP (ordinal), 3D", "Cluster-Raum-Sicht in 3D: Noise abgedimmt; Namen beim Hovern."),
]


def build_html(panels: list[dict]) -> str:
    if PLOTLY_JS.exists():
        plotly_tag = f"<script>{PLOTLY_JS.read_text()}</script>"
    else:
        plotly_tag = f'<script src="{PLOTLY_CDN}" charset="utf-8"></script>'
    cells = "\n".join(
        f'<div class="panel"><h2>{title}</h2><p>{sub}</p><div id="{div}" class="plot"></div></div>'
        for div, title, sub in PANEL_META
    )
    # a literal "</script>" inside embedded strings would terminate the script tag
    payload = json.dumps(panels, separators=(",", ":")).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>Cluster-Space Preview — Viz-Raum vs. Clustering-Raum</title>
<style>
  body {{ background: #09090b; color: #a1a1aa; font-family: {FONT}; margin: 0; padding: 24px; }}
  h1 {{ color: #e4e4e7; font-size: 18px; margin: 0 0 6px; }}
  .intro {{ font-size: 12px; color: #71717a; max-width: 1100px; margin: 0 0 20px; line-height: 1.5; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  .panel {{ background: #111113; border: 1px solid #27272a; border-radius: 8px; padding: 12px; }}
  .panel h2 {{ color: #e4e4e7; font-size: 14px; margin: 0 0 2px; }}
  .panel p {{ font-size: 11px; color: #71717a; margin: 0 0 8px; }}
  .plot {{ height: 520px; }}
</style>
{plotly_tag}
</head>
<body>
<h1>Cluster-Space Preview — sieht man die Archetypen im richtigen Raum?</h1>
<p class="intro">{PAGE_INTRO}</p>
<div class="grid">
{cells}
</div>
<script>
const PANELS = {payload};
const CONFIG = {{ displayModeBar: false, responsive: true }};
for (const p of PANELS) Plotly.newPlot(p.div, p.traces, p.layout, CONFIG);
</script>
</body>
</html>
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--outputs-dir", type=Path, default=REPO / "data" / "outputs")
    ap.add_argument("--out", type=Path, default=REPO / "viz_preview" / "cluster_space_preview.html")
    args = ap.parse_args()

    landscape, points, configs, box = load_artifacts(args.outputs_dir)
    named, groups = group_by_archetype(points)
    counts = {label: len(idxs) for label, idxs in groups.items()}
    print(f"points: {len(points)}   archetypes: {counts}")

    x = _ordinal_matrix(configs, box)
    print(f"ordinal matrix: {x.shape}")
    emb2 = umap_project(x, 2)
    emb3 = umap_project(x, 3)

    pca2 = finite_coords(points, ("cx", "cy"))
    pca3 = finite_coords(points, ("cx", "cy", "cz"))
    umap2 = {i: (float(emb2[i, 0]), float(emb2[i, 1])) for i in range(len(points))}
    umap3 = {i: tuple(float(v) for v in emb3[i]) for i in range(len(points))}
    for name, coords in [("A/pca2d", pca2), ("C/pca3d", pca3)]:
        if len(coords) < len(points):
            print(f"warning: panel {name} has only {len(coords)}/{len(points)} finite points")

    axes = landscape.get("axes") or {}
    def pc_label(key, fallback):
        label = ((axes.get(key) or {}).get("label") or fallback).strip()
        return label[:70] + "…" if len(label) > 70 else label
    shares = ((landscape.get("structure") or {}).get("pc_shares_3d")) or []
    titles3d = tuple(
        f"PC{i + 1} ({shares[i] * 100:.1f}% var)" if i < len(shares) else f"PC{i + 1}"
        for i in range(3)
    )

    panels = [
        {"div": "panel-a",
         "traces": traces_2d(pca2, points, groups, named, dim_noise=False, hulls=False),
         "layout": layout_2d(pc_label("pc1", "PC1"), pc_label("pc2", "PC2"))},
        {"div": "panel-b",
         "traces": traces_2d(umap2, points, groups, named, dim_noise=True, hulls=True),
         "layout": layout_2d("UMAP-1 (ordinal)", "UMAP-2 (ordinal)")},
        {"div": "panel-c",
         "traces": traces_3d(pca3, points, groups, named, dim_noise=False),
         "layout": layout_3d(titles3d)},
        {"div": "panel-d",
         "traces": traces_3d(umap3, points, groups, named, dim_noise=True),
         "layout": layout_3d(("UMAP-1 (ordinal)", "UMAP-2 (ordinal)", "UMAP-3 (ordinal)"))},
    ]
    for p in panels:
        n = sum(len(t["x"]) for t in p["traces"]
                if t["mode"] == "markers" and t.get("hoverinfo") == "text")
        print(f"  {p['div']}: {n} points, {len(p['traces'])} traces")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(build_html(panels))
    size_mb = args.out.stat().st_size / 1e6
    print(f"wrote {args.out} ({size_mb:.1f} MB) — data/outputs/ wurde nur gelesen, nichts geschrieben")


if __name__ == "__main__":
    main()
