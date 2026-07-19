
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import encrypt_secret, mask_secret
from app.introspection import service as intro
from app.models import Secret
from app.schemas import SecretIn, SecretOut

router = APIRouter()


@router.get("/info")
async def app_info():
    return {
        "garak_available": intro.garak_available(),
        "garak_version": intro.garak_version() if intro.garak_available() else None,
    }


@router.get("/secrets", response_model=list[SecretOut])
async def list_secrets(session: AsyncSession = Depends(get_session)):
    return (await session.execute(select(Secret).order_by(Secret.name))).scalars().all()


@router.post("/secrets", response_model=SecretOut)
async def create_secret(body: SecretIn, session: AsyncSession = Depends(get_session)):
    existing = (
        await session.execute(select(Secret).where(Secret.name == body.name))
    ).scalar_one_or_none()
    if existing:
        existing.env_var = body.env_var
        existing.ciphertext = encrypt_secret(body.value)
        existing.hint = mask_secret(body.value)
        await session.commit()
        await session.refresh(existing)
        return existing

    secret = Secret(
        name=body.name,
        env_var=body.env_var,
        ciphertext=encrypt_secret(body.value),
        hint=mask_secret(body.value),
    )
    session.add(secret)
    await session.commit()
    await session.refresh(secret)
    return secret


@router.delete("/secrets/{secret_id}")
async def delete_secret(secret_id: str, session: AsyncSession = Depends(get_session)):
    secret = await session.get(Secret, secret_id)
    if not secret:
        raise HTTPException(404, "Secret not found")
    await session.delete(secret)
    await session.commit()
    return {"status": "deleted"}
