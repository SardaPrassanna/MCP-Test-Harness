# MCP Test Harness

A production-grade test harness and web console for **Model Context Protocol (MCP) servers**, built in Python. It lets developers register MCP servers, discover their tools/resources/prompts, define and run test scenarios against them, and review results — including failures and execution logs — through a simple web UI.

> **Status:** Phase 3 (Connection & Discovery Tests) complete — project scaffolding, FastAPI app, config, a health endpoint, the MCP connection abstraction (stdio + Streamable HTTP transports, lifecycle, timeouts), and connection/discovery tests against local fake MCP servers exist. Test execution (scenario definitions and running them) and the web UI are not implemented yet. See [Development Process](#development-process).

## What It Does

1. Register MCP servers (stdio or Streamable HTTP transport).
2. Connect to a registered server.
3. Discover its available tools, resources, and prompts.
4. Define test scenarios against those capabilities.
5. Execute MCP tests and validate the results with assertions.
6. Persist test runs to a database.
7. View results, failures, and execution logs in a web UI.
8. Run complete test suites end-to-end.

## Tech Stack

**Backend**
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) — package/dependency management
- FastAPI — HTTP API
- Official [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- Pydantic — data validation/models
- SQLAlchemy + SQLite (initial storage)
- httpx — HTTP client (for Streamable HTTP MCP servers)
- pytest / pytest-asyncio — testing
- Ruff — linting/formatting
- mypy — type checking

**UI**
- Jinja2 templates (server-rendered)
- HTMX (no client-side JS framework)
- Vanilla CSS

There is intentionally no React/Node/other frontend framework in this project — the UI is server-rendered HTML enhanced with HTMX.

## Architecture

The codebase is organized so the MCP implementation stays decoupled from the web UI, with clear boundaries between:

- **MCP connection layer** — transport adapters (stdio, Streamable HTTP) behind a common interface
- **Discovery** — enumerating tools, resources, and prompts exposed by a connected server
- **Test definitions** — declarative test scenarios
- **Test execution** — running scenarios against a live MCP connection
- **Assertions** — validating MCP responses
- **Persistence** — SQLAlchemy models and repositories for servers, scenarios, and runs
- **API** — FastAPI routes
- **UI** — Jinja2/HTMX views consuming the API

## Security Considerations

- No arbitrary shell commands are executed from browser-supplied input.
- MCP server definitions must be explicitly configured, not freely user-supplied.
- Subprocess arguments are validated; `shell=True` is never used with user-controlled input.
- Subprocess execution has timeouts and safe termination handling.
- Filesystem paths are validated where relevant.
- Secrets and credentials are never logged or exposed via the API/UI.

## Getting Started

### Prerequisites

- Python 3.11 or newer
- [uv](https://github.com/astral-sh/uv) installed (`pip install uv` or see the uv docs for platform-specific installers)
- Git

### Setup

```bash
# Clone the repository
git clone https://github.com/SardaPrassanna/MCP-Test-Harness.git
cd MCP-Test-Harness
git checkout dev

# Install dependencies (creates/uses a uv-managed virtual environment,
# and will fetch Python 3.11 automatically if it's not already installed)
uv sync

# Copy environment defaults and adjust as needed
cp .env.example .env

# Run the app
uv run uvicorn mcp_test_harness.main:app --reload
```

The web console will be available at `http://127.0.0.1:8000`, with the health endpoint at `http://127.0.0.1:8000/health`.

### Running Tests

```bash
uv run pytest
```

### Linting & Type Checking

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

## Development Process

This project is built **incrementally, one phase at a time**, with exactly one Git commit per phase, using [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `test:`, `refactor:`, `docs:`, `chore:`). Each phase:

- Preserves existing functionality
- Adds tests where applicable
- Must pass `pytest`, `ruff check`, and `mypy`
- Avoids unrelated changes

Check the Git history for the current state of the project and which phase has been completed most recently.

## Project Structure

```
mcp-test-harness/
├── src/
│   └── mcp_test_harness/
│       ├── api/          # FastAPI routers (health endpoint so far)
│       ├── config/       # pydantic-settings application configuration
│       ├── mcp/          # MCP connection layer: transports, lifecycle, timeouts
│       │   └── adapters/ # StdioTransport, StreamableHttpTransport
│       ├── runner/       # test scenario execution — empty, Phase 3+
│       ├── assertions/   # response validation helpers — empty, Phase 3+
│       ├── storage/      # SQLAlchemy engine/session, repositories — empty, Phase 3+
│       ├── models/       # shared Pydantic/SQLAlchemy models (server configs so far)
│       ├── services/     # orchestration across the layers above — empty, Phase 3+
│       └── main.py       # FastAPI app factory/instance
├── tests/
├── .env.example
├── pyproject.toml
└── README.md
```

## License

No license has been specified yet for this repository.
