def test_scenario_chunk_ids_in_kb(sample_scenarios, kb_state):
    chunks = kb_state["chunks"]
    for s in sample_scenarios:
        for cid in s.source_chunk_ids:
            assert cid in chunks, f"Scenario '{s.title}' references missing chunk {cid}"


def test_chunk_source_ids_exist(sample_scenarios, kb_state):
    chunks = kb_state["chunks"]
    sources = kb_state["sources"]
    for s in sample_scenarios:
        for cid in s.source_chunk_ids:
            if cid in chunks:
                sid = chunks[cid]["source_id"]
                assert sid in sources, f"Chunk {cid} references missing source {sid}"


def test_assessment_chunk_ids_in_kb(sample_assessments, kb_state):
    chunks = kb_state["chunks"]
    for a in sample_assessments:
        for cid in a.source_chunk_ids:
            assert cid in chunks, f"Assessment for {a.scenario_id} references missing chunk {cid}"


def test_driver_chunk_ids_in_kb(sample_drivers, kb_state):
    chunks = kb_state["chunks"]
    for d in sample_drivers:
        for cid in d.source_chunk_ids:
            assert cid in chunks, f"Driver '{d.name}' references missing chunk {cid}"


def test_scenario_assumptions_reference_valid_drivers(sample_scenarios, sample_drivers):
    driver_ids = {d.id for d in sample_drivers}
    for s in sample_scenarios:
        for a in s.assumptions:
            assert a.driver_id in driver_ids, (
                f"Scenario '{s.title}' assumption references unknown driver {a.driver_id}"
            )


def test_no_orphan_assessments(sample_assessments, sample_scenarios):
    scenario_ids = {s.id for s in sample_scenarios}
    for a in sample_assessments:
        assert a.scenario_id in scenario_ids, f"Assessment references unknown scenario {a.scenario_id}"
