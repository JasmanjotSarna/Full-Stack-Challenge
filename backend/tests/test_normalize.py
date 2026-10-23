from __future__ import annotations

import pandas as pd

from app.data.normalize import (
    MAX_PLAUSIBLE_MW,
    expand_to_half_hourly,
    normalize_actuals,
    normalize_forecasts,
)

from .conftest import actual_row, forecast_rows


def test_zero_generation_is_preserved_not_treated_as_missing():
    rows = [actual_row(__import__("datetime").date(2026, 1, 4), 1, 0.0)]
    frame, report = normalize_actuals(rows)
    assert report.accepted == 1
    assert frame.iloc[0]["actual_mw"] == 0.0
    assert pd.notna(frame.iloc[0]["actual_mw"])


def test_non_wind_rows_are_rejected_and_counted():
    from datetime import date

    rows = [
        actual_row(date(2026, 1, 4), 1, 1000.0, fuel_type="WIND"),
        actual_row(date(2026, 1, 4), 2, 500.0, fuel_type="CCGT"),
    ]
    frame, report = normalize_actuals(rows)
    assert report.rejected_fuel_type == 1
    assert report.accepted == 1
    assert frame.iloc[0]["actual_mw"] == 1000.0


def test_malformed_timestamps_and_offgrid_starts_are_rejected():
    from datetime import date

    good = actual_row(date(2026, 1, 4), 1, 1000.0)
    bad_time = {**actual_row(date(2026, 1, 4), 2, 900.0), "startTime": "not-a-date"}
    off_grid = {**actual_row(date(2026, 1, 4), 3, 800.0), "startTime": "2026-01-04T01:15:00Z"}
    nan_value = {**actual_row(date(2026, 1, 4), 4, 700.0), "generation": None}
    frame, report = normalize_actuals([good, bad_time, off_grid, nan_value])
    assert report.rejected_malformed == 3
    assert report.accepted == 1


def test_implausible_and_out_of_scope_are_rejected():
    from datetime import date

    rows = [
        actual_row(date(2026, 1, 4), 1, 1000.0),
        actual_row(date(2026, 1, 4), 2, MAX_PLAUSIBLE_MW + 1),
        actual_row(date(2026, 1, 4), 3, -1.0),
        actual_row(date(2026, 2, 1), 1, 1000.0),
    ]
    frame, report = normalize_actuals(rows)
    assert report.rejected_implausible == 2
    assert report.rejected_out_of_scope == 1
    assert report.accepted == 1


def test_revisions_keep_the_latest_publication():
    from datetime import date

    first = actual_row(date(2026, 1, 4), 1, 1000.0, publish_offset_minutes=60)
    revised = actual_row(date(2026, 1, 4), 1, 1100.0, publish_offset_minutes=180)
    frame, report = normalize_actuals([revised, first])
    assert report.accepted == 1
    assert report.revisions_collapsed == 1
    assert frame.iloc[0]["actual_mw"] == 1100.0


def test_conflicting_actuals_at_same_publish_time_are_dropped():
    from datetime import date

    left = actual_row(date(2026, 1, 4), 1, 1000.0)
    right = {**left, "generation": 1001.0}
    frame, report = normalize_actuals([left, right])
    assert report.conflicts_dropped == 1
    assert report.accepted == 0
    assert frame.empty


def test_forecast_normalization_retains_all_vintages():
    from datetime import date

    day = date(2026, 1, 4)
    rows = forecast_rows(day, "2026-01-01T00:00:00Z", 1000.0, hours=range(2))
    rows += forecast_rows(day, "2026-01-02T00:00:00Z", 1100.0, hours=range(2))
    frame, report = normalize_forecasts(rows)
    assert report.accepted == 4
    assert frame["publish_time_utc"].nunique() == 2
    assert frame["target_hour_utc"].nunique() == 2


def test_forecast_non_hourly_target_is_rejected():
    from datetime import date

    row = forecast_rows(date(2026, 1, 4), "2026-01-01T00:00:00Z", 1000.0, hours=range(1))[0]
    row["startTime"] = "2026-01-04T00:30:00Z"
    _, report = normalize_forecasts([row])
    assert report.rejected_malformed == 1


def test_forecast_conflicting_vintages_are_dropped():
    from datetime import date

    row = forecast_rows(date(2026, 1, 4), "2026-01-01T00:00:00Z", 1000.0, hours=range(1))[0]
    conflicting = {**row, "generation": 1200.0}
    frame, report = normalize_forecasts([row, conflicting])
    assert report.conflicts_dropped == 1
    assert frame.empty


def test_hourly_forecast_is_step_held_onto_both_half_hours():
    from datetime import date

    rows = forecast_rows(date(2026, 1, 4), "2026-01-01T00:00:00Z", 1234.0, hours=range(2))
    forecasts, _ = normalize_forecasts(rows)
    expanded = expand_to_half_hourly(forecasts)
    assert len(expanded) == 4
    hour_zero = expanded[expanded["interval_start_utc"] == pd.Timestamp("2026-01-04T00:30:00Z")]
    assert hour_zero.iloc[0]["forecast_mw"] == 1234.0
    assert hour_zero.iloc[0]["source_target_hour_utc"] == pd.Timestamp("2026-01-04T00:00:00Z")


def test_missing_required_columns_raise():
    import pytest

    with pytest.raises(ValueError, match="missing required columns"):
        normalize_actuals([{"startTime": "2026-01-01T00:00:00Z"}])
    with pytest.raises(ValueError, match="missing required columns"):
        normalize_forecasts([{"startTime": "2026-01-01T00:00:00Z"}])
