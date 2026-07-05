"""Does the scenario field carry structure, or is it indistinguishable from random?

The combinatorial and Zwicky methods both sample a morphological field under a soft
consistency filter, then hunt for cluster structure in config space. This module asks
the prior question: does the kept sample carry ANY geometric structure that a *uniform
random* sample of the same field would not? If it does not, no clustering or projection
lever can help — the constraint signal (CIB / CCA) is too weak to shape the space, and a
diffuse high-dimensional cloud has, by concentration of measure, neither natural clusters
nor a dominant axis.

Three scale-free statistics on the one-hot config matrix:
  - ``effective_dim``     participation ratio of the PCA variance spectrum
                          (sum(var)^2 / sum(var^2)); high ⇒ isotropic, no dominant axis.
  - ``pc1``               share of variance on the top principal component; a genuine
                          dominant axis (a true continuum) would make this stand out.
  - ``best_silhouette``   peak K-means silhouette over a k-range; ceiling on separability.

Each is compared against a uniform-random null model over the SAME field (same drivers,
same #manifestations each, same n). When the pipeline output sits inside the null
distribution, the scenarios are — geometrically — a random sample of the field, and the
honest conclusion is that the elicited consistency constraints add no structure.

Pure / numpy-only and offline (no LLM, no embeddings): it consumes already-generated
config assignments, so it is fully unit-testable and reproducible for the write-up.
"""

from __future__ import annotations

import logging
import random

import numpy as np

from src.pipeline.clustering import cluster_and_select, config_matrix

log = logging.getLogger(__name__)


def _spectrum(x: np.ndarray) -> tuple[np.ndarray, float]:
    """PCA variance shares (descending) and the participation ratio of the spectrum.

    The participation ratio sum(v)^2 / sum(v^2) is the "effective number of dimensions":
    1.0 when all variance is on one axis, →rank when variance is spread evenly.
    """
    xc = x - x.mean(axis=0, keepdims=True)
    sv = np.linalg.svd(xc, full_matrices=False, compute_uv=False)
    var = sv**2
    total = var.sum()
    if total == 0:
        return np.zeros_like(var), 1.0
    shares = var / total
    eff_dim = float((shares.sum() ** 2) / (shares**2).sum())
    return shares, eff_dim


def structure_stats(
    x: np.ndarray,
    ids: list[str],
    k_range: tuple[int, int] = (4, 10),
    seed: int = 42,
) -> dict:
    """Compute (effective_dim, pc1..pc3, best_silhouette) for one config matrix."""
    shares, eff_dim = _spectrum(x)
    cl = cluster_and_select(x, ids, k=None, k_range=k_range, seed=seed)
    return {
        "n": int(x.shape[0]),
        "dims": int(x.shape[1]),
        "effective_dim": round(eff_dim, 3),
        "pc1": round(float(shares[0]) if shares.size > 0 else 0.0, 4),
        "pc2": round(float(shares[1]) if shares.size > 1 else 0.0, 4),
        "pc3": round(float(shares[2]) if shares.size > 2 else 0.0, 4),
        "best_silhouette": cl["silhouette"],
        "best_k": cl["k"],
    }


def random_field_scenarios(
    drivers: list[str],
    manifestations: dict[str, list[str]],
    n: int,
    rng: random.Random,
) -> list[dict]:
    """``n`` scenarios drawn uniformly at random from the morphological field.

    One manifestation per driver, i.i.d. uniform — the null model the real sample is
    tested against. Shaped like real scenarios (``assumptions`` list) so the same
    ``config_matrix`` builds the one-hot encoding (keeps the comparison apples-to-apples).
    """
    out = []
    for _ in range(n):
        out.append(
            {"assumptions": [{"manifestation_id": rng.choice(manifestations[d])} for d in drivers]}
        )
    return out


def null_distribution(
    drivers: list[str],
    manifestations: dict[str, list[str]],
    vocab: list[str],
    n: int,
    trials: int = 20,
    k_range: tuple[int, int] = (4, 10),
    seed: int = 0,
) -> dict:
    """Mean ± std of each structure statistic over ``trials`` uniform-random fields."""
    rng = random.Random(seed)
    rows = []
    for t in range(trials):
        scens = random_field_scenarios(drivers, manifestations, n, rng)
        rows.append(structure_stats(config_matrix(scens, vocab), [f"r{i}" for i in range(n)],
                                    k_range=k_range, seed=seed + t))
    agg = {}
    for key in ("effective_dim", "pc1", "best_silhouette"):
        vals = np.array([r[key] for r in rows], dtype=float)
        agg[key] = {"mean": round(float(vals.mean()), 4), "std": round(float(vals.std(ddof=1)), 4)}
    agg["trials"] = trials
    return agg


# Below this K-means silhouette, clusters are not separated enough to read as archetypes
# (a common rule of thumb: <0.25 = no substantial structure). A constraint filter can push
# the sample off the uniform null *statistically* without ever clearing this practical bar.
USABLE_SILHOUETTE_FLOOR = 0.25


