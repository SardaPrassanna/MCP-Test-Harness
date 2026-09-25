from fastapi import APIRouter

from mcp_test_harness.api.health import router as health_router
from mcp_test_harness.api.runs import router as runs_router
from mcp_test_harness.api.scenarios import router as scenarios_router
from mcp_test_harness.api.servers import router as servers_router

router = APIRouter()
router.include_router(health_router)
router.include_router(servers_router)
router.include_router(scenarios_router)
router.include_router(runs_router)

__all__ = ["router"]
