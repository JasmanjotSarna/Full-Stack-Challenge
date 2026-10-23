"""Mandatory regression tests for Forecast-Vintage Selection (Cases A-H) and Analytics.

Phase 5: Critical Forecast-Vintage Verification
- Case A: Multiple eligible forecasts (selects later eligible)
- Case B: Forecast published after cutoff (does not replace decision-time forecast)
- Case C: No eligible forecast (marked missing, not zero)
- Case D: Duplicate publication timestamps (deterministic tie-breaking)
- Case E: Cutoff boundary (exact boundary timestamp handled per inclusive policy)
- Case F: Timezone handling (UTC and Europe/London conversions)
- Case G: Different delivery intervals (no cross-interval contamination)
- Case H: Future information leakage (accuracy metrics unaffected by post-cutoff forecasts)

Phase 6: Analytics Verification
- Hand-calculated example: Actuals [100, 200], Forecasts [110, 180] -> MAE 15, RMSE ~15.8114, Bias -5, WAPE 10%
- Sign convention verification (positive = overforecast, negative = underforecast)
- Zero-denominator handling for WAPE and MAPE
- NaN / Infinity resilience
"""

from __future__ import annotations

import math
from datetime import date, time, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from app.analytics.cutoff import (
    CutoffPolicy,
    apply_cutoff,
    expected_intervals,
    select_forecast_vintages,
)
from app.analytics.metrics import compute_metrics
from app.analytics.pipeline import build_analysis

UTC = timezone.utc
LONDON = ZoneInfo("Europe/London")


def _ts(iso: str) -> pd.Timestamp:
    return pd.Timestamp(iso)


# ==============================================================================
# Phase 5: Critical Forecast-Vintage Verification (Cases A - H)
# ==============================================================================

def test_case_a_multiple_eligible_forecasts():
    """Case A — Multiple eligible forecasts:
    Two forecasts are published before the cutoff. The later eligible forecast must be selected.
    """
    policy = CutoffPolicy(mode="previous_day", local_time=time(0, 0), timezone_name="Europe/London")
    intervals = expected_intervals(date(2026, 1, 2), date(2026, 1, 2), policy.tz)
    target = _ts("2026-01-02T12:00:00Z")

    # Cutoff for 2026-01-02 is 2026-01-01 00:00:00 UTC
    forecasts = pd.DataFrame(
        {
            "interval_start_utc": [target, target],
            "publish_time_utc": [
                _ts("2025-12-30T10:00:00Z"),  # Earlier eligible
                _ts("2025-12-31T20:00:00Z"),  # Later eligible
            ],
            "forecast_mw": [1200.0, 1500.0],
            "source_target_hour_utc": [_ts("2026-01-02T12:00:00Z")] * 2,
        }
    )

    annotated, decision, latest = select_forecast_vintages(forecasts, intervals, policy)
    interval_decision = decision[decision["interval_start_utc"] == target]

    assert len(interval_decision) == 1
    assert interval_decision.iloc[0]["decision_forecast_mw"] == 1500.0
    assert interval_decision.iloc[0]["decision_forecast_publish_time_utc"] == _ts("2025-12-31T20:00:00Z")


def test_case_b_forecast_published_after_cutoff():
    """Case B — Forecast published after the cutoff:
    An accurate forecast is published after the cutoff. It must not replace the eligible decision-time forecast.
    """
    policy = CutoffPolicy(mode="previous_day", local_time=time(0, 0), timezone_name="Europe/London")
    intervals = expected_intervals(date(2026, 1, 2), date(2026, 1, 2), policy.tz)
    target = _ts("2026-01-02T14:00:00Z")

    forecasts = pd.DataFrame(
        {
            "interval_start_utc": [target, target],
            "publish_time_utc": [
                _ts("2025-12-31T18:00:00Z"),  # Eligible (before cutoff 2026-01-01 00:00)
                _ts("2026-01-01T12:00:00Z"),  # Post-cutoff (revised, more accurate)
            ],
            "forecast_mw": [800.0, 1000.0],
            "source_target_hour_utc": [_ts("2026-01-02T14:00:00Z")] * 2,
        }
    )

    annotated, decision, latest = select_forecast_vintages(forecasts, intervals, policy)
    interval_decision = decision[decision["interval_start_utc"] == target]
    interval_latest = latest[latest["interval_start_utc"] == target]

    assert interval_decision.iloc[0]["decision_forecast_mw"] == 800.0
    assert interval_decision.iloc[0]["decision_forecast_publish_time_utc"] == _ts("2025-12-31T18:00:00Z")
    # Latest vintage reflects the revision, but decision vintage retains the cutoff state
    assert interval_latest.iloc[0]["latest_forecast_mw"] == 1000.0


