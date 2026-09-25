from __future__ import annotations

from fastapi import APIRouter, status

from mcp_test_harness.api.deps import DbSession
from mcp_test_harness.api.schemas import ScenarioOut
from mcp_test_harness.models.scenario import TestScenario
from mcp_test_harness.services.scenarios import create_scenario, list_scenarios

router = APIRouter(tags=["tests"])


@router.get("/tests", response_model=list[ScenarioOut])
def get_tests(db: DbSession) -> list[ScenarioOut]:
    return [ScenarioOut.model_validate(record) for record in list_scenarios(db)]


@router.post("/tests", response_model=ScenarioOut, status_code=status.HTTP_201_CREATED)
def post_test(payload: TestScenario, db: DbSession) -> ScenarioOut:
    record = create_scenario(db, payload)
    return ScenarioOut.model_validate(record)
