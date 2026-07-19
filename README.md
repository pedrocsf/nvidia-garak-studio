# Garak Studio

A full web UI and orchestration layer for [garak](https://github.com/NVIDIA/garak),
NVIDIA's LLM vulnerability scanner. Garak Studio exposes garak's complete surface
(all probes, detectors, generators, harnesses, and buffs) through a
lab-console-styled interface, and adds capabilities no community tool offers
today: dynamic plugin introspection, OWASP LLM Top 10 risk mapping, an
attack-surface score with history, run-to-run diffing, multi-turn conversation
replay, and an issue-tracker-style triage workflow.

> **Design principle:** the UI never hardcodes plugin lists. It introspects the
> *installed* garak at runtime, so new probes (including your own custom ones)
> appear automatically without any code change here.

## Architecture

```
app/       FastAPI backend + SQLAlchemy (SQLite default) + WebSocket streaming
           ├─ introspection/  dynamic garak plugin + model discovery
           ├─ orchestrator/   garak subprocess launch + live streaming + cancel
           ├─ parsers/        streaming JSONL report parser + DB indexer
           └─ api/            REST routers
run.py     backend entrypoint (repo root)
web/       React + Vite + Tailwind frontend (NVIDIA-minimalist theme)
data/      run artifacts (garak's native JSONL / hit log / HTML) + SQLite db
```

The raw garak JSONL/HTML remain the **source of truth**; the backend parses and
indexes derived metrics into the database so screens load fast without
re-reading multi-GB reports.

## Prerequisites

- **Python 3.11** with **garak** installed in the same interpreter:
  ```
  pip install garak
  ```
  (Introspection imports garak as a library. On Windows, prefer
  `pip install --prefer-binary garak` to avoid source builds.)
- **Node 18+**

## Quick start (single-user, local)

**Backend** (from the repo root):
```
pip install -r requirements.txt
python run.py
```
Serves the API at http://localhost:8000 (SQLite auto-created under `data/`).

**Frontend** (from `web/`):
```
npm install
npm run dev
```
Opens http://localhost:5173, proxying `/api` and `/ws` to the backend.

Open the app, go to **New Scan**, pick the `test` generator with model name
`Blank` and probe `dan.DanInTheWild` for a credential-free smoke run.

## Full stack (team / production)

```
docker compose up --build
```
Brings up backend + frontend + Postgres + Redis. Set `GARAK_STUDIO_SECRET_KEY`
to a strong value so stored API keys are encrypted with a stable master key.

## Configuration

All settings are environment variables prefixed `GARAK_STUDIO_` (see
`.env.example`). Notable ones:

| Variable | Purpose |
|---|---|
| `GARAK_STUDIO_DATABASE_URL` | SQLite (default) or `postgresql+asyncpg://…` |
| `GARAK_STUDIO_GARAK_COMMAND` | Override how garak is launched (venv/conda) |
| `GARAK_STUDIO_SECRET_KEY` | Master key for encrypting stored secrets |

## Security notes

- **Secrets** (API keys) are encrypted at rest (Fernet) and never returned to
  the frontend after saving — only a masked hint.
- **Model output is sensitive.** garak's `xss` probe deliberately elicits XSS
  payloads, so the UI renders all prompts/outputs as plain text (never as HTML),
  and the native garak HTML report is served for viewing in a sandboxed context
  only.
- **Execution isolation:** garak runs in a separate OS process; cancelling kills
  only that process tree, never the API.

## Status vs. the roadmap

Implemented end-to-end: dynamic introspection, scan builder, live streaming
runs with cancel, native report parsing/indexing, attack-surface score, OWASP
risk matrix, run diffing with statistical-significance flags, hit triage,
external report import, SARIF export, encrypted secrets. Multi-turn replay
renders whenever a probe emits conversation turns. Scheduling, RBAC enforcement,
and the sandboxed custom-plugin editor are scaffolded in the data model but not
yet wired to UI.
