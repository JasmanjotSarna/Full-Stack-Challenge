"""Optional hourly aggregation of the aligned half-hourly analysis frame."""

from __future__ import annotations

import numpy as np
import pandas as pd

RESOLUTIONS = {"30m": "30m", "1h": "1h"}


def aggregate_resolution(frame: pd.DataFrame, resolution: str) -> pd.DataFrame:
    """Aggregate the 30-minute aligned frame to hourly rows when requested.

    Rule: values are means of available half-hours inside the hour; error is
    forecast mean minus actual mean for half-hours where both values exist.
    An hour counts as matched when at least one half-hour pair is valid.
    Missing half-hours are never treated as zero.
    """
    if resolution == "30m":
        return frame.copy()
    if resolution != "1h":
        raise ValueError(f"Unsupported resolution: {resolution!r}")
    if frame.empty:
        return frame.copy()

    working = frame.copy()
    working["_hour_start"] = working["interval_start_utc"].dt.floor("h")
    rows: list[dict] = []
    for hour, group in working.groupby("_hour_start", sort=True):
        valid = group[group["is_valid_pair"] == True]  # noqa: E712
        actuals = group["actual_mw"].dropna()
        forecasts = group["decision_forecast_mw"].dropna()
        latest = group["latest_forecast_mw"].dropna()

        if len(valid):
            error = float(valid["decision_forecast_mw"].mean() - valid["actual_mw"].mean())
            status = "matched"
        else:
            error = np.nan
            has_actual = bool(actuals.size)
            has_forecast = bool(forecasts.size)
            status = (
                "missing_actual"
                if has_forecast and not has_actual
                else "missing_forecast"
                if has_actual and not has_forecast
                else "missing_both"
            )

        first = group.iloc[0]
        rows.append(
            {
                "interval_start_utc": hour,
                "interval_start_local": hour.tz_convert("Europe/London").isoformat(),
                "local_start": hour.tz_convert("Europe/London").isoformat(),
                "delivery_date_local": first["delivery_date_local"],
                "settlement_period": int(first["settlement_period"]),
                "actual_mw": float(actuals.mean()) if actuals.size else np.nan,
                "decision_forecast_mw": float(forecasts.mean()) if forecasts.size else np.nan,
                "decision_forecast_publish_time_utc": group[
                    "decision_forecast_publish_time_utc"
                ].dropna().max(),
                "decision_forecast_lead_hours": float(valid["decision_forecast_lead_hours"].mean())
                if len(valid)
                else np.nan,
                "latest_forecast_mw": float(latest.mean()) if latest.size else np.nan,
                "latest_forecast_publish_time_utc": group[
                    "latest_forecast_publish_time_utc"
                ].dropna().max(),
                "latest_forecast_lead_hours": group["latest_forecast_lead_hours"].dropna().mean()
                if group["latest_forecast_lead_hours"].notna().any()
                else np.nan,
                "status": status,
                "is_valid_pair": status == "matched",
                "error_mw": error,
                "abs_error_mw": abs(error) if not np.isnan(error) else np.nan,
                "squared_error_mw2": error**2 if not np.isnan(error) else np.nan,
                "forecast_alignment": first["forecast_alignment"],
                "decision_forecast_is_latest": bool(
                    group["decision_forecast_publish_time_utc"].dropna().nunique() <= 1
                    and group["latest_forecast_publish_time_utc"].dropna().nunique() <= 1
                    and group["decision_forecast_is_latest"].all()
                ),
                "aggregated_half_hours": int(len(group)),
                "valid_half_hours": int(len(valid)),
            }
        )
    result = pd.DataFrame(rows)
    result["interval_start_utc"] = pd.to_datetime(result["interval_start_utc"], utc=True)
    return result
