from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MCP_HARNESS_", extra="ignore")

    app_name: str = "MCP Test Harness"
    environment: str = "development"
    debug: bool = False
    database_url: str = "sqlite:///./mcp_test_harness.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
