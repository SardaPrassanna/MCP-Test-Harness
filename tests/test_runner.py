"""Execution-engine tests against the checked-in fake stdio MCP server.

Every test here launches `tests/fixtures/fake_stdio_server.py` as a real
subprocess (via `stdio_config_factory`, defined in `tests/conftest.py`). No
external service is contacted.
"""

from collections.abc import Callable

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


# 1. Successful tool execution -------------------------------------------------


async def test_successful_scenario_passes(stdio_config_factory: StdioConfigFactory) -> None:
    result = await run_scenario(_scenario(), stdio_config_factory())

    assert result.status == "passed"
    assert result.failures == []
    assert result.error is None
    assert result.response is not None
    assert result.response["is_error"] is False


# 2. Assertion failure (tool succeeds, but response doesn't match) -------------


async def test_scenario_with_failing_assertion_reports_failure(
    stdio_config_factory: StdioConfigFactory,
) -> None:
    scenario = _scenario(assertions={"status": "success", "equals": "goodbye"})

    result = await run_scenario(scenario, stdio_config_factory())

    assert result.status == "failed"
    assert result.error is None
    assert any("goodbye" in failure.message for failure in result.failures)


# 3. Connection failure ---------------------------------------------------------


async def test_connection_failure_produces_error_result(
    stdio_config_factory: StdioConfigFactory,
) -> None:
    server = stdio_config_factory(command="definitely-not-a-real-mcp-server-binary")

    result = await run_scenario(_scenario(), server)

    assert result.status == "error"
    assert result.failures == []
    assert result.error is not None


# 4. Timeout ----------------------------------------------------------------------


async def test_tool_call_timeout_produces_error_result(
    stdio_config_factory: StdioConfigFactory,
) -> None:
    scenario = _scenario(
        name="slow_scenario", tool="slow", input={"seconds": 2.0}, assertions={"status": "success"}
    )

    result = await run_scenario(scenario, stdio_config_factory(), timeout_seconds=0.2)

    assert result.status == "error"
    assert "timed out" in result.error.lower()


# 5. Structured result object / duration -----------------------------------------


async def test_result_reports_scenario_identity_and_positive_duration(
    stdio_config_factory: StdioConfigFactory,
) -> None:
    result = await run_scenario(_scenario(), stdio_config_factory())

    assert result.scenario == "echo_scenario"
    assert result.server == "fake-stdio-server"
    assert result.tool == "echo"
    assert result.duration_seconds >= 0
