"""Server-rendered web console (Jinja2 + HTMX, no frontend build)."""

from mcp_test_harness.web.routes import STATIC_DIR, router

__all__ = ["STATIC_DIR", "router"]