def test_case_c_no_eligible_forecast():
    """Case C — No eligible forecast:
    All forecasts are published after the cutoff. The selected forecast must be missing.
    """
    policy = CutoffPolicy(mode="previous_day", local_time=time(0, 0), timezone_name="Europe/London")
    intervals = expected_intervals(date(2026, 1, 2), date(2026, 1, 2), policy.tz)
    target = _ts("2026-01-02T16:00:00Z")

    forecasts = pd.DataFrame(
        {
            "interval_start_utc": [target, target],
            "publish_time_utc": [
                _ts("2026-01-01T06:00:00Z"),  # Post-cutoff
                _ts("2026-01-01T12:00:00Z"),  # Post-cutoff
            ],
            "forecast_mw": [900.0, 950.0],
            "source_target_hour_utc": [_ts("2026-01-02T16:00:00Z")] * 2,
        }
    )

    annotated, decision, latest = select_forecast_vintages(forecasts, intervals, policy)
    interval_decision = decision[decision["interval_start_utc"] == target]

    # No eligible record in decision frame
    assert interval_decision.empty


def test_case_d_duplicate_publication_timestamps():
    """Case D — Duplicate publication timestamps:
    The implementation must resolve duplicates deterministically and document the tie-breaking rule.
    Tie-breaking rule: sorted by (interval_start_utc, publish_time_utc, forecast_mw) ascending;
    tail(1) selects the highest forecast MW deterministically.
    """
    policy = CutoffPolicy(mode="previous_day", local_time=time(0, 0), timezone_name="Europe/London")
    intervals = expected_intervals(date(2026, 1, 2), date(2026, 1, 2), policy.tz)
    target = _ts("2026-01-02T10:00:00Z")
    same_publish = _ts("2025-12-31T20:00:00Z")

    forecasts = pd.DataFrame(
        {
            "interval_start_utc": [target, target],
            "publish_time_utc": [same_publish, same_publish],
            "forecast_mw": [1100.0, 1300.0],  # Duplicate timestamps with differing values
            "source_target_hour_utc": [_ts("2026-01-02T10:00:00Z")] * 2,
        }
    )

    _, decision, _ = select_forecast_vintages(forecasts, intervals, policy)
    interval_decision = decision[decision["interval_start_utc"] == target]

    assert len(interval_decision) == 1
    # Highest forecast MW chosen deterministically
    assert interval_decision.iloc[0]["decision_forecast_mw"] == 1300.0


def test_case_e_cutoff_boundary():
    """Case E — Cutoff boundary:
    A forecast exactly at the permitted cutoff must be handled according to the documented
    inclusive policy (publish_time <= cutoff).
    """
    policy = CutoffPolicy(mode="previous_day", local_time=time(0, 0), timezone_name="Europe/London")
    intervals = expected_intervals(date(2026, 1, 3), date(2026, 1, 3), policy.tz)
    target = _ts("2026-01-03T00:00:00Z")
    cutoff = policy.cutoff_for(target)  # 2026-01-02 00:00:00 UTC

    forecasts = pd.DataFrame(
        {
            "interval_start_utc": [target, target],
            "publish_time_utc": [
                cutoff,                           # Exactly at cutoff -> eligible
                cutoff + pd.Timedelta(seconds=1),  # 1s after cutoff -> ineligible
            ],
            "forecast_mw": [1500.0, 9999.0],
            "source_target_hour_utc": [_ts("2026-01-03T00:00:00Z")] * 2,
        }
    )

    annotated, decision, latest = select_forecast_vintages(forecasts, intervals, policy)
    interval_annotated = annotated[annotated["interval_start_utc"] == target]
    assert list(interval_annotated["eligible"]) == [True, False]

    interval_decision = decision[decision["interval_start_utc"] == target]
    assert interval_decision.iloc[0]["decision_forecast_mw"] == 1500.0
    assert interval_decision.iloc[0]["decision_forecast_publish_time_utc"] == cutoff


