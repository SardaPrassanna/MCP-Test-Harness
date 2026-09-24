"""MCP connection layer: transport adapters and connection lifecycle for
stdio and Streamable HTTP MCP servers."""

from mcp_test_harness.mcp.client import MCPConnection
from mcp_test_harness.mcp.exceptions import (
    MCPConnectionError,
    MCPConnectionTimeoutError,
    MCPInitializationError,
)
from mcp_test_harness.mcp.factory import build_transport
from mcp_test_harness.mcp.transport import MCPStreamPair, MCPTransport

__all__ = [
    "MCPConnection",
    "MCPConnectionError",
    "MCPConnectionTimeoutError",
    "MCPInitializationError",
    "MCPStreamPair",
    "MCPTransport",
    "build_transport",
]
