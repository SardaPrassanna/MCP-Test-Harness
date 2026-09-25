"""Unit tests for reusable assertion evaluation.

Exercises `evaluate_assertions()` directly against hand-built
`ToolCallOutcome` values -- no MCP transport, session, or subprocess is
involved anywhere in this file.
"""

import pytest
from pydantic import ValidationError

from mcp_test_harness.assertions.evaluator import ToolCallOutcome, evaluate_assertions
from mcp_test_harness.models.result import AssertionResult
from mcp_test_harness.models.scenario import ScenarioAssertions

SUCCESS = ToolCallOutcome(is_error=False, value={"name": "Alice", "id": 1})
ERROR = ToolCallOutcome(is_error=True, value="boom")
ITEMS = ToolCallOutcome(is_error=False, value=["a", "b", "c"])


def _by_assertion(results: list[AssertionResult], assertion: str) -> AssertionResult:
    matches = [result for result in results if result.assertion == assertion]
    assert len(matches) == 1, f"expected exactly one {assertion!r} result, got {matches}"
    return matches[0]


# --- status ------------------------------------------------------------------


def test_status_equals_passes_on_match() -> None:
    results = evaluate_assertions(ScenarioAssertions(status="success"), SUCCESS)

    result = _by_assertion(results, "status")
    assert result.passed is True
    assert result.expected == "success"
    assert result.actual == "success"


def test_status_equals_fails_on_mismatch() -> None:
    results = evaluate_assertions(ScenarioAssertions(status="success"), ERROR)

    result = _by_assertion(results, "status")
    assert result.passed is False
    assert result.expected == "success"
    assert result.actual == "error"
    assert "success" in result.message and "error" in result.message


# --- response contains ---------------------------------------------------------


def test_response_contains_passes_when_present() -> None:
    results = evaluate_assertions(ScenarioAssertions(contains="name"), SUCCESS)

    result = _by_assertion(results, "contains")
    assert result.passed is True
    assert result.actual == SUCCESS.value


def test_response_contains_fails_when_absent() -> None:
    results = evaluate_assertions(ScenarioAssertions(contains="missing_key"), SUCCESS)

    result = _by_assertion(results, "contains")
    assert result.passed is False
    assert result.expected == "missing_key"


def test_response_contains_fails_gracefully_on_unsupported_value() -> None:
    outcome = ToolCallOutcome(is_error=False, value=42)

    results = evaluate_assertions(ScenarioAssertions(contains="x"), outcome)

    result = _by_assertion(results, "contains")
    assert result.passed is False
    assert "does not support containment" in result.message


# --- response field equals ------------------------------------------------------


def test_response_field_equals_passes_on_match() -> None:
    results = evaluate_assertions(ScenarioAssertions(field_equals={"name": "Alice"}), SUCCESS)

    result = _by_assertion(results, "field_equals[name]")
    assert result.passed is True
    assert result.expected == "Alice"
    assert result.actual == "Alice"


def test_response_field_equals_fails_on_mismatch() -> None:
    results = evaluate_assertions(ScenarioAssertions(field_equals={"name": "Bob"}), SUCCESS)

    result = _by_assertion(results, "field_equals[name]")
    assert result.passed is False
    assert result.expected == "Bob"
    assert result.actual == "Alice"


def test_response_field_equals_fails_when_field_missing() -> None:
    results = evaluate_assertions(ScenarioAssertions(field_equals={"missing": 1}), SUCCESS)

    result = _by_assertion(results, "field_equals[missing]")
    assert result.passed is False
    assert result.actual is None


def test_response_field_equals_fails_when_response_is_not_object_like() -> None:
    results = evaluate_assertions(ScenarioAssertions(field_equals={"name": "Alice"}), ERROR)

    result = _by_assertion(results, "field_equals[name]")
    assert result.passed is False


def test_response_field_equals_checks_multiple_fields_independently() -> None:
    results = evaluate_assertions(
        ScenarioAssertions(field_equals={"name": "Alice", "id": 999}), SUCCESS
    )

    name_result = _by_assertion(results, "field_equals[name]")
    id_result = _by_assertion(results, "field_equals[id]")
    assert name_result.passed is True
    assert id_result.passed is False


# --- response field exists ---------------------------------------------------------


def test_response_field_exists_passes_when_present() -> None:
    results = evaluate_assertions(ScenarioAssertions(field_exists=["name"]), SUCCESS)

    result = _by_assertion(results, "field_exists[name]")
    assert result.passed is True
    assert result.expected is True
    assert result.actual is True


def test_response_field_exists_fails_when_absent() -> None:
    results = evaluate_assertions(ScenarioAssertions(field_exists=["missing"]), SUCCESS)

    result = _by_assertion(results, "field_exists[missing]")
    assert result.passed is False
    assert result.actual is False


def test_response_field_exists_fails_when_response_is_not_object_like() -> None:
    results = evaluate_assertions(ScenarioAssertions(field_exists=["name"]), ERROR)

    result = _by_assertion(results, "field_exists[name]")
    assert result.passed is False


# --- minimum / maximum item count -----------------------------------------------------


def test_min_items_passes_when_count_meets_bound() -> None:
    results = evaluate_assertions(ScenarioAssertions(min_items=2), ITEMS)

    result = _by_assertion(results, "min_items")
    assert result.passed is True
    assert result.actual == 3


def test_min_items_fails_when_count_below_bound() -> None:
    results = evaluate_assertions(ScenarioAssertions(min_items=5), ITEMS)

    result = _by_assertion(results, "min_items")
    assert result.passed is False
    assert result.expected == 5
    assert result.actual == 3


def test_max_items_fails_when_count_above_bound() -> None:
    results = evaluate_assertions(ScenarioAssertions(max_items=1), ITEMS)

    result = _by_assertion(results, "max_items")
    assert result.passed is False


def test_item_count_check_fails_when_value_is_not_a_list() -> None:
    results = evaluate_assertions(ScenarioAssertions(min_items=1), SUCCESS)

    result = _by_assertion(results, "min_items")
    assert result.passed is False
    assert result.actual is None


# --- multiple checks in one scenario --------------------------------------------------


def test_all_specified_checks_are_returned_including_passing_ones() -> None:
    assertions = ScenarioAssertions(status="success", min_items=1, max_items=5)

    results = evaluate_assertions(assertions, ITEMS)

    assert {result.assertion for result in results} == {"status", "min_items", "max_items"}
    assert all(result.passed for result in results)


# --- ScenarioAssertions validation for the new checks -----------------------------------


def test_field_equals_alone_is_a_valid_assertion() -> None:
    assertions = ScenarioAssertions.model_validate({"field_equals": {"name": "Alice"}})

    assert assertions.field_equals == {"name": "Alice"}


def test_field_exists_alone_is_a_valid_assertion() -> None:
    assertions = ScenarioAssertions.model_validate({"field_exists": ["name", "id"]})

    assert assertions.field_exists == ["name", "id"]


def test_assertions_still_require_at_least_one_known_check() -> None:
    with pytest.raises(ValidationError):
        ScenarioAssertions.model_validate({})
