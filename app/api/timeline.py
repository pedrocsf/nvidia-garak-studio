from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models import Run
from app.parsers import timeline_store as store
from app.parsers.timeline import ALL_KINDS, DEFAULT_HIT_THRESHOLD

router = APIRouter()

SORTABLE = tuple(store.SORT_COLUMNS.keys())


async def _get_run(run_id: str, session: AsyncSession) -> Run:
    run = await session.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run


def _csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(v.strip() for v in value.split(",") if v.strip())


def _status_of(run: Run) -> str:
    return run.status.value if hasattr(run.status, "value") else str(run.status)


@router.get("/{run_id}/timeline")
async def get_timeline(
    run_id: str,
    q: str = Query("", description="Free-text search across prompts, outputs and labels"),
    kind: str | None = Query(None, description="Comma-separated event kinds"),
    outcome: str | None = Query(None, description="Comma-separated outcomes"),
    probe: str = Query(""),
    stream: str = Query("report", pattern="^(report|console)$"),
    sort: str = Query("seq"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    source: str = Query("auto", pattern="^(auto|index|file)$"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    run = await _get_run(run_id, session)

    if sort not in SORTABLE:
        raise HTTPException(400, f"sort must be one of: {', '.join(SORTABLE)}")

    kinds = _csv(kind)
    unknown = [k for k in kinds if k not in ALL_KINDS]
    if unknown:
        raise HTTPException(400, f"unknown kind(s): {', '.join(unknown)}")

    filters = store.TimelineFilters(
        q=q, kinds=kinds, outcomes=_csv(outcome), probe=probe, stream=stream,
        sort=sort, order=order, offset=offset, limit=limit,
    )

    use_index = source == "index"
    if source == "auto":
        is_live = _status_of(run) in ("queued", "running")
        use_index = not is_live and await store.has_index(session, run_id, stream)

    if use_index:
        payload = await store.query_from_index(session, run_id, filters)
    else:
        report_path, console_path = store.resolve_artifacts(run)
        if report_path is None and console_path is None:
            payload = {
                "source": "file", "total": 0, "offset": offset, "limit": limit,
                "events": [], "facets": {"kind": {}, "outcome": {}, "probe": {}},
            }
        else:
            payload = store.query_from_file(report_path, console_path, filters)

    payload["run_status"] = _status_of(run)
    payload["stream"] = stream
    return payload


@router.get("/{run_id}/timeline/event/{seq}")
async def get_timeline_event(
    run_id: str,
    seq: int,
    stream: str = Query("report", pattern="^(report|console)$"),
    source: str = Query("auto", pattern="^(auto|index|file)$"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    run = await _get_run(run_id, session)

    if source != "file":
        found = await store.detail_from_index(session, run_id, seq, stream)
        if found is not None:
            return {**found, "source": "index", "stream": stream}
        if source == "index":
            raise HTTPException(404, "Event not found in index")

    report_path, console_path = store.resolve_artifacts(run)
    found = store.detail_from_file(report_path, console_path, seq, stream)
    if found is None:
        raise HTTPException(404, "Event not found")
    return {**found, "source": "file", "stream": stream}


@router.post("/{run_id}/timeline/rebuild")
async def rebuild_timeline(
    run_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    run = await _get_run(run_id, session)
    report_path, console_path = store.resolve_artifacts(run)
    if report_path is None and console_path is None:
        raise HTTPException(
            404,
            f"No garak report or console log found for this run under "
            f"{store.run_dir_for(run_id)}. Nothing to rebuild from.",
        )

    result = await store.index_timeline(session, run_id, report_path, console_path)
    return {
        **result,
        "report_path": str(report_path) if report_path else None,
        "console_path": str(console_path) if console_path else None,
    }


@router.get("/{run_id}/timeline/export")
async def export_timeline(
    run_id: str,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    run = await _get_run(run_id, session)
    report_path, console_path = store.resolve_artifacts(run)

    def _generate():
        for stream, event in store.export_events(report_path, console_path):
            yield json.dumps(
                {"stream": stream, **event.as_full()}, ensure_ascii=False
            ) + "\n"

    filename = f"timeline-{run_id}.jsonl"
    return StreamingResponse(
        _generate(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{run_id}/timeline/meta")
async def timeline_meta(
    run_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    run = await _get_run(run_id, session)
    report_path, console_path = store.resolve_artifacts(run)
    return {
        "run_id": run_id,
        "run_status": _status_of(run),
        "indexed": await store.has_index(session, run_id),
        "indexed_streams": {
            s: await store.has_index(session, run_id, s) for s in store.STREAMS
        },
        "report_path": str(report_path) if report_path else None,
        "console_path": str(console_path) if console_path else None,
        "hit_threshold": DEFAULT_HIT_THRESHOLD,
        "kinds": list(ALL_KINDS),
        "streams": list(store.STREAMS),
        "sortable": list(SORTABLE),
    }
