
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.models import Hit, Run, RunStatus
from app.parsers.indexer import index_run
from app.schemas import HitOut, RunOut

router = APIRouter()


@router.get("/{run_id}/hits", response_model=list[HitOut])
async def list_hits(
    run_id: str,
    probe: str | None = Query(None),
    triage_status: str | None = Query(None),
    q: str | None = Query(None, description="full-text over prompt/output"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Hit).where(Hit.run_id == run_id)
    if probe:
        stmt = stmt.where(Hit.probe == probe)
    if triage_status:
        stmt = stmt.where(Hit.triage_status == triage_status)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Hit.prompt.ilike(like)) | (Hit.output.ilike(like)))
    stmt = stmt.order_by(Hit.probe).offset(offset).limit(limit)
    return (await session.execute(stmt)).scalars().all()


@router.get("/{run_id}/hits/count")
async def count_hits(run_id: str, session: AsyncSession = Depends(get_session)):
    total = (
        await session.execute(select(func.count(Hit.id)).where(Hit.run_id == run_id))
    ).scalar_one()
    return {"count": total}


@router.get("/{run_id}/html")
async def get_html(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await session.get(Run, run_id)
    if not run or not run.html_path or not Path(run.html_path).exists():
        raise HTTPException(404, "HTML report not available for this run.")
    return FileResponse(run.html_path, media_type="text/html")


@router.get("/{run_id}/download/jsonl")
async def download_jsonl(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await session.get(Run, run_id)
    if not run or not run.report_path or not Path(run.report_path).exists():
        raise HTTPException(404, "JSONL report not available.")
    return FileResponse(
        run.report_path, media_type="application/x-ndjson",
        filename=f"{run_id}.report.jsonl",
    )


@router.get("/{run_id}/export/sarif", response_class=PlainTextResponse)
async def export_sarif(run_id: str, session: AsyncSession = Depends(get_session)):
    import json

    hits = (await session.execute(select(Hit).where(Hit.run_id == run_id))).scalars().all()
    results = []
    for h in hits:
        results.append({
            "ruleId": f"{h.probe}/{h.detector}",
            "level": "error",
            "message": {"text": f"garak probe {h.probe} succeeded (detector {h.detector})."},
            "properties": {"score": h.score, "triage_status": h.triage_status},
        })
    sarif = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [{
            "tool": {"driver": {"name": "garak-studio", "informationUri": "https://github.com/NVIDIA/garak"}},
            "results": results,
        }],
    }
    return PlainTextResponse(json.dumps(sarif, indent=2), media_type="application/json")


@router.post("/import", response_model=RunOut)
async def import_report(
    file: UploadFile,
    label: str = Query("Imported report"),
    session: AsyncSession = Depends(get_session),
):
    if not file.filename or not file.filename.endswith(".jsonl"):
        raise HTTPException(400, "Expected a *.report.jsonl file.")

    run = Run(label=label, status=RunStatus.completed)
    session.add(run)
    await session.commit()
    await session.refresh(run)

    run_dir = settings.runs_dir / run.id
    run_dir.mkdir(parents=True, exist_ok=True)
    dest = run_dir / "imported.report.jsonl"
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    metrics = await index_run(run.id, run_dir)
    run = await session.get(Run, run.id)
    run.total_attempts = metrics.get("total_attempts", 0)
    run.total_hits = metrics.get("total_hits", 0)
    run.attack_surface_score = metrics.get("attack_surface_score")
    run.report_path = metrics.get("report_path")
    run.garak_run_uuid = metrics.get("garak_run_uuid")
    await session.commit()
    await session.refresh(run)
    return run
