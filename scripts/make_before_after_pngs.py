"""Before/after PNGs of the scenario field for the PowerPoint deck.

Same data, seeds, and styling as make_report_figures.py's space_two_lenses figure, but
exported as high-res PNGs — combined and as two standalone panels so the slide can
reveal 'before' first, then 'after'.

  report_figures/space_two_lenses.png   both panels side by side (like the SVG/PDF)
  report_figures/space_before.png       one-hot + KMeans blob (≈ random)
  report_figures/space_after.png        ordinal + HDBSCAN archetypes + continuum halo

Run:  uv run python scripts/make_before_after_pngs.py
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

SURFACE, INK, SEC, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, BASE = "#e1e0d9", "#c3c2b7"
CAT = ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7", "#e34948", "#e87ba4", "#eb6834"]
CONTINUUM = "#b8b6ac"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "sans-serif", "font.size": 11, "text.color": INK,
    "axes.edgecolor": BASE, "axes.labelcolor": SEC, "xtick.color": MUTED, "ytick.color": MUTED,
})

configs = json.load(open(f"{D}/combinatorial_state.json"))["configs"]
mb = json.load(open(f"{D}/morphbox_state.json"))
drivers, manifs = mb["drivers"], mb["manifestations"]
arch = json.load(open(f"{D}/archetypes_state.json"))

order = sorted(arch["archetypes"], key=lambda a: -a["size"])
label_by_id = {mid: a["label"] for a in order for mid in a["member_scenario_ids"]}
labels = [label_by_id.get(c.get("id"), "Continuum") for c in configs]
arch_names = [a["label"] for a in order]
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

import umap  # noqa: E402


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
    o = vals.argsort()[::-1]
    vals, vecs = vals[o], vecs[:, o]
    theta = np.degrees(np.arctan2(vecs[1, 0], vecs[0, 0]))
    w, h = 2 * n_std * np.sqrt(np.maximum(vals, 1e-9))
    ax.add_patch(Ellipse(mean, w, h, angle=theta, facecolor=color, alpha=0.13,
                         edgecolor=color, lw=1.3, zorder=0))


def bare(ax):
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color(GRID)


def draw_before(ax):
    ax.scatter(emb_oh[:, 0], emb_oh[:, 1], s=46, c="#8aa0b8", alpha=0.75,
               linewidths=0.5, edgecolors=SURFACE)
    ax.set_title(f"one-hot + KMeans   ·   silhouette {sil('onehot_kmeans', 0.07):.2f}",
                 fontsize=12, color=INK, fontweight="bold", loc="left", pad=8)


def draw_after(ax):
    cidx = [i for i, l in enumerate(labels) if l == "Continuum"]
    ax.scatter(emb_or[cidx, 0], emb_or[cidx, 1], s=15, c=CONTINUUM, alpha=0.30,
               linewidths=0, zorder=1, label="Continuum (halo)")
    for name in arch_names:
        pts = emb_or[[i for i, l in enumerate(labels) if l == name]]
        cluster_ellipse(ax, pts, color_of[name])
        ax.scatter(pts[:, 0], pts[:, 1], s=62, c=color_of[name], alpha=0.95,
                   linewidths=0.6, edgecolors=SURFACE, zorder=3, label=name)
    ax.set_title(f"ordinal + HDBSCAN   ·   silhouette {core_sil:.2f} on cores",
                 fontsize=12, color=INK, fontweight="bold", loc="left", pad=8)


# Combined (identical layout to the SVG/PDF, just rasterized).
fig, (axA, axB) = plt.subplots(1, 2, figsize=(12, 5.6))
fig.subplots_adjust(left=0.02, right=0.98, top=0.93, bottom=0.14, wspace=0.06)
bare(axA), bare(axB)
draw_before(axA)
draw_after(axB)
_h, _l = axB.get_legend_handles_labels()
fig.legend(_h, _l, loc="lower center", bbox_to_anchor=(0.5, 0.005), ncol=3, frameon=False,
           fontsize=9, labelcolor=SEC, columnspacing=2.4, handletextpad=0.5)
fig.savefig(f"{OUT}/space_two_lenses.png", dpi=300)
plt.close(fig)

# Standalone 'before'.
fig, ax = plt.subplots(figsize=(6.4, 5.8))
fig.subplots_adjust(left=0.03, right=0.97, top=0.92, bottom=0.05)
bare(ax)
draw_before(ax)
fig.savefig(f"{OUT}/space_before.png", dpi=300)
plt.close(fig)

# Standalone 'after' with its own legend.
fig, ax = plt.subplots(figsize=(6.4, 6.6))
fig.subplots_adjust(left=0.03, right=0.97, top=0.93, bottom=0.15)
bare(ax)
draw_after(ax)
_h, _l = ax.get_legend_handles_labels()
fig.legend(_h, _l, loc="lower center", bbox_to_anchor=(0.5, 0.005), ncol=2, frameon=False,
           fontsize=9, labelcolor=SEC, columnspacing=2.0, handletextpad=0.5)
fig.savefig(f"{OUT}/space_after.png", dpi=300)
plt.close(fig)

print("wrote:")
for f in ["space_two_lenses.png", "space_before.png", "space_after.png"]:
    print(f"  {OUT}/{f}")
