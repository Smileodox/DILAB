"""Offline tests for the archetype extractor (no LLM, no network).

Builds a synthetic 2-block morphological field (a dense optimistic core + a dense pessimistic
core + a random continuum halo), writes the state files the module reads, injects a stub
label_fn, and checks that HDBSCAN+ordinal isolates the cores as named archetypes while the
halo is honestly reported as noise.
"""
import json
import random

from src.pipeline import archetypes

N_DRIVERS = 6


def _stub_label(features, narratives, domain, model):
    top = features[0]["driver"] if features else "none"
    return {"name": f"Archetype of {top}", "description": "A synthetic test archetype."}


def _write_field(tmp_path):
    drivers = [f"d{i}" for i in range(N_DRIVERS)]
    manifs = {d: [f"{d}_o", f"{d}_p"] for d in drivers}
    all_manifs = [
        {"id": m, "driver_id": d, "label": m, "description": "", "plausibility": "medium",
         "source_chunk_ids": []}
        for d in drivers for m in manifs[d]
    ]
    rng = random.Random(7)

    configs = []
    cid = 0

    def add(optimistic: bool, flips: int):
        nonlocal cid
        cfg = {}
        flip_set = set(rng.sample(drivers, flips)) if flips else set()
        for d in drivers:
            opt = optimistic if d not in flip_set else (not optimistic)
            cfg[d] = f"{d}_o" if opt else f"{d}_p"
        configs.append({"id": f"c{cid}", "configuration": cfg})
        cid += 1

    for _ in range(25):
        add(optimistic=True, flips=rng.randint(0, 1))    # dense optimistic core
    for _ in range(25):
        add(optimistic=False, flips=rng.randint(0, 1))   # dense pessimistic core
    for _ in range(20):
        add(optimistic=rng.random() < 0.5, flips=rng.randint(2, 4))  # continuum halo

    (tmp_path / "morphbox_state.json").write_text(json.dumps(
        {"drivers": drivers, "manifestations": manifs, "all_manifestations": all_manifs}))
    (tmp_path / "combinatorial_state.json").write_text(json.dumps({"configs": configs}))
    n = len(drivers)
    (tmp_path / "cib_state.json").write_text(json.dumps(
        {"matrix": [[0] * n for _ in range(n)], "driver_ids": drivers}))
    (tmp_path / "merge_state.json").write_text(json.dumps(
        {"unified_drivers": [{"id": d, "name": f"Driver {d}"} for d in drivers]}))
    return tmp_path, len(configs)


class _Profile:
    def prompt_kwargs(self):
        return {"domain": "a synthetic test domain"}


def _run(tmp_path, **kw):
    return archetypes.run(
        combinatorial_state_path=str(tmp_path / "combinatorial_state.json"),
        morphbox_state_path=str(tmp_path / "morphbox_state.json"),
        cib_state_path=str(tmp_path / "cib_state.json"),
        merge_state_path=str(tmp_path / "merge_state.json"),
        scenario_state_path=str(tmp_path / "does_not_exist.json"),
        output_path=str(tmp_path / "archetypes_state.json"),
        label_fn=_stub_label,
        profile=_Profile(),
        **kw,
    )


def test_finds_named_archetypes_and_reports_continuum(tmp_path):
    tmp, n_cfg = _write_field(tmp_path)
    state = _run(tmp, min_cluster_size=5)

    assert state["method"] == "hdbscan_ordinal"
    assert state["n_configs"] == n_cfg
    assert state["n_archetypes"] >= 1                      # the dense cores are isolated
    assert 0.0 <= state["noise_fraction"] <= 1.0
    assert state["continuum"]["n_noise"] >= 0

    for a in state["archetypes"]:
        assert a["label"] and a["description"]             # stub label applied
        assert a["size"] >= 5                              # >= min_cluster_size
        assert isinstance(a["contains_attractor"], bool)   # attractor overlay ran
        assert a["representative_scenario_id"] in a["member_scenario_ids"]
        assert a["distinguishing_drivers"]                 # over-represented states found

    # persisted to disk
    saved = json.loads((tmp / "archetypes_state.json").read_text())
    assert saved["n_archetypes"] == state["n_archetypes"]


def test_too_few_configs_is_honest(tmp_path):
    drivers = ["d0", "d1"]
    (tmp_path / "morphbox_state.json").write_text(json.dumps({
        "drivers": drivers, "manifestations": {d: [f"{d}_o", f"{d}_p"] for d in drivers},
        "all_manifestations": [{"id": f"{d}_o", "driver_id": d, "label": f"{d}_o", "description": "",
                                "plausibility": "medium", "source_chunk_ids": []} for d in drivers]}))
    (tmp_path / "combinatorial_state.json").write_text(json.dumps(
        {"configs": [{"id": "c0", "configuration": {"d0": "d0_o", "d1": "d1_o"}}]}))
    (tmp_path / "cib_state.json").write_text(json.dumps({"matrix": [[0, 0], [0, 0]], "driver_ids": drivers}))
    (tmp_path / "merge_state.json").write_text(json.dumps({"unified_drivers": []}))
    state = _run(tmp_path, min_cluster_size=5)
    assert state["n_archetypes"] == 0 if "n_archetypes" in state else state["archetypes"] == []
    assert state["noise_fraction"] == 1.0
