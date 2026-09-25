"""Builds a minimal local MCP server used only by the test suite.

Exposes a handful of tools and one resource ('fake://greeting') so
connection, discovery, and execution-engine tests can exercise a real MCP
handshake and tool calls without calling any external service.
"""

import anyio
from mcp.server.mcpserver import MCPServer


def build_fake_server(name: str = "fake-test-server") -> MCPServer:
    server: MCPServer = MCPServer(name=name)

    @server.tool()
    def echo(text: str) -> str:
        """Echo the given text back."""
        return text

    @server.tool()
    def list_items(count: int = 3) -> list[str]:
        """Return `count` fake item names."""
        return [f"item-{i}" for i in range(count)]

    @server.tool()
    def boom() -> str:
        """Always raise, to exercise tool-call error handling."""
        raise ValueError("kaboom")

    @server.tool()
    async def slow(seconds: float = 1.0) -> str:
        """Sleep for `seconds` before returning, to exercise tool-call timeouts."""
        await anyio.sleep(seconds)
        return "done"

    @server.resource("fake://greeting")
    def greeting() -> str:
        """A static greeting resource."""
        return "hello from fake mcp server"

    return server
