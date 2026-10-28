<div align="center">

# Garak Studio

### A web UI and orchestration layer for the garak LLM vulnerability scanner.

**Configure a scan, watch it run live, and turn raw garak reports into scores, diffs and triage queues.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61dafb?style=flat-square&logo=react&logoColor=black)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-Tailwind-646cff?style=flat-square&logo=vite&logoColor=white)](https://vitejs.dev/)
[![garak](https://img.shields.io/badge/scanner-garak-76b900?style=flat-square)](https://github.com/NVIDIA/garak)
[![Docker](https://img.shields.io/badge/Docker-compose-2496ed?style=flat-square&logo=docker&logoColor=white)](#quick-start)
[![Apache 2.0 license](https://img.shields.io/badge/license-Apache_2.0-d22128?style=flat-square)](LICENSE)

[Features](#features) · [Quick start](#quick-start) · [Usage](#usage) · [Configuration](#configuration) · [Architecture](#architecture) · [Security notes](#security-notes) · [License](#license)

</div>

<br />

Garak Studio drives [garak](https://github.com/NVIDIA/garak) as a subprocess, streams the run live, and indexes the resulting JSONL report into a queryable database for scoring, diffing and triage.

Plugin lists are never hardcoded: the backend introspects the *installed* garak at runtime, so custom or newly released probes appear in the UI with no code change.

## Features

- **Scan builder** with a cost estimate and scan-profile support in the API.
- **Live runs** streamed over WebSocket, with progress, per-probe status and cancel.
- **Report indexing** into pass rates with confidence bounds, an attack-surface score and an OWASP risk matrix.
- **Timeline** of every event, live and indexed, searchable, sortable and exportable as NDJSON.
- **Run comparison** with a per-probe pass-rate delta and a significance flag.
- **Hit triage** with status, notes and assignee.
- **Report import and export:** bring in reports produced elsewhere, download the native HTML or JSONL, or export SARIF.
- **Encrypted secrets** for API keys, stored with Fernet and never returned in plain text.
- **Live model discovery** for Ollama, OpenAI and generic OpenAI-compatible endpoints.

## Quick start

You need Python 3.11+ with **garak importable in the same interpreter** (`pip install garak`; on Windows use `pip install --prefer-binary garak`) and Node 18+. Introspection imports garak as a library, so a garak in a different venv will not be discovered.

Backend, from the repo root:

```bash
pip install -r requirements.txt
python run.py                 # http://localhost:8000, SQLite auto-created in data/
```

Frontend, from `web/`:

```bash
npm install
npm run dev                   # http://localhost:5173
```

Full stack (backend, frontend, Postgres and Redis):

```bash
GARAK_STUDIO_SECRET_KEY=<long-random-string> docker compose up --build
```

## Usage

Smoke test with no credentials: open **New Scan**, choose generator `test`, model name `Blank` and probe `dan.DanInTheWild`, then start the run.

| Screen | What it does |
|---|---|
| **Dashboard** | Overview of scan activity and target robustness. |
| **New Scan** | Configure and launch a run: generator, model, probes, detectors, buffs and a cost estimate. |
| **Runs** | Run history. Each run opens a live view, a monitor with the timeline, and a full report. |
| **Compare** | Per-probe pass-rate delta between two runs, flagged when significant. |
| **Triage** | Review and classify hits like an issue tracker: new, confirmed, false positive or accepted risk. |
| **Plugins** | Probes, detectors, generators, harnesses and buffs found in the installed garak. |
| **Settings** | Credentials, report imports, and the garak availability and version. |

The interactive API docs are at <http://localhost:8000/docs>.

## Configuration

Environment variables use the prefix `GARAK_STUDIO_` (see `.env.example`).

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | SQLite in `data/` | Or `postgresql+asyncpg://…` |
| `DATA_DIR` | `./data` | Run artifacts and SQLite file |
| `GARAK_COMMAND` | `python -m garak` | Override how garak is launched (venv/conda) |
| `SECRET_KEY` | generated `.secret.key` | Master key for secret encryption |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama daemon for discovery and REST targets |
| `CORS_ORIGINS` | localhost:5173 | Allowed browser origins |
| `TIMELINE_POLL_INTERVAL` | `0.75` | Seconds between live report tails |

Set `GARAK_STUDIO_SECRET_KEY` in any deployment you care about: without it the Fernet key is generated into `.secret.key` at the repo root, and losing that file makes stored API keys undecryptable.

## Architecture

```
app/                     FastAPI + SQLAlchemy (async) + WebSocket
├─ introspection/        garak plugin enumeration (service.py) and
│                        live model discovery per backend (discovery.py)
├─ orchestrator/         command.py  → scan config  → garak argv + env
│                        runner.py   → subprocess, stdout stream, cancel, finalize
├─ parsers/              report.py         → eval rows + hits from *.report.jsonl
│                        timeline.py       → per-event timeline model + live tailer
│                        timeline_store.py → timeline index/query (DB or file)
│                        indexer.py        → post-run persistence + score
├─ api/                  REST routers (see table below)
├─ ws/gateway.py         in-process pub/sub broker → /ws/runs/{id}
├─ models/               ORM: runs, probe_results, hits, run_events, secrets, …
└─ core/                 settings, async engine/session, Fernet secret storage
run.py                   uvicorn entrypoint (port 8000)
web/                     React 18 + Vite + Tailwind SPA (port 5173, proxies /api, /ws)
data/                    SQLite db + per-run artifact directories
```

garak's native JSONL/HTML output stays the **source of truth**. The database only holds derived, indexed values so screens load without re-reading multi-GB reports.

### Execution flow

1. **Build.** `POST /api/scans` persists a `Run` (status `queued`) with the scan config and schedules `runner.start_run` as an asyncio task.
2. **Launch.** `build_invocation()` translates the config into `python -m garak` argv. Generator options are written to a per-run `garak_config.json` passed via `--config`; Ollama targets are mapped onto garak's `rest` generator against `/api/generate`. `XDG_DATA_HOME` is pinned to `data/runs/<run_id>/` so every artifact garak writes lands in that run's directory. Stored secrets are decrypted into the child environment only.
3. **Stream.** The process runs with `stdout`/`stderr` merged and line-tailed. Each line is appended to `console.jsonl`, scanned for the current probe and a `NN%` progress token, and published to the broker. In parallel a poller tails the growing `*.report.jsonl` and emits structured timeline events. Everything fans out over `/ws/runs/{run_id}` to the Live and Monitor screens.
4. **Cancel.** `POST /api/runs/{id}/cancel` signals the whole process group (`SIGTERM` → `SIGKILL`, `CTRL_BREAK` on Windows), never the API process.
5. **Index.** On exit 0, `indexer.index_run` parses the report into `probe_results` (totals, pass rate, CI bounds, probe tags) and `hits` (score ≥ 0.5, capped at 5000, with prompt/output/turns), computes the attack-surface score, then `timeline_store.index_timeline` writes the full event index. Run status becomes `completed`.
6. **Consume.** Report, risk matrix, timeline, run-to-run diff, triage and SARIF export.

Reports produced elsewhere can enter the same pipeline via `POST /api/reports/import` (steps 5 and 6 only).

### API surface

| Prefix | Purpose |
|---|---|
| `/api/plugins/{category}` | Introspected probes, detectors, generators, harnesses, buffs (+ `/summary`, `/refresh`) |
| `/api/discovery/models` | Live model listing for ollama / openai / generic OpenAI-compatible endpoints |
| `/api/scans` | Create run, cost estimate, scan-profile CRUD |
| `/api/runs/{id}` | Run detail, probe results, cancel, OWASP risk matrix |
| `/api/runs/{id}/timeline` | Paged/filtered/sorted events, event detail, rebuild, NDJSON export, meta |
| `/api/reports/{id}` | Hits (search/filter), native HTML, JSONL download, SARIF export, import |
| `/api/compare?a=&b=` | Per-probe pass-rate delta with significance flag (CI overlap, else ≥10pp) |
| `/api/triage` | Hit status/notes/assignee, queue, stats |
| `/api/settings` | garak availability/version, encrypted secret CRUD |
| `/ws/runs/{id}` | Live `status` / `log` / `probe` / `timeline` frames |

## Security notes

- **Secrets** are encrypted at rest (Fernet) and returned to the frontend only as a masked hint; plaintext exists solely in the garak child process environment.
- **Model output is hostile by construction.** Probes such as `xss` deliberately elicit injection payloads, so the UI renders every prompt and output as plain text, never as HTML.
- **Isolation.** garak runs in its own process group; cancelling kills that tree only.
- **No authentication.** The API is unauthenticated and the ORM carries roles that are not yet enforced. Do not expose this on an untrusted network, and scan only systems you are authorized to test.

## Status

Implemented end to end: plugin introspection, scan builder with cost estimate, live streaming runs with cancel, report parsing and indexing, attack-surface score, OWASP risk matrix, timeline, run diffing with significance flags, hit triage, report import, SARIF export and encrypted secrets.

Modelled but not wired to the UI: scheduling (`schedules`), RBAC enforcement (`users.role`) and audit-log surfacing.

## Contributing

Issues and pull requests are welcome. Keep each change focused on a single behavior.

## License

Released under the [Apache License 2.0](LICENSE), with third-party notices in [NOTICE](NOTICE). Free to use, modify, distribute and sell, commercially or otherwise, with attribution and an express patent grant.

Not affiliated with or endorsed by NVIDIA Corporation or the garak maintainers; those names identify the upstream software this project interoperates with.
