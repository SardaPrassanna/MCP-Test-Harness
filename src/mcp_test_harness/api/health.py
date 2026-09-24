from fastapi import APIRouter
from pydantic import BaseModel

from mcp_test_harness.config import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    app_name: str
    environment: str


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        environment=settings.environment,
    )
