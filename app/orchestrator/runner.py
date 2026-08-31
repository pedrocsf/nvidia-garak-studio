
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import decrypt_secret
from app.models import Run, RunStatus, Secret
from app.orchestrator.command import build_invocation, redact_command
from app.parsers import timeline_store
from app.parsers.timeline import LiveTimelineReader
from app.ws.gateway import broker

_PROBE_LINE = re.compile(r"(probes\.[\w.]+)")
_PERCENT = re.compile(r"(\d{1,3})%\|")

_TIMELINE_BATCH = 50

_processes: dict[str, asyncio.subprocess.Process] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _load_secret_env() -> dict[str, str]:
    env: dict[str, str] = {}
    async with SessionLocal() as session:
        secrets = (await session.execute(select(Secret))).scalars().all()
        for s in secrets:
            if s.env_var:
                try:
                    env[s.env_var] = decrypt_secret(s.ciphertext)
                except ValueError:
                    continue
    return env


async def _publish(run_id: str, message: dict[str, Any]) -> None:
    await broker.publish(run_id, message)


async def _publish_timeline(run_id: str, events: list) -> None:
    for start in range(0, len(events), _TIMELINE_BATCH):
        chunk = events[start : start + _TIMELINE_BATCH]
        await _publish(run_id, {
            "type": "timeline",
            "events": [e.as_row() for e in chunk],
        })


async def _stream_timeline(run_id: str, run_dir: Path, stop: asyncio.Event) -> None:
    interval = settings.timeline_poll_interval
    reader: LiveTimelineReader | None = None

    async def _drain() -> None:
        nonlocal reader
        if reader is None:
            report = timeline_store.find_report(run_dir)
            if report is None:
                return
            reader = LiveTimelineReader(report)
            await _publish(run_id, {"type": "timeline_ready", "report": str(report)})
        events = await asyncio.to_thread(reader.poll)
        if events:
            await _publish_timeline(run_id, events)

    try:
        while not stop.is_set():
            try:
                await _drain()
            except Exception:
                pass
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=interval)
        await asyncio.sleep(0.2)
        with contextlib.suppress(Exception):
            await _drain()
    except asyncio.CancelledError:
        raise


class _ConsoleLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh = None

    def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a", encoding="utf-8", buffering=1)

    def write(self, line: str) -> None:
        if self._fh is None:
            return
        try:
            self._fh.write(json.dumps(
                {"ts": _now().isoformat(), "line": line}, ensure_ascii=False
            ) + "\n")
        except Exception:
            pass

    def close(self) -> None:
        if self._fh is not None:
            with contextlib.suppress(Exception):
                self._fh.close()
            self._fh = None


async def _set_status(run_id: str, **fields) -> None:
    async with SessionLocal() as session:
        run = await session.get(Run, run_id)
        if not run:
            return
        for k, v in fields.items():
            setattr(run, k, v)
        await session.commit()


