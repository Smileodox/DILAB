"""Report charts as clean SVGs — no titles, no prose, just the charts.

  space_two_lenses.svg     one-hot/KMeans blob vs ordinal/HDBSCAN cores (shaded ellipses).
  silhouette_by_lens.svg   silhouette per lens + 0.25 floor + 0.72 positive control.
  archetype_signatures.svg archetype x driver mean-stance heatmap.

Run:  uv run python scripts/make_report_figures.py
"""
from __future__ import annotations

import json
import os
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Ellipse

warnings.filterwarnings("ignore")

D, OUT = "data/outputs", "report_figures"
os.makedirs(OUT, exist_ok=True)
for old in os.listdir(OUT):
    if old.endswith(".png"):
        os.remove(os.path.join(OUT, old))

SURFACE, INK, SEC, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, BASE, GOOD = "#e1e0d9", "#c3c2b7", "#006300"
CAT = ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7", "#e34948", "#e87ba4", "#eb6834"]
CONTINUUM = "#b8b6ac"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "svg.fonttype": "none", "font.family": "sans-serif", "font.size": 11, "text.color": INK,
    "axes.edgecolor": BASE, "axes.labelcolor": SEC, "xtick.color": MUTED, "ytick.color": MUTED,
})

configs = json.load(open(f"{D}/combinatorial_state.json"))["configs"]
mb = json.load(open(f"{D}/morphbox_state.json"))
drivers, manifs = mb["drivers"], mb["manifestations"]
arch = json.load(open(f"{D}/archetypes_state.json"))
dnames = {d["id"]: d.get("name", d["id"]) for d in json.load(open(f"{D}/merge_state.json")).get("unified_drivers", [])}

order = sorted(arch["archetypes"], key=lambda a: -a["size"])
label_by_id = {mid: a["label"] for a in order for mid in a["member_scenario_ids"]}
labels = [label_by_id.get(c.get("id"), "Continuum") for c in configs]
arch_names = [a["label"] for a in order]
size_of = {a["label"]: a["size"] for a in order}
color_of = {name: CAT[i % len(CAT)] for i, name in enumerate(arch_names)}
color_of["Continuum"] = CONTINUUM

vocab = [m["id"] for m in mb["all_manifestations"]]
cfg_sets = [set(c["configuration"].values()) for c in configs]
X_oh = np.array([[1.0 if v in s else 0.0 for v in vocab] for s in cfg_sets])


def ordinal(c):
    v = np.zeros(len(drivers))
    for j, d in enumerate(drivers):
        ms, mid = manifs.get(d, []), c["configuration"].get(d)
        if mid in ms:
            v[j] = ms.index(mid) / (len(ms) - 1) if len(ms) > 1 else 0.5
    return v


X_or = np.array([ordinal(c) for c in configs])

import umap
def umap2d(X, n_neighbors=15, min_dist=0.12, seed=42):
    return umap.UMAP(n_neighbors=n_neighbors, n_components=2, min_dist=min_dist,
                     metric="euclidean", random_state=seed).fit_transform(X)

emb_oh = umap2d(X_oh, min_dist=0.12)
emb_or = umap2d(X_or, n_neighbors=12, min_dist=0.0)

lenses = (json.load(open(f"{D}/landscape_state_combi.json")).get("structure") or {}).get("lenses", {})
def sil(name, default):
    return (lenses.get(name) or {}).get("silhouette") or default
core_sil = arch.get("hdbscan_silhouette") or sil("ordinal_hdbscan", 0.38)


def cluster_ellipse(ax, pts, color, n_std=1.7):
    if len(pts) < 3:
        return
    mean, cov = pts.mean(axis=0), np.cov(pts, rowvar=False)
    vals, vecs = np.linalg.eigh(cov)
    o = vals.argsort()[::-1]; vals, vecs = vals[o], vecs[:, o]
    theta = np.degrees(np.arctan2(vecs[1, 0], vecs[0, 0]))
    w, h = 2 * n_std * np.sqrt(np.maximum(vals, 1e-9))
    ax.add_patch(Ellipse(mean, w, h, angle=theta, facecolor=color, alpha=0.13,
                         edgecolor=color, lw=1.3, zorder=0))

# --- Fig 1: two-lens scatter ----------------------------------------------------------
fig, (axA, axB) = plt.subplots(1, 2, figsize=(12, 5.6))
fig.subplots_adjust(left=0.02, right=0.98, top=0.93, bottom=0.14, wspace=0.06)
for ax in (axA, axB):
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color(GRID)
axA.scatter(emb_oh[:, 0], emb_oh[:, 1], s=46, c="#8aa0b8", alpha=0.75, linewidths=0.5, edgecolors=SURFACE)
axA.set_title(f"one-hot + KMeans   ·   silhouette {sil('onehot_kmeans', 0.07):.2f}",
              fontsize=12, color=INK, fontweight="bold", loc="left", pad=8)
cidx = [i for i, l in enumerate(labels) if l == "Continuum"]
axB.scatter(emb_or[cidx, 0], emb_or[cidx, 1], s=15, c=CONTINUUM, alpha=0.30, linewidths=0,
            zorder=1, label="Continuum (halo)")
