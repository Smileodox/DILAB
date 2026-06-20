"""Combinatorial scenario sampling with a soft CIB consistency filter.

Alternative to the Weimer-Jehle fixed-point path in ``morphological.py``. Instead of
collapsing the morphological field to its few CIB fixed points (and then forcing one
seed per archetype), this samples the field broadly and uses the SAME CIB matrix only
as a *soft* filter: a combination is kept unless it is strongly self-contradictory.

The kept combinations are written in the SAME schema as ``consistency_state.json`` so
that ``scenario_gen.run()`` consumes them as a drop-in. Downstream, narratives are
clustered in embedding space (see ``clustering.py``) and one representative per cluster
is chosen — the structure emerges bottom-up rather than from imposed archetypes.

Input:  morphbox_state.json + cib_state.json
Output: data/outputs/combinatorial_state.json
"""

from __future__ import annotations

import json
import logging
import random

from src import config
from src.models.morphological import (
    ConsistencyResult,
    DriverManifestation,
    MorphologicalBox,
)
from src.pipeline.morphological import (
    _config_key,
    _manif_position,
    _total_consistency,
    infer_scenario_type,
)

log = logging.getLogger(__name__)


def contradiction_ratio(
    config_map: dict[str, str],
    morph_box: MorphologicalBox,
    cib_matrix: list[list[int]],
    driver_index: dict[str, int],
) -> float:
    """Fraction of CIB cross-impact weight that is *misaligned* in this configuration.

    Uses the exact directional logic of ``support_score`` (morphological.py): for each
    ordered driver pair j→k with a non-zero CIB score, the pair is "aligned" when k's
    manifestation sits where j's influence pushes it (positive CIB pushes k toward the
    same optimism as j; negative CIB pushes the opposite way). Misalignment is the
    distance between k's actual position and that target, weighted by |CIB|.

    Returns 0.0 (every cross-impact perfectly satisfied) .. 1.0 (every one maximally
    violated). This is the soft replacement for the hard fixed-point gate.
    """
    total_weight = 0.0
    misaligned = 0.0
    for k_id, k_manif in config_map.items():
        k_idx = driver_index[k_id]
        k_pos = _manif_position(morph_box, k_id, k_manif)
        for j_id, j_manif in config_map.items():
            if j_id == k_id:
                continue
            j_idx = driver_index[j_id]
            cib_val = cib_matrix[j_idx][k_idx]
            if cib_val == 0:
                continue
            j_pos = _manif_position(morph_box, j_id, j_manif)
            optimism_j = 1.0 - j_pos
            target_pos = (1.0 - optimism_j) if cib_val > 0 else optimism_j
            distance = abs(k_pos - target_pos)
            weight = abs(cib_val)
            total_weight += weight
            misaligned += weight * distance

    if total_weight == 0.0:
        return 0.0
    return misaligned / total_weight


def sample_combinations(
    morph_box: MorphologicalBox,
    cib_matrix: list[list[int]],
    driver_index: dict[str, int],
    n_samples: int,
    oversample_factor: float = 3.0,
    reject_threshold: float = 0.35,
    seed: int | None = None,
) -> list[ConsistencyResult]:
    """Randomly sample distinct configurations, keeping the soft-CIB-consistent ones.

    Draws up to ``n_samples * oversample_factor`` i.i.d. configurations (one
    manifestation per driver), deduplicates, rejects any whose ``contradiction_ratio``
    exceeds ``reject_threshold``, and stops once ``n_samples`` are kept. Deterministic
    for a fixed ``seed``. No fixed-point iteration and no archetype quota — that is the
    whole point of the bottom-up method.
    """
    rng = random.Random(seed)
    n_draw = max(n_samples, int(n_samples * oversample_factor))
    seen: set[tuple[str, ...]] = set()
    kept: list[ConsistencyResult] = []
    n_drawn = 0
    n_rejected = 0

    for _ in range(n_draw):
        if len(kept) >= n_samples:
            break
        cfg = {d: rng.choice(morph_box.manifestations[d]) for d in morph_box.drivers}
        key = _config_key(cfg, morph_box)
        if key in seen:
            continue
        seen.add(key)
        n_drawn += 1

        cr = contradiction_ratio(cfg, morph_box, cib_matrix, driver_index)
        if cr > reject_threshold:
            n_rejected += 1
            continue

        score = _total_consistency(cfg, morph_box, cib_matrix, driver_index)
        kept.append(
            ConsistencyResult(
                configuration=dict(cfg),
                consistency_score=round(score, 3),
                is_consistent=True,
                contradiction_ratio=round(cr, 4),
                scenario_type=infer_scenario_type(cfg, morph_box),  # descriptive only
                is_fixed_point=False,
                frequency=1,
            )
        )

    # Most internally-consistent first (purely for stable, readable output ordering).
    kept.sort(key=lambda r: (r.contradiction_ratio, -r.consistency_score))

    if len(kept) < n_samples:
        log.warning(
            "Combinatorial sampling kept %d/%d (drew %d unique, rejected %d at threshold %.2f). "
            "Raise COMBI_OVERSAMPLE_FACTOR or COMBI_REJECT_THRESHOLD for more.",
            len(kept), n_samples, n_drawn, n_rejected, reject_threshold,
        )
    else:
        log.info(
            "Combinatorial sampling: kept %d (drew %d unique, rejected %d at threshold %.2f)",
            len(kept), n_drawn, n_rejected, reject_threshold,
        )
    return kept


def run(
    morphbox_state_path: str = "data/outputs/morphbox_state.json",
    cib_state_path: str = "data/outputs/cib_state.json",
    output_path: str = "data/outputs/combinatorial_state.json",
    n_samples: int | None = None,
    oversample_factor: float | None = None,
    reject_threshold: float | None = None,
    seed: int | None = None,
) -> dict:
    """Load the morphological box + CIB matrix, sample combinations, write state file."""
    n_samples = config.COMBI_N_SAMPLES if n_samples is None else n_samples
    oversample_factor = (
        config.COMBI_OVERSAMPLE_FACTOR if oversample_factor is None else oversample_factor
    )
    reject_threshold = (
        config.COMBI_REJECT_THRESHOLD if reject_threshold is None else reject_threshold
    )
    seed = config.COMBI_SEED if seed is None else seed

    with open(morphbox_state_path) as f:
        morphbox_raw = json.load(f)
    with open(cib_state_path) as f:
        cib = json.load(f)

    morph_box = MorphologicalBox(
        drivers=morphbox_raw["drivers"],
        manifestations=morphbox_raw["manifestations"],
        all_manifestations=[
            DriverManifestation(**m) for m in morphbox_raw["all_manifestations"]
        ],
    )
    cib_matrix = cib["matrix"]
    driver_index = {did: i for i, did in enumerate(cib["driver_ids"])}

    results = sample_combinations(
        morph_box,
        cib_matrix,
        driver_index,
        n_samples=n_samples,
        oversample_factor=oversample_factor,
        reject_threshold=reject_threshold,
        seed=seed,
    )

    state = {
        "configs": [r.model_dump(mode="json") for r in results],
        "method": "combinatorial",
        "sampling": {
            "n_samples_target": n_samples,
            "n_kept": len(results),
            "oversample_factor": oversample_factor,
            "reject_threshold": reject_threshold,
            "seed": seed,
        },
        "n_combinations": len(results),
    }
    with open(output_path, "w") as f:
        json.dump(state, f, indent=2)

    print(f"  Combinatorial: {len(results)} combinations kept → {output_path}")
    return state
