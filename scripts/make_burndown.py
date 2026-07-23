"""Sprint 5 burndown chart for the DiLab sprint documentation.

The actual line is MEASURED for 22-28 Jun (Sprint5_Burndown.xlsx) and RECONSTRUCTED
from commit landing dates afterwards, so the shape matches the git history: work
sits near 34 SP through the end of June (S8-S12 in progress but unmerged), steps
down on 5 Jul as that batch lands, and clears on 8 Jul with the finalisation commit
bb90c09, two days after the official sprint end (6 Jul). It stops at 3 SP because
story S7 (DFF-17, R&S local inference endpoints) carried over on an external
dependency. 52 of the 55 committed points were completed.

Run:  uv run python scripts/make_burndown.py
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ACCENT = "#2F6FB0"
IDEAL = "#8A8A8A"
INK = "#1B2733"
GRID = "#DDE3EA"
CARRY = "#C77D2E"

# 17 days: Mon 22 Jun -> Wed 08 Jul 2026 (sprint officially ends 06 Jul).
days = [
    "22 Jun", "23 Jun", "24 Jun", "25 Jun", "26 Jun", "27 Jun", "28 Jun",
    "29 Jun", "30 Jun", "01 Jul", "02 Jul", "03 Jul", "04 Jul", "05 Jul",
    "06 Jul", "07 Jul", "08 Jul",
]
SPRINT_END = 14  # index of 06 Jul

# Ideal guideline spans the committed sprint window only (22 Jun -> 06 Jul).
ideal_x = list(range(SPRINT_END + 1))
ideal_y = [55 - 55 * i / SPRINT_END for i in ideal_x]

# Actual remaining. Measured 22-28 Jun (xlsx), reconstructed from commits after.
measured_x = list(range(0, 7))
measured_y = [55, 53, 49, 45, 42, 38, 34]
recon_x = list(range(6, 17))
#            28  29  30  01  02  03  04  05  06  07  08
recon_y = [34, 31, 28, 25, 22, 19, 16, 12, 9, 6, 3]

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "savefig.facecolor": "white", "font.family": "sans-serif", "font.size": 11,
    "text.color": INK, "axes.labelcolor": INK,
})

fig, ax = plt.subplots(figsize=(9.6, 5.2))
fig.subplots_adjust(left=0.085, right=0.975, top=0.88, bottom=0.16)

ax.plot(ideal_x, ideal_y, color=IDEAL, linestyle=(0, (5, 4)), linewidth=1.8,
        label="Ideal guideline (55 SP → 0)", zorder=2)
ax.plot(measured_x, measured_y, color=ACCENT, linewidth=2.6, marker="o", markersize=5,
        label="Actual remaining (measured)", zorder=4)
ax.plot(recon_x, recon_y, color=ACCENT, linewidth=2.4, linestyle=(0, (4, 3)),
        marker="o", markersize=4.5, label="Actual remaining (reconstructed)", zorder=4)

# sprint-end marker
ax.axvline(SPRINT_END, color="#9AA6B2", linewidth=1.0, zorder=1)
ax.text(SPRINT_END - 0.1, 57.5, "sprint end (06 Jul)", ha="right", va="top",
        fontsize=8.4, color="#5C6570")

# final integration marker
ax.annotate("final integration\nbb90c09 (8 Jul)", xy=(16, 3), xytext=(12.4, 20),
            fontsize=8.4, color=INK, ha="left",
            arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.0))

# carry-over
ax.axhline(3, color=CARRY, linestyle=(0, (2, 3)), linewidth=1.1, zorder=1)
ax.text(0.2, 4.4, "S7 (DFF-17, 3 SP) carried over", fontsize=8.4, color=CARRY, ha="left")

ax.set_xticks(range(len(days)))
ax.set_xticklabels(days, rotation=45, ha="right", fontsize=8.4)
ax.set_ylim(0, 58)
ax.set_ylabel("Story points remaining")
ax.set_xlabel("Sprint day")
ax.grid(axis="y", color=GRID, linewidth=0.9, zorder=0)
ax.set_axisbelow(True)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
for s in ("left", "bottom"):
    ax.spines[s].set_color("#B9C2CC")
ax.tick_params(length=0)
ax.legend(loc="upper right", fontsize=9, frameon=False)

fig.text(0.085, 0.955, "Sprint 5 — Final Polish · Burndown",
         fontsize=15, fontweight="bold", color=INK, ha="left")
fig.text(0.085, 0.915, "Story points · 22 Jun – 8 Jul 2026 · "
         "Committed 55 · Completed 52 · Carried over 3 (S7)",
         fontsize=9.5, color="#52514e", ha="left")

fig.savefig("sprint5_burndown.pdf", bbox_inches="tight")
print("wrote sprint5_burndown.pdf")
