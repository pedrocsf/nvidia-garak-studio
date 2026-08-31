from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_HIT_THRESHOLD = 0.5

KIND_RUN_START = "run_start"
KIND_CONFIG = "config"
KIND_PROBE_START = "probe_start"
KIND_ATTEMPT = "attempt"
KIND_EVAL = "eval"
KIND_PAYLOAD = "payload"
KIND_TREE = "tree"
KIND_RUN_END = "run_end"
KIND_CONSOLE = "console"
KIND_ERROR = "error"

ALL_KINDS = (
    KIND_RUN_START, KIND_CONFIG, KIND_PROBE_START, KIND_ATTEMPT, KIND_EVAL,
    KIND_PAYLOAD, KIND_TREE, KIND_RUN_END, KIND_CONSOLE, KIND_ERROR,
)

OUTCOME_HIT = "hit"
OUTCOME_PASS = "pass"
OUTCOME_INFO = "info"
OUTCOME_ERROR = "error"

SEARCH_TEXT_CAP = 8000
DETAIL_TEXT_CAP = 40000

_ERROR_RE_WORDS = ("error", "traceback", "exception", "critical", "failed")


@dataclass
class TimelineEvent:
    seq: int
    kind: str
    title: str
    summary: str = ""
    ts: str | None = None
    probe: str = ""
    detector: str = ""
    outcome: str = OUTCOME_INFO
    score: float | None = None
    attempt_uuid: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def search_text(self) -> str:
        parts = [
            self.kind, self.title, self.summary, self.probe,
            self.detector, self.outcome, self.attempt_uuid or "",
        ]
        d = self.detail
        parts.append(str(d.get("prompt", "")))
        for o in d.get("outputs", []) or []:
            parts.append(str(o))
        for t in d.get("turns", []) or []:
            if isinstance(t, dict):
                parts.append(str(t.get("text", "")))
        parts.append(str(d.get("goal", "")))
        return " ".join(p for p in parts if p).lower()[:SEARCH_TEXT_CAP]

    def as_row(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "kind": self.kind,
            "title": self.title,
            "summary": self.summary,
            "ts": self.ts,
            "probe": self.probe,
            "detector": self.detector,
            "outcome": self.outcome,
            "score": self.score,
            "attempt_uuid": self.attempt_uuid,
        }

    def as_full(self) -> dict[str, Any]:
        return {**self.as_row(), "detail": self.detail}


def _message_text(msg: Any) -> str:
    if msg is None:
        return ""
    if isinstance(msg, str):
        return msg
    if isinstance(msg, dict):
        text = msg.get("text")
        if text:
            return str(text)
        if msg.get("data_path"):
            kind = msg.get("data_type") or "binary"
            return f"<{kind}: {msg['data_path']}>"
        return ""
    return str(msg)


def _conversation_turns(conv: Any) -> list[dict[str, str]]:
    if not isinstance(conv, dict):
        return []
    turns = conv.get("turns")
    if not isinstance(turns, list):
        return []
    out: list[dict[str, str]] = []
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        out.append({
            "role": str(turn.get("role", "")),
            "text": _message_text(turn.get("content"))[:DETAIL_TEXT_CAP],
        })
    return out


def _prompt_text(entry: dict) -> str:
    prompt = entry.get("prompt")
    turns = _conversation_turns(prompt)
    if turns:
        for turn in reversed(turns):
            if turn["role"] == "user" and turn["text"]:
                return turn["text"]
        return turns[-1]["text"]
    if isinstance(prompt, str):
        return prompt
    if isinstance(prompt, dict):
        return _message_text(prompt)
    return ""


def _output_texts(entry: dict) -> list[str]:
    outputs = entry.get("outputs")
    if isinstance(outputs, str):
        return [outputs]
    if not isinstance(outputs, list):
        return []
    return [_message_text(o)[:DETAIL_TEXT_CAP] for o in outputs if o is not None]


def _all_turns(entry: dict) -> list[dict[str, str]]:
    conversations = entry.get("conversations")
    if isinstance(conversations, list) and conversations:
        collected: list[dict[str, str]] = []
        for conv in conversations:
            collected.extend(_conversation_turns(conv))
        if collected:
            return collected
    return _conversation_turns(entry.get("prompt"))


def _short(text: str, limit: int = 120) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _strip_prefix(name: Any, prefix: str) -> str:
    name = str(name or "")
    return name[len(prefix):] if name.startswith(prefix) else name


def iter_report_lines(path: Path) -> Iterator[dict]:
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                yield record


def _event_init(entry: dict) -> TimelineEvent:
    version = entry.get("garak_version", "?")
    return TimelineEvent(
        seq=0,
        kind=KIND_RUN_START,
        title=f"garak {version} started",
        summary=f"run {entry.get('run', '?')}",
        ts=entry.get("start_time"),
        detail={"garak_version": version, "run": entry.get("run"),
                "start_time": entry.get("start_time")},
    )


