from __future__ import annotations

import time
from typing import Any

import anyio
from mcp.types import CallToolResult, TextContent

from mcp_test_harness.assertions.evaluator import capture_outcome, evaluate_assertions
from mcp_test_harness.mcp.client import MCPConnection
from mcp_test_harness.mcp.exceptions import MCPConnectionError
from mcp_test_harness.models.result import ScenarioResult
from mcp_test_harness.models.scenario import TestScenario
from mcp_test_harness.models.server import ServerConfig


async def run_scenario(
    scenario: TestScenario,
    server: ServerConfig,
    *,
    timeout_seconds: float | None = None,
) -> ScenarioResult:
    """Execute a single declarative scenario against a live MCP server.

    Owns the whole pipeline: opens a fresh `MCPConnection` to `server`,
    invokes `scenario.tool` with `scenario.input`, captures the response,
    and checks it against `scenario.assertions`. Never raises: connection
    failures, tool-call timeouts, and unexpected exceptions are all
    captured as an `"error"` `ScenarioResult` rather than propagating, so a
    single bad scenario can't take down a run of many.

    `timeout_seconds` bounds only the tool invocation itself; it defaults
    to the server's own `request_timeout_seconds`. Connection setup is
    bounded separately by the server's `connect_timeout_seconds`.
    """
    effective_timeout = (
        timeout_seconds if timeout_seconds is not None else server.request_timeout_seconds
    )
    started_at = time.perf_counter()

    try:
        async with MCPConnection(server) as session:
            with anyio.fail_after(effective_timeout):
                result: CallToolResult = await session.call_tool(scenario.tool, scenario.input)
    except TimeoutError:
        return _error_result(
            scenario,
            duration_seconds=time.perf_counter() - started_at,
            error=f"tool call {scenario.tool!r} timed out after {effective_timeout}s",
        )
    except MCPConnectionError as exc:
        return _error_result(
            scenario, duration_seconds=time.perf_counter() - started_at, error=str(exc)
        )
    except Exception as exc:  # noqa: BLE001 - deliberately broad: a scenario must never crash the runner
        return _error_result(
            scenario,
            duration_seconds=time.perf_counter() - started_at,
            error=f"unexpected error calling tool {scenario.tool!r}: {exc}",
        )

    duration_seconds = time.perf_counter() - started_at
    outcome = capture_outcome(result)
    failures = evaluate_assertions(scenario.assertions, outcome)

    return ScenarioResult(
        scenario=scenario.name,
        server=scenario.server,
        tool=scenario.tool,
        status="passed" if not failures else "failed",
        duration_seconds=duration_seconds,
        failures=failures,
        response=_serialize_response(result),
    )


def _error_result(scenario: TestScenario, *, duration_seconds: float, error: str) -> ScenarioResult:
    return ScenarioResult(
        scenario=scenario.name,
        server=scenario.server,
        tool=scenario.tool,
        status="error",
        duration_seconds=duration_seconds,
        error=error,
    )


def _serialize_response(result: CallToolResult) -> dict[str, Any]:
    return {
        "is_error": result.is_error,
        "structured_content": result.structured_content,
        "content": [
            item.text if isinstance(item, TextContent) else item.model_dump(mode="json")
            for item in result.content
        ],
    }
