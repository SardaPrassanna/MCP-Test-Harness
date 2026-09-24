import asyncio
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

import pytest

from mcp_test_harness.mcp import client as client_module
from mcp_test_harness.mcp.adapters import StdioTransport, StreamableHttpTransport
from mcp_test_harness.mcp.client import MCPConnection
from mcp_test_harness.mcp.exceptions import (
    MCPConnectionError,
    MCPConnectionTimeoutError,
    MCPInitializationError,
)
from mcp_test_harness.mcp.factory import build_transport
from mcp_test_harness.models.server import StdioServerConfig, StreamableHttpServerConfig


def _stdio_config(**overrides: Any) -> StdioServerConfig:
    return StdioServerConfig(
        name="test-server",
        command="python",
        connect_timeout_seconds=overrides.pop("connect_timeout_seconds", 0.2),
        **overrides,
    )


class _SucceedingTransport:
    def connect(self) -> AbstractAsyncContextManager[tuple[Any, Any]]:
        @asynccontextmanager
        async def _cm() -> AsyncIterator[tuple[Any, Any]]:
            yield object(), object()

        return _cm()


class _HangingTransport:
    def connect(self) -> AbstractAsyncContextManager[tuple[Any, Any]]:
        @asynccontextmanager
        async def _cm() -> AsyncIterator[tuple[Any, Any]]:
            await asyncio.sleep(10)
            yield object(), object()

        return _cm()


class _FailingTransport:
    def connect(self) -> AbstractAsyncContextManager[tuple[Any, Any]]:
        @asynccontextmanager
        async def _cm() -> AsyncIterator[tuple[Any, Any]]:
            raise RuntimeError("connection refused")
            yield object(), object()  # pragma: no cover - unreachable

        return _cm()


class _FakeClientSession:
    instances: list["_FakeClientSession"] = []

    def __init__(
        self, read_stream: Any, write_stream: Any, read_timeout_seconds: float | None = None
    ) -> None:
        self.read_stream = read_stream
        self.write_stream = write_stream
        self.read_timeout_seconds = read_timeout_seconds
        self.initialized = False
        self.closed = False
        _FakeClientSession.instances.append(self)

    async def __aenter__(self) -> "_FakeClientSession":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        self.closed = True

    async def initialize(self) -> None:
        self.initialized = True


class _FailingInitializeSession(_FakeClientSession):
    async def initialize(self) -> None:
        raise RuntimeError("handshake rejected")


class _HangingInitializeSession(_FakeClientSession):
    async def initialize(self) -> None:
        await asyncio.sleep(10)


@pytest.fixture(autouse=True)
def _reset_fake_sessions() -> None:
    _FakeClientSession.instances.clear()


def test_build_transport_selects_stdio_adapter() -> None:
    transport = build_transport(StdioServerConfig(name="local", command="python"))

    assert isinstance(transport, StdioTransport)


def test_build_transport_selects_streamable_http_adapter() -> None:
    transport = build_transport(
        StreamableHttpServerConfig(name="remote", url="https://example.com/mcp")
    )

    assert isinstance(transport, StreamableHttpTransport)


async def test_connect_succeeds_and_initializes_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_module, "build_transport", lambda _config: _SucceedingTransport())
    monkeypatch.setattr(client_module, "ClientSession", _FakeClientSession)

    connection = MCPConnection(_stdio_config())
    session = await connection.connect()

    assert isinstance(session, _FakeClientSession)
    assert session.initialized is True
    assert connection.is_connected is True
    assert connection.session is session

    await connection.close()

    assert connection.is_connected is False
    assert session.closed is True


async def test_connect_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_module, "build_transport", lambda _config: _SucceedingTransport())
    monkeypatch.setattr(client_module, "ClientSession", _FakeClientSession)

    connection = MCPConnection(_stdio_config())
    first = await connection.connect()
    second = await connection.connect()

    assert first is second
    assert len(_FakeClientSession.instances) == 1

    await connection.close()


async def test_connect_raises_timeout_when_transport_hangs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client_module, "build_transport", lambda _config: _HangingTransport())
    monkeypatch.setattr(client_module, "ClientSession", _FakeClientSession)

    connection = MCPConnection(_stdio_config(connect_timeout_seconds=0.05))

    with pytest.raises(MCPConnectionTimeoutError):
        await connection.connect()

    assert connection.is_connected is False


async def test_connect_raises_timeout_when_initialize_hangs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client_module, "build_transport", lambda _config: _SucceedingTransport())
    monkeypatch.setattr(client_module, "ClientSession", _HangingInitializeSession)

    connection = MCPConnection(_stdio_config(connect_timeout_seconds=0.05))

    with pytest.raises(MCPConnectionTimeoutError):
        await connection.connect()

    assert connection.is_connected is False


async def test_connect_raises_connection_error_on_transport_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client_module, "build_transport", lambda _config: _FailingTransport())
    monkeypatch.setattr(client_module, "ClientSession", _FakeClientSession)

    connection = MCPConnection(_stdio_config())

    with pytest.raises(MCPConnectionError):
        await connection.connect()

    assert connection.is_connected is False


async def test_connect_raises_initialization_error_on_handshake_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client_module, "build_transport", lambda _config: _SucceedingTransport())
    monkeypatch.setattr(client_module, "ClientSession", _FailingInitializeSession)

    connection = MCPConnection(_stdio_config())

    with pytest.raises(MCPInitializationError):
        await connection.connect()

    assert connection.is_connected is False


async def test_session_property_raises_before_connect() -> None:
    connection = MCPConnection(_stdio_config())

    with pytest.raises(MCPConnectionError):
        _ = connection.session


async def test_async_context_manager_connects_and_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client_module, "build_transport", lambda _config: _SucceedingTransport())
    monkeypatch.setattr(client_module, "ClientSession", _FakeClientSession)

    async with MCPConnection(_stdio_config()) as session:
        assert isinstance(session, _FakeClientSession)
        assert session.initialized is True

    assert session.closed is True