async def start_run(run_id: str) -> None:
    async with SessionLocal() as session:
        run = await session.get(Run, run_id)
        if run is None:
            return
        config = dict(run.config or {})

    run_dir = settings.runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    argv, extra_env = build_invocation(config, run_dir)

    env = os.environ.copy()
    env.update(await _load_secret_env())
    env.update(extra_env)
    env["PYTHONUNBUFFERED"] = "1"

    await _set_status(
        run_id, status=RunStatus.running, started_at=_now(),
    )
    await _publish(run_id, {
        "type": "status", "status": "running",
        "command": redact_command(argv),
    })

    try:
        creationflags = 0
        preexec_fn = None
        if sys.platform == "win32":
            creationflags = getattr(
                __import__("subprocess"), "CREATE_NEW_PROCESS_GROUP", 0
            )
        else:
            preexec_fn = os.setsid

        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(run_dir),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            creationflags=creationflags,
            preexec_fn=preexec_fn,
        )
    except FileNotFoundError as exc:
        await _fail(run_id, f"Could not launch garak: {exc}")
        return

    _processes[run_id] = proc

    console = _ConsoleLog(timeline_store.console_path_for(run_id))
    console.open()
    stop_tail = asyncio.Event()
    tail_task = asyncio.create_task(_stream_timeline(run_id, run_dir, stop_tail))

    current_probe: str | None = None
    try:
        assert proc.stdout is not None
        async for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace").rstrip("\n")
            console.write(line)
            event: dict[str, Any] = {"type": "log", "line": line}

            m = _PROBE_LINE.search(line)
            if m and m.group(1) != current_probe:
                current_probe = m.group(1)
                event["probe"] = current_probe
                await _publish(run_id, {"type": "probe", "probe": current_probe})

            pm = _PERCENT.search(line)
            if pm:
                event["percent"] = int(pm.group(1))

            await _publish(run_id, event)

        exit_code = await proc.wait()
    except asyncio.CancelledError:
        await _terminate(proc)
        await _stop_tail(tail_task, stop_tail)
        console.close()
        await _index_timeline(run_id, run_dir)
        await _set_status(run_id, status=RunStatus.cancelled, finished_at=_now())
        await _publish(run_id, {"type": "status", "status": "cancelled"})
        raise
    finally:
        _processes.pop(run_id, None)

    await _stop_tail(tail_task, stop_tail)
    console.close()

    if exit_code == 0:
        await _finalize_success(run_id, run_dir)
    else:
        await _index_timeline(run_id, run_dir)
        await _fail(run_id, f"garak exited with code {exit_code}", exit_code=exit_code)


async def _stop_tail(task: asyncio.Task, stop: asyncio.Event) -> None:
    stop.set()
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=5)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        task.cancel()
    except Exception:
        pass


async def _index_timeline(run_id: str, run_dir: Path) -> None:
    report = timeline_store.find_report(run_dir)
    console_path = timeline_store.console_path_for(run_id)
    if report is None and not console_path.exists():
        return
    try:
        async with SessionLocal() as session:
            await timeline_store.index_timeline(
                session, run_id, report,
                console_path if console_path.exists() else None,
            )
    except Exception:
        pass


async def _finalize_success(run_id: str, run_dir: Path) -> None:
    from app.parsers.indexer import index_run

    await _publish(run_id, {"type": "status", "status": "parsing"})
    try:
        metrics = await index_run(run_id, run_dir)
    except Exception as exc:
        await _set_status(
            run_id, status=RunStatus.completed, finished_at=_now(), exit_code=0,
            error=f"(report parsing failed: {exc})",
        )
        await _publish(run_id, {"type": "status", "status": "completed", "warning": str(exc)})
        return

    await _set_status(
        run_id,
        status=RunStatus.completed,
        finished_at=_now(),
        exit_code=0,
        total_attempts=metrics.get("total_attempts", 0),
        total_hits=metrics.get("total_hits", 0),
        attack_surface_score=metrics.get("attack_surface_score"),
        report_path=metrics.get("report_path"),
        hitlog_path=metrics.get("hitlog_path"),
        html_path=metrics.get("html_path"),
        garak_run_uuid=metrics.get("garak_run_uuid"),
    )
    await _publish(run_id, {"type": "status", "status": "completed", "metrics": metrics})


async def _fail(run_id: str, message: str, exit_code: int | None = None) -> None:
    await _set_status(
        run_id, status=RunStatus.failed, finished_at=_now(),
        error=message, exit_code=exit_code,
    )
    await _publish(run_id, {"type": "status", "status": "failed", "error": message})


async def _terminate(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    try:
        if sys.platform == "win32":
            proc.send_signal(signal.CTRL_BREAK_EVENT)
            await asyncio.sleep(1)
            if proc.returncode is None:
                proc.kill()
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            await asyncio.sleep(2)
            if proc.returncode is None:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except ProcessLookupError:
        pass
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


async def cancel_run(run_id: str) -> bool:
    proc = _processes.get(run_id)
    if not proc:
        return False
    await _terminate(proc)
    await _set_status(run_id, status=RunStatus.cancelled, finished_at=_now())
    await _publish(run_id, {"type": "status", "status": "cancelled"})
    return True


def is_running(run_id: str) -> bool:
    return run_id in _processes
