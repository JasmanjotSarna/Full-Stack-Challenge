# Customer Demo Script (4–5 minutes)

Audience: product/forecasting stakeholders. Focus on business value and trust. (Section duration: ≤ 5 minutes; combined total with technical demo: ≤ 10 minutes).

## Setup
- Ensure backend running at `http://127.0.0.1:8000` with shipped dataset loaded.
- Ensure frontend running at `http://127.0.0.1:5173` (or built/served).
- Have browser open to the app.

## Script

### 1) Context & scope (30s)
- **Point to header**: "WindScope — UK Wind Forecast Intelligence. Forecast-accuracy analysis only."
- **Policy strip**: Call out the cutoff policy — "latest forecast published on or before 00:00 Europe/London on D-1 (analytical assumption, not a market gate)." Note it's configurable and visible.
- **Scope**: National GB wind, Jan 1–31 2026, Europe/London.

### 2) Headline accuracy (60–90s)
- **KPI grid**: Walk through MAE/RMSE/bias/WAPE/MAPE, sample count, coverage.
- **Key message**: "Bias is +1,890 MW (overforecast on average). WAPE ~19.2%, MAPE ~23.6% with a stated denominator policy (excludes actuals <100 MW)."
- **Coverage**: "91.67% matched; 124 intervals missing forecasts (never filled). 0 missing actuals."

### 3) When/where misses happen (90s)
- **Forecast vs actual chart**: Show aligned series; note hourly forecasts are step-held to half-hours.
- **Error distribution**: Discuss spread (over/underforecast).
- **Daily accuracy**: Identify days with higher error.
- **Hourly profile**: Show diurnal pattern of error/accuracy.
- **Extreme errors**: Review largest under/overforecasts with timestamps.

### 4) Auditability & trust (90–120s)
- **Aligned data table**: Pick an interval, show actual/decision-time/latest forecast, error, lead time. Export CSV to show exactly what's displayed.
- **Vintage audit modal**: Click "Inspect vintages" on a row. Show all published vintages, which ones are **eligible at cutoff**, which one was **selected** (latest eligible), and publish times. Emphasize "no post-cutoff data used".
- **Quality panel**: Point to completeness, missing counts, provenance (Elexon FUELHH/WINDFOR).
- **Methodology panel**: Read key points: alignment (hourly→half-hour step-hold), cutoff policy, leak-free selection, MAPE/WAPE definitions, sign convention, revision is hindsight-only.

### 5) Close (15–30s)
- **Reiterate**: "This is forecast-accuracy intelligence only — not demand/procurement/trading. All assumptions are explicit and test-covered."

## Notes
- If API is slow/unavailable, show the error state with retry.
- Don't speculate on market rules; stick to "analytical assumption".
- All numbers should match the shipped dataset.
