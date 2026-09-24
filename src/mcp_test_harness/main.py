from fastapi import FastAPI

from mcp_test_harness.api import router as api_router
from mcp_test_harness.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug)
    app.include_router(api_router)
    return app


app = create_app()
