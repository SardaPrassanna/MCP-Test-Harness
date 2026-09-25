from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mcp.types import CallToolResult, TextContent

from mcp_test_harness.models.result import AssertionResult
from mcp_test_harness.models.scenario import ScenarioAssertions

_MISSING = object()


@dataclass(frozen=True)
class ToolCallOutcome:
    """The assertable part of a tool call's response.

    `value` is the tool's structured output when the server provided one
    (unwrapped from FastMCP's `{"result": ...}` envelope for non-object
    return types), falling back to the concatenated text content otherwise.

    This is the only type the assertion checks below operate on — they
    never see an MCP transport, session, or raw protocol message.
    """

    is_error: bool
    value: Any

    @property
    def status(self) -> str:
        return "error" if self.is_error else "success"

    @property
    def items(self) -> list[Any] | None:
        return self.value if isinstance(self.value, list) else None


def capture_outcome(result: CallToolResult) -> ToolCallOutcome:
    """Extract the part of a raw MCP `CallToolResult` that assertions check.

    This is the one function in this module that touches an MCP transport
    type; everything below it works only against `ToolCallOutcome`.
    """
    structured = result.structured_content
    if isinstance(structured, dict) and structured.keys() == {"result"}:
        value: Any = structured["result"]
    elif structured is not None:
        value = structured
    else:
        texts = [item.text for item in result.content if isinstance(item, TextContent)]
        value = texts[0] if len(texts) == 1 else texts

    return ToolCallOutcome(is_error=result.is_error, value=value)


def _result(
    assertion: str, *, expected: Any, actual: Any, passed: bool, message: str
) -> AssertionResult:
    return AssertionResult(
        assertion=assertion, expected=expected, actual=actual, passed=passed, message=message
    )


def _check_status(
    assertions: ScenarioAssertions, outcome: ToolCallOutcome
) -> AssertionResult | None:
    if assertions.status is None:
        return None
    passed = outcome.status == assertions.status
    return _result(
        "status",
        expected=assertions.status,
        actual=outcome.status,
        passed=passed,
        message="status matched"
        if passed
        else f"expected status {assertions.status!r}, got {outcome.status!r}",
    )


def _check_item_count(
    kind: str, limit: int | None, compare: str, outcome: ToolCallOutcome
) -> AssertionResult | None:
    if limit is None:
        return None
    items = outcome.items
    if items is None:
        return _result(
            kind,
            expected=limit,
            actual=None,
            passed=False,
            message=f"expected a list-like result to check item count, got {outcome.value!r}",
        )
    count = len(items)
    passed = count >= limit if compare == "min" else count <= limit
    bound_word = "at least" if compare == "min" else "at most"
    return _result(
        kind,
        expected=limit,
        actual=count,
        passed=passed,
        message="item count matched"
        if passed
        else f"expected {bound_word} {limit} item(s), got {count}",
    )


def _check_equals(
    assertions: ScenarioAssertions, outcome: ToolCallOutcome
) -> AssertionResult | None:
    if "equals" not in assertions.model_fields_set:
        return None
    passed = outcome.value == assertions.equals
    return _result(
        "equals",
        expected=assertions.equals,
        actual=outcome.value,
        passed=passed,
        message="value matched"
        if passed
        else f"expected value to equal {assertions.equals!r}, got {outcome.value!r}",
    )


def _check_contains(
    assertions: ScenarioAssertions, outcome: ToolCallOutcome
) -> AssertionResult | None:
    if "contains" not in assertions.model_fields_set:
        return None
    try:
        contained = assertions.contains in outcome.value
    except TypeError:
        return _result(
            "contains",
            expected=assertions.contains,
            actual=outcome.value,
            passed=False,
            message=f"response value {outcome.value!r} does not support containment checks",
        )
    return _result(
        "contains",
        expected=assertions.contains,
        actual=outcome.value,
        passed=contained,
        message="value contained"
        if contained
        else f"expected value to contain {assertions.contains!r}, got {outcome.value!r}",
    )


def _check_field_equals(
    assertions: ScenarioAssertions, outcome: ToolCallOutcome
) -> list[AssertionResult]:
    if not assertions.field_equals:
        return []
    results = []
    for field, expected_value in assertions.field_equals.items():
        assertion = f"field_equals[{field}]"
        if not isinstance(outcome.value, dict):
            results.append(
                _result(
                    assertion,
                    expected=expected_value,
                    actual=None,
                    passed=False,
                    message=f"expected an object-like result to read field {field!r} from, "
                    f"got {outcome.value!r}",
                )
            )
            continue
        actual_value = outcome.value.get(field, _MISSING)
        if actual_value is _MISSING:
            results.append(
                _result(
                    assertion,
                    expected=expected_value,
                    actual=None,
                    passed=False,
                    message=f"expected field {field!r} to equal {expected_value!r}, "
                    "but the field is missing",
                )
            )
            continue
        passed = actual_value == expected_value
        results.append(
            _result(
                assertion,
                expected=expected_value,
                actual=actual_value,
                passed=passed,
                message="field matched"
                if passed
                else f"expected field {field!r} to equal {expected_value!r}, got {actual_value!r}",
            )
        )
    return results


def _check_field_exists(
    assertions: ScenarioAssertions, outcome: ToolCallOutcome
) -> list[AssertionResult]:
    if not assertions.field_exists:
        return []
    results = []
    for field in assertions.field_exists:
        assertion = f"field_exists[{field}]"
        exists = isinstance(outcome.value, dict) and field in outcome.value
        results.append(
            _result(
                assertion,
                expected=True,
                actual=exists,
                passed=exists,
                message="field present"
                if exists
                else f"expected field {field!r} to exist, got {outcome.value!r}",
            )
        )
    return results


def evaluate_assertions(
    assertions: ScenarioAssertions, outcome: ToolCallOutcome
) -> list[AssertionResult]:
    """Check a captured tool outcome against every assertion a scenario specifies.

    Returns one `AssertionResult` per specified check (including checks
    that passed), so a `TestResult` can explain itself fully. An empty
    return is impossible in practice: `ScenarioAssertions` requires at
    least one check to be specified.
    """
    checks = [
        _check_status(assertions, outcome),
        _check_item_count("min_items", assertions.min_items, "min", outcome),
        _check_item_count("max_items", assertions.max_items, "max", outcome),
        _check_equals(assertions, outcome),
        _check_contains(assertions, outcome),
    ]
    results = [check for check in checks if check is not None]
    results.extend(_check_field_equals(assertions, outcome))
    results.extend(_check_field_exists(assertions, outcome))
    return results
