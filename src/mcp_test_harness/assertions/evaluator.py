from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mcp.types import CallToolResult, TextContent

from mcp_test_harness.models.scenario import ScenarioAssertions


@dataclass(frozen=True)
class ToolCallOutcome:
    """The assertable part of a tool call's response.

    `value` is the tool's structured output when the server provided one
    (unwrapped from FastMCP's `{"result": ...}` envelope for non-object
    return types), falling back to the concatenated text content otherwise.
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
    """Extract the part of a raw MCP `CallToolResult` that assertions check."""
    structured = result.structured_content
    if isinstance(structured, dict) and structured.keys() == {"result"}:
        value: Any = structured["result"]
    elif structured is not None:
        value = structured
    else:
        texts = [item.text for item in result.content if isinstance(item, TextContent)]
        value = texts[0] if len(texts) == 1 else texts

    return ToolCallOutcome(is_error=result.is_error, value=value)


def evaluate_assertions(assertions: ScenarioAssertions, outcome: ToolCallOutcome) -> list[str]:
    """Check a captured tool outcome against a scenario's assertions.

    Returns a list of human-readable failure descriptions; an empty list
    means every specified assertion held.
    """
    failures: list[str] = []
    fields_set = assertions.model_fields_set

    if assertions.status is not None and outcome.status != assertions.status:
        failures.append(f"expected status {assertions.status!r}, got {outcome.status!r}")

    if assertions.min_items is not None or assertions.max_items is not None:
        items = outcome.items
        if items is None:
            failures.append(
                "expected a list-like result to check item count, but "
                f"response value was {outcome.value!r}"
            )
        else:
            count = len(items)
            if assertions.min_items is not None and count < assertions.min_items:
                failures.append(f"expected at least {assertions.min_items} item(s), got {count}")
            if assertions.max_items is not None and count > assertions.max_items:
                failures.append(f"expected at most {assertions.max_items} item(s), got {count}")

    if "equals" in fields_set and outcome.value != assertions.equals:
        failures.append(f"expected value to equal {assertions.equals!r}, got {outcome.value!r}")

    if "contains" in fields_set:
        try:
            contained = assertions.contains in outcome.value
        except TypeError:
            failures.append(
                f"response value {outcome.value!r} does not support containment checks"
            )
        else:
            if not contained:
                failures.append(
                    f"expected value to contain {assertions.contains!r}, got {outcome.value!r}"
                )

    return failures