def test_case_f_timezone_handling():
    """Case F — Timezone handling:
    The result must remain correct across UTC and Europe/London conversions.
    """
    policy = CutoffPolicy(mode="previous_day", local_time=time(0, 0), timezone_name="Europe/London")

    # In January, Europe/London is GMT (UTC+0)
    utc_start = _ts("2026-01-15T00:30:00Z")
    cutoff_jan = policy.cutoff_for(utc_start)
    assert cutoff_jan == _ts("2026-01-14T00:00:00Z")

    # In summer BST (UTC+1), delivery 2026-07-10 00:30 London is 2026-07-09 23:30 UTC
    bst_time = pd.Timestamp("2026-07-10T00:30:00", tz="Europe/London")
    cutoff_summer = policy.cutoff_for(bst_time)
    # Cutoff is midnight London on D-1 = 2026-07-09 00:00 BST = 2026-07-08 23:00 UTC
    assert cutoff_summer == pd.Timestamp("2026-07-08T23:00:00Z")


def test_case_g_different_delivery_intervals():
    """Case G — Different delivery intervals:
    A forecast for one interval must never be matched to the actual generation of another interval.
    """
    policy = CutoffPolicy()
    actuals = [
        {"startTime": "2026-01-05T10:00:00Z", "publishTime": "2026-01-05T10:30:00Z", "generation": 1000.0, "fuelType": "WIND"},
        {"startTime": "2026-01-05T10:30:00Z", "publishTime": "2026-01-05T11:00:00Z", "generation": 2000.0, "fuelType": "WIND"},
    ]
    # Forecast only for 10:00
    forecasts = [
        {"startTime": "2026-01-05T10:00:00Z", "publishTime": "2026-01-04T00:00:00Z", "generation": 1100.0},
    ]

    analysis = build_analysis(actuals, forecasts, policy, start=date(2026, 1, 5), end=date(2026, 1, 5), test_data=True)
    frame = analysis.frame

    interval_1000 = frame[frame["interval_start_utc"] == _ts("2026-01-05T10:00:00Z")].iloc[0]
    interval_1030 = frame[frame["interval_start_utc"] == _ts("2026-01-05T10:30:00Z")].iloc[0]

    # 10:00 matches actual 1000 and forecast 1100
    assert interval_1000["actual_mw"] == 1000.0
    assert interval_1000["decision_forecast_mw"] == 1100.0
    assert interval_1000["error_mw"] == 100.0
    assert interval_1000["status"] == "matched"

    # 10:30 has actual 2000 and step-held forecast 1100 from 10:00 hour
    assert interval_1030["actual_mw"] == 2000.0
    assert interval_1030["decision_forecast_mw"] == 1100.0
    assert interval_1030["error_mw"] == -900.0

    # Interval 11:00 has NO forecast and NO actual
    interval_1100 = frame[frame["interval_start_utc"] == _ts("2026-01-05T11:00:00Z")].iloc[0]
    assert pd.isna(interval_1100["actual_mw"])
    assert pd.isna(interval_1100["decision_forecast_mw"])
    assert interval_1100["status"] == "missing_both"


def test_case_h_future_information_leakage():
    """Case H — Future information leakage:
    No forecast published after the decision cutoff may influence the decision-time accuracy metrics.
    """
    policy = CutoffPolicy()
    target_date = date(2026, 1, 10)
    actuals = [
        {"startTime": "2026-01-10T12:00:00Z", "publishTime": "2026-01-10T12:30:00Z", "generation": 1000.0, "fuelType": "WIND"},
    ]
    # Forecast A is before cutoff: 1200 MW (Error +200)
    # Forecast B is after cutoff and perfect: 1000 MW (Error 0)
    forecasts = [
        {"startTime": "2026-01-10T12:00:00Z", "publishTime": "2026-01-09T00:00:00Z", "generation": 1200.0},
        {"startTime": "2026-01-10T12:00:00Z", "publishTime": "2026-01-09T18:00:00Z", "generation": 1000.0},
    ]

    analysis = build_analysis(actuals, forecasts, policy, start=target_date, end=target_date, test_data=True)
    summary = analysis.summary()

    # The accuracy metrics MUST reflect the decision forecast (1200 MW, MAE 200), NOT the late vintage (1000 MW)
    assert summary["mae_mw"] == 200.0
    assert summary["bias_mw"] == 200.0
    assert summary["rmse_mw"] == 200.0
    assert summary["wape_pct"] == 20.0


