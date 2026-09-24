from mcp_test_harness.mcp.adapters import StdioTransport, StreamableHttpTransport
from mcp_test_harness.mcp.transport import MCPTransport
from mcp_test_harness.models.server import ServerConfig


def build_transport(config: ServerConfig) -> MCPTransport:
    """Build the transport adapter for an explicit, validated server config.

    `config` must already be a `StdioServerConfig` or
    `StreamableHttpServerConfig` instance (e.g. loaded from operator-managed
    server registration data) — this function never accepts or interprets
    raw, unvalidated input.
    """
    if config.transport == "stdio":
        return StdioTransport(config)
    if config.transport == "streamable_http":
        return StreamableHttpTransport(config)
    msg = f"unsupported transport: {config.transport!r}"  # pragma: no cover
    raise ValueError(msg)  # pragma: no cover
