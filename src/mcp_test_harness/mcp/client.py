from __future__ import annotations

from contextlib import AsyncExitStack
from types import TracebackType

import anyio
from mcp import ClientSession

from mcp_test_harness.mcp.exceptions import (
    MCPConnectionError,
    MCPConnectionTimeoutError,
    MCPInitializationError,
)
from mcp_test_harness.mcp.factory import build_transport
from mcp_test_harness.models.server import ServerConfig


class MCPConnection:
    """Owns the lifecycle of a single connection to one MCP server.

    Opens the configured transport, performs the MCP `initialize` handshake,
    and guarantees the transport and session are torn down together —
    whether closed normally, on error, or on timeout.

    Usage:
        async with MCPConnection(config) as session:
            tools = await session.list_tools()
    """

    def __init__(self, config: ServerConfig) -> None:
        self._config = config
        self._transport = build_transport(config)
        self._exit_stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    @property
    def session(self) -> ClientSession:
        if self._session is None:
            raise MCPConnectionError(
                "connection is not open; use 'async with MCPConnection(...)' or call connect()"
            )
        return self._session

    @property
    def is_connected(self) -> bool:
        return self._session is not None

    async def connect(self) -> ClientSession:
        if self._session is not None:
            return self._session

        exit_stack = AsyncExitStack()

        # A transport's `connect()` context manager is held open by
        # `exit_stack` for the whole life of the connection, so its *entry*
        # can't be bounded with `anyio.fail_after`/`asyncio.wait_for`: the MCP
        # SDK opens anyio task groups while entering, and anyio requires a
        # cancel scope's enter and exit to nest strictly within the same
        # task — a timeout scope that closes here while the task group stays
        # open past it (or a `wait_for`-spawned task that enters it) breaks
        # that invariant. Opening a transport is local/non-blocking (spawning
        # a subprocess, constructing an HTTP client), so real hangs surface
        # in `initialize()` below, which we do bound.
        try:
            read_stream, write_stream = await exit_stack.enter_async_context(
                self._transport.connect()
            )
        except Exception as exc:
            await exit_stack.aclose()
            raise MCPConnectionError(
                f"failed to open transport to MCP server {self._config.name!r}: {exc}"
            ) from exc

        try:
            session = await exit_stack.enter_async_context(
                ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=self._config.request_timeout_seconds,
                )
            )
            with anyio.fail_after(self._config.connect_timeout_seconds):
                await session.initialize()
        except TimeoutError as exc:
            await exit_stack.aclose()
            raise MCPConnectionTimeoutError(
                f"timed out initializing MCP server {self._config.name!r}"
            ) from exc
        except Exception as exc:
            await exit_stack.aclose()
            raise MCPInitializationError(
                f"failed to initialize MCP server {self._config.name!r}: {exc}"
            ) from exc

        self._exit_stack = exit_stack
        self._session = session
        return session

    async def close(self) -> None:
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
        self._exit_stack = None
        self._session = None

    async def __aenter__(self) -> ClientSession:
        return await self.connect()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()
