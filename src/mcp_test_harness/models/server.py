from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

_SAFE_COMMAND_TOKEN = re.compile(r"^[A-Za-z0-9_./:\\-]+$")


class StdioServerConfig(BaseModel):
    """Explicit, operator-configured launch parameters for a stdio MCP server.

    Every field is a discrete, validated value rather than a free-form shell
    string, so a config can never be built from an unparsed, browser-supplied
    command line.
    """

    transport: Literal["stdio"] = "stdio"
    name: str = Field(min_length=1)
    command: str = Field(min_length=1)
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] | None = None
    cwd: str | None = None
    encoding: str = "utf-8"
    connect_timeout_seconds: float = Field(default=30.0, gt=0)
    request_timeout_seconds: float = Field(default=30.0, gt=0)

    @field_validator("command")
    @classmethod
    def _validate_command(cls, value: str) -> str:
        if not _SAFE_COMMAND_TOKEN.match(value):
            raise ValueError(
                "command must be a single executable path/name with no shell "
                "metacharacters or embedded arguments"
            )
        return value

    @field_validator("args")
    @classmethod
    def _validate_args(cls, value: list[str]) -> list[str]:
        for arg in value:
            if any(ch in arg for ch in ("|", "&", ";", "`", "$(", "\n", "\r")):
                raise ValueError(f"argument {arg!r} contains disallowed shell metacharacters")
        return value


class StreamableHttpServerConfig(BaseModel):
    """Explicit, operator-configured connection parameters for a Streamable
    HTTP MCP server."""

    transport: Literal["streamable_http"] = "streamable_http"
    name: str = Field(min_length=1)
    url: HttpUrl
    headers: dict[str, str] | None = None
    connect_timeout_seconds: float = Field(default=30.0, gt=0)
    request_timeout_seconds: float = Field(default=30.0, gt=0)


ServerConfig = Annotated[
    StdioServerConfig | StreamableHttpServerConfig,
    Field(discriminator="transport"),
]
