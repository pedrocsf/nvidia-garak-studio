
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = REPO_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GARAK_STUDIO_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "Garak Studio"
    debug: bool = True

    data_dir: Path = DEFAULT_DATA_DIR
    database_url: str = f"sqlite+aiosqlite:///{(DEFAULT_DATA_DIR / 'studio.db').as_posix()}"

    garak_command: str = os.environ.get("GARAK_STUDIO_GARAK_COMMAND", "")

    secret_key: str | None = None

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    ollama_host: str = "http://localhost:11434"

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    @property
    def reports_dir(self) -> Path:
        return self.data_dir / "reports"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.runs_dir, self.reports_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings


settings = get_settings()
