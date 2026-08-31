from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Run, RunEvent
from app.parsers.timeline import (
    DEFAULT_HIT_THRESHOLD,
    TimelineEvent,
    iter_console,
    iter_events,
)

CONSOLE_FILENAME = "console.jsonl"
INDEX_BATCH = 500

STREAM_REPORT = "report"
STREAM_CONSOLE = "console"
STREAMS = (STREAM_REPORT, STREAM_CONSOLE)

SORT_COLUMNS = {
    "seq": RunEvent.seq,
    "kind": RunEvent.kind,
    "probe": RunEvent.probe,
    "detector": RunEvent.detector,
    "outcome": RunEvent.outcome,
    "score": RunEvent.score,
    "title": RunEvent.title,
}

_SORT_KEYS = {
    "seq": lambda e: e.seq,
    "kind": lambda e: e.kind,
    "probe": lambda e: e.probe,
    "detector": lambda e: e.detector,
    "outcome": lambda e: e.outcome,
    "score": lambda e: e.score or 0.0,
    "title": lambda e: e.title.lower(),
}


def _sort_events(events: list[TimelineEvent], sort: str, order: str) -> list[TimelineEvent]:
    keyfn = _SORT_KEYS.get(sort, _SORT_KEYS["seq"])
    reverse = order == "desc"

    scored, unscored = events, []
    if sort == "score":
        scored = [e for e in events if e.score is not None]
        unscored = [e for e in events if e.score is None]

    scored.sort(key=lambda e: e.seq)
    scored.sort(key=keyfn, reverse=reverse)
    unscored.sort(key=lambda e: e.seq)
    return scored + unscored


@dataclass
class TimelineFilters:
    q: str = ""
    kinds: tuple[str, ...] = ()
    outcomes: tuple[str, ...] = ()
    probe: str = ""
    stream: str = STREAM_REPORT
    sort: str = "seq"
    order: str = "asc"
    offset: int = 0
    limit: int = 100

    @property
    def terms(self) -> list[str]:
        return [t for t in self.q.lower().split() if t]


def run_dir_for(run_id: str) -> Path:
    return settings.runs_dir / run_id


def console_path_for(run_id: str) -> Path:
    return run_dir_for(run_id) / CONSOLE_FILENAME


