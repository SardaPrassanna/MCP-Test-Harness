"""API tests for the REST layer: servers, tests (scenarios), and runs.

Each test builds a fresh FastAPI app bound to a scratch SQLite database file
under `tmp_path`, so tests never share state and never touch the project's
real `mcp_test_harness.db`. Server registrations point at the checked-in
fake stdio MCP server (`tests/fixtures/fake_stdio_server.py`, launched as a
real subprocess) so `/runs` exercises a genuine MCP handshake and tool call.
No external service is contacted.
"""

import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from mcp_test_harness.config import Settings
from mcp_test_harness.main import create_app

FAKE_STDIO_SERVER_SCRIPT = Path(__file__).parent / "fixtures" / "fake_stdio_server.py"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    settings = Settings(database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    return TestClient(create_app(settings))


def _server_payload(name: str = "fake-stdio-server") -> dict[str, Any]:
    return {
        "transport": "stdio",
        "name": name,
        "command": sys.executable,
        "args": [str(FAKE_STDIO_SERVER_SCRIPT)],
    }


def _scenario_payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "name": "echo_scenario",
        "server": "fake-stdio-server",
        "tool": "echo",
        "input": {"text": "hello"},
        "assertions": {"status": "success", "equals": "hello"},
    }
    data.update(overrides)
    return data


# --- health (unaffected by persistence) -----------------------------------------


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# --- GET/POST /servers -------------------------------------------------------------


def test_register_and_list_servers(client: TestClient) -> None:
    create = client.post("/servers", json=_server_payload())
    assert create.status_code == 201
    body = create.json()
    assert body["name"] == "fake-stdio-server"
    assert body["transport"] == "stdio"
    assert "id" in body

    listing = client.get("/servers")
    assert listing.status_code == 200
    assert [server["name"] for server in listing.json()] == ["fake-stdio-server"]


def test_registering_duplicate_server_name_is_rejected(client: TestClient) -> None:
    client.post("/servers", json=_server_payload())

    response = client.post("/servers", json=_server_payload())

    assert response.status_code == 409


def test_registering_malformed_server_is_rejected(client: TestClient) -> None:
    response = client.post("/servers", json={"transport": "stdio", "name": "broken"})

    assert response.status_code == 422


# --- GET/POST /tests -----------------------------------------------------------------


def test_register_and_list_scenarios(client: TestClient) -> None:
    create = client.post("/tests", json=_scenario_payload())
    assert create.status_code == 201
    body = create.json()
    assert body["name"] == "echo_scenario"
    assert "id" in body

    listing = client.get("/tests")
    assert listing.status_code == 200
    assert [scenario["name"] for scenario in listing.json()] == ["echo_scenario"]


def test_registering_malformed_scenario_is_rejected(client: TestClient) -> None:
    response = client.post("/tests", json={"name": "broken"})

    assert response.status_code == 422


# --- POST/GET /runs, GET /runs/{run_id} ----------------------------------------------


def test_run_passing_scenario(client: TestClient) -> None:
    client.post("/servers", json=_server_payload())
    scenario_id = client.post("/tests", json=_scenario_payload()).json()["id"]

    response = client.post("/runs", json={"scenario_ids": [scenario_id]})

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "passed"
    assert body["passed"] == 1
    assert body["failed"] == 0
    assert body["errored"] == 0
    assert len(body["results"]) == 1
    assert body["results"][0]["status"] == "passed"
    assert body["results"][0]["tool"] == "echo"


def test_run_failing_scenario(client: TestClient) -> None:
    client.post("/servers", json=_server_payload())
    scenario_id = client.post(
        "/tests", json=_scenario_payload(assertions={"equals": "goodbye"})
    ).json()["id"]

    response = client.post("/runs", json={"scenario_ids": [scenario_id]})

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "failed"
    assert body["failed"] == 1
    assert body["results"][0]["assertions"][0]["passed"] is False


def test_run_with_unknown_scenario_id_is_rejected(client: TestClient) -> None:
    response = client.post("/runs", json={"scenario_ids": [999]})

    assert response.status_code == 400


def test_run_with_unregistered_server_is_rejected(client: TestClient) -> None:
    scenario_id = client.post(
        "/tests", json=_scenario_payload(server="never-registered")
    ).json()["id"]

    response = client.post("/runs", json={"scenario_ids": [scenario_id]})

    assert response.status_code == 400


def test_run_requires_at_least_one_scenario_id(client: TestClient) -> None:
    response = client.post("/runs", json={"scenario_ids": []})

    assert response.status_code == 422


def test_get_run_and_list_runs(client: TestClient) -> None:
    client.post("/servers", json=_server_payload())
    scenario_id = client.post("/tests", json=_scenario_payload()).json()["id"]
    run_id = client.post("/runs", json={"scenario_ids": [scenario_id]}).json()["id"]

    detail = client.get(f"/runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == run_id
    assert len(detail.json()["results"]) == 1

    listing = client.get("/runs")
    assert listing.status_code == 200
    assert [run["id"] for run in listing.json()] == [run_id]


def test_get_unknown_run_returns_404(client: TestClient) -> None:
    response = client.get("/runs/999")

    assert response.status_code == 404
