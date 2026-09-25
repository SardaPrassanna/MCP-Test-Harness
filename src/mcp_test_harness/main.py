from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from mcp_test_harness.api import router as api_router
from mcp_test_harness.config import Settings, get_settings
from mcp_test_harness.web import STATIC_DIR
from mcp_test_harness.web import router as web_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug)
    app.state.settings = settings
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(api_router)
    app.include_router(web_router)
    return app


app = create_app()
