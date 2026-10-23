"""Read-side analysis service used by the HTTP layer.

The service loads one validated, immutable dataset at startup and derives all
responses from it. No endpoint contains hard-coded production-looking values.
"""

from __future__ import annotations

import threading
import time
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

from ..analytics.cutoff import CutoffPolicy
from ..analytics.metrics import (
    compute_metrics,
    data_quality_counts,
    grouped_accuracy,
    largest_errors,
    revision_summary,
    summarise_lead_time,
)
from ..analytics.pipeline import AnalysisResult
from ..analytics.resample import aggregate_resolution
from ..analytics.store import (
    DatasetError,
    analysis_from_payload,
    dataset_summary,
    load_payload,
)
from ..core.config import SCOPE_END, SCOPE_START, Settings, get_settings
from ..data.sources import FORECAST_ALIGNMENT_NOTE, SOURCES
from ..core.logging import get_logger

logger = get_logger(__name__)

SIGN_CONVENTION = (
    "error_MW = decision-time forecast − actual. Positive = overforecast (forecast exceeded "
    "actual generation). Negative = underforecast (actual generation exceeded the forecast)."
)
MISSING_POLICY = (
    "Missing forecasts or actuals are preserved as null and excluded from accuracy metrics. "
    "They are never filled from later forecast vintages, other dates, or other datasets."
)


class DatasetUnavailable(RuntimeError):
    pass


class InvalidRequest(ValueError):
    pass


