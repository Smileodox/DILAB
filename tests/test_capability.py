"""Capability proof: the soft-CIB sampler turns driver COUPLING into detectable structure.

This is the experiment that settles "is the pipeline broken, or are the drivers bad?".
We feed the REAL ``combinatorial.sample_combinations`` a synthetic morphological field and
vary ONLY the CIB coupling:

  - 8 drivers, 2 manifestations each (binary optimism: ``_o`` = optimistic, ``_p`` = pessimistic).
  - Two blocks of 4. within-block CIB = +S (members want the SAME optimism);
    cross-block CIB = -S (blocks want OPPOSITE optimism).

At strong coupling the only low-contradiction worlds are two mirror archetypes
(block-A optimistic / block-B pessimistic, and vice-versa) → the sampled field CLUSTERS.
At zero coupling the soft filter is inert → a uniform-random field → no structure.

The live spectrum field (pc1 ~0.07, eff_dim ~29/55, silhouette ~0.08, "above null, no
clusters") matches the UNCOUPLED case here — i.e. the ≈random/continuum result is a
driver-coupling deficit, not a defect in the machinery. NOTE: ``contradiction_ratio`` is a
*normalized* ratio, so coupling magnitude cancels (S=1, 2, 3 are identical) — this proves
coupling PRESENT vs ABSENT, not a graded strength dial.

Pure / offline (no LLM, no embeddings, no data/outputs), deterministic for a fixed seed.
"""
from __future__ import annotations

from src.models.morphological import DriverManifestation, MorphologicalBox
from src.pipeline import structure
from src.pipeline.combinatorial import sample_combinations

N_DRIVERS = 8
BLOCK_SIZE = 4  # two blocks of 4


def _synthetic_field():
    """8 binary drivers in two blocks; returns (MorphologicalBox, morphbox-dict, driver_index, block)."""
    drivers = [f"d{i}" for i in range(N_DRIVERS)]
    manifs = {d: [f"{d}_o", f"{d}_p"] for d in drivers}  # index 0 = optimistic, 1 = pessimistic
    all_manifestations = [
        {"id": m, "driver_id": d, "label": m, "description": "", "plausibility": "medium"}
        for d in drivers
        for m in manifs[d]
    ]
    box = MorphologicalBox(
        drivers=drivers,
        manifestations=manifs,
        all_manifestations=[DriverManifestation(**m) for m in all_manifestations],
    )
    mdict = {"drivers": drivers, "manifestations": manifs, "all_manifestations": all_manifestations}
    driver_index = {d: i for i, d in enumerate(drivers)}
    block = {d: (0 if i < BLOCK_SIZE else 1) for i, d in enumerate(drivers)}
    return box, mdict, driver_index, block


def _cib_matrix(block: dict[str, int], drivers: list[str], strength: int) -> list[list[int]]:
    """within-block = +strength, cross-block = -strength, diagonal = 0."""
    n = len(drivers)
    m = [[0] * n for _ in range(n)]
    for a in range(n):
        for b in range(n):
            if a == b:
                continue
            m[a][b] = strength if block[drivers[a]] == block[drivers[b]] else -strength
    return m


def _run(strength: int) -> tuple[dict, int]:
    box, mdict, didx, block = _synthetic_field()
    cib = _cib_matrix(block, box.drivers, strength)
    kept = sample_combinations(
        box, cib, didx, n_samples=150, oversample_factor=20, reject_threshold=0.35, seed=42
    )
    scenarios = structure.configs_to_scenarios([r.model_dump(mode="json") for r in kept])
    res = structure.analyze(scenarios, mdict, k_range=(2, 6), null_trials=20, seed=42)
    return res, len(kept)


def test_coupling_on_yields_usable_structure():
    """Strong block-anti-aligned coupling → the sampler produces clean, separable clusters."""
    res, n_kept = _run(strength=3)
    assert n_kept >= 10  # the archetype ball survives the soft filter
    assert res["verdict"] == "usable structure"
    assert res["usable_structure"] is True
    assert res["observed"]["best_silhouette"] > 0.5   # observed ~0.72, far above the 0.25 floor
    assert res["observed"]["pc1"] > 0.4               # observed ~0.61: a genuine dominant axis
    assert res["observed"]["effective_dim"] < 4.0     # observed ~2.5: collapses toward 2 axes
    assert res["z_scores"]["best_silhouette"] > 3.0   # observed z ~8.6


def test_coupling_off_is_indistinguishable_from_random():
    """Zero coupling → inert filter → a uniform-random field → no structure (honest default)."""
    res, n_kept = _run(strength=0)
    assert n_kept >= 100  # nothing rejected
    assert res["verdict"] == "≈ uniform random"
    assert res["usable_structure"] is False
    assert res["observed"]["effective_dim"] > 6.0     # observed ~7.8 of max 8: isotropic
