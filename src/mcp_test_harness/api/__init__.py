from fastapi import APIRouter

from mcp_test_harness.api.health import router as health_router

router = APIRouter()
router.include_router(health_router)

__all__ = ["router"]
