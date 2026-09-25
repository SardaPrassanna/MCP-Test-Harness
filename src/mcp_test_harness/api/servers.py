from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from mcp_test_harness.api.deps import DbSession
from mcp_test_harness.api.schemas import ServerOut
from mcp_test_harness.models.server import ServerConfig
from mcp_test_harness.services.servers import (
    ServerAlreadyExistsError,
    create_server,
    list_servers,
)

router = APIRouter(tags=["servers"])


@router.get("/servers", response_model=list[ServerOut])
def get_servers(db: DbSession) -> list[ServerOut]:
    return [ServerOut.model_validate(record) for record in list_servers(db)]


@router.post("/servers", response_model=ServerOut, status_code=status.HTTP_201_CREATED)
def post_server(payload: ServerConfig, db: DbSession) -> ServerOut:
    try:
        record = create_server(db, payload)
    except ServerAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ServerOut.model_validate(record)
