import asyncio
import socket
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
import uvicorn

from mcp_test_harness.models.server import StdioServerConfig
from tests.fixtures.fake_server import build_fake_server

FAKE_STDIO_SERVER_SCRIPT = Path(__file__).parent / "fixtures" / "fake_stdio_server.py"


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def fake_stdio_server_config(
    *, name: str = "fake-stdio-server", startup_delay: float = 0.0, **overrides: object
) -> StdioServerConfig:
    """A `StdioServerConfig` that launches the checked-in fake MCP server."""
    args = [str(FAKE_STDIO_SERVER_SCRIPT)]
    if startup_delay:
        args += ["--startup-delay", str(startup_delay)]
    kwargs: dict[str, object] = {"name": name, "command": sys.executable, "args": args}
    kwargs.update(overrides)
    return StdioServerConfig(**kwargs)


@pytest.fixture
def stdio_config_factory():
    return fake_stdio_server_config


@pytest_asyncio.fixture
async def fake_http_server_url() -> AsyncIterator[str]:
    """Runs the fake MCP server over Streamable HTTP on a local loopback port."""
    server = build_fake_server(name="fake-http-server")
    app = server.streamable_http_app()
    port = _free_local_port()

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    uv_server = uvicorn.Server(config)

    serve_task = asyncio.create_task(uv_server.serve())
    try:
        for _ in range(500):
            if uv_server.started:
                break
            await asyncio.sleep(0.01)
        else:  # pragma: no cover - defensive
            raise RuntimeError("fake HTTP MCP server failed to start")

        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        uv_server.should_exit = True
        await serve_task
