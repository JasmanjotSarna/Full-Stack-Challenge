"""Reproducible refresh of the validated January 2026 dataset.

Usage (from backend/):
    python -m app.data.refresh
    python -m app.data.refresh --dry-run
    python -m app.data.refresh --output ../data/processed/windscope_january_2026.json.gz

Fetch failures raise: a failed request is never treated as an empty dataset and
never overwrites the last known-good cache.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from ..analytics.cutoff import CutoffPolicy
from ..analytics.pipeline import build_analysis, utc_now_iso
from ..analytics.store import build_payload, save_payload
from ..core.config import SCOPE_END, SCOPE_START, Settings, get_settings
from ..core.logging import configure_logging, get_logger
from .elexon_client import ElexonClient, ElexonAPIError

logger = get_logger(__name__)

# A publication may precede the scope and still contain the first delivery day.
PUBLISH_LOOKBACK_DAYS = 4
PUBLISH_LOOKAHEAD_DAYS = 2
MIN_ACTUAL_COVERAGE = 0.50


def refresh(start=SCOPE_START, end=SCOPE_END, *, output: Path | None = None, dry_run: bool = False) -> dict:
    settings = get_settings()
    if start != SCOPE_START or end != SCOPE_END:
        raise SystemExit(
            f"WindScope is scoped to {SCOPE_START}..{SCOPE_END} (Europe/London). "
            f"Refusing to build a dataset for {start}..{end}."
        )
    policy = CutoffPolicy(
        mode=settings.cutoff_mode,
        local_time=settings.cutoff_local_clock,
        lead_hours=settings.cutoff_lead_hours,
        timezone_name=settings.forecast_timezone,
    )
    publish_start = datetime.combine(SCOPE_START, time(0, 0), tzinfo=timezone.utc) - timedelta(
        days=PUBLISH_LOOKBACK_DAYS
    )
    publish_end = datetime.combine(SCOPE_END, time(0, 0), tzinfo=timezone.utc) + timedelta(
        days=PUBLISH_LOOKAHEAD_DAYS
    )
    fetched_at = utc_now_iso()

    logger.info(
        "refresh started",
        extra={"event": "refresh_start", "dataset": "FUELHH+WINDFOR"},
    )
    with ElexonClient(settings) as client:
        actual_rows = client.fetch_actual_wind(SCOPE_START, SCOPE_END)
        forecast_rows = client.fetch_wind_forecasts(publish_start, publish_end)

    analysis = build_analysis(
        actual_rows,
        forecast_rows,
        policy,
        start=SCOPE_START,
        end=SCOPE_END,
        mape_min_actual_mw=settings.mape_min_actual_mw,
        generated_at=utc_now_iso(),
        fetched_at=fetched_at,
        test_data=False,
    )
    summary = analysis.summary()
    if summary["expected_intervals"] != 1488:
        raise RuntimeError(
            f"Scope produced {summary['expected_intervals']} expected intervals; 1,488 are "
            "required for January 2026. Refusing to write an unexpected dataset."
        )
    actual_coverage = (
        (summary["matched_intervals"] + summary["missing_forecast_intervals"])
        / summary["expected_intervals"]
    )
    if actual_coverage < MIN_ACTUAL_COVERAGE:
        raise RuntimeError(
            f"Actual generation covers only {actual_coverage:.1%} of January 2026 intervals "
            f"(minimum {MIN_ACTUAL_COVERAGE:.0%}). The source may be unavailable or the request "
            "may be misconfigured. Refusing to overwrite the cache with an incomplete dataset."
        )

    actual_fetch = {
        "endpoint": f"{settings.elexon_base_url}/datasets/FUELHH",
        "params": {
            "settlementDateFrom": SCOPE_START.isoformat(),
            "settlementDateTo": SCOPE_END.isoformat(),
            "fuelType": "WIND",
        },
        "records_received": len(actual_rows),
        "records_accepted": len(analysis.actuals),
        "coverage_of_expected_pct": round(actual_coverage * 100, 4),
    }
    forecast_fetch = {
        "endpoint": f"{settings.elexon_base_url}/datasets/WINDFOR",
        "params": {
            "publishDateTimeFrom": publish_start.isoformat().replace("+00:00", "Z"),
            "publishDateTimeTo": publish_end.isoformat().replace("+00:00", "Z"),
        },
        "records_received": len(forecast_rows),
        "records_accepted": len(analysis.forecasts),
        "publications": int(analysis.forecasts["publish_time_utc"].nunique())
        if not analysis.forecasts.empty
        else 0,
    }
    payload = build_payload(
        analysis,
        actual_fetch=actual_fetch,
        forecast_fetch=forecast_fetch,
        is_test_data=False,
    )
    target = output or settings.dataset_path()

    if not dry_run:
        save_payload(payload, target)
        logger.info(
            "dataset written",
            extra={"event": "dataset_written", "records": len(payload["actuals"]) + len(payload["forecasts"])},
        )

    result = {
        "ok": True,
        "dry_run": dry_run,
        "output": str(target),
        "generated_at": payload["generated_at"],
        "scope": payload["scope"],
        "completeness": payload["completeness"],
        "validation": payload["validation"],
        "warnings": payload["warnings"],
    }
    print(json.dumps(result, indent=2))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh the WindScope January 2026 dataset")
    parser.add_argument("--output", type=Path, default=None, help="Output .json.gz path")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and validate without writing")
    args = parser.parse_args(argv)
    configure_logging(get_settings().log_level)
    try:
        refresh(output=args.output, dry_run=args.dry_run)
    except ElexonAPIError as exc:
        print(f"Elexon API error: {exc}", file=sys.stderr)
        return 2
    except (RuntimeError, SystemExit) as exc:
        print(f"Refresh failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
