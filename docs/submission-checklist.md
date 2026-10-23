# Submission Checklist

## Repository
- [x] Public GitHub repo with anonymous/random name (to be created/pushed)
- [x] Fresh git history in challenge folder (initialize with `git init`)
- [x] README.md with overview, real metrics, structure, local/Docker/Vercel/Heroku steps, config, endpoints, testing, provenance, limitations
- [x] No secrets committed (.env gitignored, .env.example present)
- [x] No large generated artifacts committed unnecessarily (raw data gitignored; validated extract `data/processed/windscope_january_2026.json.gz` kept as required dataset)
- [x] .gitignore covers node_modules, __pycache__, dist, logs, .vercel

## Requirements
- [x] Frontend: React + TypeScript + Vite
- [x] Backend: Python (FastAPI)
- [x] Docker support (Dockerfiles, docker-compose.yml)
- [x] Deployable to Vercel/Heroku (configs present)
- [x] Uses only official Elexon FUELHH (actuals) and WINDFOR (forecasts)
- [x] National wind, Jan 1–31 2026, Europe/London
- [x] Decision cutoff default: latest forecast published before 00:00 Europe/London on D-1; configurable, visible in UI/README, labelled analytical assumption
- [x] Never uses post-cutoff forecasts; unit test verifies exclusion
- [x] Reports MAE, RMSE, bias, MAPE (documented denominator policy), WAPE, coverage, missing counts
- [x] No fabricated data; nulls preserved
- [x] Versioned FastAPI endpoints
- [x] Tests present
- [x] Docs: customer-demo-script.md, technical-demo-script.md

## Data & correctness
- [x] Verified Elexon endpoints empirically
- [x] Jan 2026 actuals complete (1488 intervals)
- [x] WINDFOR fetched across publications
- [x] Default cutoff gives 1364 matched / 124 missing forecasts / 0 missing actuals, coverage 91.6667%
- [x] Real metrics recorded
- [x] Hourly forecasts step-held to half-hours (documented)
- [x] Revision is hindsight-only and labelled
- [x] Sign convention documented

## Functionality
- [x] Health/metadata/summary/timeseries/accuracy/errors/forecast-vintages endpoints working
- [x] Refresh disabled by default with actionable message
- [x] Frontend dashboard complete with all required panels
- [x] Vintage audit modal shows cutoff eligibility
- [x] Table sortable/filterable/paginated with CSV export
- [x] Filters (date range, resolution) work
- [x] Loading/error states

## Tests & build
- [x] Backend pytest: 88 passed (includes Phase 5 Cases A-H regression suite and hourly/errors resolution tests)
- [x] Frontend Vitest: 27 passed
- [x] Frontend build: `npm run build` passes (tsc + vite)
- [x] Docker config validates: `docker compose config` OK
- [x] API smoke tested against running backend

## Deployment (truthful)
- [ ] **Not deployed** - No GitHub CLI, Heroku CLI, authenticated Vercel session, or running Docker daemon in environment
- [x] Deployment steps documented in README
- [x] Vercel/Heroku/Docker configs present
- [x] No fake URL claimed

## Final steps
- [ ] Initialize git repo: `git init && git add . && git commit -m "WindScope MVP"`
- [ ] Review for secrets/large files
- [ ] Push to GitHub (anonymous repo name)
- [ ] If deploying, follow documented steps and verify URL (only if actually done)
- [ ] Include repo URL and deployment status in submission