def find_report(run_dir: Path) -> Path | None:
    if not run_dir.exists():
        return None
    matches = sorted(
        run_dir.rglob("*.report.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return matches[0] if matches else None


def resolve_artifacts(run: Run) -> tuple[Path | None, Path | None]:
    report: Path | None = None
    if run.report_path:
        candidate = Path(run.report_path)
        if candidate.exists():
            report = candidate
    if report is None:
        report = find_report(run_dir_for(run.id))

    console = console_path_for(run.id)
    return report, (console if console.exists() else None)


def _to_row(run_id: str, stream: str, event: TimelineEvent) -> RunEvent:
    return RunEvent(
        run_id=run_id,
        stream=stream,
        seq=event.seq,
        kind=event.kind,
        title=event.title,
        summary=event.summary,
        ts=event.ts,
        probe=event.probe,
        detector=event.detector,
        outcome=event.outcome,
        score=event.score,
        attempt_uuid=event.attempt_uuid,
        search_text=event.search_text(),
        detail=event.detail,
    )


async def index_timeline(
    session: AsyncSession,
    run_id: str,
    report_path: Path | None,
    console_path: Path | None,
    hit_threshold: float = DEFAULT_HIT_THRESHOLD,
) -> dict[str, Any]:
    await session.execute(delete(RunEvent).where(RunEvent.run_id == run_id))

    cap = settings.timeline_max_events
    counts = {STREAM_REPORT: 0, STREAM_CONSOLE: 0}
    truncated: list[str] = []

    sources = (
        (STREAM_REPORT, iter_events(report_path, hit_threshold)),
        (STREAM_CONSOLE, iter_console(console_path)),
    )

    for stream, source in sources:
        batch: list[RunEvent] = []
        for event in source:
            if counts[stream] >= cap:
                truncated.append(stream)
                break
            batch.append(_to_row(run_id, stream, event))
            counts[stream] += 1
            if len(batch) >= INDEX_BATCH:
                session.add_all(batch)
                await session.flush()
                batch = []
        if batch:
            session.add_all(batch)
            await session.flush()

    await session.commit()
    return {
        "indexed": sum(counts.values()),
        "counts": counts,
        "truncated": sorted(set(truncated)),
    }


async def has_index(session: AsyncSession, run_id: str, stream: str | None = None) -> bool:
    stmt = select(func.count()).select_from(RunEvent).where(RunEvent.run_id == run_id)
    if stream:
        stmt = stmt.where(RunEvent.stream == stream)
    return bool(await session.scalar(stmt))


def _apply_common(stmt, run_id: str, f: TimelineFilters, *, with_facet_dims: bool):
    stmt = stmt.where(RunEvent.run_id == run_id, RunEvent.stream == f.stream)
    for term in f.terms:
        stmt = stmt.where(RunEvent.search_text.like(f"%{term}%"))
    if f.probe:
        stmt = stmt.where(RunEvent.probe == f.probe)
    if with_facet_dims:
        if f.kinds:
            stmt = stmt.where(RunEvent.kind.in_(f.kinds))
        if f.outcomes:
            stmt = stmt.where(RunEvent.outcome.in_(f.outcomes))
    return stmt


async def _facets_from_index(session: AsyncSession, run_id: str, f: TimelineFilters):
    async def counts(column):
        stmt = _apply_common(
            select(column, func.count()).select_from(RunEvent),
            run_id, f, with_facet_dims=False,
        ).group_by(column)
        rows = (await session.execute(stmt)).all()
        return {str(k or ""): int(v) for k, v in rows}

    probe_stmt = _apply_common(
        select(RunEvent.probe, func.count()).select_from(RunEvent),
        run_id, f, with_facet_dims=True,
    ).where(RunEvent.probe != "").group_by(RunEvent.probe)
    probe_rows = (await session.execute(probe_stmt)).all()

    return {
        "kind": await counts(RunEvent.kind),
        "outcome": await counts(RunEvent.outcome),
        "probe": dict(sorted(
            ((str(k), int(v)) for k, v in probe_rows),
            key=lambda kv: kv[1], reverse=True,
        )[:50]),
    }


async def query_from_index(
    session: AsyncSession, run_id: str, f: TimelineFilters
) -> dict[str, Any]:
    total = await session.scalar(
        _apply_common(
            select(func.count()).select_from(RunEvent), run_id, f, with_facet_dims=True
        )
    )

    column = SORT_COLUMNS.get(f.sort, RunEvent.seq)
    direction = column.desc() if f.order == "desc" else column.asc()
    direction = direction.nullslast()
    stmt = _apply_common(select(RunEvent), run_id, f, with_facet_dims=True)
    stmt = stmt.order_by(direction, RunEvent.seq.asc()).offset(f.offset).limit(f.limit)
    rows = (await session.execute(stmt)).scalars().all()

    return {
        "source": "index",
        "total": int(total or 0),
        "offset": f.offset,
        "limit": f.limit,
        "events": [_row_to_dict(r) for r in rows],
        "facets": await _facets_from_index(session, run_id, f),
    }


def _row_to_dict(row: RunEvent) -> dict[str, Any]:
    return {
        "seq": row.seq,
        "kind": row.kind,
        "title": row.title,
        "summary": row.summary,
        "ts": row.ts,
        "probe": row.probe,
        "detector": row.detector,
        "outcome": row.outcome,
        "score": row.score,
        "attempt_uuid": row.attempt_uuid,
    }


async def detail_from_index(
    session: AsyncSession, run_id: str, seq: int, stream: str = STREAM_REPORT
) -> dict[str, Any] | None:
    row = (
        await session.execute(
            select(RunEvent).where(
                RunEvent.run_id == run_id,
                RunEvent.stream == stream,
                RunEvent.seq == seq,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return {**_row_to_dict(row), "detail": row.detail or {}}


def _matches(event: TimelineEvent, f: TimelineFilters, *, with_facet_dims: bool) -> bool:
    if f.probe and event.probe != f.probe:
        return False
    if f.terms:
        haystack = event.search_text()
        if not all(term in haystack for term in f.terms):
            return False
    if with_facet_dims:
        if f.kinds and event.kind not in f.kinds:
            return False
        if f.outcomes and event.outcome not in f.outcomes:
            return False
    return True


def _file_source(
    report_path: Path | None,
    console_path: Path | None,
    stream: str,
    hit_threshold: float,
) -> Iterable[TimelineEvent]:
    if stream == STREAM_CONSOLE:
        return iter_console(console_path)
    return iter_events(report_path, hit_threshold)


def query_from_file(
    report_path: Path | None,
    console_path: Path | None,
    f: TimelineFilters,
    hit_threshold: float = DEFAULT_HIT_THRESHOLD,
) -> dict[str, Any]:
    base: list[TimelineEvent] = []
    kind_counter: Counter = Counter()
    outcome_counter: Counter = Counter()
    probe_counter: Counter = Counter()

    for event in _file_source(report_path, console_path, f.stream, hit_threshold):
        if not _matches(event, f, with_facet_dims=False):
            continue
        kind_counter[event.kind] += 1
        outcome_counter[event.outcome] += 1
        if _matches(event, f, with_facet_dims=True):
            base.append(event)
            if event.probe:
                probe_counter[event.probe] += 1

    base = _sort_events(base, f.sort, f.order)
    window = base[f.offset : f.offset + f.limit]
    return {
        "source": "file",
        "total": len(base),
        "offset": f.offset,
        "limit": f.limit,
        "events": [e.as_row() for e in window],
        "facets": {
            "kind": dict(kind_counter),
            "outcome": dict(outcome_counter),
            "probe": dict(probe_counter.most_common(50)),
        },
    }


def detail_from_file(
    report_path: Path | None,
    console_path: Path | None,
    seq: int,
    stream: str = STREAM_REPORT,
    hit_threshold: float = DEFAULT_HIT_THRESHOLD,
) -> dict[str, Any] | None:
    for event in _file_source(report_path, console_path, stream, hit_threshold):
        if event.seq == seq:
            return event.as_full()
        if event.seq > seq:
            break
    return None


def export_events(
    report_path: Path | None,
    console_path: Path | None,
    hit_threshold: float = DEFAULT_HIT_THRESHOLD,
) -> Iterable[tuple[str, TimelineEvent]]:
    for event in iter_events(report_path, hit_threshold):
        yield STREAM_REPORT, event
    for event in iter_console(console_path):
        yield STREAM_CONSOLE, event