def _event_setup(entry: dict) -> TimelineEvent:
    model_type = entry.get("plugins.model_type") or entry.get("model_type") or "?"
    model_name = entry.get("plugins.model_name") or entry.get("model_name") or ""
    probe_spec = entry.get("plugins.probe_spec") or entry.get("probe_spec") or "all"
    target = f"{model_type}:{model_name}" if model_name else str(model_type)
    config = {k: v for k, v in entry.items() if k != "entry_type"}
    return TimelineEvent(
        seq=0,
        kind=KIND_CONFIG,
        title=f"Configuration resolved — target {target}",
        summary=f"probes: {_short(probe_spec, 80)}",
        detail={"config": config},
    )


def _event_payload(entry: dict) -> TimelineEvent:
    name = entry.get("payload_name") or entry.get("name") or "?"
    entries = entry.get("entries") or entry.get("size")
    return TimelineEvent(
        seq=0,
        kind=KIND_PAYLOAD,
        title=f"Payload loaded — {name}",
        summary=f"{entries} entries" if entries is not None else "",
        detail={k: v for k, v in entry.items() if k != "entry_type"},
    )


def _event_tree(entry: dict) -> TimelineEvent:
    probe = str(entry.get("probe") or entry.get("probe_classname") or "")
    node = entry.get("node_id") or entry.get("id") or ""
    return TimelineEvent(
        seq=0,
        kind=KIND_TREE,
        title=f"Search node explored — {node}" if node else "Search node explored",
        summary=_short(entry.get("node_parent") or "", 80),
        probe=probe,
        detail={k: v for k, v in entry.items() if k != "entry_type"},
    )


def _event_completion(entry: dict) -> TimelineEvent:
    return TimelineEvent(
        seq=0,
        kind=KIND_RUN_END,
        title="Run finished",
        summary=f"run {entry.get('run', '?')}",
        ts=entry.get("end_time"),
        detail={k: v for k, v in entry.items() if k != "entry_type"},
    )


def _event_eval(entry: dict) -> TimelineEvent:
    probe = _strip_prefix(entry.get("probe") or entry.get("probe_classname"), "probes.")
    detector = _strip_prefix(entry.get("detector"), "detector.")
    detector = _strip_prefix(detector, "detectors.")

    passed = int(entry.get("passed") or 0)
    fails = entry.get("fails")
    total = entry.get("total_evaluated")
    if total is None:
        total = entry.get("total") or entry.get("instances") or 0
    total = int(total or 0)
    if fails is None:
        fails = max(0, total - passed)
    fails = int(fails)

    pass_rate = (passed / total) if total else 0.0
    ci_low = entry.get("confidence_lower", entry.get("ci_low"))
    ci_high = entry.get("confidence_upper", entry.get("ci_high"))

    return TimelineEvent(
        seq=0,
        kind=KIND_EVAL,
        title=f"Evaluated {probe} / {detector}",
        summary=f"{passed}/{total} passed ({pass_rate:.0%}), {fails} failed",
        probe=probe,
        detector=detector,
        outcome=OUTCOME_HIT if fails else OUTCOME_PASS,
        score=round(1.0 - pass_rate, 4),
        detail={
            "probe": probe, "detector": detector,
            "passed": passed, "failed": fails, "total": total,
            "nones": entry.get("nones"),
            "total_processed": entry.get("total_processed"),
            "pass_rate": round(pass_rate, 4),
            "confidence_lower": ci_low, "confidence_upper": ci_high,
            "confidence_method": entry.get("confidence_method"),
        },
    )


def _event_attempt(entry: dict, hit_threshold: float) -> TimelineEvent:
    probe = _strip_prefix(entry.get("probe_classname") or entry.get("probe"), "probes.")
    prompt = _prompt_text(entry)
    outputs = _output_texts(entry)
    turns = _all_turns(entry)

    raw_results = entry.get("detector_results") or {}
    detector_scores: dict[str, list[float]] = {}
    if isinstance(raw_results, dict):
        for name, scores in raw_results.items():
            name = _strip_prefix(_strip_prefix(str(name), "detector."), "detectors.")
            values = scores if isinstance(scores, list) else [scores]
            numeric: list[float] = []
            for value in values:
                try:
                    numeric.append(float(value))
                except (TypeError, ValueError):
                    continue
            if numeric:
                detector_scores[name] = numeric

    top_score: float | None = None
    firing: list[str] = []
    for name, values in detector_scores.items():
        best = max(values)
        if top_score is None or best > top_score:
            top_score = best
        if best >= hit_threshold:
            firing.append(name)

    if not detector_scores:
        outcome = OUTCOME_INFO
    elif firing:
        outcome = OUTCOME_HIT
    else:
        outcome = OUTCOME_PASS

    detector_label = ", ".join(sorted(firing)) if firing else ", ".join(sorted(detector_scores))
    verdict = "HIT" if outcome == OUTCOME_HIT else "pass" if outcome == OUTCOME_PASS else "no verdict"

    return TimelineEvent(
        seq=0,
        kind=KIND_ATTEMPT,
        title=_short(prompt or "(empty prompt)", 140),
        summary=f"{verdict} · {_short(outputs[0], 90) if outputs else 'no output'}",
        probe=probe,
        detector=detector_label,
        outcome=outcome,
        score=top_score,
        attempt_uuid=entry.get("uuid"),
        detail={
            "prompt": prompt,
            "outputs": outputs,
            "turns": turns,
            "detector_scores": detector_scores,
            "firing_detectors": sorted(firing),
            "hit_threshold": hit_threshold,
            "goal": entry.get("goal"),
            "probe": probe,
            "probe_params": entry.get("probe_params"),
            "targets": entry.get("targets"),
            "notes": entry.get("notes"),
            "attempt_seq": entry.get("seq"),
            "status": entry.get("status"),
        },
    )


