from fastapi import APIRouter

from mcp_test_harness.api.health import router as health_router
from mcp_test_harness.api.runs import router as runs_router
from mcp_test_harness.api.scenarios import router as scenarios_router
from mcp_test_harness.api.servers import router as servers_router

# Health stays unprefixed (infra probes expect it at the root). The
# resource routers move under /api so the bare paths (/servers, /tests,
# /runs, /runs/{run_id}) are free for the web console's HTML pages.
router = APIRouter()
router.include_router(health_router)
router.include_router(servers_router, prefix="/api")
router.include_router(scenarios_router, prefix="/api")
router.include_router(runs_router, prefix="/api")

__all__ = ["router"]
