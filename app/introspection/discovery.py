
from __future__ import annotations

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import decrypt_secret
from app.models import Secret

_TIMEOUT = httpx.Timeout(5.0, connect=3.0)

DISCOVERABLE = {"ollama", "openai", "generic", "rest", "nim", "nvcf"}


async def _secret_value(env_var: str) -> str | None:
    async with SessionLocal() as session:
        row = (
            await session.execute(select(Secret).where(Secret.env_var == env_var))
        ).scalar_one_or_none()
    if not row:
        return None
    try:
        return decrypt_secret(row.ciphertext)
    except ValueError:
        return None


async def discover_ollama() -> dict:
    url = f"{settings.ollama_host.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except httpx.ConnectError:
        return {"models": [], "source": "ollama",
                "note": f"Ollama not reachable at {settings.ollama_host}. Is it running?"}
    except Exception as exc:
        return {"models": [], "source": "ollama", "note": f"Ollama error: {exc}"}

    models = [m.get("name") for m in data.get("models", []) if m.get("name")]
    note = None if models else "Ollama is running but no models are pulled."
    return {"models": sorted(models), "source": "ollama", "note": note}


async def _discover_openai_compatible(base_url: str, api_key: str | None, source: str) -> dict:
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    url = f"{base_url.rstrip('/')}/models"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 401:
                return {"models": [], "source": source,
                        "note": "Authentication failed — check the stored API key."}
            resp.raise_for_status()
            data = resp.json()
    except httpx.ConnectError:
        return {"models": [], "source": source, "note": f"Endpoint not reachable: {url}"}
    except Exception as exc:
        return {"models": [], "source": source, "note": f"Discovery error: {exc}"}

    items = data.get("data", data if isinstance(data, list) else [])
    models = [m.get("id") for m in items if isinstance(m, dict) and m.get("id")]
    note = None if models else "Endpoint returned no models."
    return {"models": sorted(models), "source": source, "note": note}


async def discover_openai() -> dict:
    api_key = await _secret_value("OPENAI_API_KEY")
    if not api_key:
        return {"models": [], "source": "openai",
                "note": "No OPENAI_API_KEY stored. Add it under Settings to list models."}
    return await _discover_openai_compatible("https://api.openai.com/v1", api_key, "openai")


async def discover_generic(base_url: str | None, api_key_env: str | None) -> dict:
    if not base_url:
        return {"models": [], "source": "generic",
                "note": "Provide a base URL (e.g. http://host:8000/v1) to discover models."}
    api_key = await _secret_value(api_key_env) if api_key_env else None
    return await _discover_openai_compatible(base_url, api_key, "generic")


async def discover(generator_type: str, base_url: str | None = None,
                   api_key_env: str | None = None) -> dict:
    gt = (generator_type or "").lower()
    if gt == "ollama":
        return await discover_ollama()
    if gt == "openai":
        return await discover_openai()
    if gt in {"generic", "rest", "nim", "nvcf"}:
        return await discover_generic(base_url, api_key_env)
    return {"models": [], "source": gt,
            "note": f"Automatic discovery is not supported for '{generator_type}'. "
                    "Enter the model name manually."}
