"""Connection and discovery tests against local fake MCP servers.

Every test here either launches the checked-in fake stdio server
(`tests/fixtures/fake_stdio_server.py`) as a real subprocess, or serves the
fake server (`tests/fixtures/fake_server.py`) over Streamable HTTP on a
loopback port. No external service is contacted.
"""

from collections.abc import Callable

import pytest
from pydantic import TypeAdapter, ValidationError

from mcp_test_harness.mcp.client import MCPConnection
from mcp_test_harness.mcp.exceptions import (
    MCPConnectionError,
    MCPConnectionTimeoutError,
)
from mcp_test_harness.models.server import (
    ServerConfig,
    StdioServerConfig,
    StreamableHttpServerConfig,
)

server_config_adapter: TypeAdapter[ServerConfig] = TypeAdapter(ServerConfig)

StdioConfigFactory = Callable[..., StdioServerConfig]


# 1. Successful connection ---------------------------------------------------


async def test_successful_connection_over_stdio(stdio_config_factory: StdioConfigFactory) -> None:
    config = stdio_config_factory()

    async with MCPConnection(config) as session:
        assert session.server_info is not None
        assert session.server_info.name == "fake-test-server"


async def test_successful_connection_over_http(fake_http_server_url: str) -> None:
    config = StreamableHttpServerConfig(name="fake-http-server", url=fake_http_server_url)

    async with MCPConnection(config) as session:
        assert session.server_info is not None
        assert session.server_info.name == "fake-http-server"


# 2. Connection failure -------------------------------------------------------


async def test_connection_failure_for_nonexistent_command(
    stdio_config_factory: StdioConfigFactory,
) -> None:
    config = stdio_config_factory(command="definitely-not-a-real-mcp-server-binary")

    with pytest.raises(MCPConnectionError):
        async with MCPConnection(config):
            pass  # pragma: no cover - never reached


# 3. Timeout -------------------------------------------------------------------


async def test_connect_times_out_against_slow_starting_server(
    stdio_config_factory: StdioConfigFactory,
) -> None:
    config = stdio_config_factory(startup_delay=2.0, connect_timeout_seconds=0.2)

    with pytest.raises(MCPConnectionTimeoutError):
        async with MCPConnection(config):
            pass  # pragma: no cover - never reached


# 4. Stdio lifecycle ------------------------------------------------------------


async def test_stdio_connection_supports_close_and_reconnect(
    stdio_config_factory: StdioConfigFactory,
) -> None:
    config = stdio_config_factory()
    connection = MCPConnection(config)

    assert connection.is_connected is False

    session = await connection.connect()
    assert connection.is_connected is True
    await session.list_tools()  # the underlying process is alive and responsive

    await connection.close()
    assert connection.is_connected is False

    reconnected_session = await connection.connect()
    assert connection.is_connected is True
    await reconnected_session.list_tools()

    await connection.close()
    assert connection.is_connected is False


# 5. HTTP connection failure ------------------------------------------------------


async def test_http_connection_fails_when_nothing_is_listening() -> None:
    config = StreamableHttpServerConfig(
        name="unreachable-http-server",
        url="http://127.0.0.1:1/mcp",
        connect_timeout_seconds=1.0,
    )

    with pytest.raises(MCPConnectionError):
        async with MCPConnection(config):
            pass  # pragma: no cover - never reached


# 6. Tool discovery ---------------------------------------------------------------


async def test_tool_discovery_over_stdio(stdio_config_factory: StdioConfigFactory) -> None:
    async with MCPConnection(stdio_config_factory()) as session:
        result = await session.list_tools()

    assert [tool.name for tool in result.tools] == ["echo", "list_items", "boom", "slow"]


# 7. Resource discovery -------------------------------------------------------------


async def test_resource_discovery_over_stdio(stdio_config_factory: StdioConfigFactory) -> None:
    async with MCPConnection(stdio_config_factory()) as session:
        result = await session.list_resources()

    assert [str(resource.uri) for resource in result.resources] == ["fake://greeting"]


# 8. Malformed server configuration -------------------------------------------------


def test_malformed_configuration_missing_command_is_rejected() -> None:
    with pytest.raises(ValidationError):
        server_config_adapter.validate_python({"transport": "stdio", "name": "broken"})


def test_malformed_configuration_unknown_transport_is_rejected() -> None:
    with pytest.raises(ValidationError):
        server_config_adapter.validate_python(
            {"transport": "carrier-pigeon", "name": "broken", "command": "python"}
        )
