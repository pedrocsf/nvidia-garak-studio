
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.introspection import service as intro

router = APIRouter()


@router.get("/summary")
async def plugin_summary():
    if not intro.garak_available():
        raise HTTPException(503, "garak is not installed/importable in this environment.")
    return intro.summary()


@router.get("/{category}")
async def list_plugins(
    category: str,
    meta: bool = Query(True, description="Include per-plugin metadata (slower)."),
):
    if category not in intro.PLUGIN_CATEGORIES:
        raise HTTPException(
            404, f"Unknown category '{category}'. One of {intro.PLUGIN_CATEGORIES}."
        )
    if not intro.garak_available():
        raise HTTPException(503, "garak is not installed/importable in this environment.")
    try:
        return intro.list_category(category, include_meta=meta)
    except intro.GarakUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post("/refresh")
async def refresh_cache():
    intro.clear_cache()
    return {"status": "cleared"}
