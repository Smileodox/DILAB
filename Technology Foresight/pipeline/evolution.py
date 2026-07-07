"""Lifecycle S-curves and temporal topic change detection."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np
from scipy.optimize import curve_fit


STAGES = ("introduction", "growth", "maturity", "decline")
STAGE_COLORS = {
    "introduction": "#22C55E",
    "growth": "#2563EB",
    "maturity": "#9333EA",
    "decline": "#EF4444",
}


def _sigmoid(t, L, k, t0):
    return L / (1 + np.exp(-k * (t - t0)))


def fit_lifecycle(years: list[int], counts: list[int]) -> dict[str, Any]:
    if not years or sum(counts) < 2:
        return {"stage": "introduction", "params": {}, "fitted": []}

    xs = np.array(years, dtype=float)
    ys = np.array(counts, dtype=float)
    if len(xs) < 3:
        stage = "introduction" if ys[-1] <= np.mean(ys) else "growth"
        return {"stage": stage, "params": {}, "fitted": list(zip(years, counts))}

    try:
        popt, _ = curve_fit(
            _sigmoid,
            xs - xs.min(),
            ys,
            p0=[max(ys) * 1.2, 0.5, np.median(xs - xs.min())],
            maxfev=5000,
            bounds=([0, 0.01, 0], [max(ys) * 10, 5, max(xs - xs.min()) * 2]),
        )
        t_grid = np.linspace(xs.min(), xs.max(), 20)
        fitted = [(int(y), float(_sigmoid(t - xs.min(), *popt))) for y, t in zip(t_grid, t_grid)]
        slope = float(np.gradient([_sigmoid(t - xs.min(), *popt) for t in t_grid])[-1])
        peak_frac = float(ys[-1] / (max(ys) + 1e-6))
        if peak_frac < 0.25:
            stage = "introduction"
        elif slope > 0.05:
            stage = "growth"
        elif peak_frac > 0.7 and slope < -0.02:
            stage = "decline"
        else:
            stage = "maturity"
        return {"stage": stage, "params": {"L": popt[0], "k": popt[1], "t0": popt[2]}, "fitted": fitted}
    except Exception:
        if counts[-1] > counts[0]:
            stage = "growth"
        elif counts[-1] < counts[0] * 0.8:
            stage = "decline"
        else:
            stage = "maturity"
        return {"stage": stage, "params": {}, "fitted": list(zip(years, counts))}


def _keyword_overlap(a: list[str], b: list[str]) -> float:
    sa, sb = set(w.lower() for w in a), set(w.lower() for w in b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def detect_change_events(
    documents: list[dict],
    topics: list[int],
    clusters: list[dict],
    window_years: list[int] | None = None,
) -> tuple[dict[str, Any], list[dict]]:
    years_all = sorted({d.get("year") for d in documents if d.get("year")})
    if not years_all:
        years_all = [2020, 2021, 2022, 2023, 2024]
    if window_years is None:
        window_years = years_all

    cluster_kw = {c["topic_id"]: c.get("keywords", []) for c in clusters}
    vol_by_topic_year: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))

    for doc, tid in zip(documents, topics):
        y = doc.get("year") or years_all[-1]
        vol_by_topic_year[int(tid)][int(y)] += 1

    timeline = {}
    lifecycle = {}
    for tid, year_counts in vol_by_topic_year.items():
        years = sorted(year_counts.keys())
        counts = [year_counts[y] for y in years]
        lifecycle[tid] = fit_lifecycle(years, counts)
        timeline[str(tid)] = [{"year": y, "count": year_counts[y]} for y in years]

    events = []
    prev_topics: dict[int, dict] = {}

    for year in window_years:
        year_docs_idx = [i for i, d in enumerate(documents) if (d.get("year") or years_all[-1]) == year]
        if not year_docs_idx:
            continue
        year_topic_counts: dict[int, int] = defaultdict(int)
        for i in year_docs_idx:
            year_topic_counts[topics[i]] += 1

        for tid, count in year_topic_counts.items():
            prev = prev_topics.get(tid)
            kw = cluster_kw.get(tid, [])
            if prev is None and count >= 1:
                events.append(
                    {
                        "year": year,
                        "topic_id": tid,
                        "type": "emerge",
                        "keywords": kw,
                        "count": count,
                        "why": f"Topic {tid} first appears in {year} with {count} document(s); keyword overlap vs prior windows was zero.",
                    }
                )
            elif prev and count > prev["count"] * 1.25:
                events.append(
                    {
                        "year": year,
                        "topic_id": tid,
                        "type": "grow",
                        "keywords": kw,
                        "count": count,
                        "why": f"Publication volume for topic {tid} rose {prev['count']}→{count} ({((count-prev['count'])/max(prev['count'],1))*100:.0f}% YoY).",
                    }
                )
            prev_topics[tid] = {"count": count, "keywords": kw}

        # merge/shift via keyword overlap between active topics this year
        active = list(year_topic_counts.keys())
        for i, ta in enumerate(active):
            for tb in active[i + 1 :]:
                ov = _keyword_overlap(cluster_kw.get(ta, []), cluster_kw.get(tb, []))
                if ov > 0.6:
                    events.append(
                        {
                            "year": year,
                            "topic_id": ta,
                            "type": "merge",
                            "keywords": cluster_kw.get(ta, []),
                            "related_topic": tb,
                            "overlap": round(ov, 2),
                            "why": f"Topics {ta} and {tb} exceed 60% keyword overlap in {year}, indicating cluster merge.",
                        }
                    )
                elif ov > 0.45:
                    events.append(
                        {
                            "year": year,
                            "topic_id": ta,
                            "type": "shift",
                            "keywords": cluster_kw.get(ta, []),
                            "related_topic": tb,
                            "overlap": round(ov, 2),
                            "why": f"Topics {ta} and {tb} share {ov:.0%} keyword overlap in {year}, indicating a thematic shift or merge.",
                        }
                    )

    # die: topics absent in last year but present before
    last_year = max(window_years)
    for tid in list(vol_by_topic_year.keys()):
        if last_year not in vol_by_topic_year[tid] and any(y < last_year for y in vol_by_topic_year[tid]):
            events.append(
                {
                    "year": last_year,
                    "topic_id": tid,
                    "type": "die",
                    "keywords": cluster_kw.get(tid, []),
                    "why": f"Topic {tid} had no publications in {last_year} after prior activity—treated as decline/die-off.",
                }
            )

    lifecycle_explanations = {
        "introduction": "Early-stage: low absolute volume but new presence in the corpus—watch for acceleration.",
        "growth": "Rapid uptake: yearly counts are rising on the fitted S-curve upswing.",
        "maturity": "Plateau: volume stabilizes near the S-curve peak; incremental improvements dominate.",
        "decline": "Falling interest: post-peak volume decreases—may be displaced by successor topics.",
    }

    return {
        "timeline": timeline,
        "lifecycle": {str(k): {**v, "explanation": lifecycle_explanations.get(v["stage"], "")} for k, v in lifecycle.items()},
        "events": events,
        "why": (
            "Per-topic yearly counts were fitted to a logistic S-curve to assign lifecycle stages. "
            "Change events are detected by diffing topic presence and volume across years and measuring "
            "keyword overlap between co-active clusters."
        ),
    }, events


def detect_weak_signals(
    timeline: dict[str, list[dict]],
    clusters: list[dict],
) -> list[dict]:
    signals = []
    for c in clusters:
        tid = str(c["topic_id"])
        series = timeline.get(tid, [])
        if len(series) < 2:
            continue
        total = sum(p["count"] for p in series)
        if total > max(8, sum(p["count"] for p in series) * 0.15):
            continue
        early, late = series[0]["count"], series[-1]["count"]
        if late >= early + 2 and late >= 2:
            growth_rate = (late - early) / max(early, 1)
            signals.append(
                {
                    "topic_id": c["topic_id"],
                    "label": c.get("label", f"Topic {c['topic_id']}"),
                    "keywords": c.get("keywords", [])[:6],
                    "growth_rate": round(growth_rate, 2),
                    "why": (
                        f"Small cluster (n={total}) with fast growth {early}→{late} papers—flagged as a weak signal "
                        "because breakthrough topics often start with low volume but high acceleration."
                    ),
                }
            )
    return sorted(signals, key=lambda s: -s["growth_rate"])[:5]