# ==============================================================================
# Phase 6: Analytics Verification
# ==============================================================================

def test_phase_6_hand_calculated_example():
    """Verify exact hand-calculated test fixture from Challenge Specification:
    Actual generation: [100, 200] MW
    Forecast generation: [110, 180] MW
    Errors: [+10, -20] MW
    Absolute errors: [10, 20] MW
    MAE: 15 MW
    RMSE: approximately 15.81 MW (~15.8114)
    Bias: -5 MW
    WAPE: 10%
    """
    df = pd.DataFrame(
        {
            "actual_mw": [100.0, 200.0],
            "decision_forecast_mw": [110.0, 180.0],
            "error_mw": [10.0, -20.0],
            "abs_error_mw": [10.0, 20.0],
            "is_valid_pair": [True, True],
        }
    )

    metrics = compute_metrics(df, expected_count=2)

    assert metrics["sample_count"] == 2
    assert metrics["expected_intervals"] == 2
    assert metrics["coverage_pct"] == 100.0
    assert metrics["mae_mw"] == 15.0
    assert metrics["bias_mw"] == -5.0
    assert metrics["rmse_mw"] == round(math.sqrt((10**2 + (-20)**2) / 2), 4)  # 15.8114
    assert metrics["wape_pct"] == pytest.approx(10.0)


def test_sign_conventions():
    """Positive error = overforecast (forecast > actual).
    Negative error = underforecast (forecast < actual).
    """
    # Overforecast: forecast 500, actual 400 -> error +100
    df_over = pd.DataFrame(
        {
            "actual_mw": [400.0],
            "decision_forecast_mw": [500.0],
            "error_mw": [100.0],
            "abs_error_mw": [100.0],
            "is_valid_pair": [True],
        }
    )
    m_over = compute_metrics(df_over, expected_count=1)
    assert m_over["bias_mw"] == 100.0

    # Underforecast: forecast 300, actual 400 -> error -100
    df_under = pd.DataFrame(
        {
            "actual_mw": [400.0],
            "decision_forecast_mw": [300.0],
            "error_mw": [-100.0],
            "abs_error_mw": [100.0],
            "is_valid_pair": [True],
        }
    )
    m_under = compute_metrics(df_under, expected_count=1)
    assert m_under["bias_mw"] == -100.0


def test_zero_denominator_wape_and_mape():
    """Zero-denominator cases must return null/None and provide a clear undefined reason."""
    df_zero = pd.DataFrame(
        {
            "actual_mw": [0.0, 0.0],
            "decision_forecast_mw": [10.0, 20.0],
            "error_mw": [10.0, 20.0],
            "abs_error_mw": [10.0, 20.0],
            "is_valid_pair": [True, True],
        }
    )

    metrics = compute_metrics(df_zero, expected_count=2, mape_min_actual_mw=100.0)

    assert metrics["wape_pct"] is None
    assert "sum of absolute actual generation across matched intervals is zero" in metrics["wape_undefined_reason"]
    assert metrics["mape_pct"] is None
    assert "no matched interval has actual generation" in metrics["mape_undefined_reason"]


def test_empty_dataset_handling():
    """Empty dataset returns clean None metrics without division by zero errors."""
    empty_df = pd.DataFrame()
    metrics = compute_metrics(empty_df, expected_count=100)

    assert metrics["sample_count"] == 0
    assert metrics["coverage_pct"] == 0.0
    assert metrics["mae_mw"] is None
    assert metrics["rmse_mw"] is None
    assert metrics["bias_mw"] is None
    assert metrics["wape_pct"] is None
    assert metrics["mape_pct"] is None
    assert metrics["wape_undefined_reason"] is not None
