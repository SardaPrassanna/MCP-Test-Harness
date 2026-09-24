import pytest
from pydantic import TypeAdapter, ValidationError

from mcp_test_harness.models.server import (
    ServerConfig,
    StdioServerConfig,
    StreamableHttpServerConfig,
)

server_config_adapter: TypeAdapter[ServerConfig] = TypeAdapter(ServerConfig)


def test_stdio_config_accepts_explicit_command_and_args() -> None:
    config = StdioServerConfig(name="local-echo", command="python", args=["-m", "echo_server"])

    assert config.transport == "stdio"
    assert config.command == "python"
    assert config.args == ["-m", "echo_server"]


def test_stdio_config_rejects_shell_metacharacters_in_command() -> None:
    with pytest.raises(ValidationError):
        StdioServerConfig(name="bad", command="python && rm -rf /")


def test_stdio_config_rejects_shell_metacharacters_in_args() -> None:
    with pytest.raises(ValidationError):
        StdioServerConfig(name="bad", command="python", args=["-c", "os.system('rm -rf /')` "])


def test_http_config_accepts_valid_url() -> None:
    config = StreamableHttpServerConfig(name="remote", url="https://example.com/mcp")

    assert config.transport == "streamable_http"
    assert str(config.url) == "https://example.com/mcp"


def test_http_config_rejects_invalid_url() -> None:
    with pytest.raises(ValidationError):
        StreamableHttpServerConfig(name="bad", url="not-a-url")


def test_server_config_discriminates_stdio_by_transport_field() -> None:
    server = server_config_adapter.validate_python(
        {"transport": "stdio", "name": "local", "command": "python"}
    )

    assert isinstance(server, StdioServerConfig)


def test_server_config_discriminates_http_by_transport_field() -> None:
    server = server_config_adapter.validate_python(
        {"transport": "streamable_http", "name": "remote", "url": "https://example.com/mcp"}
    )

    assert isinstance(server, StreamableHttpServerConfig)
