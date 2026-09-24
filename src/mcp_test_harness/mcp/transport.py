from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol

# The MCP SDK's read/write stream types are internal generics; adapters only
# ever pass them straight through to `mcp.ClientSession`, so `Any` avoids
# depending on SDK-private type paths.
MCPStreamPair = tuple[Any, Any]


class MCPTransport(Protocol):
    """A connectable transport that yields the raw MCP read/write streams.

    Implementations wrap the MCP SDK's own client context managers
    (`stdio_client`, `streamable_http_client`, ...) behind a common shape so
    the connection layer above does not need to know which transport it is
    using.
    """

    def connect(self) -> AbstractAsyncContextManager[MCPStreamPair]:
        """Open the transport, yielding (read_stream, write_stream) for the
        duration of the returned async context manager."""
        ...


__all__ = ["MCPStreamPair", "MCPTransport"]
