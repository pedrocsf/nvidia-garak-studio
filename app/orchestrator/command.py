
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from app.core.config import settings


def _garak_base_command() -> list[str]:
    if settings.garak_command:
        return settings.garak_command.split()
    return [sys.executable, "-m", "garak"]


def _ollama_rest_config(model: str, host: str) -> dict[str, Any]:
    return {
        "rest": {
            "name": f"ollama:{model}",
            "uri": f"{host.rstrip('/')}/api/generate",
            "method": "post",
            "headers": {"Content-Type": "application/json"},
            "req_template_json_object": {
                "model": model,
                "prompt": "$INPUT",
                "stream": False,
                "keep_alive": "30m",
            },
            "response_json": True,
            "response_json_field": "response",
            "request_timeout": 300,
        }
    }


def build_invocation(config: dict[str, Any], run_dir: Path) -> tuple[list[str], dict[str, str]]:
    argv = _garak_base_command()
    extra_env: dict[str, str] = {}
    config_file_payload: dict[str, Any] = {}

    gen = config.get("generator", {}) or {}
    gen_type = gen.get("type")
    gen_name = gen.get("name")

    if str(gen_type).lower() == "ollama":
        ollama_host = gen.get("options", {}).get("host") or "http://localhost:11434"
        rest_config = _ollama_rest_config(gen_name or "llama3", ollama_host)
        config_file_payload.setdefault("plugins", {}).setdefault(
            "generators", {}
        ).update(rest_config)
        argv += ["--model_type", "rest"]
    else:
        if gen_type:
            argv += ["--model_type", str(gen_type)]
        if gen_name:
            argv += ["--model_name", str(gen_name)]

        gen_options = gen.get("options") or config.get("generator_options") or {}
        if gen_options and gen_type:
            config_file_payload.setdefault("plugins", {}).setdefault("generators", {})[
                gen_type
            ] = gen_options

    probes = config.get("probes")
    if probes and probes != "all":
        if isinstance(probes, (list, tuple)):
            argv += ["--probes", ",".join(str(p) for p in probes)]
        else:
            argv += ["--probes", str(probes)]

    detectors = config.get("detectors")
    if detectors and detectors != "auto":
        if isinstance(detectors, (list, tuple)):
            argv += ["--detectors", ",".join(str(d) for d in detectors)]
        else:
            argv += ["--detectors", str(detectors)]

    if config.get("harness"):
        argv += ["--harness", str(config["harness"])]

    buffs = config.get("buffs")
    if buffs:
        joined = ",".join(str(b) for b in buffs) if isinstance(buffs, (list, tuple)) else str(buffs)
        argv += ["--buffs", joined]

    if config.get("generations"):
        argv += ["--generations", str(int(config["generations"]))]
    if config.get("seed") is not None:
        argv += ["--seed", str(int(config["seed"]))]
    if config.get("parallel_attempts"):
        argv += ["--parallel_attempts", str(int(config["parallel_attempts"]))]

    prefix = config.get("report_prefix") or "garak-studio"
    argv += ["--report_prefix", str(prefix)]

    extra_env["XDG_DATA_HOME"] = str(run_dir)

    if config_file_payload:
        cfg_path = run_dir / "garak_config.json"
        cfg_path.write_text(json.dumps(config_file_payload, indent=2), encoding="utf-8")
        argv += ["--config", str(cfg_path)]

    extra = config.get("extra_args")
    if extra and isinstance(extra, (list, tuple)):
        argv += [str(a) for a in extra]

    return argv, extra_env


def redact_command(argv: list[str]) -> str:
    out = []
    skip_next = False
    for i, tok in enumerate(argv):
        if skip_next:
            out.append("•••")
            skip_next = False
            continue
        low = tok.lower()
        if any(k in low for k in ("key", "token", "secret")) and "=" not in tok:
            out.append(tok)
            skip_next = True
        else:
            out.append(tok)
    return " ".join(out)
