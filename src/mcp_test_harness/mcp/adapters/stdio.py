from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp import StdioServerParameters, stdio_client

from mcp_test_harness.mcp.transport import MCPStreamPair
from mcp_test_harness.models.server import StdioServerConfig


class StdioTransport:
    """Connects to an MCP server launched as a local subprocess over stdio.

    The launch command comes only from an explicit, pre-validated
    `StdioServerConfig` — never from an unparsed string supplied by a
    request — and is passed to the subprocess without a shell.
    """

    def __init__(self, config: StdioServerConfig) -> None:
        self._config = config

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[MCPStreamPair]:
        params = StdioServerParameters(
            command=self._config.command,
            args=list(self._config.args),
            env=self._config.env,
            cwd=self._config.cwd,
            encoding=self._config.encoding,
        )
        async with stdio_client(params) as (read_stream, write_stream):
            yield read_stream, write_stream
