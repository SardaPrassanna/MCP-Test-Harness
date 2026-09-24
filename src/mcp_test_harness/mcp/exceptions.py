class MCPConnectionError(Exception):
    """Base error for MCP connection failures."""


class MCPConnectionTimeoutError(MCPConnectionError):
    """Raised when connecting to or initializing an MCP server exceeds its timeout."""


class MCPInitializationError(MCPConnectionError):
    """Raised when the MCP session handshake (`initialize`) fails."""
