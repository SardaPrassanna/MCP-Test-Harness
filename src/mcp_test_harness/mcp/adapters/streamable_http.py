from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx2
from mcp.client.streamable_http import streamable_http_client

from mcp_test_harness.mcp.transport import MCPStreamPair
from mcp_test_harness.models.server import StreamableHttpServerConfig


class StreamableHttpTransport:
    """Connects to an MCP server exposed over the Streamable HTTP transport."""

    def __init__(self, config: StreamableHttpServerConfig) -> None:
        self._config = config

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[MCPStreamPair]:
        http_client = httpx2.AsyncClient(
            headers=self._config.headers,
            timeout=self._config.request_timeout_seconds,
        )
        async with http_client:
            async with streamable_http_client(str(self._config.url), http_client=http_client) as (
                read_stream,
                write_stream,
            ):
                yield read_stream, write_stream
