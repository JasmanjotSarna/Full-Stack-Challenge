# Architecture — WindScope

## Overview
WindScope is a split app: FastAPI backend (analytics + API) and React/Vite frontend (dashboard). Data is precomputed from official Elexon BMRS sources into a validated compressed dataset shipped in-repo.

## Data sources (official)
- **FUELHH** (`https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH`) — half-hourly actual generation by fuel type. Queried with `settlementDateFrom/To`, `fuelType=WIND`. Filtered to national wind for GB.
- **WINDFOR** (`https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR`) — wind forecasts published over time (vintages). Queried with `publishDateTimeFrom/To`.

Constraints observed: date filters capped at 7 days (client uses 6-day windows). No authentication required.

## Scope
- **Period**: 2026-01-01 to 2026-01-31 (inclusive), Europe/London
- **Resolution**: 30-minute settlement periods (native actuals). Hourly forecasts are **step-held to both half-hours** in each hour.
- **Geography**: National wind (GB)

## Decision cutoff policy (analytical, leak-free)
Default: **`previous_day` at `00:00 Europe/London`**.
- For delivery interval on day D, eligible forecasts are those with `publish_time_utc <= cutoff_utc(D-1, 00:00 Europe/London)`.
- Among eligible vintages for the same delivery interval, select the **greatest publish_time** (latest published before cutoff).
- Duplicates (interval, publish time) with conflicting values are excluded; ties broken deterministically by highest forecast MW.
- The cutoff is **labelled as an analytical assumption**, not a verified market gate-closure time. Configurable via env (`CUTOFF_MODE`, `CUTOFF_LOCAL_TIME`, `CUTOFF_LEAD_HOURS`, `FORECAST_TIMEZONE`).
- A unit test ensures a later (more accurate) forecast published after cutoff is **excluded**.

## Pipeline
1. **Fetch** (`app/data/elexon_client.py`): chunked requests, retries with jittered backoff, rate limiting, timeout handling.
2. **Normalize** (`app/data/normalize.py`): parse timestamps to UTC, identify fuel/series, coerce numeric values.
3. **Build analysis** (`app/analytics/pipeline.py`): align to settlement intervals, apply cutoff to select decision-time forecast per interval, compute latest vintage for revision (hindsight-only), compute errors, lead times.
4. **Metrics** (`app/analytics/metrics.py`): MAE, RMSE, bias, WAPE, MAPE (with `MAPE_MIN_ACTUAL_MW` denominator policy), grouping, revision stats.
5. **Store/payload** (`app/analytics/store.py`): serialize to validated payload with schema version, provenance, completeness, validation, warnings; compress as gzip JSON.
6. **Serve** (`app/services/analysis_service.py`): load dataset, filter by date/resolution, compute grouped results on demand. Supports dependency injection for tests.

## API design
- Versioned prefix `/api/v1`
- Consistent error envelope: `{"error":{"code","message","details"}}`
- Endpoints: health, metadata, summary, timeseries, accuracy, errors, forecast-vintages, refresh (protected/disabled)
- Out-of-scope requests → 400. Dataset missing → 503. Validation errors → 422.
- CORS configured; operational headers added (nosniff, X-Frame-Options DENY, Referrer-Policy, X-Process-Time-Ms).

## Frontend
- React 19 + TypeScript + Vite 7, Recharts 3
- Plain CSS design system (light enterprise theme). No icon libraries.
- Views: header/health, policy strip, filters (date range, resolution), KPI grid, forecast chart, error distribution, daily/hourly accuracy, extreme errors, sortable/filterable/paginated aligned table with CSV export, vintage audit modal, quality/methodology panels, footer.
- API client (`services/api.ts`) supports absolute or relative base URL via `VITE_API_BASE_URL`.
- State via hooks (`useDashboardData`, `useMetadata`).

## Deployment topology
- **Dev**: backend on :8000, frontend on :5173 (Vite proxy not required if CORS set; or call directly)
- **Docker compose**: `api` (FastAPI, serves dataset from mounted/copied path) + `web` (nginx serving SPA, proxies `/api/` to `api:8000` on same origin). Web build uses `VITE_API_BASE_URL=""`.
- **Vercel**: static SPA; set `VITE_API_BASE_URL` to backend origin. `vercel.json` rewrites to `index.html`, adds security headers.
- **Heroku**: container deploy via `heroku.yml` building `backend/Dockerfile`; app listens on `$PORT`.

## Testing strategy
- **Backend**: pytest. Unit tests for client/chunking/retries, normalize, cutoff (leakage/DST), metrics (WAPE/MAPE policies, grouping, revision), store, API integration. Test data injected via `create_app(service=build_test_service(...))` — never from production dataset.
- **Frontend**: Vitest + Testing Library. Pure function tests (format/csv/derived) and component tests (KpiGrid).

## Security & data integrity
- No secrets in repo. `.env*` gitignored except `.env.example`.
- Refresh endpoint disabled by default; requires `ALLOW_REFRESH_ENDPOINT=true` + `REFRESH_TOKEN` with HMAC comparison.
- Never fabricate data; missing values preserved as null and excluded from metrics.
- Test data labelled "TEST DATA" and guarded by `ALLOW_TEST_DATA`.
- Only official Elexon datasets used.
- Scope enforced; out of range rejected.
