"""Forecast accuracy metrics with explicit missing-data and denominator handling.

Sign convention: error = forecast - actual.
Positive error = overforecast (expected wind exceeded observed wind).
Negative error = underforecast (observed wind exceeded the forecast).
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

LEAD_BINS = [-np.inf, 12, 24, 36, 48, 60, np.inf]
LEAD_LABELS = ["≤12h", "12–24h", "24–36h", "36–48h", "48–60h", ">60h"]


def _maybe(value: float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return None
    return round(float(value), 4)


def compute_metrics(
    frame: pd.DataFrame,
    *,
    expected_count: int,
    mape_min_actual_mw: float = 100.0,
) -> dict[str, object]:
    """Compute metrics from a matched frame.

    ``frame`` must contain error_mw, abs_error_mw and actual_mw for every interval
    (valid pairs and missing rows). Only valid pairs enter the accuracy metrics.
    """
    valid = frame[frame.get("is_valid_pair", False) == True] if not frame.empty else frame  # noqa: E712
    sample_count = int(len(valid))
    result: dict[str, object] = {
        "sample_count": sample_count,
        "expected_intervals": int(expected_count),
        "coverage_pct": _maybe(sample_count / expected_count * 100 if expected_count else None),
        "mae_mw": None,
        "rmse_mw": None,
        "bias_mw": None,
        "wape_pct": None,
        "mape_pct": None,
        "mape_sample_count": 0,
        "mape_excluded_count": sample_count,
        "mape_min_actual_mw": mape_min_actual_mw,
        "wape_undefined_reason": None,
        "mape_undefined_reason": None,
    }
    if sample_count == 0:
        result["wape_undefined_reason"] = "No matched intervals with both a valid actual and a valid eligible forecast."
        result["mape_undefined_reason"] = result["wape_undefined_reason"]
        return result

    errors = valid["error_mw"].astype(float)
    actuals = valid["actual_mw"].astype(float)
    absolute_errors = errors.abs()

    result["mae_mw"] = _maybe(absolute_errors.mean())
    result["rmse_mw"] = _maybe(np.sqrt(np.mean(np.square(errors.to_numpy(dtype=float)))))
    result["bias_mw"] = _maybe(errors.mean())

    sum_abs_actual = float(actuals.abs().sum())
    if sum_abs_actual > 0:
        result["wape_pct"] = _maybe(absolute_errors.sum() / sum_abs_actual * 100)
    else:
        result["wape_undefined_reason"] = (
            "WAPE is undefined because the sum of absolute actual generation across matched intervals is zero."
        )

    mape_mask = actuals >= mape_min_actual_mw
    mape_sample = int(mape_mask.sum())
    result["mape_sample_count"] = mape_sample
    result["mape_excluded_count"] = sample_count - mape_sample
    if mape_sample > 0:
        pct = (absolute_errors[mape_mask] / actuals[mape_mask]).mean() * 100
        result["mape_pct"] = _maybe(pct)
    else:
        result["mape_undefined_reason"] = (
            f"MAPE is undefined: no matched interval has actual generation ≥ "
            f"{mape_min_actual_mw:g} MW. Near-zero denominators are excluded by policy."
        )
    return result


def classify_status(frame: pd.DataFrame) -> pd.Series:
    has_actual = frame["actual_mw"].notna()
    has_forecast = frame["decision_forecast_mw"].notna()
    status = np.select(
        [has_actual & has_forecast, has_actual & ~has_forecast, ~has_actual & has_forecast],
        ["matched", "missing_forecast", "missing_actual"],
        default="missing_both",
    )
    return pd.Series(status, index=frame.index, dtype="object")


def data_quality_counts(frame: pd.DataFrame) -> dict[str, int]:
    status = frame["status"].astype(str) if "status" in frame else classify_status(frame)
    return {
        "expected_intervals": int(len(frame)),
        "matched_intervals": int((status == "matched").sum()),
        "missing_forecast_intervals": int((status == "missing_forecast").sum()),
        "missing_actual_intervals": int((status == "missing_actual").sum()),
        "missing_both_intervals": int((status == "missing_both").sum()),
        "valid_pairs": int(frame["is_valid_pair"].fillna(False).sum()) if not frame.empty else 0,
    }


def _group_key(frame: pd.DataFrame, group_by: str) -> pd.Series:
    if group_by == "day":
        return frame["delivery_date_local"].astype(str)
    if group_by == "week":
        dates = pd.to_datetime(frame["delivery_date_local"])
        iso = dates.dt.isocalendar()
        return iso["year"].astype(str) + "-W" + iso["week"].astype(int).astype(str).str.zfill(2)
    if group_by == "hour":
        if "local_start" in frame.columns:
            local = pd.to_datetime(frame["local_start"], utc=True).dt.tz_convert("Europe/London")
        elif "interval_start_local" in frame.columns:
            local = pd.to_datetime(frame["interval_start_local"])
        else:
            local = frame["interval_start_utc"].dt.tz_convert("Europe/London")
        return local.dt.hour
    if group_by == "lead_time":
        leads = frame["decision_forecast_lead_hours"]
        buckets = pd.cut(leads, bins=LEAD_BINS, labels=LEAD_LABELS, right=False)
        return buckets.astype(object).where(leads.notna(), other="no eligible forecast")
    raise ValueError(f"Unsupported group_by: {group_by!r}")


def grouped_accuracy(
    frame: pd.DataFrame, group_by: str, *, mape_min_actual_mw: float = 100.0
) -> list[dict[str, object]]:
    if frame.empty:
        return []
    working = frame.copy()
    working["_group"] = _group_key(working, group_by)
    rows: list[dict[str, object]] = []
    for key, group in working.groupby("_group", dropna=False, sort=False):
        metrics = compute_metrics(
            group, expected_count=len(group), mape_min_actual_mw=mape_min_actual_mw
        )
        counts = data_quality_counts(group)
        if group_by == "hour":
            label = f"{int(key):02d}:00–{int(key):02d}:59"
        elif group_by == "week":
            label = str(key)
        else:
            label = str(key)
        rows.append(
            {
                "group": str(key),
                "label": label,
                "expected_intervals": counts["expected_intervals"],
                "sample_count": metrics["sample_count"],
                "mae_mw": metrics["mae_mw"],
                "rmse_mw": metrics["rmse_mw"],
                "bias_mw": metrics["bias_mw"],
                "wape_pct": metrics["wape_pct"],
                "mape_pct": metrics["mape_pct"],
                "mape_sample_count": metrics["mape_sample_count"],
                "coverage_pct": metrics["coverage_pct"],
                "missing_forecast_intervals": counts["missing_forecast_intervals"],
                "missing_actual_intervals": counts["missing_actual_intervals"],
            }
        )
    if group_by == "hour":
        rows.sort(key=lambda row: int(row["group"]))
    elif group_by == "lead_time":
        order = {label: index for index, label in enumerate(LEAD_LABELS + ["no eligible forecast"])}
        rows.sort(key=lambda row: order.get(row["group"], 99))
    else:
        rows.sort(key=lambda row: row["group"])
    return rows


def largest_errors(
    frame: pd.DataFrame, *, sort: str = "absolute_error", limit: int = 20
) -> list[dict[str, object]]:
    valid = frame[frame["is_valid_pair"] == True].copy()  # noqa: E712
    if valid.empty:
        return []
    if sort == "underforecast":
        ordered = valid.sort_values(["error_mw", "interval_start_utc"], ascending=[True, True])
    elif sort == "overforecast":
        ordered = valid.sort_values(["error_mw", "interval_start_utc"], ascending=[False, True])
    elif sort == "absolute_error":
        ordered = valid.sort_values(
            ["abs_error_mw", "interval_start_utc"], ascending=[False, True]
        )
    else:
        raise ValueError(f"Unsupported error sort: {sort!r}")
    ordered = ordered.head(limit)
    rows = []
    for row in ordered.itertuples(index=False):
        local_val = getattr(row, "local_start", None) or getattr(row, "interval_start_local", None)
        if local_val is None and hasattr(row, "interval_start_utc"):
            local_val = pd.Timestamp(row.interval_start_utc).tz_convert("Europe/London").isoformat()
        rows.append(
            {
                "interval_start_utc": _iso(row.interval_start_utc),
                "interval_start_local": str(local_val) if local_val is not None else None,
                "delivery_date": row.delivery_date_local,
                "settlement_period": int(row.settlement_period),
                "actual_mw": _maybe(row.actual_mw),
                "decision_forecast_mw": _maybe(row.decision_forecast_mw),
                "decision_forecast_publish_time_utc": _iso(row.decision_forecast_publish_time_utc),
                "decision_forecast_lead_hours": _maybe(row.decision_forecast_lead_hours),
                "error_mw": _maybe(row.error_mw),
                "abs_error_mw": _maybe(row.abs_error_mw),
                "direction": "overforecast" if row.error_mw > 0 else "underforecast" if row.error_mw < 0 else "exact",
            }
        )
    return rows


def revision_summary(frame: pd.DataFrame) -> dict[str, object]:
    """Magnitude of the revision between the decision-time and latest forecast."""
    both = frame.dropna(subset=["decision_forecast_mw", "latest_forecast_mw"]).copy()
    if both.empty:
        return {
            "sample_count": 0,
            "mean_abs_revision_mw": None,
            "max_abs_revision_mw": None,
            "mean_signed_revision_mw": None,
            "note": "No intervals have both a decision-time and a subsequently published forecast.",
        }
    revision = both["latest_forecast_mw"] - both["decision_forecast_mw"]
    return {
        "sample_count": int(len(both)),
        "mean_abs_revision_mw": _maybe(revision.abs().mean()),
        "max_abs_revision_mw": _maybe(revision.abs().max()),
        "mean_signed_revision_mw": _maybe(revision.mean()),
        "note": (
            "Latest available vintage minus decision-time forecast. Positive values mean the "
            "forecast was revised upwards after the purchasing cutoff. Revision data is for "
            "hindsight learning only and was not available at the decision time."
        ),
    }


def _iso(value: object) -> str | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC").isoformat().replace("+00:00", "Z")


def summarise_lead_time(frame: pd.DataFrame) -> dict[str, object]:
    leads = frame["decision_forecast_lead_hours"].dropna()
    if leads.empty:
        return {"sample_count": 0, "min_hours": None, "median_hours": None, "max_hours": None}
    return {
        "sample_count": int(len(leads)),
        "min_hours": _maybe(leads.min()),
        "median_hours": _maybe(leads.median()),
        "max_hours": _maybe(leads.max()),
    }
