from datetime import date, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from app.analytics.cutoff import (
    CutoffPolicy,
    apply_cutoff,
    expected_intervals,
    select_forecast_vintages,
)

UTC = timezone.utc


def ts(value: str) -> pd.Timestamp:
    return pd.Timestamp(value)


def test_default_cutoff_is_local_midnight_previous_day():
    policy = CutoffPolicy()
    cutoff = policy.cutoff_for(ts("2026-01-15T12:00:00Z"))
    assert cutoff == ts("2026-01-14T00:00:00Z")
    assert policy.identifier == "previous_day@00:00[Europe/London]"
    assert policy.as_dict()["is_analytical_assumption"] is True


def test_cutoff_uses_local_calendar_day_not_utc_day():
    policy = CutoffPolicy()
    # 00:30 local on 15 Jan is still 00:30 UTC in winter; cutoff is 14 Jan 00:00.
    assert policy.cutoff_for(ts("2026-01-15T00:30:00Z")) == ts("2026-01-14T00:00:00Z")


def test_cutoff_handles_dst_start_2026():
    policy = CutoffPolicy()
    # Delivery begins at local midnight on Sunday 29 March (GMT, 00:00Z).
    assert policy.cutoff_for(ts("2026-03-29T00:00:00Z")) == ts("2026-03-28T00:00:00Z")
    # Monday 30 March starts at local midnight BST = 23:00Z on the 29th.
    assert policy.cutoff_for(ts("2026-03-29T23:00:00Z")) == ts("2026-03-29T00:00:00Z")


def test_cutoff_handles_dst_end_2026():
    policy = CutoffPolicy()
    # 25 Oct local midnight is BST -> 23:00Z on 24 Oct.
    assert policy.cutoff_for(ts("2026-10-24T23:00:00Z")) == ts("2026-10-23T23:00:00Z")


def test_dst_days_have_46_and_50_periods():
    tz = ZoneInfo("Europe/London")
    spring = expected_intervals(date(2026, 3, 29), date(2026, 3, 29), tz)
    autumn = expected_intervals(date(2026, 10, 25), date(2026, 10, 25), tz)
    assert len(spring) == 46
    assert len(autumn) == 50


def test_january_has_1488_expected_intervals():
    frame = expected_intervals(date(2026, 1, 1), date(2026, 1, 31), ZoneInfo("Europe/London"))
    assert len(frame) == 1488
    assert frame["settlement_period"].max() == 48
    assert frame["interval_start_utc"].dt.tz is not None


def test_cutoff_is_inclusive_at_the_boundary():
    policy = CutoffPolicy()
    intervals = expected_intervals(date(2026, 1, 2), date(2026, 1, 2), policy.tz)
    forecasts = pd.DataFrame(
        {
            "interval_start_utc": [ts("2026-01-02T00:00:00Z")] * 3,
            "publish_time_utc": [
                ts("2026-01-01T00:00:00Z"),  # exactly at cutoff
                ts("2026-01-01T00:00:01Z"),  # one second late
                ts("2025-12-31T23:00:00Z"),
            ],
            "forecast_mw": [1000.0, 9999.0, 900.0],
            "source_target_hour_utc": [ts("2026-01-02T00:00:00Z")] * 3,
        }
    )

    annotated, decision, latest = select_forecast_vintages(forecasts, intervals, policy)

    assert list(annotated["eligible"]) == [True, False, True]
    # Latest eligible is the boundary record, not the post-cutoff record.
    assert decision.iloc[0]["decision_forecast_mw"] == 1000.0
    assert decision.iloc[0]["decision_forecast_publish_time_utc"] == ts(
        "2026-01-01T00:00:00Z"
    )
    assert latest.iloc[0]["latest_forecast_mw"] == 9999.0


def test_only_the_latest_eligible_vintage_is_selected():
    policy = CutoffPolicy()
    intervals = expected_intervals(date(2026, 1, 2), date(2026, 1, 2), policy.tz)
    forecasts = pd.DataFrame(
        {
            "interval_start_utc": [ts("2026-01-02T00:00:00Z")] * 3,
            "publish_time_utc": [
                ts("2025-12-30T22:30:00Z"),
                ts("2025-12-31T12:00:00Z"),
                ts("2025-12-31T22:30:00Z"),
            ],
            "forecast_mw": [500.0, 700.0, 900.0],
            "source_target_hour_utc": [ts("2026-01-02T00:00:00Z")] * 3,
        }
    )
    _, decision, _ = select_forecast_vintages(forecasts, intervals, policy)
    assert decision.iloc[0]["decision_forecast_mw"] == 900.0
    assert decision.iloc[0]["decision_forecast_lead_hours"] == pytest.approx(25.5)


def test_lead_hours_mode_uses_interval_relative_boundary():
    policy = CutoffPolicy(mode="lead_hours", lead_hours=30)
    start = ts("2026-01-10T12:00:00Z")
    assert policy.cutoff_for(start) == start - pd.Timedelta(hours=30)
    assert policy.identifier == "lead_hours=30[absolute]"
    assert "analytical assumption" in policy.describe()


def test_apply_cutoff_with_empty_forecasts_keeps_schema():
    policy = CutoffPolicy()
    intervals = expected_intervals(date(2026, 1, 2), date(2026, 1, 2), policy.tz)
    empty = pd.DataFrame(
        {
            "interval_start_utc": pd.Series(dtype="datetime64[ns, UTC]"),
            "forecast_mw": pd.Series(dtype="float64"),
            "publish_time_utc": pd.Series(dtype="datetime64[ns, UTC]"),
            "source_target_hour_utc": pd.Series(dtype="datetime64[ns, UTC]"),
        }
    )
    annotated = apply_cutoff(empty, intervals, policy)
    assert annotated.empty
    assert "eligible" in annotated.columns


def test_unsupported_mode_is_rejected():
    with pytest.raises(ValueError):
        CutoffPolicy(mode="market_gate")


def test_negative_lead_hours_is_rejected():
    with pytest.raises(ValueError):
        CutoffPolicy(mode="lead_hours", lead_hours=-1)


def test_time_of_day_policy_is_configurable():
    policy = CutoffPolicy(local_time=time(12, 0))
    cutoff = policy.cutoff_for(ts("2026-01-15T18:00:00Z"))
    assert cutoff == ts("2026-01-14T12:00:00Z")
    assert policy.identifier == "previous_day@12:00[Europe/London]"


def test_cutoff_for_naive_timestamp_is_treated_as_utc():
    policy = CutoffPolicy()
    assert policy.cutoff_for(pd.Timestamp("2026-01-02 00:00:00")) == ts("2026-01-01T00:00:00Z")


def test_expected_intervals_rejects_reversed_range():
    with pytest.raises(ValueError):
        expected_intervals(date(2026, 1, 2), date(2026, 1, 1), ZoneInfo("Europe/London"))


def test_expected_intervals_are_half_hourly():
    frame = expected_intervals(date(2026, 1, 5), date(2026, 1, 5), ZoneInfo("Europe/London"))
    gaps = frame["interval_start_utc"].diff().dropna().unique()
    assert list(gaps) == [pd.Timedelta(minutes=30)]
    assert frame["settlement_period"].tolist() == list(range(1, 49))
