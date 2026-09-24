from pathlib import Path

import pytest
from pydantic import ValidationError

from mcp_test_harness.models.scenario import ScenarioAssertions, TestScenario
from mcp_test_harness.models.scenario_loader import (
    ScenarioLoadError,
    load_scenarios_from_file,
    load_scenarios_from_text,
)

VALID_SCENARIO = {
    "name": "list_users",
    "server": "demo",
    "tool": "list_users",
    "input": {"limit": 5},
    "assertions": {"status": "success", "min_items": 1},
}


# --- TestScenario / ScenarioAssertions model validation ---------------------


def test_valid_scenario_is_accepted() -> None:
    scenario = TestScenario.model_validate(VALID_SCENARIO)

    assert scenario.name == "list_users"
    assert scenario.server == "demo"
    assert scenario.tool == "list_users"
    assert scenario.input == {"limit": 5}
    assert scenario.assertions == ScenarioAssertions(status="success", min_items=1)


def test_scenario_defaults_input_to_empty_mapping() -> None:
    data = {key: value for key, value in VALID_SCENARIO.items() if key != "input"}

    scenario = TestScenario.model_validate(data)

    assert scenario.input == {}


@pytest.mark.parametrize("missing_field", ["name", "server", "tool", "assertions"])
def test_scenario_missing_required_field_is_rejected(missing_field: str) -> None:
    data = dict(VALID_SCENARIO)
    del data[missing_field]

    with pytest.raises(ValidationError):
        TestScenario.model_validate(data)


def test_scenario_rejects_unknown_top_level_field() -> None:
    data = {**VALID_SCENARIO, "unexpected": "field"}

    with pytest.raises(ValidationError):
        TestScenario.model_validate(data)


def test_scenario_rejects_blank_name() -> None:
    data = {**VALID_SCENARIO, "name": ""}

    with pytest.raises(ValidationError):
        TestScenario.model_validate(data)


def test_assertions_reject_unknown_key() -> None:
    with pytest.raises(ValidationError):
        ScenarioAssertions.model_validate({"status": "success", "totally_made_up": True})


def test_assertions_require_at_least_one_check() -> None:
    with pytest.raises(ValidationError):
        ScenarioAssertions.model_validate({})


def test_assertions_reject_min_items_greater_than_max_items() -> None:
    with pytest.raises(ValidationError):
        ScenarioAssertions.model_validate({"min_items": 5, "max_items": 1})


def test_assertions_accept_equals_check_alone() -> None:
    assertions = ScenarioAssertions.model_validate({"equals": "ok"})

    assert assertions.equals == "ok"


# --- Loading from YAML / JSON text -------------------------------------------


def test_load_single_scenario_from_yaml_text() -> None:
    text = """
name: list_users
server: demo
tool: list_users
input:
  limit: 5
assertions:
  status: success
  min_items: 1
"""

    scenarios = load_scenarios_from_text(text, format="yaml")

    assert len(scenarios) == 1
    assert scenarios[0].name == "list_users"


def test_load_multiple_scenarios_from_yaml_text() -> None:
    text = """
- name: list_users
  server: demo
  tool: list_users
  assertions:
    status: success
- name: get_user
  server: demo
  tool: get_user
  input:
    id: 1
  assertions:
    status: success
"""

    scenarios = load_scenarios_from_text(text, format="yaml")

    assert [scenario.name for scenario in scenarios] == ["list_users", "get_user"]


def test_load_scenarios_from_json_text() -> None:
    import json

    text = json.dumps([VALID_SCENARIO])

    scenarios = load_scenarios_from_text(text, format="json")

    assert len(scenarios) == 1
    assert scenarios[0].tool == "list_users"


def test_load_scenarios_rejects_malformed_yaml_syntax() -> None:
    with pytest.raises(ScenarioLoadError):
        load_scenarios_from_text("name: [unterminated", format="yaml")


def test_load_scenarios_rejects_malformed_json_syntax() -> None:
    with pytest.raises(ScenarioLoadError):
        load_scenarios_from_text("{not valid json", format="json")


def test_load_scenarios_rejects_empty_source() -> None:
    with pytest.raises(ScenarioLoadError, match="empty"):
        load_scenarios_from_text("", format="yaml")


def test_load_scenarios_rejects_non_mapping_list_item() -> None:
    with pytest.raises(ScenarioLoadError, match="must be a mapping"):
        load_scenarios_from_text("- just a string\n- name: also-not-a-mapping-list", format="yaml")


def test_load_scenarios_reports_which_scenario_is_invalid() -> None:
    text = """
- name: good_one
  server: demo
  tool: list_users
  assertions:
    status: success
- name: bad_one
  server: demo
  tool: list_users
  assertions: {}
"""

    with pytest.raises(ScenarioLoadError, match="bad_one"):
        load_scenarios_from_text(text, format="yaml")


# --- Loading from files -------------------------------------------------------


def test_load_scenarios_from_yaml_file(tmp_path: Path) -> None:
    scenario_file = tmp_path / "scenarios.yaml"
    scenario_file.write_text(
        "name: list_users\nserver: demo\ntool: list_users\nassertions:\n  status: success\n",
        encoding="utf-8",
    )

    scenarios = load_scenarios_from_file(scenario_file)

    assert len(scenarios) == 1
    assert scenarios[0].name == "list_users"


def test_load_scenarios_from_json_file(tmp_path: Path) -> None:
    import json

    scenario_file = tmp_path / "scenarios.json"
    scenario_file.write_text(json.dumps([VALID_SCENARIO]), encoding="utf-8")

    scenarios = load_scenarios_from_file(scenario_file)

    assert len(scenarios) == 1


def test_load_scenarios_from_file_rejects_unsupported_extension(tmp_path: Path) -> None:
    scenario_file = tmp_path / "scenarios.txt"
    scenario_file.write_text("name: x", encoding="utf-8")

    with pytest.raises(ScenarioLoadError, match="unsupported"):
        load_scenarios_from_file(scenario_file)


def test_load_scenarios_from_file_reports_missing_file() -> None:
    with pytest.raises(ScenarioLoadError):
        load_scenarios_from_file("does/not/exist.yaml")


def test_load_scenarios_from_file_includes_file_path_in_error(tmp_path: Path) -> None:
    scenario_file = tmp_path / "broken.yaml"
    scenario_file.write_text("name: [unterminated", encoding="utf-8")

    with pytest.raises(ScenarioLoadError, match=r"broken\.yaml"):
        load_scenarios_from_file(scenario_file)
