"""Builds a minimal local MCP server used only by the test suite.

Exposes one tool ('echo') and one resource ('fake://greeting') so
connection and discovery tests can exercise a real MCP handshake without
calling any external service.
"""

from mcp.server.mcpserver import MCPServer


def build_fake_server(name: str = "fake-test-server") -> MCPServer:
    server: MCPServer = MCPServer(name=name)

    @server.tool()
    def echo(text: str) -> str:
        """Echo the given text back."""
        return text

    @server.resource("fake://greeting")
    def greeting() -> str:
        """A static greeting resource."""
        return "hello from fake mcp server"

    return server
