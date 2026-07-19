
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models import ProbeResult, Run

router = APIRouter()


def _significant(a: ProbeResult, b: ProbeResult) -> bool:
    if None not in (a.ci_low, a.ci_high, b.ci_low, b.ci_high):
        return a.ci_high < b.ci_low or b.ci_high < a.ci_low  # type: ignore[operator]
    return abs(a.pass_rate - b.pass_rate) >= 0.1


@router.get("")
async def compare_runs(
    a: str = Query(..., description="baseline run id"),
    b: str = Query(..., description="comparison run id"),
    session: AsyncSession = Depends(get_session),
):
    run_a = await session.get(Run, a)
    run_b = await session.get(Run, b)

    rows_a = (await session.execute(select(ProbeResult).where(ProbeResult.run_id == a))).scalars().all()
    rows_b = (await session.execute(select(ProbeResult).where(ProbeResult.run_id == b))).scalars().all()

    map_a = {(r.probe, r.detector): r for r in rows_a}
    map_b = {(r.probe, r.detector): r for r in rows_b}
    keys = sorted(set(map_a) | set(map_b))

    diffs = []
    for key in keys:
        ra, rb = map_a.get(key), map_b.get(key)
        pr_a = ra.pass_rate if ra else None
        pr_b = rb.pass_rate if rb else None
        delta = (pr_b - pr_a) if (pr_a is not None and pr_b is not None) else None
        direction = "unchanged"
        if delta is not None:
            if delta > 0.001:
                direction = "improved"
            elif delta < -0.001:
                direction = "regressed"
        diffs.append({
            "probe": key[0],
            "detector": key[1],
            "pass_rate_a": pr_a,
            "pass_rate_b": pr_b,
            "delta": round(delta, 4) if delta is not None else None,
            "direction": direction,
            "significant": bool(ra and rb and _significant(ra, rb)),
        })

    return {
        "run_a": {"id": a, "label": run_a.label if run_a else None,
                  "score": run_a.attack_surface_score if run_a else None},
        "run_b": {"id": b, "label": run_b.label if run_b else None,
                  "score": run_b.attack_surface_score if run_b else None},
        "diffs": diffs,
    }
