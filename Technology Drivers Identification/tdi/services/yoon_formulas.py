"""
DVI formulas from Wang & Zhu (2026) MLWS-TF / Expert Systems With Applications 298:
  - DoV, DoD with Yoon (2012) time weighting (Eq. 7–10)
  - DoI via TF-IDF internal impact score I_i(d) (Eq. 11–13)
  - KVM / KDM / KIM quadrant maps with median thresholds
  - Three-dimensional joint validation across visibility, diffusion, impact maps
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

from tdi.models.schemas import ArxivPaper, ExtractedEntity

TIME_WEIGHT = 0.5  # α — time-weighting factor (Wang & Zhu, 2026; Yoon, 2012)


@dataclass
class PeriodStats:
    period_index: int
    year: str
    tf: int
    df: int
    nn: int
    dov: float
    dod: float
    doi: float
    dov_rate: float = 0.0
    dod_rate: float = 0.0
    doi_rate: float = 0.0


@dataclass
class TermDVIResult:
    term: str
    periods: list[PeriodStats] = field(default_factory=list)
    absolute_tf: float = 0.0
    absolute_df: float = 0.0
    avg_dov: float = 0.0
    avg_dov_rate: float = 0.0
    avg_dod: float = 0.0
    avg_dod_rate: float = 0.0
    avg_doi: float = 0.0
    avg_doi_rate: float = 0.0
    visibility: float = 0.0
    diffusion: float = 0.0
    impact: float = 0.0
    growth_rate: float = 0.0
    composite: float = 0.0
    quadrant_visibility: str = ""
    quadrant_diffusion: str = ""
    quadrant_impact: str = ""
    signal_type: str = "weak_signal"
    joint_consistent: bool = False


@dataclass
class DVIThresholds:
    median_dov: float = 0.0
    median_dov_rate: float = 0.0
    median_dod: float = 0.0
    median_dod_rate: float = 0.0
    median_doi: float = 0.0
    median_doi_rate: float = 0.0


def tokenize(text: str) -> list[str]:
    return re.findall(r"\b[a-z0-9][a-z0-9\-]{1,}\b", text.lower())


def term_variants(term: str) -> list[str]:
    base = term.lower().strip()
    parts = [p for p in re.split(r"[\s\-/]+", base) if len(p) > 2]
    return list({base, *parts})


def count_tf(text: str, variants: list[str]) -> int:
    tokens = tokenize(text)
    count = 0
    joined = " ".join(tokens)
    for variant in variants:
        if " " in variant or "-" in variant:
            count += joined.count(variant.replace("-", " "))
            count += joined.count(variant)
        else:
            count += sum(1 for t in tokens if variant in t or t == variant)
    return count


def document_contains(text: str, variants: list[str]) -> bool:
    joined = text.lower()
    return any(v in joined for v in variants)


def group_papers_by_year(papers: list[ArxivPaper]) -> list[tuple[str, list[ArxivPaper]]]:
    from collections import defaultdict

    buckets: dict[str, list[ArxivPaper]] = defaultdict(list)
    for paper in papers:
        year = paper.published[:4] if paper.published and len(paper.published) >= 4 else "unknown"
        buckets[year].append(paper)

    ordered_years = sorted(buckets.keys())
    if len(ordered_years) == 1:
        return [(ordered_years[0], buckets[ordered_years[0]])]
    return [(year, buckets[year]) for year in ordered_years]


def geometric_mean(values: list[float]) -> float:
    positives = [max(v, 1e-9) for v in values if v > 0]
    if not positives:
        return 0.0
    return math.exp(sum(math.log(v) for v in positives) / len(positives))


def arithmetic_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def growth_rate(current: float, previous: float) -> float:
    """DoX_rate(t) = (DoX(t) - DoX(t-1)) / DoX(t)  [Wang & Zhu, 2026, Eq. 10/13]"""
    if current <= 0:
        return 0.0
    return (current - previous) / current


def compute_dov(tf: int, nn: int, period_index: int, n_periods: int) -> float:
    if nn <= 0:
        return 0.0
    time_factor = 1.0 - TIME_WEIGHT * (n_periods - period_index)
    return (tf / nn) * max(time_factor, 0.0)


def compute_dod(df: int, nn: int, period_index: int, n_periods: int) -> float:
    if nn <= 0:
        return 0.0
    time_factor = 1.0 - TIME_WEIGHT * (n_periods - period_index)
    return (df / nn) * max(time_factor, 0.0)


def build_corpus_token_stats(papers: list[ArxivPaper]) -> tuple[int, dict[str, int], list[tuple[str, list[str]]]]:
    n_docs = max(len(papers), 1)
    df_counts: dict[str, int] = {}
    docs: list[tuple[str, list[str]]] = []

    for paper in papers:
        text = f"{paper.title} {paper.abstract}".lower()
        tokens = tokenize(text)
        docs.append((text, tokens))
        for token in set(tokens):
            df_counts[token] = df_counts.get(token, 0) + 1

    return n_docs, df_counts, docs


def term_tfidf(tokens: list[str], variants: list[str], n_docs: int, df_counts: dict[str, int]) -> float:
    if not tokens:
        return 0.0

    joined = " ".join(tokens)
    tf = count_tf(joined, variants) / max(len(tokens), 1)
    df = 0
    for variant in variants:
        df = max(df, df_counts.get(variant, 0))
        if " " not in variant and "-" not in variant:
            df = max(df, sum(1 for t in set(tokens) if variant in t or t == variant))
    if df == 0 and document_contains(joined, variants):
        df = 1

    idf = math.log(n_docs / (1 + df))
    return tf * idf


def internal_impact_score(
    text: str,
    tokens: list[str],
    variants: list[str],
    n_docs: int,
    df_counts: dict[str, int],
) -> float:
    """
    I_i(d) = TFIDF(k_i, d, D) / Σ_w TFIDF(w, d, D) if k_i ∈ d, else 0  [Eq. 11]
    """
    if not document_contains(text, variants):
        return 0.0

    unique_tokens = list(dict.fromkeys(tokens))
    token_weights = [term_tfidf(tokens, [tok], n_docs, df_counts) for tok in unique_tokens]
    total = sum(token_weights)
    if total <= 0:
        return 0.0

    term_weight = term_tfidf(tokens, variants, n_docs, df_counts)
    return term_weight / total


def compute_doi_period(
    period_papers: list[ArxivPaper],
    variants: list[str],
    period_index: int,
    n_periods: int,
    n_docs: int,
    df_counts: dict[str, int],
) -> float:
    """DoI_i(t) = (Σ I_i(d) / |D(t)|) × (1 - α·(T-t))  [Eq. 12]"""
    if not period_papers:
        return 0.0

    impacts = [
        internal_impact_score(
            f"{paper.title} {paper.abstract}".lower(),
            tokenize(f"{paper.title} {paper.abstract}"),
            variants,
            n_docs,
            df_counts,
        )
        for paper in period_papers
    ]
    nn = max(len(impacts), 1)
    time_factor = 1.0 - TIME_WEIGHT * (n_periods - period_index)
    return (sum(impacts) / nn) * max(time_factor, 0.0)


def compute_term_statistics(
    term: str,
    papers: list[ArxivPaper],
    corpus_stats: tuple[int, dict[str, int], list[tuple[str, list[str]]]] | None = None,
) -> TermDVIResult:
    variants = term_variants(term)
    period_groups = group_papers_by_year(papers)
    n_periods = len(period_groups)
    n_docs, df_counts, _all_docs = corpus_stats or build_corpus_token_stats(papers)

    result = TermDVIResult(term=term)
    total_tf = 0
    total_df = 0

    for idx, (year, period_papers) in enumerate(period_groups, start=1):
        nn = len(period_papers)
        tf = sum(count_tf(f"{p.title} {p.abstract}", variants) for p in period_papers)
        df = sum(1 for p in period_papers if document_contains(f"{p.title} {p.abstract}", variants))
        dov = compute_dov(tf, nn, idx, n_periods)
        dod = compute_dod(df, nn, idx, n_periods)
        doi = compute_doi_period(period_papers, variants, idx, n_periods, n_docs, df_counts)

        result.periods.append(
            PeriodStats(period_index=idx, year=year, tf=tf, df=df, nn=nn, dov=dov, dod=dod, doi=doi)
        )
        total_tf += tf
        total_df += df

    for i in range(1, len(result.periods)):
        prev = result.periods[i - 1]
        cur = result.periods[i]
        cur.dov_rate = growth_rate(cur.dov, prev.dov)
        cur.dod_rate = growth_rate(cur.dod, prev.dod)
        cur.doi_rate = growth_rate(cur.doi, prev.doi)

    result.absolute_tf = total_tf / max(n_periods, 1)
    result.absolute_df = total_df / max(n_periods, 1)

    result.avg_dov = round(arithmetic_mean([p.dov for p in result.periods]), 6)
    result.avg_dod = round(arithmetic_mean([p.dod for p in result.periods]), 6)
    result.avg_doi = round(arithmetic_mean([p.doi for p in result.periods]), 6)
    result.avg_dov_rate = round(arithmetic_mean([p.dov_rate for p in result.periods if p.period_index > 1]), 6)
    result.avg_dod_rate = round(arithmetic_mean([p.dod_rate for p in result.periods if p.period_index > 1]), 6)
    result.avg_doi_rate = round(arithmetic_mean([p.doi_rate for p in result.periods if p.period_index > 1]), 6)

    result.visibility = result.avg_dov
    result.diffusion = result.avg_dod
    result.impact = result.avg_doi
    result.growth_rate = geometric_mean(
        [v for v in [result.avg_dov_rate, result.avg_dod_rate, result.avg_doi_rate] if v > 0]
    )

    return result


def normalize_scores(results: dict[str, TermDVIResult]) -> None:
    if not results:
        return

    # growth_rate is assigned by ML estimator in dvi_analyzer (not min-max here)
    for key in ("visibility", "diffusion", "impact"):
        values = [getattr(r, key) for r in results.values()]
        lo, hi = min(values), max(values)
        span = hi - lo
        for r in results.values():
            raw = getattr(r, key)
            norm = (raw - lo) / span if span > 0 else 0.5
            setattr(r, key, round(min(max(norm, 0.0), 1.0), 4))


def median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 0:
        return (ordered[mid - 1] + ordered[mid]) / 2
    return ordered[mid]


def classify_quadrant(
    avg_value: float,
    avg_rate: float,
    median_value: float,
    median_rate: float,
) -> str:
    """
    KVM / KDM / KIM quadrant rules (Wang & Zhu, 2026, Section 3.3.2):
      upper-left  (low value, high rate)  → weak_signal
      upper-right (high value, high rate) → strong_signal
      lower-left  (low value, low rate)   → latent_signal
      lower-right (high value, low rate)  → well_established
    """
    high_value = avg_value >= median_value
    high_rate = avg_rate >= median_rate

    if not high_value and high_rate:
        return "weak_signal"
    if high_value and high_rate:
        return "strong_signal"
    if not high_value and not high_rate:
        return "latent_signal"
    return "well_established"


def joint_classify_signal(q_vis: str, q_diff: str, q_imp: str) -> tuple[str, bool]:
    """
    Three-dimensional joint validation (Wang & Zhu, 2026):
    classify when the keyword falls in the same quadrant across KVM, KDM, and KIM.
    """
    quadrants = [q_vis, q_diff, q_imp]
    if quadrants[0] == quadrants[1] == quadrants[2]:
        return quadrants[0], True

    counts = Counter(quadrants)
    top, count = counts.most_common(1)[0]
    if count >= 2:
        return top, False

    # All three maps disagree — no strict joint class; prefer early-stage foresight signals
    for preferred in ("weak_signal", "latent_signal", "strong_signal", "well_established"):
        if preferred in quadrants:
            return preferred, False
    return quadrants[0], False


def compute_thresholds(results: dict[str, TermDVIResult]) -> DVIThresholds:
    items = list(results.values())
    return DVIThresholds(
        median_dov=median([r.avg_dov for r in items]),
        median_dov_rate=median([r.avg_dov_rate for r in items]),
        median_dod=median([r.avg_dod for r in items]),
        median_dod_rate=median([r.avg_dod_rate for r in items]),
        median_doi=median([r.avg_doi for r in items]),
        median_doi_rate=median([r.avg_doi_rate for r in items]),
    )


def assign_quadrants_and_classify(results: dict[str, TermDVIResult]) -> DVIThresholds:
    thresholds = compute_thresholds(results)

    for result in results.values():
        result.quadrant_visibility = classify_quadrant(
            result.avg_dov, result.avg_dov_rate,
            thresholds.median_dov, thresholds.median_dov_rate,
        )
        result.quadrant_diffusion = classify_quadrant(
            result.avg_dod, result.avg_dod_rate,
            thresholds.median_dod, thresholds.median_dod_rate,
        )
        result.quadrant_impact = classify_quadrant(
            result.avg_doi, result.avg_doi_rate,
            thresholds.median_doi, thresholds.median_doi_rate,
        )
        signal_type, consistent = joint_classify_signal(
            result.quadrant_visibility,
            result.quadrant_diffusion,
            result.quadrant_impact,
        )
        result.signal_type = signal_type
        result.joint_consistent = consistent
        result.composite = round(
            geometric_mean([result.visibility, result.diffusion, max(result.impact, 1e-9)]),
            4,
        )

    return thresholds


def classify_signal(
    result: TermDVIResult,
    avg_tf: float,
    avg_df: float,
    growth_threshold: float,
) -> str:
    """Return pre-computed MLWS-TF joint signal type."""
    return result.signal_type or "weak_signal"


def analyze_terms(
    terms: list[str],
    papers: list[ArxivPaper],
    entities: list[ExtractedEntity],
) -> tuple[dict[str, TermDVIResult], float, float, float, DVIThresholds]:
    unique_terms = list(dict.fromkeys(t for t in terms if t.strip()))
    corpus_stats = build_corpus_token_stats(papers)
    raw_results = {
        term: compute_term_statistics(term, papers, corpus_stats)
        for term in unique_terms
    }

    normalize_scores(raw_results)
    thresholds = assign_quadrants_and_classify(raw_results)

    avg_tf = sum(r.absolute_tf for r in raw_results.values()) / max(len(raw_results), 1)
    avg_df = sum(r.absolute_df for r in raw_results.values()) / max(len(raw_results), 1)
    growth_values = sorted(r.growth_rate for r in raw_results.values())
    growth_threshold = growth_values[max(int(len(growth_values) * 0.7) - 1, 0)] if growth_values else 0.0

    return raw_results, avg_tf, avg_df, growth_threshold, thresholds
