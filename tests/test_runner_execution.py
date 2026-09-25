"""Comprehensive execution-engine coverage.

Exercises `run_scenario()` against the checked-in fake stdio MCP server
(`tests/fixtures/fake_stdio_server.py`, launched as a real subprocess via
`stdio_config_factory` from `tests/conftest.py`) for every real-world
outcome the runner has to handle cleanly, plus one fully-mocked case for a
failure mode no real server can trigger on demand (an unexpected exception
from deep inside the MCP client). No external service is contacted.
"""

from collections.abc import Callable
from typing import Any

import pytest

from mcp_test_harness import runner as runner_module
from mcp_test_harness.models.scenario import TestScenario
from mcp_test_harness.models.server import StdioServerConfig
from mcp_test_harness.runner.engine import run_scenario

StdioConfigFactory = Callable[..., StdioServerConfig]


def _scenario(**overrides: object) -> TestScenario:
    data: dict[str, object] = {
        "name": "echo_scenario",
        "server": "fake-stdio-server",
        "tool": "echo",
        "input": {"text": "hello"},
        "assertions": {"status": "success", "equals": "hello"},
    }
    data.update(overrides)
    return TestScenario.model_validate(data)


# 1. Successful tool execution ---------------------------------------------------


async def test_successful_tool_execution(stdio_config_factory: StdioConfigFactory) -> None:
    result = await run_scenario(_scenario(), stdio_config_factory())

    assert result.status == "passed"
    assert result.error is None
    assert result.failures == []


# 2. Tool failure (call succeeds, but doesn't do what the scenario expected) ----


async def test_tool_failure_is_reported_as_failed_not_error(
    stdio_config_factory: StdioConfigFactory,
) -> None:
    scenario = _scenario(tool="list_items", input={"count": 1}, assertions={"min_items": 5})

    result = await run_scenario(scenario, stdio_config_factory())

    assert result.status == "failed"
    assert result.error is None
    assert any("5" in failure for failure in result.failures)


# 3. Connection failure -------------------------------------------------------------


async def test_connection_failure(stdio_config_factory: StdioConfigFactory) -> None:
    server = stdio_config_factory(command="definitely-not-a-real-mcp-server-binary")

    result = await run_scenario(_scenario(), server)

    assert result.status == "error"
    assert result.error is not None
    assert result.failures == []


# 4. Timeout ---------------------------------------------------------------------------


async def test_timeout(stdio_config_factory: StdioConfigFactory) -> None:
    scenario = _scenario(tool="slow", input={"seconds": 2.0}, assertions={"status": "success"})

    result = await run_scenario(scenario, stdio_config_factory(), timeout_seconds=0.2)

    assert result.status == "error"
    assert "timed out" in result.error.lower()


# 5. Malformed input ------------------------------------------------------------------


async def test_malformed_input_surfaces_as_mcp_tool_error(
    stdio_config_factory: StdioConfigFactory,
) -> None:
    scenario = _scenario(input={"wrong_field": 1})

    result = await run_scenario(scenario, stdio_config_factory())

    assert result.status == "failed"
    assert result.response is not None
    assert result.response["is_error"] is True
    assert any("status" in failure for failure in result.failures)


# 6. MCP error response ----------------------------------------------------------------


async def test_mcp_error_response_is_captured_and_matched_by_status_assertion(
    stdio_config_factory: StdioConfigFactory,
) -> None:
    scenario = _scenario(tool="boom", input={}, assertions={"status": "error"})

    result = await run_scenario(scenario, stdio_config_factory())

    assert result.status == "passed"
    assert result.response is not None
    assert result.response["is_error"] is True
    assert any(
        "error executing tool boom" in text.lower()
        for text in result.response["content"]
        if isinstance(text, str)
    )


# 7. Execution duration -----------------------------------------------------------------


async def test_execution_duration_reflects_real_elapsed_time(
    stdio_config_factory: StdioConfigFactory,
) -> None:
    scenario = _scenario(
        name="slow_scenario",
        tool="slow",
        input={"seconds": 0.3},
        assertions={"status": "success"},
    )

    result = await run_scenario(scenario, stdio_config_factory(), timeout_seconds=5.0)

    assert result.status == "passed"
    assert result.duration_seconds >= 0.3


# 8. Unexpected exception ----------------------------------------------------------------


class _FakeSession:
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        raise RuntimeError("socket exploded")


class _FakeConnection:
    def __init__(self, _config: object) -> None:
        pass

    async def __aenter__(self) -> _FakeSession:
        return _FakeSession()

    async def __aexit__(self, *exc_info: object) -> None:
        return None


async def test_unexpected_exception_is_captured_as_error(
    monkeypatch: pytest.MonkeyPatch, stdio_config_factory: StdioConfigFactory
) -> None:
    monkeypatch.setattr(runner_module.engine, "MCPConnection", _FakeConnection)

    result = await run_scenario(_scenario(), stdio_config_factory())

    assert result.status == "error"
    assert result.failures == []
    assert "unexpected error" in result.error.lower()
    assert "socket exploded" in result.error
