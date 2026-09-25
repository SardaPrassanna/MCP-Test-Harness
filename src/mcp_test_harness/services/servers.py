from __future__ import annotations

from typing import Literal

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session

from mcp_test_harness.mcp.client import MCPConnection
from mcp_test_harness.mcp.exceptions import MCPConnectionError
from mcp_test_harness.models.server import ServerConfig
from mcp_test_harness.storage.models import ServerRecord

_server_config_adapter: TypeAdapter[ServerConfig] = TypeAdapter(ServerConfig)


class ServerAlreadyExistsError(Exception):
    """Raised when registering a server whose name is already taken."""


class ServerNotFoundError(Exception):
    """Raised when a referenced server name has no registered config."""


def create_server(db: Session, config: ServerConfig) -> ServerRecord:
    """Register a new MCP server. `config.name` must not already be taken."""
    existing = db.scalar(select(ServerRecord).where(ServerRecord.name == config.name))
    if existing is not None:
        raise ServerAlreadyExistsError(f"server {config.name!r} is already registered")

    record = ServerRecord(
        name=config.name,
        transport=config.transport,
        config=config.model_dump(mode="json"),
    )
    db.add(record)
    db.flush()
    db.refresh(record)
    return record


def list_servers(db: Session) -> list[ServerRecord]:
    return list(db.scalars(select(ServerRecord).order_by(ServerRecord.id)))


def get_server(db: Session, server_id: int) -> ServerRecord:
    record = db.get(ServerRecord, server_id)
    if record is None:
        raise ServerNotFoundError(f"no server with id {server_id}")
    return record


def get_server_config(db: Session, name: str) -> ServerConfig:
    """Look up a registered server by name and rebuild its validated `ServerConfig`."""
    record = db.scalar(select(ServerRecord).where(ServerRecord.name == name))
    if record is None:
        raise ServerNotFoundError(f"no server registered with name {name!r}")
    return config_from_record(record)


def config_from_record(record: ServerRecord) -> ServerConfig:
    """Rebuild the validated `ServerConfig` a stored `ServerRecord` was created from."""
    return _server_config_adapter.validate_python(record.config)


async def check_server_status(config: ServerConfig) -> Literal["online", "unreachable"]:
    """Attempt a real MCP handshake against `config` and report whether it succeeded."""
    try:
        async with MCPConnection(config):
            pass
    except MCPConnectionError:
        return "unreachable"
    return "online"


async def discover_tools(config: ServerConfig) -> list[str]:
    """Connect to `config` and list the tool names it advertises."""
    async with MCPConnection(config) as session:
        result = await session.list_tools()
    return [tool.name for tool in result.tools]
