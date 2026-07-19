
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.introspection import service as intro
from app.models import Run, RunStatus, ScanProfile
from app.orchestrator import runner
from app.schemas import (
    CostEstimate,
    CostEstimateRequest,
    ProfileIn,
    ProfileOut,
    RunOut,
    ScanRequest,
)

router = APIRouter()

_AVG_PROMPTS_PER_PROBE = 25


@router.post("", response_model=RunOut)
async def create_scan(req: ScanRequest, session: AsyncSession = Depends(get_session)):
    cfg = req.config.model_dump()
    run = Run(
        label=req.label or f"{cfg['generator'].get('type','')}:{cfg['generator'].get('name','')}",
        profile_id=req.profile_id,
        generator_type=cfg["generator"].get("type", ""),
        target_model=cfg["generator"].get("name", "") or "",
        config=cfg,
        status=RunStatus.queued,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    asyncio.create_task(runner.start_run(run.id))
    return run


@router.post("/estimate", response_model=CostEstimate)
async def estimate(req: CostEstimateRequest):
    cfg = req.config
    probes = cfg.probes
    if probes == "all" or not probes:
        try:
            probe_count = len(intro.list_category("probes", include_meta=False)) if intro.garak_available() else 0
        except Exception:
            probe_count = 0
        note = "Estimating against ALL probes — consider narrowing the selection."
    else:
        probe_count = len(probes) if isinstance(probes, list) else 1
        note = "Estimate based on selected probes and average prompts/probe."

    estimated_prompts = probe_count * _AVG_PROMPTS_PER_PROBE
    estimated_generations = estimated_prompts * cfg.generations
    return CostEstimate(
        probe_count=probe_count,
        estimated_prompts=estimated_prompts,
        generations=cfg.generations,
        estimated_generations=estimated_generations,
        note=note,
    )


@router.get("/profiles", response_model=list[ProfileOut])
async def list_profiles(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(ScanProfile).order_by(ScanProfile.updated_at.desc()))).scalars().all()
    return rows


@router.post("/profiles", response_model=ProfileOut)
async def create_profile(body: ProfileIn, session: AsyncSession = Depends(get_session)):
    profile = ScanProfile(name=body.name, description=body.description, config=body.config)
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile


@router.put("/profiles/{profile_id}", response_model=ProfileOut)
async def update_profile(profile_id: str, body: ProfileIn, session: AsyncSession = Depends(get_session)):
    profile = await session.get(ScanProfile, profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
    profile.name = body.name
    profile.description = body.description
    profile.config = body.config
    profile.version += 1
    await session.commit()
    await session.refresh(profile)
    return profile


@router.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: str, session: AsyncSession = Depends(get_session)):
    profile = await session.get(ScanProfile, profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
    await session.delete(profile)
    await session.commit()
    return {"status": "deleted"}
