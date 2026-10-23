# Technical Demo Script (4–5 minutes)

Audience: engineers/reviewers. Focus on correctness, reproducibility, tests, and architecture. (Section duration: ≤ 5 minutes; combined total with customer demo: ≤ 10 minutes).

## Setup
- Backend running on :8000, frontend on :5173 (or use Docker)
- Have terminals ready for pytest/npm test
- Have API docs open at `/docs`

## Script

### 1) Architecture & sources (60s)
- **Show layout**: `backend/` (FastAPI, analytics, client) + `frontend/` (React/Vite) + `data/processed/` (shipped dataset)
- **Sources**: Explain FUELHH (actuals) and WINDFOR (forecasts) from Elexon BMRS v1, no auth, 7-day cap handled by chunking.
- **Scope**: Jan 2026 enforced in config and refresh CLI.

### 2) Cutoff & leak-free selection (90s)
- **Code**: Show `backend/app/analytics/cutoff.py` — `CutoffPolicy` computes cutoff per delivery day, filters eligible by publish time, selects latest eligible per interval.
- **Test**: Point to `backend/tests/test_cutoff.py` — leakage test ensures later forecast excluded.
- **API**: Hit `/api/v1/metadata` and `/api/v1/forecast-vintages?delivery_date=2026-01-02` to show eligibility/selection.
- **Note**: Default `previous_day@00:00 Europe/London` is analytical assumption.

### 3) Metrics & data integrity (60–90s)
- **Metrics**: Show `backend/app/analytics/metrics.py` — MAE/RMSE/bias/WAPE/MAPE with `MAPE_MIN_ACTUAL_MW`, grouping, revision (hindsight-only), lead time.
- **Integrity**: Show `backend/app/data/refresh.py` guards — requires 1488 intervals, ≥50% actual coverage, refuses wrong scope, never overwrites on fetch failure, never fills missing data.
- **Dataset**: Show `data/processed/windscope_january_2026.json.gz` loaded; `is_test_data: false`.

### 4) API surface & error handling (60s)
- **Docs**: Browse `/docs` — versioned routes, schemas, error responses.
- **Smoke test**: Call `GET /api/v1/summary`, `GET /api/v1/timeseries?resolution=1h`, `GET /api/v1/accuracy?group_by=hour`, `GET /api/v1/errors?limit=5`.
- **Errors**: Show 400 for out of scope, 503 for missing dataset, consistent envelope.

### 5) Tests, build, Docker (90–120s)
- **Backend tests**: `cd backend && pytest -q` — show 88 passed.
- **Frontend tests**: `cd frontend && npm run test` — show 27 passed.
- **Frontend build**: `cd frontend && npm run build` — passes (tsc + vite). Chunk warning acceptable.
- **Docker**: Show `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile` + `nginx.conf`. Note same-origin proxy at `/api/`, web build arg `VITE_API_BASE_URL`. Docker daemon not available in this env (documented).
- **Test isolation**: Show `tests/conftest.py` uses `create_app(service=...)` / test fixtures (TEST DATA labelled).

### 6) Deployment prep (30s)
- **Vercel**: `frontend/vercel.json` with SPA rewrites/headers
- **Heroku**: `heroku.yml` builds backend Dockerfile
- **Truthful status**: No deployment performed (missing CLIs/auth/daemon). Documented in README.

## Verification checklist to mention
- [x] Only official Elexon data
- [x] No post-cutoff forecasts used (tested)
- [x] Missing data preserved as null, excluded from metrics
- [x] Cutoff policy explicit and configurable
- [x] Metrics definitions documented
- [x] Tests pass
- [x] Docker assets present
- [x] README with real metrics
- [x] No secrets committed
