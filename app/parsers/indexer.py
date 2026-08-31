
from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import delete

from app.core.database import SessionLocal
from app.introspection import service as intro
from app.models import Hit, ProbeResult, Run
from app.parsers import timeline_store
from app.parsers.report import ParsedReport, parse_report


def _find_artifacts(run_dir: Path) -> dict[str, str | None]:
    def _find(pattern: str) -> str | None:
        matches = sorted(run_dir.rglob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        return str(matches[0]) if matches else None

    return {
        "report_path": _find("*.report.jsonl"),
        "hitlog_path": _find("*.hitlog.jsonl") or _find("*.hitlog.json"),
        "html_path": _find("*.report.html"),
    }


def _probe_tags(probe: str) -> list[str]:
    try:
        fq = probe if probe.startswith("probes.") else f"probes.{probe}"
        for info in intro.list_category("probes"):
            if info["name"] == fq or info["name"].endswith(probe):
                return info.get("tags", [])
    except Exception:
        pass
    return []


def compute_attack_surface_score(report: ParsedReport) -> float | None:
    total = sum(r.total for r in report.evals)
    if not total:
        return None
    weighted_pass = sum(r.passed for r in report.evals)
    return round(100.0 * weighted_pass / total, 1)


async def index_run(run_id: str, run_dir: Path) -> dict[str, Any]:
    artifacts = _find_artifacts(run_dir)
    report_path = artifacts["report_path"]
    if not report_path:
        raise FileNotFoundError(
            f"No *.report.jsonl found under {run_dir}. garak may have failed "
            "before writing a report."
        )

    parsed = parse_report(Path(report_path))
    score = compute_attack_surface_score(parsed)

    async with SessionLocal() as session:
        await session.execute(delete(ProbeResult).where(ProbeResult.run_id == run_id))
        await session.execute(delete(Hit).where(Hit.run_id == run_id))

        for row in parsed.evals:
            session.add(ProbeResult(
                run_id=run_id,
                probe=row.probe,
                detector=row.detector,
                total=row.total,
                passed=row.passed,
                failed=row.failed,
                pass_rate=row.pass_rate,
                ci_low=row.ci_low,
                ci_high=row.ci_high,
                tags=_probe_tags(row.probe),
            ))

        for hit in parsed.hits[:5000]:
            session.add(Hit(
                run_id=run_id,
                probe=hit.probe,
                detector=hit.detector,
                attempt_uuid=hit.attempt_uuid,
                prompt=hit.prompt[:20000],
                output=hit.output[:20000],
                score=hit.score,
                turns=hit.turns,
            ))

        run = await session.get(Run, run_id)
        if run and parsed.target_model and not run.target_model:
            run.target_model = parsed.target_model
        if run and parsed.generator_type and not run.generator_type:
            run.generator_type = parsed.generator_type

        await session.commit()

    timeline_result: dict[str, Any] = {}
    console_path = timeline_store.console_path_for(run_id)
    try:
        async with SessionLocal() as session:
            timeline_result = await timeline_store.index_timeline(
                session,
                run_id,
                Path(report_path),
                console_path if console_path.exists() else None,
            )
    except Exception as exc:
        timeline_result = {"error": str(exc)}

    return {
        "total_attempts": parsed.total_attempts,
        "total_hits": parsed.total_hits,
        "attack_surface_score": score,
        "garak_run_uuid": parsed.garak_run_uuid,
        "timeline": timeline_result,
        **artifacts,
    }