class AnalysisService:
    def __init__(
        self,
        analysis: AnalysisResult | None,
        payload: dict[str, Any] | None,
        settings: Settings | None = None,
        load_error: str | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._analysis = analysis
        self._payload = payload
        self._load_error = load_error
        self._started = time.monotonic()
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    @classmethod
    def load(cls, settings: Settings | None = None) -> "AnalysisService":
        settings = settings or get_settings()
        try:
            payload = load_payload(settings.dataset_path())
            if payload.get("is_test_data") and not _allow_test_data():
                raise DatasetError(
                    "Dataset is labelled TEST DATA and this runtime does not allow test data."
                )
            policy = CutoffPolicy(
                mode=settings.cutoff_mode,
                local_time=settings.cutoff_local_clock,
                lead_hours=settings.cutoff_lead_hours,
                timezone_name=settings.forecast_timezone,
            )
            analysis = analysis_from_payload(
                payload, policy=policy, mape_min_actual_mw=settings.mape_min_actual_mw
            )
            logger.info(
                "dataset loaded",
                extra={
                    "event": "dataset_loaded",
                    "records": len(analysis.actuals) + len(analysis.forecasts),
                },
            )
            return cls(analysis, payload, settings)
        except DatasetError as exc:
            logger.error("dataset unavailable", extra={"event": "dataset_error"})
            return cls(None, None, settings, load_error=str(exc))

    def reload(self) -> None:
        with self._lock:
            replacement = AnalysisService.load(self.settings)
            self._analysis = replacement._analysis
            self._payload = replacement._payload
            self._load_error = replacement._load_error

    @property
    def available(self) -> bool:
        return self._analysis is not None

    @property
    def analysis(self) -> AnalysisResult:
        if self._analysis is None:
            raise DatasetUnavailable(
                self._load_error
                or "The January 2026 dataset is not available. Run the data refresh command."
            )
        return self._analysis

    @property
    def policy(self) -> CutoffPolicy:
        return self.analysis.policy

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _validate_range(self, start: date, end: date) -> None:
        if start > end:
            raise InvalidRequest("start_date must be on or before end_date")
        if start < SCOPE_START or end > SCOPE_END:
            raise InvalidRequest(
                f"Requested period {start}..{end} is outside the January 2026 scope "
                f"({SCOPE_START}..{SCOPE_END}). Other months are not substituted."
            )

    def _frame(self, start: date, end: date, resolution: str) -> pd.DataFrame:
        if resolution not in {"30m", "1h"}:
            raise InvalidRequest("resolution must be '30m' or '1h'")
        frame = self.analysis.slice(start, end)
        frame = aggregate_resolution(frame, resolution)
        if "interval_start_local" not in frame.columns:
            frame = frame.copy()
            frame["interval_start_local"] = (
                frame["interval_start_utc"]
                .dt.tz_convert(self.settings.forecast_timezone)
                .map(lambda value: value.isoformat())
            )
        if "local_start" not in frame.columns:
            frame = frame.copy()
            frame["local_start"] = frame["interval_start_local"]
        return frame

    def _period(self, start: date, end: date) -> dict[str, str]:
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "timezone": self.settings.forecast_timezone,
        }

    def _notes(self, resolution: str) -> list[str]:
        notes = [MISSING_POLICY, FORECAST_ALIGNMENT_NOTE]
        if resolution == "1h":
            notes.append(
                "Hourly view: values are means of available half-hourly observations within the "
                "hour; an hour is valid when at least one half-hour pair is valid."
            )
        return notes

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------
    def health(self) -> dict[str, Any]:
        dataset = self._payload or {}
        return {
            "status": "ok" if self.available else "degraded",
            "service": self.settings.app_name,
            "version": self.settings.app_version,
            "environment": self.settings.environment,
            "dataset_available": self.available,
            "real_source_data": bool(self.available and not dataset.get("is_test_data")),
            "test_data": bool(dataset.get("is_test_data", False)),
            "dataset_generated_at": dataset.get("generated_at"),
            "last_successful_refresh": dataset.get("generated_at"),
            "uptime_seconds": round(time.monotonic() - self._started, 3),
            "cutoff_policy": self.policy.identifier
            if self.available
            else self.settings.cutoff_mode,
        }

    def metadata(self) -> dict[str, Any]:
        settings = self.settings
        policy = (
            self.analysis.policy.as_dict()
            if self.available
            else CutoffPolicy(
                mode=settings.cutoff_mode,
                local_time=settings.cutoff_local_clock,
                lead_hours=settings.cutoff_lead_hours,
                timezone_name=settings.forecast_timezone,
            ).as_dict()
        )
        dataset = dataset_summary(self._payload) if self._payload else {}
        warnings = list(dataset.get("warnings") or [])
        if not self.available and self._load_error:
            warnings.insert(0, self._load_error)
        return {
            "product": "WindScope — UK Wind Forecast Intelligence",
            "scope": {
                "start": SCOPE_START.isoformat(),
                "end": SCOPE_END.isoformat(),
                "timezone": settings.forecast_timezone,
                "description": (
                    "National GB wind generation, delivery periods 1–31 January 2026 inclusive. "
                    "No other month, year or generation source is substituted."
                ),
            },
            "dataset": {
                "available": self.available,
                "real_source_data": bool(dataset.get("is_test_data") is False and self.available),
                "test_data": bool(dataset.get("is_test_data", False)),
                "last_successful_refresh": dataset.get("generated_at"),
                "generated_at": dataset.get("generated_at"),
                "fetched_at": dataset.get("fetched_at"),
                "date_range": {
                    "start": SCOPE_START.isoformat(),
                    "end": SCOPE_END.isoformat(),
                    "timezone": settings.forecast_timezone,
                },
                "actual_resolution": "30m",
                "forecast_resolution": "1h",
                "alignment": dataset.get("forecast_alignment", {}),
                "completeness": dataset.get("completeness", {}),
                "validation": dataset.get("validation", {}),
                "fetch": dataset.get("fetch", {}),
                "refresh_mode": (
                    "Validated data is shipped with the deployment as a compressed extract. "
                    "Rebuild it with `python -m app.data.refresh`."
                ),
                "warnings": warnings,
            },
            "cutoff_policy": policy,
            "timezone": settings.forecast_timezone,
            "sources": [
                {
                    "dataset": source["dataset"],
                    "name": source["name"],
                    "url": source["url"],
                    "description": source["description"],
                }
                for source in SOURCES.values()
            ],
            "metrics_policy": {
                "sign_convention": SIGN_CONVENTION,
                "mae": "mean(abs(forecast − actual)), MW",
                "rmse": "sqrt(mean((forecast − actual)^2)), MW",
                "bias": "mean(forecast − actual), MW — positive means overforecast",
                "wape": "sum(abs(forecast − actual)) / sum(abs(actual)) × 100; null if denominator is zero",
                "mape": (
                    f"mean(abs(forecast − actual) / actual) × 100 over intervals with actual ≥ "
                    f"{settings.mape_min_actual_mw:g} MW; near-zero denominators are excluded and "
                    "the excluded count is reported"
                ),
                "coverage": "valid matched intervals / expected intervals × 100",
                "missing_policy": MISSING_POLICY,
            },
            "assumptions": [
                "The decision cutoff is an analytical assumption, not a verified market gate-closure time.",
                "Each hourly WINDFOR value is step-held onto both half-hours of that hour; no interpolation.",
                "Actual generation is national transmission-metered wind as reported by FUELHH.",
                "This product analyses wind forecast accuracy only; it does not model demand, prices, "
                "thermal availability, procurement volumes or financial savings.",
                "January 2026 contains 1,488 half-hour settlement periods in Europe/London.",
            ],
            "warnings": warnings,
        }

    def summary(self, start: date, end: date, resolution: str = "30m") -> dict[str, Any]:
        self._validate_range(start, end)
        frame = self._frame(start, end, resolution)
        metrics = compute_metrics(
            frame,
            expected_count=len(frame),
            mape_min_actual_mw=self.settings.mape_min_actual_mw,
        )
        counts = data_quality_counts(frame)
        return {
            "period": self._period(start, end),
            "resolution": resolution,
            "metrics": metrics,
            "data_quality": counts,
            "cutoff_policy": self.analysis.policy.as_dict(),
            "lead_time": summarise_lead_time(frame),
            "revision": revision_summary(frame),
            "sign_convention": SIGN_CONVENTION,
            "forecast_alignment": "hourly_step_hold_to_half_hour",
            "notes": self._notes(resolution),
        }

    def timeseries(self, start: date, end: date, resolution: str = "30m") -> dict[str, Any]:
        self._validate_range(start, end)
        frame = self._frame(start, end, resolution)
        points = [self._point(row) for row in frame.itertuples(index=False)]
        return {
            "period": self._period(start, end),
            "resolution": resolution,
            "count": len(points),
            "points": points,
            "notes": self._notes(resolution),
        }

    def accuracy(
        self, start: date, end: date, group_by: str = "day", resolution: str = "30m"
    ) -> dict[str, Any]:
        self._validate_range(start, end)
        if group_by not in {"day", "week", "hour", "lead_time"}:
            raise InvalidRequest("group_by must be one of: day, week, hour, lead_time")
        frame = self._frame(start, end, resolution)
        groups = grouped_accuracy(
            frame, group_by, mape_min_actual_mw=self.settings.mape_min_actual_mw
        )
        return {
            "period": self._period(start, end),
            "group_by": group_by,
            "groups": groups,
            "sign_convention": SIGN_CONVENTION,
        }

    def errors(
        self,
        start: date,
        end: date,
        *,
        sort: str = "absolute_error",
        limit: int = 20,
        resolution: str = "30m",
    ) -> dict[str, Any]:
        self._validate_range(start, end)
        if sort not in {"absolute_error", "underforecast", "overforecast"}:
            raise InvalidRequest("sort must be one of: absolute_error, underforecast, overforecast")
        if not 1 <= limit <= 500:
            raise InvalidRequest("limit must be between 1 and 500")
        frame = self._frame(start, end, resolution)
        rows = largest_errors(frame, sort=sort, limit=limit)
        return {
            "period": self._period(start, end),
            "sort": sort,
            "limit": limit,
            "count": len(rows),
            "errors": rows,
            "sign_convention": SIGN_CONVENTION,
        }

    def vintages(
        self, delivery_date: date, interval_start: str | None = None
    ) -> dict[str, Any]:
        self._validate_range(delivery_date, delivery_date)
        frame = self.analysis.frame
        day_rows = frame[frame["delivery_date_local"] == delivery_date.isoformat()]
        if day_rows.empty:
            raise InvalidRequest(f"No delivery intervals found for {delivery_date}")

        policy = self.analysis.policy
        annotated = self.analysis.annotated_forecasts
        annotated_local = annotated.copy()
        annotated_local["_delivery_date"] = (
            annotated_local["interval_start_utc"]
            .dt.tz_convert(policy.tz)
            .dt.strftime("%Y-%m-%d")
        )
        day_annotated = annotated_local[annotated_local["_delivery_date"] == delivery_date.isoformat()]

        chosen = None
        parsed: pd.Timestamp | None = None
        if interval_start:
            try:
                parsed = pd.Timestamp(interval_start)
            except (ValueError, TypeError) as exc:
                raise InvalidRequest("interval_start must be an ISO-8601 timestamp") from exc
            if parsed.tzinfo is None:
                parsed = parsed.tz_localize("UTC")
            parsed = parsed.tz_convert("UTC")
            matches = day_rows[day_rows["interval_start_utc"] == parsed]
            if matches.empty:
                raise InvalidRequest(
                    "interval_start is not an expected half-hour interval on the requested delivery date"
                )
            chosen = matches.iloc[0]
            cutoff = policy.cutoff_for(parsed)
            interval_annotated = day_annotated[day_annotated["interval_start_utc"] == parsed]
            selected_publish = chosen["decision_forecast_publish_time_utc"]
            vintages = []
            for row in interval_annotated.sort_values("publish_time_utc").itertuples(index=False):
                publish = row.publish_time_utc
                vintages.append(
                    {
                        "publish_time_utc": _ts(publish),
                        "forecast_mw": _f(row.forecast_mw),
                        "eligible": bool(publish <= cutoff),
                        "is_selected": bool(
                            pd.notna(selected_publish) and publish == selected_publish
                        ),
                        "lead_hours": _f(
                            (parsed - publish).total_seconds() / 3600.0
                        ),
                    }
                )
            intervals_payload: list[dict[str, Any]] = []
        else:
            cutoff = policy.cutoff_for(day_rows.iloc[0]["interval_start_utc"])
            vintages = []
            counts = (
                day_annotated.groupby("interval_start_utc")
                .agg(
                    available=("publish_time_utc", "count"),
                    eligible=("eligible", "sum"),
                )
                .reset_index()
            )
            count_map = {
                pd.Timestamp(row.interval_start_utc): (int(row.available), int(row.eligible))
                for row in counts.itertuples(index=False)
            }
            intervals_payload = []
            for row in day_rows.itertuples(index=False):
                available, eligible = count_map.get(pd.Timestamp(row.interval_start_utc), (0, 0))
                intervals_payload.append(
                    {
                        "interval_start_utc": _ts(row.interval_start_utc),
                        "interval_start_local": row.local_start,
                        "settlement_period": int(row.settlement_period),
                        "actual_mw": _f(row.actual_mw),
                        "decision_forecast_mw": _f(row.decision_forecast_mw),
                        "decision_forecast_publish_time_utc": _ts(
                            row.decision_forecast_publish_time_utc
                        ),
                        "status": row.status,
                        "available_vintages": available,
                        "eligible_vintages": eligible,
                    }
                )

        return {
            "delivery_date": delivery_date.isoformat(),
            "timezone": self.settings.forecast_timezone,
            "cutoff_policy": policy.as_dict(),
            "interval_start_utc": _ts(parsed) if chosen is not None else None,
            "cutoff_utc": _ts(cutoff),
            "selected_publish_time_utc": _ts(chosen["decision_forecast_publish_time_utc"])
            if chosen is not None
            else None,
            "vintages": vintages,
            "intervals": intervals_payload,
            "note": (
                "Only vintages with eligible=true were available at the cutoff. The selected "
                "vintage is the latest eligible one. Later vintages are shown for hindsight "
                "revision analysis only and were not used in accuracy metrics."
            ),
        }

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------
    def _point(self, row: Any) -> dict[str, Any]:
        return {
            "interval_start_utc": _ts(row.interval_start_utc),
            "interval_start_local": row.interval_start_local,
            "delivery_date": row.delivery_date_local,
            "settlement_period": int(row.settlement_period),
            "actual_mw": _f(row.actual_mw),
            "decision_forecast_mw": _f(row.decision_forecast_mw),
            "latest_forecast_mw": _f(row.latest_forecast_mw),
            "decision_forecast_publish_time_utc": _ts(row.decision_forecast_publish_time_utc),
            "decision_forecast_lead_hours": _f(row.decision_forecast_lead_hours),
            "latest_forecast_publish_time_utc": _ts(row.latest_forecast_publish_time_utc),
            "error_mw": _f(row.error_mw),
            "abs_error_mw": _f(row.abs_error_mw),
            "status": row.status,
            "decision_forecast_is_latest": bool(row.decision_forecast_is_latest),
            "forecast_alignment": row.forecast_alignment,
        }


