
from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_HIT_THRESHOLD = 0.5


def iter_report(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


@dataclass
class EvalRow:
    probe: str
    detector: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    ci_low: float | None = None
    ci_high: float | None = None

    @property
    def pass_rate(self) -> float:
        return (self.passed / self.total) if self.total else 0.0


@dataclass
class HitRow:
    probe: str
    detector: str
    attempt_uuid: str | None
    prompt: str
    output: str
    score: float | None
    turns: list | None = None


@dataclass
class ParsedReport:
    garak_run_uuid: str | None = None
    target_model: str | None = None
    generator_type: str | None = None
    evals: list[EvalRow] = field(default_factory=list)
    hits: list[HitRow] = field(default_factory=list)
    total_attempts: int = 0
    total_hits: int = 0


def _first(d: dict, *keys, default=None):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


def _norm_detector(name: str) -> str:
    name = str(name)
    if name.startswith("detector."):
        return name[len("detector."):]
    return name


def _extract_output(attempt: dict) -> str:
    outputs = _first(attempt, "outputs", "response", default=None)
    if isinstance(outputs, list) and outputs:
        first = outputs[0]
        if isinstance(first, dict):
            return str(_first(first, "text", "content", default=first))
        return str(first)
    if isinstance(outputs, str):
        return outputs
    return ""


def _extract_prompt(attempt: dict) -> str:
    prompt = _first(attempt, "prompt", "prompt_text", default="")
    if isinstance(prompt, dict):
        return str(_first(prompt, "text", "content", default=prompt))
    if isinstance(prompt, list):
        return " ".join(str(p) for p in prompt)
    return str(prompt)


def _extract_turns(attempt: dict) -> list | None:
    for key in ("conversations", "messages", "turns", "history"):
        val = attempt.get(key)
        if isinstance(val, list) and val:
            return val
    return None


def parse_report(path: Path, hit_threshold: float = DEFAULT_HIT_THRESHOLD) -> ParsedReport:
    report = ParsedReport()
    eval_index: dict[tuple[str, str], EvalRow] = {}

    for entry in iter_report(path):
        etype = str(entry.get("entry_type", "")).lower()

        if etype == "init":
            report.garak_run_uuid = report.garak_run_uuid or _first(
                entry, "run", "uuid", "run_uuid"
            )

        elif "setup" in etype or etype == "config" or "start_run" in etype:
            report.garak_run_uuid = report.garak_run_uuid or _first(
                entry, "run", "uuid", "run_uuid"
            )
            report.target_model = report.target_model or _first(
                entry, "model_name", "_config.plugins.model_name", "target"
            )
            report.generator_type = report.generator_type or _first(
                entry, "model_type", "_config.plugins.model_type", "generator_type"
            )

        elif etype == "attempt":
            if entry.get("status") not in (2, "2"):
                continue
            report.total_attempts += 1
            probe = str(_first(entry, "probe_classname", "probe", default="unknown"))
            det_results = _first(entry, "detector_results", "detectors", default={}) or {}
            prompt = _extract_prompt(entry)
            output = _extract_output(entry)
            turns = _extract_turns(entry)
            attempt_uuid = _first(entry, "uuid", "attempt_uuid")

            if isinstance(det_results, dict):
                for detector, scores in det_results.items():
                    detector = _norm_detector(detector)
                    score_list = scores if isinstance(scores, list) else [scores]
                    for score in score_list:
                        try:
                            sval = float(score)
                        except (TypeError, ValueError):
                            continue
                        key = (probe, str(detector))
                        row = eval_index.setdefault(key, EvalRow(probe, str(detector)))
                        row.total += 1
                        if sval >= hit_threshold:
                            row.failed += 1
                            report.total_hits += 1
                            report.hits.append(HitRow(
                                probe=probe, detector=str(detector),
                                attempt_uuid=attempt_uuid, prompt=prompt,
                                output=output, score=sval, turns=turns,
                            ))
                        else:
                            row.passed += 1

        elif etype == "eval":
            probe = str(_first(entry, "probe", "probe_classname", default="unknown"))
            detector = _norm_detector(_first(entry, "detector", default="unknown"))
            total = int(_first(entry, "total", "instances", default=0) or 0)
            passed = int(_first(entry, "passed", default=0) or 0)
            row = eval_index.get((probe, detector)) or EvalRow(probe, detector)
            if total:
                row.total = total
                row.passed = passed
                row.failed = total - passed
            row.ci_low = _first(entry, "ci_low", "confidence_low", "lower_bound")
            row.ci_high = _first(entry, "ci_high", "confidence_high", "upper_bound")
            eval_index[(probe, detector)] = row

    report.evals = list(eval_index.values())
    return report
