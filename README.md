# WindScope — UK Wind Forecast Intelligence

WindScope is a production-minded MVP for the REint Full Stack SWE Challenge v4. It analyses **January 2026 national GB wind generation**: comparing Elexon actuals against day-ahead forecast vintages using a configurable, **labelled analytical decision cutoff** (default: latest forecast published on/before **00:00 Europe/London on D-1**). The app is **forecast-accuracy analysis only** — not demand forecasting, procurement volumes, or trading/pricing.

## Live / deployment status (truthful)

- **Git repo**: To be initialized locally (this folder is inside another git repo; a fresh `git init` is required).
- **Deployed URL**: **Not deployed.** No GitHub CLI, Heroku CLI, authenticated Vercel session, or running Docker daemon were available in this environment. Exact manual steps are provided below; no URL has been claimed or verified.

## What it shows (real metrics for Jan 2026)

From the validated shipped dataset (`data/processed/windscope_january_2026.json.gz`):
- **Period**: 2026-01-01 to 2026-01-31, **Europe/London**, **30m resolution**
- **Matched intervals**: 1,364 / 1,488 (expected) — **coverage 91.6667%**
- **Missing forecasts**: 124; **missing actuals**: 0 (no null actuals). Intervals with missing forecasts/actuals are **preserved as null and excluded** from accuracy metrics (never filled).
- **MAE**: 2,218.7977 MW | **RMSE**: 2,690.3571 MW | **Bias**: +1,890.6246 MW (overforecast)  
- **WAPE**: 19.2113% | **MAPE**: 23.6431% (MAPE uses denominator policy: excludes actuals < 100 MW; here 1,364 included / 0 excluded)
- **Lead time (decision-time forecast)**: min 25.5h, median 36.25h, max 47.0h  
- **Forecast alignment**: WINDFOR is hourly; values are **step-held to both half-hours** (`hourly_step_hold_to_half_hour`). Actuals are native half-hourly.

> Sign convention: `error_MW = decision-time forecast - actual`. Positive = overforecast.

## Repository layout

```
.
├── backend/                # FastAPI app, analytics, Elexon client, tests
│   ├── app/
│   │   ├── analytics/      # cutoff, metrics, pipeline, store, resample
│   │   ├── api/routes.py   # versioned API (/api/v1/*)
│   │   ├── core/           # config, logging
│   │   ├── data/           # elexon_client, normalize, refresh CLI
│   │   ├── models/         # Pydantic schemas
│   │   └── services/       # analysis service (test injection supported)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── tests/              # 88 tests (client/chunking, cutoff/leakage, metrics, store, API, cases A–H)
├── frontend/               # React + TypeScript + Vite + Recharts
│   ├── src/
│   │   ├── components/     # dashboard panels, chart, table, modal
│   │   ├── hooks/          # data fetching hooks
│   │   ├── services/api.ts # API client (supports relative/VITE_API_BASE_URL)
│   │   ├── styles/         # design system (plain CSS)
│   │   ├── test/           # 27 Vitest tests
│   │   └── utils/          # format/csv/derived
│   ├── Dockerfile          # multi-stage build + nginx
│   ├── nginx.conf          # serves SPA, proxies /api to backend
│   ├── vercel.json
│   └── package.json
├── data/
│   ├── processed/          # validated extract windscope_january_2026.json.gz (kept)
│   └── raw/                # gitignored except .gitkeep
├── docs/                   # architecture, demo scripts, submission checklist
├── docker-compose.yml      # api + web (web proxies /api via nginx)
├── heroku.yml              # Heroku Container Registry/Docker deploy (builds backend)
├── .env.example
└── .gitignore
```

## Quickstart (local dev)

### Prerequisites
- Python 3.11+ (tested with 3.12)
- Node.js 20+ (tested with 22)
- Git