def _event_console(record: dict, ts_fallback: str | None = None) -> TimelineEvent:
    line = str(record.get("line", ""))
    lowered = line.lower()
    is_error = any(word in lowered for word in _ERROR_RE_WORDS)
    return TimelineEvent(
        seq=0,
        kind=KIND_ERROR if is_error else KIND_CONSOLE,
        title=_short(line, 200) or "(blank line)",
        ts=record.get("ts") or ts_fallback,
        outcome=OUTCOME_ERROR if is_error else OUTCOME_INFO,
        detail={"line": line},
    )


def _entry_to_event(entry: dict, hit_threshold: float) -> TimelineEvent | None:
    etype = str(entry.get("entry_type", "")).lower().strip()
    if etype == "init":
        return _event_init(entry)
    if etype in ("start_run setup", "setup", "config"):
        return _event_setup(entry)
    if etype == "payload_init":
        return _event_payload(entry)
    if etype == "tree_data":
        return _event_tree(entry)
    if etype == "completion":
        return _event_completion(entry)
    if etype == "eval":
        return _event_eval(entry)
    if etype == "attempt":
        if entry.get("status") not in (2, "2"):
            return None
        return _event_attempt(entry, hit_threshold)
    return None


def _expand(
    entry: dict, hit_threshold: float, current_probe: str | None
) -> tuple[list[TimelineEvent], str | None]:
    event = _entry_to_event(entry, hit_threshold)
    if event is None:
        return [], current_probe

    out: list[TimelineEvent] = []
    if event.kind == KIND_ATTEMPT and event.probe and event.probe != current_probe:
        current_probe = event.probe
        out.append(TimelineEvent(
            seq=0,
            kind=KIND_PROBE_START,
            title=f"Probe started — {event.probe}",
            summary=str(event.detail.get("goal") or ""),
            probe=event.probe,
            detail={"probe": event.probe, "goal": event.detail.get("goal")},
        ))
    out.append(event)
    return out, current_probe


def iter_events(
    report_path: Path | None,
    hit_threshold: float = DEFAULT_HIT_THRESHOLD,
) -> Iterator[TimelineEvent]:
    if not report_path or not report_path.exists():
        return

    seq = 0
    current_probe: str | None = None
    for entry in iter_report_lines(report_path):
        events, current_probe = _expand(entry, hit_threshold, current_probe)
        for event in events:
            event.seq = seq
            seq += 1
            yield event


def iter_console(console_path: Path | None) -> Iterator[TimelineEvent]:
    if not console_path or not console_path.exists():
        return

    seq = 0
    with console_path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                record = {"line": line}
            if not isinstance(record, dict):
                continue
            event = _event_console(record)
            event.seq = seq
            seq += 1
            yield event


class LiveTimelineReader:
    def __init__(
        self, report_path: Path, hit_threshold: float = DEFAULT_HIT_THRESHOLD
    ) -> None:
        self.path = report_path
        self.hit_threshold = hit_threshold
        self.offset = 0
        self.seq = 0
        self.current_probe: str | None = None
        self._partial = ""

    def poll(self) -> list[TimelineEvent]:
        if not self.path.exists():
            return []
        try:
            size = self.path.stat().st_size
        except OSError:
            return []
        if size <= self.offset:
            return []

        with self.path.open("r", encoding="utf-8", errors="replace") as fh:
            fh.seek(self.offset)
            chunk = fh.read()
            self.offset = fh.tell()

        data = self._partial + chunk
        if not data.endswith("\n"):
            data, _, self._partial = data.rpartition("\n")
        else:
            self._partial = ""

        out: list[TimelineEvent] = []
        for line in data.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue
            events, self.current_probe = _expand(
                entry, self.hit_threshold, self.current_probe
            )
            for event in events:
                event.seq = self.seq
                self.seq += 1
                out.append(event)
        return out


def collect_events(
    report_path: Path | None,
    hit_threshold: float = DEFAULT_HIT_THRESHOLD,
    limit: int | None = None,
) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    for event in iter_events(report_path, hit_threshold):
        events.append(event)
        if limit is not None and len(events) >= limit:
            break
    return events
