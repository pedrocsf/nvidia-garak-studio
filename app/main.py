
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    compare,
    discovery,
    plugins,
    reports,
    runs,
    scans,
    settings_routes,
    timeline,
    triage,
)
from app.core.config import settings
from app.core.database import init_db
from app.ws.gateway import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Web UI and orchestration layer for the garak LLM vulnerability scanner.",
    license_info={
        "name": "Apache-2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0",
    },
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(plugins.router, prefix="/api/plugins", tags=["plugins"])
app.include_router(discovery.router, prefix="/api/discovery", tags=["discovery"])
app.include_router(scans.router, prefix="/api/scans", tags=["scans"])
app.include_router(runs.router, prefix="/api/runs", tags=["runs"])
app.include_router(timeline.router, prefix="/api/runs", tags=["timeline"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(compare.router, prefix="/api/compare", tags=["compare"])
app.include_router(triage.router, prefix="/api/triage", tags=["triage"])
app.include_router(settings_routes.router, prefix="/api/settings", tags=["settings"])
app.include_router(ws_router)


@app.get("/api/health")
async def health() -> dict:
    from app.introspection import service as intro

    return {
        "status": "ok",
        "app": settings.app_name,
        "garak_available": intro.garak_available(),
    }