### 1) Backend
From repo root:
```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
# source .venv/bin/activate
pip install -r requirements.txt
# Run API (dataset is pre-shipped; loads from data/processed or /app/data/processed)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
API docs: http://127.0.0.1:8000/docs | Root: http://127.0.0.1:8000/

### 2) Frontend
In another terminal:
```bash
cd frontend
npm ci
# Point to local API (default) or set VITE_API_BASE_URL
npm run dev
```
App: http://127.0.0.1:5173

To build:
```bash
npm run build  # tsc --noEmit && vite build
npm run preview
```
Tests: `npm run test` (Vitest: 27 passed). Backend: `cd backend && pytest -q` (88 passed).

## Configuration

Copy `.env.example` to configure. Key settings (see `backend/app/core/config.py`):
- **Scope (enforced)**: Jan 1–31 2026, Europe/London
- **Cutoff**: `CUTOFF_MODE` (`previous_day` default), `CUTOFF_LOCAL_TIME` (`00:00`), `FORECAST_TIMEZONE` (`Europe/London`), `CUTOFF_LEAD_HOURS` (24). This is an **analytical assumption** and is surfaced in UI/metadata.
- **Elexon**: public BMRS API, no auth. Client chunks by ≤6 days, retries with backoff, rate-limited.
- **Metrics**: `MAPE_MIN_ACTUAL_MW` (100). MAPE denominator policy is documented in API/UI.
- **CORS**: `CORS_ORIGINS`
- **Refresh**: `ALLOW_REFRESH_ENDPOINT=false`, `REFRESH_TOKEN=` by default (disabled). Use CLI refresh.

Frontend base URL: `VITE_API_BASE_URL` (Vite env). Empty/relative works with same-origin proxying (Docker/nginx). See `frontend/src/services/api.ts`.

## API (versioned `/api/v1`)
- `GET /health` — service + dataset readiness
- `GET /metadata` — provenance, cutoff policy, completeness, assumptions (never uses post-cutoff forecasts)
- `GET /summary` — KPIs + data quality + cutoff policy + lead time + revision (revision is hindsight-only)
- `GET /timeseries` — aligned actual/decision-time/latest forecasts + errors; `resolution` 30m|1h
- `GET /accuracy` — grouped metrics by `day|week|hour|lead_time`
- `GET /errors` — largest misses with sorting
- `GET /forecast-vintages` — audit trail per delivery interval/date with cutoff eligibility
- `POST /refresh` — **disabled by default** (503 with guidance). Rebuild via CLI.

All responses use consistent error shape. Out of scope dates return 400.

## Data provenance & rebuild

**Shipped dataset**: `data/processed/windscope_january_2026.json.gz` contains validated Jan 2026 FUELHH (actuals) + WINDFOR (forecasts), built with the default cutoff policy. It is treated as production data for this MVP (labelled `is_test_data: false`).

**Rebuild from Elexon (CLI):**
```bash
cd backend
# Ensure env configured (or use defaults)
python -m app.data.refresh                # writes to configured dataset path
# or
python -m app.data.refresh --dry-run
```
Notes from implementation:
- Fetches FUELHH for `2026-01-01..2026-01-31` and WINDFOR from publish window (lookback 4d / lookahead 2d around scope)
- Enforces scope to Jan 2026 only (refuses other ranges)
- Requires expected intervals == 1488; requires actual coverage ≥ 50% (safety checks)
- Never overwrites last-known-good on fetch failures; never fills missing data from later vintages
- Cuts off forecasts using configured policy (leak-free selection)
- Writes compressed JSON with schema version, provenance, validation, completeness, warnings

## Docker (local)

From repo root:
```bash
docker compose up --build
```
- API: http://localhost:8000
- Web (nginx): http://localhost:8080 (proxies `/api` to API; same-origin)

Build context: `docker-compose.yml` uses `.` for API (copies `backend/` + `data/processed/`) and `./frontend` for web. Docker daemon was **not available** in this environment so images were not built here.

## Deployment (manual, no credentials available)

**Vercel (frontend only recommended):**
- Framework: Vite (`frontend/vercel.json` present)
- Build: `npm run build` from `frontend/`, output `dist`
- Set env var `VITE_API_BASE_URL` to your hosted backend URL (e.g. `https://your-api.example.com`). With empty value, frontend uses relative `/api` (only works behind same-origin proxy).
- SPA rewrites and security headers configured.

**Heroku (backend via Container Registry):**
- `heroku.yml` builds `backend/Dockerfile` with repo root context; `CMD` respects `$PORT`.
- Ensure dataset is present in the image or mounted. The shipped Dockerfile copies `data/processed/windscope_january_2026.json.gz` into the image.
- Set config vars (CORS, cutoff policy) as needed; do **not** enable refresh endpoint in prod without a strong token.

**No deployment performed** in this session (missing CLIs/auth/daemon). See `docs/submission-checklist.md` for verification steps.

## Testing

- **Backend**: `cd backend && pytest -q` — **88 passed**. Covers Elexon client (retries/chunking), normalization, cutoff/DST/leakage, metrics (MAE/RMSE/bias/MAPE/WAPE, grouping, revision, lead), store/payload, API routes (incl. leak test: later forecast excluded), and full regression test suite (Cases A through H, hand-calculated test fixture, zero-denominators, 1h resolution). TEST DATA fixtures injected via `create_app(service=...)`/`build_test_service`.
- **Frontend**: `cd frontend && npm run test` — **27 passed**. Covers formatting, CSV export, derived calculations, KpiGrid rendering.

## AI Tools Used

In accordance with the REint Full Stack SWE Challenge requirements:
- **Model / Assistant**: Google DeepMind Antigravity AI assistant (Gemini 3.8 Flash model).
- **Assistance Scope**:
  - Code audit, inspection, and defect identification (including discovery of hourly resolution runtime errors in `resample.py`/`metrics.py` and unhandled `None` state in `_service`).
  - Development of regression tests for Phase 5 forecast-vintage eligibility (Cases A through H: multiple eligible forecasts, post-cutoff arrival, absent forecasts, deterministic tie-breaking, cutoff boundary inclusiveness, timezone conversions, interval isolation, future information leakage).
  - Implementation of hand-calculated test fixtures and formula verification for MAE, RMSE, Bias, and WAPE with zero-denominator handling.
  - Verification of Docker Compose, Heroku, and Vercel configurations and documentation.
- **Human Oversight**: All calculations, Elexon schema rules, cutoff policies, and statistical formulae were independently reviewed and verified against the challenge specification and live Elexon BMRS endpoint contracts.

## Security & notes
- No secrets committed (`.env` gitignored). Refresh endpoint disabled by default; token auth + HMAC compare when enabled.
- Test data is never mixed with production; guard in place (`ALLOW_TEST_DATA`).
- Only official Elexon datasets used (FUELHH actuals, WINDFOR forecasts). No fabricated data.
- Analysis is forecast-accuracy only; clearly labeled throughout UI and docs.
- PowerShell may display unicode mojibake in some consoles, but API/data are UTF-8 correct.
