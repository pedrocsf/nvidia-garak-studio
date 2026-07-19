
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models import AuditLog, Hit, TriageStatus
from app.schemas import HitOut, TriageUpdate

router = APIRouter()


@router.patch("/hits/{hit_id}", response_model=HitOut)
async def update_triage(hit_id: str, body: TriageUpdate, session: AsyncSession = Depends(get_session)):
    hit = await session.get(Hit, hit_id)
    if not hit:
        raise HTTPException(404, "Hit not found")

    if body.triage_status is not None:
        try:
            hit.triage_status = TriageStatus(body.triage_status)
        except ValueError:
            raise HTTPException(422, f"Invalid triage_status '{body.triage_status}'")
    if body.triage_note is not None:
        hit.triage_note = body.triage_note
    if body.assignee_id is not None:
        hit.assignee_id = body.assignee_id or None

    session.add(AuditLog(
        action="triage_update", target_type="hit", target_id=hit_id,
        detail={"status": hit.triage_status.value, "note": hit.triage_note},
    ))
    await session.commit()
    await session.refresh(hit)
    return hit


@router.get("/queue", response_model=list[HitOut])
async def triage_queue(
    status: str | None = Query(None),
    assignee_id: str | None = Query(None),
    limit: int = Query(100, le=500),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Hit)
    if status:
        stmt = stmt.where(Hit.triage_status == status)
    if assignee_id:
        stmt = stmt.where(Hit.assignee_id == assignee_id)
    stmt = stmt.order_by(Hit.updated_at.desc()).limit(limit)
    return (await session.execute(stmt)).scalars().all()


@router.get("/stats")
async def triage_stats(session: AsyncSession = Depends(get_session)):
    rows = (
        await session.execute(select(Hit.triage_status, func.count(Hit.id)).group_by(Hit.triage_status))
    ).all()
    return {status.value if hasattr(status, "value") else str(status): count for status, count in rows}