def _f(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        return None
    return round(float(value), 3)


def _ts(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        return None
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC").isoformat().replace("+00:00", "Z")


def _allow_test_data() -> bool:
    import os

    return os.environ.get("ALLOW_TEST_DATA", "").lower() in {"1", "true", "yes"}


def build_test_service(
    actual_rows: list[dict],
    forecast_rows: list[dict],
    *,
    policy: CutoffPolicy | None = None,
    settings: Settings | None = None,
    mape_min_actual_mw: float = 100.0,
) -> AnalysisService:
    """TEST DATA helper for API tests. Never used by the production app."""
    from ..analytics.pipeline import build_analysis

    settings = settings or get_settings()
    policy = policy or CutoffPolicy()
    analysis = build_analysis(
        actual_rows,
        forecast_rows,
        policy,
        mape_min_actual_mw=mape_min_actual_mw,
        test_data=True,
    )
    payload = {
        "generated_at": analysis.generated_at,
        "is_test_data": True,
        "scope": {"start": SCOPE_START.isoformat(), "end": SCOPE_END.isoformat()},
        "sources": SOURCES,
        "completeness": analysis.summary(),
        "warnings": analysis.warnings,
        "validation": {
            "actual": analysis.actual_report.as_dict(),
            "forecast": analysis.forecast_report.as_dict(),
        },
        "fetch": {},
        "forecast_alignment": {"method": "hourly_step_hold_to_half_hour"},
    }
    return AnalysisService(analysis, payload, settings)
