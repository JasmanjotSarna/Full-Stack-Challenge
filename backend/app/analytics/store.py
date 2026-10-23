"""Cached dataset persistence.

The validated January 2026 extract is stored as a compressed JSON document and
can be shipped inside the container image. It is a cache of real Elexon data,
not a synthetic fallback; its provenance and generation time are always exposed.
"""

from __future__ import annotations

import gzip
import json
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from ..core.config import DATASET_SCHEMA_VERSION, SCOPE_END, SCOPE_START, Settings
from ..data.sources import FORECAST_ALIGNMENT_NOTE, SCOPE_NOTE, SOURCES
from .pipeline import AnalysisResult, build_analysis, utc_now_iso


class DatasetError(RuntimeError):
    """Raised when the cached dataset is missing, invalid or out of scope."""


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "tzinfo"):
        moment = value
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


def build_payload(
    analysis: AnalysisResult,
    *,
    actual_fetch: dict[str, Any],
    forecast_fetch: dict[str, Any],
    is_test_data: bool = False,
) -> dict[str, Any]:
    summary = analysis.summary()
    return {
        "schema_version": DATASET_SCHEMA_VERSION,
        "generated_at": analysis.generated_at or utc_now_iso(),
        "fetched_at": analysis.fetched_at,
        "scope": {
            "start": SCOPE_START.isoformat(),
            "end": SCOPE_END.isoformat(),
            "timezone": analysis.policy.timezone_name,
            "description": SCOPE_NOTE,
        },
        "sources": SOURCES,
        "forecast_alignment": {
            "method": "hourly_step_hold_to_half_hour",
            "note": FORECAST_ALIGNMENT_NOTE,
        },
        "is_test_data": is_test_data,
        "fetch": {
            "actual": actual_fetch,
            "forecast": forecast_fetch,
        },
        "validation": {
            "actual": analysis.actual_report.as_dict(),
            "forecast": analysis.forecast_report.as_dict(),
        },
        "completeness": {
            "expected_intervals": summary["expected_intervals"],
            "matched_intervals": summary["matched_intervals"],
            "missing_forecast_intervals": summary["missing_forecast_intervals"],
            "missing_actual_intervals": summary["missing_actual_intervals"],
            "missing_both_intervals": summary["missing_both_intervals"],
            "coverage_pct": summary["coverage_pct"],
        },
        "warnings": analysis.warnings,
        "actuals": [
            {
                "startTime": _iso(row["interval_start_utc"]),
                "publishTime": _iso(row["actual_publish_time_utc"]),
                "generation": float(row["actual_mw"]),
                "fuelType": "WIND",
                "settlementDate": row.get("source_settlement_date"),
                "settlementPeriod": _jsonable(row.get("source_settlement_period")),
            }
            for _, row in analysis.actuals.iterrows()
        ],
        "forecasts": [
            {
                "startTime": _iso(row["target_hour_utc"]),
                "publishTime": _iso(row["publish_time_utc"]),
                "generation": float(row["forecast_mw"]),
            }
            for _, row in analysis.forecasts.iterrows()
        ],
    }


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    try:
        if value != value:  # NaN
            return None
    except Exception:
        pass
    if hasattr(value, "item"):
        return value.item()
    return value


def save_payload(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    fd, tmp_name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=6, mtime=0) as gz:
                gz.write(text.encode("utf-8"))
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def load_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise DatasetError(
            f"No validated dataset found at {path}. Run the refresh command: "
            "`python -m app.data.refresh` from the backend directory."
        )
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetError(f"Cached dataset at {path} could not be read: {exc}") from exc
    if not isinstance(payload, dict):
        raise DatasetError("Cached dataset is not a JSON object.")
    if payload.get("schema_version") != DATASET_SCHEMA_VERSION:
        raise DatasetError(
            f"Cached dataset schema version {payload.get('schema_version')!r} is not supported "
            f"(expected {DATASET_SCHEMA_VERSION}). Rebuild it with the refresh command."
        )
    scope = payload.get("scope") or {}
    if scope.get("start") != SCOPE_START.isoformat() or scope.get("end") != SCOPE_END.isoformat():
        raise DatasetError(
            "Cached dataset scope does not match the required January 2026 delivery window. "
            "Refusing to serve a different month or year."
        )
    for key in ("actuals", "forecasts"):
        if not isinstance(payload.get(key), list):
            raise DatasetError(f"Cached dataset is missing the '{key}' array.")
    return payload


def analysis_from_payload(
    payload: dict[str, Any],
    *,
    policy,
    mape_min_actual_mw: float,
) -> AnalysisResult:
    return build_analysis(
        payload["actuals"],
        payload["forecasts"],
        policy,
        start=date.fromisoformat(payload["scope"]["start"]),
        end=date.fromisoformat(payload["scope"]["end"]),
        mape_min_actual_mw=mape_min_actual_mw,
        generated_at=payload.get("generated_at"),
        fetched_at=payload.get("fetched_at"),
        test_data=bool(payload.get("is_test_data")),
        dataset_warnings=list(payload.get("warnings") or []),
    )


def load_analysis(settings: Settings) -> tuple[AnalysisResult, dict[str, Any]]:
    payload = load_payload(settings.dataset_path())
    if payload.get("is_test_data") and not _allow_test_data():
        raise DatasetError(
            "The dataset is labelled TEST DATA and this runtime does not allow test data. "
            "Rebuild the real January 2026 dataset with the refresh command."
        )
    analysis = analysis_from_payload(
        payload,
        policy=_policy_from_settings(settings),
        mape_min_actual_mw=settings.mape_min_actual_mw,
    )
    return analysis, payload


def _allow_test_data() -> bool:
    return os.environ.get("ALLOW_TEST_DATA", "").lower() in {"1", "true", "yes"}


def _policy_from_settings(settings: Settings):
    from ..analytics.cutoff import CutoffPolicy

    return CutoffPolicy(
        mode=settings.cutoff_mode,
        local_time=settings.cutoff_local_clock,
        lead_hours=settings.cutoff_lead_hours,
        timezone_name=settings.forecast_timezone,
    )


def dataset_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_at": payload.get("generated_at"),
        "fetched_at": payload.get("fetched_at"),
        "is_test_data": bool(payload.get("is_test_data")),
        "validation": payload.get("validation", {}),
        "completeness": payload.get("completeness", {}),
        "fetch": payload.get("fetch", {}),
        "sources": payload.get("sources", SOURCES),
        "forecast_alignment": payload.get("forecast_alignment", {}),
        "warnings": payload.get("warnings", []),
    }
