"""End-to-end analytics pipeline: normalize -> align -> select -> measure.

No actual generation value is passed into vintage selection. Selection happens
strictly on publication time, which makes accuracy-based leakage impossible by
construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone

import pandas as pd

from ..core.config import SCOPE_END, SCOPE_START
from ..data.normalize import (
    NormalizationReport,
    expand_to_half_hourly,
    normalize_actuals,
    normalize_forecasts,
)
from .cutoff import CutoffPolicy, expected_intervals, select_forecast_vintages
from .metrics import classify_status, compute_metrics, data_quality_counts

FORECAST_ALIGNMENT = "hourly_step_hold_to_half_hour"


@dataclass
class AnalysisResult:
    frame: pd.DataFrame
    annotated_forecasts: pd.DataFrame
    expected: pd.DataFrame
    actuals: pd.DataFrame
    forecasts: pd.DataFrame
    policy: CutoffPolicy
    actual_report: NormalizationReport
    forecast_report: NormalizationReport
    warnings: list[str] = field(default_factory=list)
    generated_at: str | None = None
    fetched_at: str | None = None
    mape_min_actual_mw: float = 100.0
    test_data: bool = False

    @property
    def expected_count(self) -> int:
        return int(len(self.frame))

    @property
    def valid(self) -> pd.DataFrame:
        return self.frame[self.frame["is_valid_pair"] == True]  # noqa: E712

    def summary(self) -> dict[str, object]:
        counts = data_quality_counts(self.frame)
        metrics = compute_metrics(
            self.frame,
            expected_count=self.expected_count,
            mape_min_actual_mw=self.mape_min_actual_mw,
        )
        return {**metrics, **counts, "forecast_alignment": FORECAST_ALIGNMENT}

    def slice(self, start: date, end: date) -> pd.DataFrame:
        dates = pd.to_datetime(self.frame["delivery_date_local"]).dt.date
        return self.frame[(dates >= start) & (dates <= end)].copy()


def build_analysis(
    actual_rows: list[dict],
    forecast_rows: list[dict],
    policy: CutoffPolicy,
    *,
    start: date = SCOPE_START,
    end: date = SCOPE_END,
    mape_min_actual_mw: float = 100.0,
    generated_at: str | None = None,
    fetched_at: str | None = None,
    test_data: bool = False,
    dataset_warnings: list[str] | None = None,
) -> AnalysisResult:
    expected = expected_intervals(start, end, policy.tz)
    actuals, actual_report = normalize_actuals(actual_rows)
    forecasts, forecast_report = normalize_forecasts(forecast_rows)

    expanded = expand_to_half_hourly(forecasts)
    # Keep only forecast points that align with an in-scope expected interval.
    expanded = expanded[
        expanded["interval_start_utc"].isin(expected["interval_start_utc"])
    ].reset_index(drop=True)

    annotated, decision, latest = select_forecast_vintages(expanded, expected, policy)

    frame = expected.merge(
        actuals[
            [
                "interval_start_utc",
                "actual_mw",
                "actual_publish_time_utc",
            ]
        ],
        on="interval_start_utc",
        how="left",
    )
    frame = frame.merge(
        decision[
            [
                "interval_start_utc",
                "decision_forecast_mw",
                "decision_forecast_publish_time_utc",
                "decision_forecast_lead_hours",
                "decision_forecast_source_target_hour_utc",
            ]
        ],
        on="interval_start_utc",
        how="left",
    )
    frame = frame.merge(
        latest[
            [
                "interval_start_utc",
                "latest_forecast_mw",
                "latest_forecast_publish_time_utc",
                "latest_forecast_lead_hours",
            ]
        ],
        on="interval_start_utc",
        how="left",
    )

    for column in (
        "actual_mw",
        "decision_forecast_mw",
        "latest_forecast_mw",
        "decision_forecast_lead_hours",
        "latest_forecast_lead_hours",
    ):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame["status"] = classify_status(frame)
    frame["is_valid_pair"] = (frame["status"] == "matched") & frame["actual_mw"].notna() & frame[
        "decision_forecast_mw"
    ].notna()
    valid = frame["is_valid_pair"]
    frame["error_mw"] = (frame["decision_forecast_mw"] - frame["actual_mw"]).where(valid)
    frame["abs_error_mw"] = frame["error_mw"].abs()
    frame["squared_error_mw2"] = frame["error_mw"] ** 2
    frame["forecast_alignment"] = FORECAST_ALIGNMENT
    frame["decision_forecast_is_latest"] = (
        frame["decision_forecast_publish_time_utc"]
        == frame["latest_forecast_publish_time_utc"]
    )
    frame = frame.sort_values("interval_start_utc").reset_index(drop=True)

    counts = data_quality_counts(frame)
    warnings: list[str] = list(dataset_warnings or [])
    warnings.extend(actual_report.warnings)
    warnings.extend(forecast_report.warnings)
    if counts["missing_forecast_intervals"]:
        warnings.append(
            f"{counts['missing_forecast_intervals']} delivery interval(s) have no forecast "
            "published on or before the decision cutoff. They are reported as missing and were "
            "not back-filled with later vintages."
        )
    if counts["missing_actual_intervals"]:
        warnings.append(
            f"{counts['missing_actual_intervals']} delivery interval(s) have no observed actual "
            "generation. They are excluded from accuracy metrics."
        )
    if counts["missing_both_intervals"]:
        warnings.append(
            f"{counts['missing_both_intervals']} delivery interval(s) have neither an eligible "
            "forecast nor an actual."
        )
    if counts["matched_intervals"] == 0:
        warnings.append(
            "No delivery interval has both a valid actual and a valid decision-time forecast. "
            "Accuracy metrics are undefined."
        )

    # Stable, unique warnings.
    warnings = list(dict.fromkeys(warnings))

    return AnalysisResult(
        frame=frame,
        annotated_forecasts=annotated,
        expected=expected,
        actuals=actuals,
        forecasts=forecasts,
        policy=policy,
        actual_report=actual_report,
        forecast_report=forecast_report,
        warnings=warnings,
        generated_at=generated_at,
        fetched_at=fetched_at,
        mape_min_actual_mw=mape_min_actual_mw,
        test_data=test_data,
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
