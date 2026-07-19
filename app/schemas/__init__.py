
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GeneratorConfig(BaseModel):
    type: str
    name: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class ScanConfig(BaseModel):
    generator: GeneratorConfig
    probes: list[str] | str = "all"
    detectors: list[str] | str = "auto"
    harness: str | None = None
    buffs: list[str] = Field(default_factory=list)
    generations: int = 10
    seed: int | None = None
    parallel_attempts: int | None = None
    report_prefix: str | None = None
    extra_args: list[str] = Field(default_factory=list)


class ScanRequest(BaseModel):
    label: str = ""
    config: ScanConfig
    profile_id: str | None = None


class RunOut(BaseModel):
    id: str
    label: str
    target_model: str
    generator_type: str
    status: str
    exit_code: int | None
    error: str | None
    total_attempts: int
    total_hits: int
    attack_surface_score: float | None
    created_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None

    class Config:
        from_attributes = True


class ProbeResultOut(BaseModel):
    probe: str
    detector: str
    total: int
    passed: int
    failed: int
    pass_rate: float
    ci_low: float | None
    ci_high: float | None
    tags: list[str]

    class Config:
        from_attributes = True


class HitOut(BaseModel):
    id: str
    run_id: str
    probe: str
    detector: str
    attempt_uuid: str | None
    prompt: str
    output: str
    score: float | None
    turns: list | None
    triage_status: str
    triage_note: str
    assignee_id: str | None

    class Config:
        from_attributes = True


class TriageUpdate(BaseModel):
    triage_status: str | None = None
    triage_note: str | None = None
    assignee_id: str | None = None


class ProfileIn(BaseModel):
    name: str
    description: str = ""
    config: dict[str, Any]


class ProfileOut(BaseModel):
    id: str
    name: str
    description: str
    config: dict[str, Any]
    version: int
    created_at: datetime | None
    updated_at: datetime | None

    class Config:
        from_attributes = True


class SecretIn(BaseModel):
    name: str
    env_var: str
    value: str


class SecretOut(BaseModel):
    id: str
    name: str
    env_var: str
    hint: str
    created_at: datetime | None

    class Config:
        from_attributes = True


class CostEstimateRequest(BaseModel):
    config: ScanConfig


class CostEstimate(BaseModel):
    probe_count: int
    estimated_prompts: int
    generations: int
    estimated_generations: int
    note: str
