"""Shared fixtures. All synthetic records are explicitly TEST DATA.

The production dataset is never used by the test suite, and these helpers are
never imported by the application.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.config import Settings
from app.services.analysis_service import AnalysisService, build_test_service

TEST_DAY = date(2026, 1, 2)
MISSING_DAY = date(2026, 1, 3)


def actual_row(
    day: date,
    settlement_period: int,
    generation: float,
    *,
    publish_offset_minutes: int = 120,
    fuel_type: str = "WIND",
) -> dict:
    """A syntactically valid FUELHH row (TEST DATA)."""
    start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc) + timedelta(
        minutes=30 * (settlement_period - 1)
    )
    published = start + timedelta(minutes=publish_offset_minutes)
    return {
        "dataset": "FUELHH",
        "startTime": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "publishTime": published.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generation": generation,
        "fuelType": fuel_type,
        "settlementDate": day.isoformat(),
        "settlementPeriod": settlement_period,
    }


def actual_rows(day: date, value: float = 1000.0) -> list[dict]:
    return [actual_row(day, period, value) for period in range(1, 49)]


def forecast_rows(
    day: date,
    publish_time: str,
    value: float,
    *,
    hours: range | None = None,
) -> list[dict]:
    """Hourly WINDFOR rows for a publication (TEST DATA)."""
    rows = []
    for hour in hours if hours is not None else range(24):
        start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc) + timedelta(
            hours=hour
        )
        rows.append(
            {
                "dataset": "WINDFOR",
                "startTime": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "publishTime": publish_time,
                "generation": value,
            }
        )
    return rows


@pytest.fixture(scope="session")
def leakage_dataset() -> tuple[list[dict], list[dict]]:
    """Actuals = 1,000 MW; eligible forecast = 1,200 MW; post-cutoff = 1,000 MW.

    A naive implementation that looked at the latest (more accurate) vintage
    would report MAE 0. The correct answer is MAE 200 MW.
    """
    actuals = actual_rows(TEST_DAY, 1000.0)
    forecasts = forecast_rows(
        TEST_DAY, "2025-12-31T22:30:00Z", 1200.0
    ) + forecast_rows(TEST_DAY, "2026-01-01T12:00:00Z", 1000.0)
    return actuals, forecasts


@pytest.fixture(scope="session")
def test_settings(tmp_path_factory) -> Settings:
    data_dir = tmp_path_factory.mktemp("windscope-test-data")
    return Settings(environment="test", data_dir=data_dir)


@pytest.fixture()
def test_service(test_settings: Settings) -> AnalysisService:
    actuals = actual_rows(TEST_DAY, 1000.0) + actual_rows(MISSING_DAY, 900.0)
    forecasts = forecast_rows(
        TEST_DAY, "2025-12-31T22:30:00Z", 1200.0
    ) + forecast_rows(TEST_DAY, "2026-01-01T12:00:00Z", 1000.0)
    # Only 00:00 and 01:00 are covered on the missing day -> 44 gaps.
    forecasts += forecast_rows(MISSING_DAY, "2026-01-02T00:00:00Z", 950.0, hours=range(2))
    return build_test_service(actuals, forecasts, settings=test_settings)


@pytest.fixture()
def leakage_service(test_settings: Settings, leakage_dataset) -> AnalysisService:
    actuals, forecasts = leakage_dataset
    return build_test_service(actuals, forecasts, settings=test_settings)
