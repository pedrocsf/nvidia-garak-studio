# Garak Studio

Web UI and orchestration layer for [garak](https://github.com/NVIDIA/garak), the
LLM vulnerability scanner. It drives garak as a subprocess, streams the run live,
and indexes the resulting JSONL report into a queryable database for scoring,
diffing and triage.

Plugin lists are never hardcoded: the backend introspects the *installed* garak at
runtime, so custom or newly released probes appear in the UI with no code change.

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

garak's native JSONL/HTML output stays the **source of truth**. The database only
holds derived, indexed values so screens load without re-reading multi-GB reports.

## Execution flow

1. **Build** — `POST /api/scans` persists a `Run` (status `queued`) with the scan
   config and schedules `runner.start_run` as an asyncio task.
2. **Launch** — `build_invocation()` translates the config into `python -m garak`
   argv. Generator options are written to a per-run `garak_config.json` passed via
   `--config`; Ollama targets are mapped onto garak's `rest` generator against
   `/api/generate`. `XDG_DATA_HOME` is pinned to `data/runs/<run_id>/` so every
   artifact garak writes lands in that run's directory. Stored secrets are
   decrypted into the child environment only.
3. **Stream** — the process runs with `stdout`/`stderr` merged and line-tailed.
   Each line is appended to `console.jsonl`, scanned for the current probe and a
   `NN%` progress token, and published to the broker. In parallel a poller tails
   the growing `*.report.jsonl` and emits structured timeline events. Everything
   fans out over `/ws/runs/{run_id}` to the Live and Monitor screens.
4. **Cancel** — `POST /api/runs/{id}/cancel` signals the whole process group
   (`SIGTERM` → `SIGKILL`, `CTRL_BREAK` on Windows), never the API process.
5. **Index** — on exit 0, `indexer.index_run` parses the report into
   `probe_results` (totals, pass rate, CI bounds, probe tags) and `hits`
   (score ≥ 0.5, capped at 5000, with prompt/output/turns), computes the
   attack-surface score, then `timeline_store.index_timeline` writes the full
   event index. Run status becomes `completed`.
6. **Consume** — report, risk matrix, timeline, run-to-run diff, triage, SARIF
   export.

Reports produced elsewhere can enter the same pipeline via
`POST /api/reports/import` (steps 5–6 only).

## API surface

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

Interactive docs: <http://localhost:8000/docs>.

## Requirements

- Python 3.11+ with **garak importable in the same interpreter** (`pip install garak`;
  on Windows use `pip install --prefer-binary garak`). Introspection imports garak as
  a library, so a garak in a different venv will not be discovered.
- Node 18+.

## Quick start

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

Smoke test with no credentials: **New Scan** → generator `test`, model name
`Blank`, probe `dan.DanInTheWild`.

Full stack (backend + frontend + Postgres + Redis):

```bash
GARAK_STUDIO_SECRET_KEY=<long-random-string> docker compose up --build
```

## Configuration

Environment variables, prefix `GARAK_STUDIO_` (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | SQLite in `data/` | Or `postgresql+asyncpg://…` |
| `DATA_DIR` | `./data` | Run artifacts and SQLite file |
| `GARAK_COMMAND` | `python -m garak` | Override how garak is launched (venv/conda) |
| `SECRET_KEY` | generated `.secret.key` | Master key for secret encryption |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama daemon for discovery and REST targets |
| `CORS_ORIGINS` | localhost:5173 | Allowed browser origins |
| `TIMELINE_POLL_INTERVAL` | `0.75` | Seconds between live report tails |

Set `GARAK_STUDIO_SECRET_KEY` in any deployment you care about: without it the
Fernet key is generated into `.secret.key` at the repo root, and losing that file
makes stored API keys undecryptable.

## Security notes

- **Secrets** are encrypted at rest (Fernet) and returned to the frontend only as
  a masked hint; plaintext exists solely in the garak child process environment.
- **Model output is hostile by construction.** Probes such as `xss` deliberately
  elicit injection payloads, so the UI renders every prompt and output as plain
  text, never as HTML.
- **Isolation.** garak runs in its own process group; cancelling kills that tree
  only.
- **No authentication.** The API is unauthenticated and the ORM carries roles that
  are not yet enforced — do not expose this on an untrusted network. Scan only
  systems you are authorised to test.

## Status

Implemented end-to-end: plugin introspection, scan builder with cost estimate,
live streaming runs with cancel, report parsing/indexing, attack-surface score,
OWASP risk matrix, timeline (live + indexed, searchable, exportable), run diffing
with significance flags, hit triage, report import, SARIF export, encrypted
secrets.

Modelled but not wired to the UI: scheduling (`schedules`), RBAC enforcement
(`users.role`), audit-log surfacing.

## License

Apache License 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE). Free to use,
modify, distribute and sell, commercially or otherwise, with attribution and an
express patent grant.

Not affiliated with or endorsed by NVIDIA Corporation or the garak maintainers;
those names identify the upstream software this project interoperates with.
