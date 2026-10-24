# RecoverChain

Revenue-recovery decisioning system. Failed payments, overdue invoices and
abandoned checkouts arrive as events, are correlated into **cases**, and each case
is driven through a fixed lifecycle:

```
ingest → risk assessment → root-cause diagnosis → recovery prediction →
next-best action + expected recoverable value → policy / safety gate →
specialist agent execution (sandbox) → outcome verification → audit
```

A second subsystem, the **Dataset Lab**, ingests arbitrary CSV/Parquet/XLSX data,
semantically maps columns to canonical fields, checks ML readiness (leakage,
minimum-information contract), trains **shadow-only** models, and can replay
dataset rows through the case pipeline.

**Safety invariants (do not break):**
- ML output is advisory **shadow-only**; the deterministic **Policy Engine** is the
  sole authority for whether an action executes.
- Execution is **simulated** (`MockExecutionAdapter`) — no live payment/comms APIs.
- Post-outcome ("leakage") columns are detected and excluded from ML features.

See [docs/PROJECT_REPORT.md](docs/PROJECT_REPORT.md) for the architecture map and
[docs/history/](docs/history/) for the design notes kept per iteration.

---

## Prerequisites

- Python 3.12+ (the repo currently runs on 3.14)
- Node.js 18+ (frontend)
- Docker (optional — for PostgreSQL + Redis; SQLite is the default otherwise)

## Backend — setup & run

```bash
cd backend
python -m venv venv
venv\Scripts\activate                # Windows  (source venv/bin/activate on POSIX)
pip install -r requirements.txt      # runtime;  -r requirements-core.txt for a lean install
pip install -r requirements-dev.txt  # + ruff / mypy / pytest-cov / pip-audit (for CI parity)
copy .env.example .env               # then edit
```

Environment (`.env` or shell):

| Var | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/recoverchain` | use `sqlite:///./dev.db` for local |
| `REDIS_URL` | `redis://localhost:6379/0` | only used by `/health` today |
| `API_KEY` | `test-api-key` | required header `X-API-Key` on mutating routes; dev default logs a startup warning |
| `CORS_ORIGINS` | `*` | explicit allow-list in prod (`*` disables credentialed CORS) |
| `RATE_LIMIT_ENABLED` / `RATE_LIMIT_RPM` | `1` / `120` | per-key/-IP request limit |
| `MAX_UPLOAD_BYTES` | `536870912` | dataset upload cap (512 MiB) |
| `GEMINI_API_KEY` | _(unset)_ | only for the optional real-LLM evaluation mode |

Full list and prod notes: [backend/.env.example](backend/.env.example). The
frontend reads `VITE_API_KEY` at build time (see `frontend/.env.example`).

Run the API (from `backend/`, with `PYTHONPATH=.`):

```bash
set PYTHONPATH=.
set DATABASE_URL=sqlite:///./dev.db
uvicorn api.main:app --reload          # http://localhost:8000/docs
```

Database schema:

- **SQLite dev/test** — tables auto-create on startup.
- **PostgreSQL (or any non-SQLite)** — schema is owned by Alembic:
  ```bash
  set PYTHONPATH=.
  alembic upgrade head
  ```

## Frontend — setup & run

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173  (proxies /api -> 127.0.0.1:8000)
npm run build      # tsc + vite production build
```

## Full stack

```bash
python run.py       # starts backend :8000 + frontend :5173 (forces SQLite)
```

## Tests

```bash
cd backend
set PYTHONPATH=.
pytest                    # full suite, 216 tests (isolated throwaway SQLite DB)
pytest -m fast            # fast unit tests only
pytest -m integration     # DB / API / adapter tests
pytest tests/test_policy.py::test_name -q   # single test
pytest --cov             # coverage report (CI gate: 80%)

ruff check . && ruff format --check .        # backend lint + format
```

Frontend checks: `npm run lint`, `npm run format:check`, `npm run build` (tsc).

The test suite forces its own database (`_pytest_recoverchain.db`, created fresh
and dropped per session) — override with `RECOVERCHAIN_TEST_DATABASE_URL`.

## Containers

```bash
cp .env.example .env         # set POSTGRES_PASSWORD, API_KEY, CORS_ORIGINS (compose requires them)
docker-compose up --build    # postgres :5432 + redis :6379 + api :8000 + web :5173
```

`postgres` + `redis` alone:

```bash
docker-compose up -d postgres redis
```

## Key endpoints

| Method | Path | Notes |
|---|---|---|
| `POST` | `/events` / `/events/batch` | ingest one / many; `auto_advance` runs the pipeline |
| `POST` | `/cases/{id}/advance` | run assess→diagnose→predict→recommend→policy |
| `POST` | `/cases/{id}/{assess-risk,diagnose,predict-recovery,recommend-action,policy-check,execute,verify}` | individual stages |
| `POST` | `/cases/{id}/stop` | halt automated recovery (STOPPED) |
| `GET` | `/cases`, `/cases/{id}`, `/dashboard/metrics` | dashboard reads |
| `GET` | `/system/*` | read-only observability (cases, models, executions, audit, policy) |
| `GET` | `/datasets`, `/datasets/{id}`, `/datasets/{id}/{preview,workflow-status}` | Dataset Lab reads (open) |
| `POST` | `/datasets/{upload,…/analyze,…/ml-readiness,…/train,…/mapping,…/generate-cases}` | Dataset Lab writes (auth) |

Mutating routes — cases **and** datasets — require header `X-API-Key`
(`API_KEY` env, dev default `test-api-key`). Requests are rate limited per key/IP.

## Repository layout

| Path | Purpose |
|---|---|
| `backend/domain/` | Framework-free Pydantic models, `CaseState`, lifecycle, interfaces |
| `backend/application/` | Stage engines (risk, diagnosis, prediction, action, policy, agents, verification), Dataset Lab, ML training |
| `backend/infrastructure/` | SQLAlchemy ORM, repositories, DB/Redis clients |
| `backend/api/` | FastAPI routers: `main.py` (case pipeline), `dataset_router.py`, `system_router.py` |
| `backend/alembic/` | Migrations |
| `backend/evaluation/` | Deterministic scenario harness + curated dataset metadata |
| `frontend/src/` | React 18 + Vite + react-router SPA |
| `docs/history/` | Phase-by-phase architecture notes |
