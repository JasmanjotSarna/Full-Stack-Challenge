"""Elexon BMRS dataset identifiers and source documentation."""

from __future__ import annotations

SOURCES = {
    "actual": {
        "dataset": "FUELHH",
        "name": "Elexon BMRS — Half-hourly fuel type generation (FUELHH)",
        "url": "https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream",
        "endpoint": "/datasets/FUELHH",
        "description": (
            "Half-hourly actual generation by fuel type, filtered to fuelType=WIND. "
            "National-level GB transmission-metered wind generation."
        ),
        "fields": {
            "startTime": "Target half-hour delivery period start (UTC).",
            "publishTime": "Time at which the observed value was published (UTC).",
            "generation": "Actual wind generation in MW.",
            "fuelType": "Filtered to WIND.",
            "settlementDate": "GB settlement date supplied by the source.",
            "settlementPeriod": "Settlement period 1–48 (50 on autumn DST days).",
        },
    },
    "forecast": {
        "dataset": "WINDFOR",
        "name": "Elexon BMRS — Wind generation forecast (WINDFOR)",
        "url": "https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream",
        "endpoint": "/datasets/WINDFOR",
        "description": (
            "National wind generation forecast runs. Each publication covers a rolling "
            "three-day hourly horizon. Historic runs are retrieved by publication time."
        ),
        "fields": {
            "startTime": "Forecast target hour (UTC, hourly resolution).",
            "publishTime": "Time at which the forecast run was published (UTC).",
            "generation": "Forecast wind generation in MW.",
        },
    },
}

FORECAST_ALIGNMENT_NOTE = (
    "WINDFOR is published at hourly resolution. Each hourly value is applied to both "
    "half-hour settlement periods that begin in that hour (step-hold, no interpolation). "
    "This alignment assumption is recorded on every row; actual generation remains native "
    "half-hourly data."
)

SCOPE_NOTE = (
    "Analysis is restricted to GB national wind delivery periods from 2026-01-01 through "
    "2026-01-31 inclusive, interpreted in Europe/London. Requests outside this scope are "
    "rejected; no other month or year is substituted."
)
