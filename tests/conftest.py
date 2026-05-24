import json
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


@pytest.fixture
def merge_state():
    return _load("merge_state.json")


@pytest.fixture
def scenario_state():
    return _load("scenario_state.json")


@pytest.fixture
def final_analysis():
    return _load("final_analysis.json")


@pytest.fixture
def kb_state():
    return _load("kb_state.json")


@pytest.fixture
def cib_state():
    return _load("cib_state.json")


@pytest.fixture
def sample_drivers(merge_state):
    from src.models.drivers import TechDriver
    return [TechDriver(**d) for d in merge_state["unified_drivers"]]


@pytest.fixture
def sample_scenarios(scenario_state):
    from src.models.scenarios import Scenario
    return [Scenario(**s) for s in scenario_state["scenarios"]]


@pytest.fixture
def sample_assessments(final_analysis):
    from src.models.evaluation import Assessment
    return [Assessment(**a) for a in final_analysis["assessments"]]


@pytest.fixture
def morphbox_state():
    return _load("morphbox_state.json")


@pytest.fixture
def consistency_state():
    return _load("consistency_state.json")