def configs_to_scenarios(configs: list[dict]) -> list[dict]:
    """Adapt combinatorial-state configs to the scenario shape the matrix builder expects.

    A config carries ``configuration`` = {driver_id: manifestation_id}; the structure test
    only needs the manifestation set, so this lets the null test run straight on sampled
    configs without first generating narratives (isolates the CCA variable, keeps it cheap).
    """
    out = []
    for i, c in enumerate(configs):
        cfg = c.get("configuration", {})
        out.append({"id": c.get("id", f"c{i}"),
                    "assumptions": [{"manifestation_id": m} for m in cfg.values()]})
    return out


def analyze(
    scenarios: list[dict],
    morphbox: dict,
    k_range: tuple[int, int] = (4, 10),
    null_trials: int = 20,
    seed: int = 42,
    silhouette_floor: float = USABLE_SILHOUETTE_FLOOR,
) -> dict:
    """Compare a method's scenario field to a uniform-random null over the same field.

    ``morphbox`` is the parsed ``morphbox_*_state.json`` (drivers, manifestations,
    all_manifestations). Returns the observed statistics, the null distribution, per-
    statistic z-scores, and a three-way verdict.

    Two separate questions, deliberately not conflated:
      - ``above_null``: is the sample statistically distinguishable from random
        (silhouette z >= 2)? A binding constraint filter shows up here.
      - ``usable_structure``: is the separation also large enough *in absolute terms*
        (silhouette >= ``silhouette_floor``) to read as archetypes? This is what a
        clustering deliverable actually needs — and statistical significance alone does
        not deliver it.
    """
    drivers = morphbox["drivers"]
    manifestations = morphbox["manifestations"]
    vocab = [m["id"] for m in morphbox["all_manifestations"]]
    ids = [s.get("id", f"s{i}") for i, s in enumerate(scenarios)]

    observed = structure_stats(config_matrix(scenarios, vocab), ids, k_range=k_range, seed=seed)
    null = null_distribution(drivers, manifestations, vocab, n=len(scenarios),
                             trials=null_trials, k_range=k_range, seed=seed)

    def _z(key):
        std = null[key]["std"] or 1e-9
        return round((observed[key] - null[key]["mean"]) / std, 2)

    z = {key: _z(key) for key in ("effective_dim", "pc1", "best_silhouette")}
    above_null = z["best_silhouette"] >= 2.0
    usable_structure = above_null and observed["best_silhouette"] >= silhouette_floor
    if usable_structure:
        verdict = "usable structure"
    elif above_null:
        verdict = "above null, but no usable clusters"
    else:
        verdict = "≈ uniform random"
    return {
        "observed": observed,
        "null": null,
        "z_scores": z,
        "above_null": bool(above_null),
        "usable_structure": bool(usable_structure),
        "verdict": verdict,
    }


# --- axis-DIRECTION stability referee -------------------------------------------------
# The null test asks "is the signal bigger than random?" (magnitude). This asks the second,
# easily-forgotten question: "does the axis MEAN the same thing twice?" (direction). A
# near-isotropic field (pc1 ≈ pc2) has degenerate leading PCs whose *direction* is ill-defined,
# so the top PC's loading vector rotates across elicitations/reseeds — and any "the axis is X"
# interpretation is then a labelling artifact, not a robust finding. Magnitude-robust ≠
# meaning-robust; conflating the two is the trap that bit both the reviewer and this author.
DIRECTION_STABILITY_BAR = 0.7


def pc_loadings(scenarios: list[dict], vocab: list[str], k: int = 3) -> np.ndarray:
    """Top-``k`` PC loading vectors (unit rows) of the one-hot config field — the axis DIRECTIONS.

    These are the right-singular vectors of the centred config matrix, i.e. which manifestations
    define each principal axis. Compare them across elicitations to test direction stability.
    """
    x = config_matrix(scenarios, vocab).astype(float)
    xc = x - x.mean(axis=0, keepdims=True)
    _, _, vt = np.linalg.svd(xc, full_matrices=False)
    return vt[: min(k, vt.shape[0])]


def axis_direction_stability(field_a: list[dict], field_b: list[dict], vocab: list[str],
                             k: int = 3, bar: float = DIRECTION_STABILITY_BAR) -> dict:
    """|cos| of matched PC loadings across two config fields (sign-invariant) + #stable axes.

    ``field_a``/``field_b`` are scenario lists from two elicitations (or reseeds) over the SAME
    manifestation ``vocab``. Returns per-axis absolute cosine of the loading vectors and how many
    clear the ``bar`` (an a-priori "same axis" threshold, NOT tuned to any downstream metric).
    Low |cos| even between reseeds ⇒ the field is near-isotropic and its "axes" are not real.
    """
    La, Lb = pc_loadings(field_a, vocab, k), pc_loadings(field_b, vocab, k)
    m = min(La.shape[0], Lb.shape[0])
    cosines = [round(abs(float(La[i] @ Lb[i])), 4) for i in range(m)]
    return {"abs_cos": cosines, "stable_axes": sum(1 for c in cosines if c >= bar), "bar": bar}
