from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import TypeAdapter, ValidationError

from mcp_test_harness.api.deps import DbSession
from mcp_test_harness.mcp.exceptions import MCPConnectionError
from mcp_test_harness.models.scenario import TestScenario
from mcp_test_harness.models.server import ServerConfig
from mcp_test_harness.services.runs import (
    RunNotFoundError,
    execute_run,
    get_run,
    list_runs,
)
from mcp_test_harness.services.scenarios import (
    ScenarioNotFoundError,
    create_scenario,
    list_scenarios,
)
from mcp_test_harness.services.servers import (
    ServerAlreadyExistsError,
    ServerNotFoundError,
    check_server_status,
    config_from_record,
    create_server,
    discover_tools,
    get_server,
    list_servers,
)

router = APIRouter(include_in_schema=False)

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

_server_config_adapter: TypeAdapter[ServerConfig] = TypeAdapter(ServerConfig)

RECENT_RUNS_LIMIT = 5


# --- pages -----------------------------------------------------------------------


@router.get("/", include_in_schema=False)
def index() -> RedirectResponse:
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: DbSession) -> HTMLResponse:
    runs = list_runs(db)
    recent_runs = list(reversed(runs))[:RECENT_RUNS_LIMIT]
    latest_run = runs[-1] if runs else None
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "active": "dashboard",
            "servers": list_servers(db),
            "total_tests": len(list_scenarios(db)),
            "latest_run": latest_run,
            "recent_runs": recent_runs,
        },
    )


@router.get("/servers", response_class=HTMLResponse)
def servers_page(request: Request, db: DbSession) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "servers.html", {"active": "servers", "servers": list_servers(db)}
    )


@router.post("/servers")
async def register_server(request: Request, db: DbSession) -> RedirectResponse:
    form = await request.form()
    payload = {
        "transport": form.get("transport", "stdio"),
        "name": form.get("name", ""),
        "command": form.get("command", ""),
        "args": (str(form.get("args") or "")).split(),
        "url": form.get("url") or None,
    }
    try:
        config = _server_config_adapter.validate_python(payload)
        create_server(db, config)
    except (ValidationError, ServerAlreadyExistsError) as exc:
        return RedirectResponse(f"/servers?error={quote(str(exc))}", status_code=303)
    return RedirectResponse("/servers", status_code=303)


@router.get("/servers/{server_id}/status", response_class=HTMLResponse)
async def server_status_fragment(server_id: int, request: Request, db: DbSession) -> HTMLResponse:
    try:
        config = config_from_record(get_server(db, server_id))
    except ServerNotFoundError:
        return templates.TemplateResponse(request, "partials/server_status.html", {})
    status_value = await check_server_status(config)
    return templates.TemplateResponse(
        request, "partials/server_status.html", {"status": status_value}
    )


@router.get("/servers/{server_id}/tools", response_class=HTMLResponse)
async def server_tools_fragment(server_id: int, request: Request, db: DbSession) -> HTMLResponse:
    try:
        config = config_from_record(get_server(db, server_id))
    except ServerNotFoundError:
        return templates.TemplateResponse(
            request, "partials/server_tools.html", {"error": "server not found"}
        )
    try:
        tools = await discover_tools(config)
    except MCPConnectionError as exc:
        return templates.TemplateResponse(
            request, "partials/server_tools.html", {"error": str(exc)}
        )
    return templates.TemplateResponse(request, "partials/server_tools.html", {"tools": tools})


@router.get("/tests", response_class=HTMLResponse)
def tests_page(request: Request, db: DbSession) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "tests.html",
        {"active": "tests", "scenarios": list_scenarios(db), "servers": list_servers(db)},
    )


@router.post("/tests")
async def register_scenario(request: Request, db: DbSession) -> RedirectResponse:
    form = await request.form()
    try:
        input_data = json.loads(str(form.get("input") or "{}"))
        assertions_data = json.loads(str(form.get("assertions") or "{}"))
        scenario = TestScenario.model_validate(
            {
                "name": form.get("name", ""),
                "server": form.get("server", ""),
                "tool": form.get("tool", ""),
                "input": input_data,
                "assertions": assertions_data,
            }
        )
        create_scenario(db, scenario)
    except (json.JSONDecodeError, ValidationError) as exc:
        return RedirectResponse(f"/tests?error={quote(str(exc))}", status_code=303)
    return RedirectResponse("/tests", status_code=303)


@router.post("/tests/{scenario_id}/run", response_class=HTMLResponse)
async def run_single_test(scenario_id: int, request: Request, db: DbSession) -> HTMLResponse:
    try:
        run_record = await execute_run(db, [scenario_id])
    except (ScenarioNotFoundError, ServerNotFoundError) as exc:
        return templates.TemplateResponse(
            request, "partials/run_trigger_result.html", {"error": str(exc)}
        )
    return templates.TemplateResponse(
        request, "partials/run_trigger_result.html", {"run": run_record}
    )


@router.post("/tests/run-all", response_class=HTMLResponse)
async def run_all_tests(request: Request, db: DbSession) -> HTMLResponse:
    scenario_ids = [record.id for record in list_scenarios(db)]
    if not scenario_ids:
        return templates.TemplateResponse(
            request, "partials/run_trigger_result.html", {"error": "no scenarios registered"}
        )
    run_record = await execute_run(db, scenario_ids)
    return templates.TemplateResponse(
        request, "partials/run_trigger_result.html", {"run": run_record}
    )


@router.get("/runs", response_class=HTMLResponse)
def runs_page(request: Request, db: DbSession) -> HTMLResponse:
    runs = list(reversed(list_runs(db)))
    return templates.TemplateResponse(request, "runs.html", {"active": "runs", "runs": runs})


@router.get("/runs/{run_id}", response_class=HTMLResponse)
def run_detail_page(run_id: int, request: Request, db: DbSession) -> HTMLResponse:
    try:
        run_record = get_run(db, run_id)
    except RunNotFoundError as exc:
        return templates.TemplateResponse(
            request,
            "not_found.html",
            {"active": "runs", "message": str(exc)},
            status_code=404,
        )
    return templates.TemplateResponse(
        request, "run_detail.html", {"active": "runs", "run": run_record}
    )
