from __future__ import annotations

import math

import numpy as np
import pandas as pd

from app.analytics.metrics import (
    classify_status,
    compute_metrics,
    data_quality_counts,
    grouped_accuracy,
    largest_errors,
    revision_summary,
    summarise_lead_time,
)


def frame(errors: list[float | None], actuals: list[float | None]) -> pd.DataFrame:
    data = pd.DataFrame(
        {
            "actual_mw": pd.to_numeric(pd.Series(actuals), errors="coerce"),
            "error_mw": pd.to_numeric(pd.Series(errors), errors="coerce"),
        }
    )
    data["decision_forecast_mw"] = data["actual_mw"] + data["error_mw"]
    data["abs_error_mw"] = data["error_mw"].abs()
    data["is_valid_pair"] = data["error_mw"].notna() & data["actual_mw"].notna()
    data["delivery_date_local"] = "2026-01-02"
    data["local_start"] = [
        pd.Timestamp("2026-01-02T00:00:00Z") + pd.Timedelta(minutes=30 * index)
        for index in range(len(data))
    ]
    data["interval_start_utc"] = data["local_start"]
    data["settlement_period"] = range(1, len(data) + 1)
    data["decision_forecast_lead_hours"] = 25.5
    data["decision_forecast_publish_time_utc"] = pd.Timestamp("2025-12-31T22:30:00Z")
    data["latest_forecast_mw"] = data["decision_forecast_mw"] + 10
    data["latest_forecast_publish_time_utc"] = pd.Timestamp("2026-01-01T12:00:00Z")
    data["status"] = classify_status(data)
    return data


def test_known_metric_values():
    data = frame([100.0, -50.0, 200.0], [1000.0, 500.0, 2000.0])
    metrics = compute_metrics(data, expected_count=3)
    assert metrics["sample_count"] == 3
    assert metrics["mae_mw"] == 116.6667
    assert metrics["rmse_mw"] == round(math.sqrt((100**2 + 50**2 + 200**2) / 3), 4)
    assert metrics["bias_mw"] == 83.3333
    assert metrics["wape_pct"] == 10.0
    assert metrics["mape_pct"] is not None
    assert metrics["coverage_pct"] == 100.0


def test_bias_sign_convention_positive_is_overforecast():
    data = frame([250.0], [1000.0])
    assert compute_metrics(data, expected_count=1)["bias_mw"] == 250.0


def test_mape_excludes_near_zero_actuals_and_reports_counts():
    data = frame([10.0, 100.0], [50.0, 1000.0])
    metrics = compute_metrics(data, expected_count=2, mape_min_actual_mw=100.0)
    assert metrics["mape_sample_count"] == 1
    assert metrics["mape_excluded_count"] == 1
    assert metrics["mape_pct"] == 10.0
    assert metrics["mae_mw"] == 55.0


def test_mape_undefined_when_all_denominators_are_small():
    data = frame([10.0], [50.0])
    metrics = compute_metrics(data, expected_count=1, mape_min_actual_mw=100.0)
    assert metrics["mape_pct"] is None
    assert "no matched interval" in metrics["mape_undefined_reason"]


def test_no_valid_pairs_returns_nulls_not_zero():
    data = frame([None], [None])
    metrics = compute_metrics(data, expected_count=1)
    assert metrics["sample_count"] == 0
    assert metrics["mae_mw"] is None
    assert metrics["rmse_mw"] is None
    assert metrics["bias_mw"] is None
    assert metrics["wape_pct"] is None
    assert metrics["coverage_pct"] == 0.0


def test_wape_undefined_when_total_actual_is_zero():
    data = frame([0.0], [0.0])
    metrics = compute_metrics(data, expected_count=1)
    assert metrics["wape_pct"] is None
    assert "zero" in metrics["wape_undefined_reason"]


def test_missing_forecast_status_and_counts():
    data = frame([None, 100.0, None], [1000.0, 1000.0, None])
    data.loc[2, "decision_forecast_mw"] = 1200.0
    data["status"] = classify_status(data)
    counts = data_quality_counts(data)
    assert counts["matched_intervals"] == 1
    assert counts["missing_forecast_intervals"] == 1
    assert counts["missing_actual_intervals"] == 1
    assert counts["valid_pairs"] == 1


def test_grouped_accuracy_by_day_and_hour():
    data = frame([100.0, -100.0, 50.0, -50.0], [1000.0] * 4)
    data.loc[2:, "delivery_date_local"] = "2026-01-03"
    daily = grouped_accuracy(data, "day")
    assert [row["group"] for row in daily] == ["2026-01-02", "2026-01-03"]
    assert daily[0]["mae_mw"] == 100.0
    hourly = grouped_accuracy(data, "hour")
    assert hourly[0]["group"] == "0"
    assert hourly[0]["label"] == "00:00–00:59"


def test_largest_errors_ordering_and_limit():
    data = frame([100.0, -300.0, 200.0, -50.0], [1000.0] * 4)
    absolute = largest_errors(data, sort="absolute_error", limit=2)
    assert [row["abs_error_mw"] for row in absolute] == [300.0, 200.0]
    under = largest_errors(data, sort="underforecast", limit=1)
    assert under[0]["error_mw"] == -300.0
    assert under[0]["direction"] == "underforecast"
    over = largest_errors(data, sort="overforecast", limit=1)
    assert over[0]["error_mw"] == 200.0
    assert over[0]["direction"] == "overforecast"


def test_revision_summary_uses_latest_minus_decision():
    data = frame([100.0, 100.0], [1000.0, 1000.0])
    data["latest_forecast_mw"] = [900.0, 1200.0]
    summary = revision_summary(data)
    assert summary["sample_count"] == 2
    assert summary["mean_signed_revision_mw"] == -50.0
    assert summary["mean_abs_revision_mw"] == 150.0
    assert summary["max_abs_revision_mw"] == 200.0


def test_lead_time_summary_ignores_nulls():
    data = frame([100.0, 100.0], [1000.0, 1000.0])
    data["decision_forecast_lead_hours"] = [24.0, np.nan]
    summary = summarise_lead_time(data)
    assert summary["sample_count"] == 1
    assert summary["median_hours"] == 24.0