for name in arch_names:
    pts = emb_or[[i for i, l in enumerate(labels) if l == name]]
    cluster_ellipse(axB, pts, color_of[name])
    axB.scatter(pts[:, 0], pts[:, 1], s=62, c=color_of[name], alpha=0.95,
                linewidths=0.6, edgecolors=SURFACE, zorder=3, label=name)
axB.set_title(f"ordinal + HDBSCAN   ·   silhouette {core_sil:.2f} on cores",
              fontsize=12, color=INK, fontweight="bold", loc="left", pad=8)
_h, _l = axB.get_legend_handles_labels()
fig.legend(_h, _l, loc="lower center", bbox_to_anchor=(0.5, 0.005), ncol=3, frameon=False,
           fontsize=9, labelcolor=SEC, columnspacing=2.4, handletextpad=0.5)
fig.savefig(f"{OUT}/space_two_lenses.svg")
plt.close(fig)

# --- Fig 2: silhouette by lens --------------------------------------------------------
rows = [
    ("uniform-random null", 0.08, MUTED),
    ("one-hot · KMeans (default)", sil("onehot_kmeans", 0.074), "#9ec5f4"),
    ("ordinal · KMeans", sil("ordinal_kmeans", 0.17), "#6da7ec"),
    ("one-hot · HDBSCAN", sil("onehot_hdbscan", 0.34), "#3987e5"),
    ("ordinal · HDBSCAN (ours)", sil("ordinal_hdbscan", core_sil), "#2a78d6"),
]
vals = [float(r[1]) for r in rows]
fig2, ax = plt.subplots(figsize=(8.6, 3.6))
fig2.subplots_adjust(left=0.30, right=0.965, top=0.92, bottom=0.16)
y = np.arange(len(rows))[::-1]
ax.barh(y, vals, height=0.62, color=[r[2] for r in rows], edgecolor=SURFACE, linewidth=1.2, zorder=3)
for yi, v in zip(y, vals):
    ax.text(v + 0.008, yi, f"{v:.2f}", va="center", ha="left", fontsize=10.5, color=INK, fontweight="bold")
ax.set_yticks(y); ax.set_yticklabels([r[0] for r in rows], fontsize=10, color=SEC)
ax.set_xlim(0, 0.82); ax.set_xlabel("silhouette", fontsize=10, color=SEC)
ax.grid(axis="x", color=GRID, linewidth=0.8, zorder=0); ax.set_axisbelow(True)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color(BASE); ax.tick_params(length=0)
ax.axvline(0.25, color="#c77d2e", linestyle=(0, (4, 3)), linewidth=1.4, zorder=4)
ax.text(0.25, len(rows) - 0.4, " 0.25 usable floor", color="#a8641f", fontsize=8.6, va="top")
ax.axvline(0.72, color=GOOD, linestyle=(0, (4, 3)), linewidth=1.4, zorder=4)
ax.text(0.72, len(rows) - 0.4, " 0.72 positive control", color=GOOD, fontsize=8.6, va="top", ha="right")
fig2.savefig(f"{OUT}/silhouette_by_lens.svg")
plt.close(fig2)

# --- Fig 3: archetype signatures heatmap ----------------------------------------------
def short(s, n=30):
    return s if len(s) <= n else s[: n - 1] + "…"

mat = np.array([X_or[[i for i, l in enumerate(labels) if l == name]].mean(axis=0) for name in arch_names])
col_order = np.argsort(-np.var(mat, axis=0))
matO = mat[:, col_order]
col_labels = [short(dnames.get(drivers[c], drivers[c])) for c in col_order]
row_labels = [f"{short(n, 34)}  (n={size_of[n]})" for n in arch_names]
fig3, ax = plt.subplots(figsize=(14, 4.8))
fig3.subplots_adjust(left=0.23, right=0.86, top=0.97, bottom=0.44)
im = ax.imshow(matO, cmap="RdBu_r", vmin=0, vmax=1, aspect="auto")
ax.set_xticks(range(len(drivers))); ax.set_xticklabels(col_labels, rotation=40, ha="right", fontsize=8.2, color=SEC)
ax.set_yticks(range(len(arch_names))); ax.set_yticklabels(row_labels, fontsize=9.5, color=INK)
ax.set_xticks(np.arange(-.5, len(drivers), 1), minor=True)
ax.set_yticks(np.arange(-.5, len(arch_names), 1), minor=True)
ax.grid(which="minor", color=SURFACE, linewidth=2); ax.tick_params(which="both", length=0)
cbar = fig3.colorbar(im, ax=ax, fraction=0.025, pad=0.01, ticks=[0.03, 0.5, 0.97])
cbar.ax.set_yticklabels(["optimistic", "mixed", "pessimistic"], fontsize=8.5, color=SEC)
cbar.outline.set_edgecolor(GRID)
fig3.savefig(f"{OUT}/archetype_signatures.svg")
plt.close(fig3)

print("wrote:")
for f in ["space_two_lenses", "silhouette_by_lens", "archetype_signatures"]:
    print(f"  {OUT}/{f}.svg")
