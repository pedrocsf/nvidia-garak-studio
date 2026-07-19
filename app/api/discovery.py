
from __future__ import annotations

from fastapi import APIRouter, Query

from app.introspection import discovery

router = APIRouter()


@router.get("/models")
async def discover_models(
    type: str = Query(..., description="Generator/backend type, e.g. ollama, openai."),
    base_url: str | None = Query(None, description="Base URL for generic/REST discovery."),
    api_key_env: str | None = Query(
        None, description="Env var name of a stored secret to authenticate discovery."
    ),
):
    return await discovery.discover(type, base_url=base_url, api_key_env=api_key_env)


@router.get("/supported")
async def supported():
    return {"discoverable": sorted(discovery.DISCOVERABLE)}
