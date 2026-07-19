
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models import ProbeResult, Run
from app.orchestrator import runner
from app.schemas import ProbeResultOut, RunOut

router = APIRouter()


@router.get("", response_model=list[RunOut])
async def list_runs(
    status: str | None = Query(None),
    limit: int = Query(100, le=500),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Run).order_by(Run.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(Run.status == status)
    return (await session.execute(stmt)).scalars().all()


@router.get("/{run_id}", response_model=RunOut)
async def get_run(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await session.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run


@router.get("/{run_id}/results", response_model=list[ProbeResultOut])
async def run_results(run_id: str, session: AsyncSession = Depends(get_session)):
    rows = (
        await session.execute(
            select(ProbeResult).where(ProbeResult.run_id == run_id).order_by(ProbeResult.pass_rate)
        )
    ).scalars().all()
    return rows


@router.post("/{run_id}/cancel")
async def cancel(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await session.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    ok = await runner.cancel_run(run_id)
    if not ok:
        raise HTTPException(409, "Run is not currently executing.")
    return {"status": "cancelled"}


@router.get("/{run_id}/risk-matrix")
async def risk_matrix(run_id: str, session: AsyncSession = Depends(get_session)):
    rows = (
        await session.execute(select(ProbeResult).where(ProbeResult.run_id == run_id))
    ).scalars().all()

    buckets: dict[str, dict] = {}
    for r in rows:
        owasp_tags = [t for t in (r.tags or []) if isinstance(t, str) and t.lower().startswith("owasp")]
        if not owasp_tags:
            owasp_tags = ["unmapped"]
        for tag in owasp_tags:
            b = buckets.setdefault(tag, {"category": tag, "total": 0, "failed": 0, "probes": set()})
            b["total"] += r.total
            b["failed"] += r.failed
            b["probes"].add(r.probe)

    result = []
    for b in buckets.values():
        total = b["total"]
        result.append({
            "category": b["category"],
            "total": total,
            "failed": b["failed"],
            "failure_rate": round(b["failed"] / total, 3) if total else 0.0,
            "probe_count": len(b["probes"]),
        })
    result.sort(key=lambda x: x["failure_rate"], reverse=True)
    return result
