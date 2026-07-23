"""Presentation chart assets — clean SVGs, no titles, no legends baked in.

  bars_slider_archetype.svg   where the 4 positions of the example driver land
                              (stacked counts by archetype, final-run crosstab)

Legend chips + captions live in the HTML deck, not in the SVG.
Also copies the three existing report figures into presentation/assets/.

Run:  uv run python scripts/make_presentation_assets.py
"""
from __future__ import annotations

import json
import os
import shutil
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

D, OUT = "data/outputs", "presentation/assets"
os.makedirs(OUT, exist_ok=True)

SURFACE, INK, SEC, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
CAT = ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7"]
CONTINUUM = "#b8b6ac"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "svg.fonttype": "none", "font.family": "sans-serif", "font.size": 12, "text.color": INK,
})

TGT = "f33ab61e5a83"  # Shift to dynamic shared and harmonised spectrum access
POSITIONS = {  # manifestation id -> short row label (deck is English)
    "1059b351f4fc": "Cross-border\nobservatories",
    "dfc4067e44b2": "Automated\nenforcement",
    "c194c947c9e0": "National\nislands",
    "e45190ee9f17": "Hot-spot\npolicing",
}

arch = json.load(open(f"{D}/archetypes_state.json"))
order = sorted(arch["archetypes"], key=lambda a: -a["size"])
member = {sid: a["label"] for a in order for sid in a["member_scenario_ids"]}
series = [a["label"] for a in order] + ["Continuum"]
color_of = dict(zip(series, CAT + [CONTINUUM]))
# ink labels on light segments (validator: relief for low-contrast fills)
label_ink = {"#1baf7a": INK, "#eda100": INK, CONTINUUM: INK}

configs = json.load(open(f"{D}/combinatorial_state.json"))["configs"]
cross = {mid: Counter() for mid in POSITIONS}
for c in configs:
    mid = c["configuration"].get(TGT)
    if mid in cross:
        cross[mid][member.get(c["id"], "Continuum")] += 1

fig, ax = plt.subplots(figsize=(9.6, 3.5))
rows = list(POSITIONS)
for yi, mid in enumerate(rows):
    x = 0.0
    for s in series:
        n = cross[mid].get(s, 0)
        if not n:
            continue
        ax.barh(yi, n, left=x, height=0.58, color=color_of[s],
                edgecolor=SURFACE, linewidth=2)
        if n >= 3:  # direct count labels where the segment can carry them
            ax.text(x + n / 2, yi, str(n), ha="center", va="center", fontsize=11,
                    color=label_ink.get(color_of[s], "white"))
        x += n
    ax.text(x + 0.8, yi, f"{int(x)}", ha="left", va="center", fontsize=11, color=MUTED)
ax.set_yticks(range(len(rows)), [POSITIONS[m] for m in rows], fontsize=12, color=SEC)
ax.invert_yaxis()
ax.set_xlim(0, 52)
ax.set_xticks([])
for sp in ax.spines.values():
    sp.set_visible(False)
fig.tight_layout()
fig.savefig(f"{OUT}/bars_slider_archetype.svg", bbox_inches="tight")
plt.close(fig)
print(f"wrote {OUT}/bars_slider_archetype.svg")

for name in ("space_two_lenses", "silhouette_by_lens", "archetype_signatures"):
    shutil.copy(f"report_figures/{name}.svg", f"{OUT}/{name}.svg")
    print(f"copied {name}.svg")
