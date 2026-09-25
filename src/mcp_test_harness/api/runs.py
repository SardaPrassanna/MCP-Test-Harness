from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from mcp_test_harness.api.deps import DbSession
from mcp_test_harness.api.schemas import RunCreateRequest, RunDetailOut, RunSummaryOut
from mcp_test_harness.services.runs import RunNotFoundError, execute_run, get_run, list_runs
from mcp_test_harness.services.scenarios import ScenarioNotFoundError
from mcp_test_harness.services.servers import ServerNotFoundError

router = APIRouter(tags=["runs"])


@router.post("/runs", response_model=RunDetailOut, status_code=status.HTTP_201_CREATED)
async def post_run(payload: RunCreateRequest, db: DbSession) -> RunDetailOut:
    try:
        record = await execute_run(db, payload.scenario_ids)
    except (ScenarioNotFoundError, ServerNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RunDetailOut.model_validate(record)


@router.get("/runs", response_model=list[RunSummaryOut])
def get_runs(db: DbSession) -> list[RunSummaryOut]:
    return [RunSummaryOut.model_validate(record) for record in list_runs(db)]


@router.get("/runs/{run_id}", response_model=RunDetailOut)
def get_run_detail(run_id: int, db: DbSession) -> RunDetailOut:
    try:
        record = get_run(db, run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return RunDetailOut.model_validate(record)
