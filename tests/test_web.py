"""Integration tests for the server-rendered web console.

Each test builds a fresh FastAPI app bound to a scratch SQLite database
file under `tmp_path`, exactly like `tests/test_api.py`, and drives the
console the way a browser (or HTMX) would: HTML form POSTs and GETs
against `/dashboard`, `/servers`, `/tests`, `/runs`, and `/runs/{run_id}`.
Server registrations point at the checked-in fake stdio MCP server, so
status/tool-discovery/run actions exercise a real MCP handshake. No
external service is contacted.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mcp_test_harness.config import Settings
from mcp_test_harness.main import create_app

FAKE_STDIO_SERVER_SCRIPT = Path(__file__).parent / "fixtures" / "fake_stdio_server.py"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    settings = Settings(database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    return TestClient(create_app(settings))


def _register_server(client: TestClient, name: str = "fake-stdio-server") -> None:
    response = client.post(
        "/servers",
        data={
            "transport": "stdio",
            "name": name,
            "command": sys.executable,
            "args": str(FAKE_STDIO_SERVER_SCRIPT),
        },
    )
    assert response.status_code == 200  # followed the redirect back to /servers


def _register_scenario(
    client: TestClient,
    *,
    name: str = "echo_scenario",
    server: str = "fake-stdio-server",
    assertions: str = '{"status": "success", "equals": "hello"}',
) -> None:
    response = client.post(
        "/tests",
        data={
            "name": name,
            "server": server,
            "tool": "echo",
            "input": '{"text": "hello"}',
            "assertions": assertions,
        },
    )
    assert response.status_code == 200  # followed the redirect back to /tests


# --- basic page rendering, including on an empty database --------------------------------


def test_index_redirects_to_dashboard(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"


def test_dashboard_renders_with_no_data(client: TestClient) -> None:
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "No servers registered" in response.text


def test_servers_page_renders_with_no_data(client: TestClient) -> None:
    response = client.get("/servers")

    assert response.status_code == 200
    assert "No servers registered" in response.text


def test_tests_page_renders_with_no_data(client: TestClient) -> None:
    response = client.get("/tests")

    assert response.status_code == 200
    assert "No scenarios registered" in response.text


def test_runs_page_renders_with_no_data(client: TestClient) -> None:
    response = client.get("/runs")

    assert response.status_code == 200
    assert "No runs yet" in response.text


def test_static_stylesheet_is_served(client: TestClient) -> None:
    response = client.get("/static/style.css")

    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]


# --- servers page: register, list, status, discover tools -------------------------------


def test_register_server_via_form_and_list(client: TestClient) -> None:
    _register_server(client)

    page = client.get("/servers")
    assert "fake-stdio-server" in page.text
    assert client.get("/api/servers").json()[0]["name"] == "fake-stdio-server"


def test_registering_malformed_server_via_form_redirects_with_error(client: TestClient) -> None:
    response = client.post("/servers", data={"transport": "stdio", "name": "broken"})

    assert response.status_code == 200
    assert "error" in str(response.url)


def test_server_status_fragment_reports_online_for_reachable_server(client: TestClient) -> None:
    _register_server(client)
    server_id = client.get("/api/servers").json()[0]["id"]

    fragment = client.get(f"/servers/{server_id}/status")

    assert fragment.status_code == 200
    assert "online" in fragment.text


def test_server_status_fragment_reports_unreachable_for_bad_command(client: TestClient) -> None:
    client.post(
        "/servers",
        data={
            "transport": "stdio",
            "name": "broken-server",
            "command": "definitely-not-a-real-mcp-server-binary",
        },
    )
    server_id = client.get("/api/servers").json()[0]["id"]

    fragment = client.get(f"/servers/{server_id}/status")

    assert fragment.status_code == 200
    assert "unreachable" in fragment.text


def test_discover_tools_fragment_lists_tool_names(client: TestClient) -> None:
    _register_server(client)
    server_id = client.get("/api/servers").json()[0]["id"]

    fragment = client.get(f"/servers/{server_id}/tools")

    assert fragment.status_code == 200
    assert "echo" in fragment.text
    assert "list_items" in fragment.text


# --- tests page: register, run one, run the suite -----------------------------------------


def test_register_scenario_via_form_and_list(client: TestClient) -> None:
    _register_server(client)
    _register_scenario(client)

    page = client.get("/tests")
    assert "echo_scenario" in page.text
    assert client.get("/api/tests").json()[0]["name"] == "echo_scenario"


def test_registering_malformed_scenario_via_form_redirects_with_error(client: TestClient) -> None:
    response = client.post(
        "/tests",
        data={"name": "broken", "server": "x", "tool": "echo", "input": "{}", "assertions": "{}"},
    )

    assert response.status_code == 200
    assert "error" in str(response.url)


def test_run_single_test_fragment_reports_pass_and_links_to_run(client: TestClient) -> None:
    _register_server(client)
    _register_scenario(client)
    scenario_id = client.get("/api/tests").json()[0]["id"]

    fragment = client.post(f"/tests/{scenario_id}/run")

    assert fragment.status_code == 200
    assert "badge-passed" in fragment.text
    assert "/runs/1" in fragment.text


def test_run_test_suite_executes_all_scenarios(client: TestClient) -> None:
    _register_server(client)
    _register_scenario(client, name="a")
    _register_scenario(client, name="b", assertions='{"equals": "not-hello"}')

    fragment = client.post("/tests/run-all")

    assert fragment.status_code == 200
    assert "badge-failed" in fragment.text  # aggregate status: one scenario failed

    run = client.get("/api/runs").json()[0]
    assert run["passed"] == 1
    assert run["failed"] == 1


def test_run_all_with_no_scenarios_reports_an_error_without_crashing(client: TestClient) -> None:
    fragment = client.post("/tests/run-all")

    assert fragment.status_code == 200
    assert "no scenarios registered" in fragment.text


# --- runs page and run detail --------------------------------------------------------------


def test_runs_page_lists_a_completed_run(client: TestClient) -> None:
    _register_server(client)
    _register_scenario(client)
    scenario_id = client.get("/api/tests").json()[0]["id"]
    client.post(f"/tests/{scenario_id}/run")

    page = client.get("/runs")

    assert page.status_code == 200
    assert "/runs/1" in page.text
    assert "passed" in page.text


def test_run_detail_page_shows_assertion_results(client: TestClient) -> None:
    _register_server(client)
    _register_scenario(client)
    scenario_id = client.get("/api/tests").json()[0]["id"]
    client.post(f"/tests/{scenario_id}/run")
    run_id = client.get("/api/runs").json()[0]["id"]

    page = client.get(f"/runs/{run_id}")

    assert page.status_code == 200
    assert "echo_scenario" in page.text
    assert "equals" in page.text  # assertion name shown in the failure/pass list


def test_run_detail_page_shows_failure_and_error_detail(client: TestClient) -> None:
    _register_server(client)
    _register_scenario(client, assertions='{"equals": "goodbye"}')
    scenario_id = client.get("/api/tests").json()[0]["id"]
    client.post(f"/tests/{scenario_id}/run")
    run_id = client.get("/api/runs").json()[0]["id"]

    page = client.get(f"/runs/{run_id}")

    assert page.status_code == 200
    assert "badge-failed" in page.text
    assert "goodbye" in page.text


def test_run_detail_page_returns_404_for_missing_run(client: TestClient) -> None:
    response = client.get("/runs/999")

    assert response.status_code == 404
