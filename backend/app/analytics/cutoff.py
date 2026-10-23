"""Decision-cutoff policy and leak-free forecast vintage selection.

The cutoff is an explicit analytical assumption. It is not presented as an
official market gate-closure time. Forecast selection is performed before any
accuracy calculation and only uses information available at the cutoff.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

UTC = timezone.utc


@dataclass(frozen=True)
class CutoffPolicy:
    mode: str = "previous_day"  # "previous_day" | "lead_hours"
    local_time: time = time(0, 0)
    lead_hours: float = 24.0
    timezone_name: str = "Europe/London"

    def __post_init__(self) -> None:
        if self.mode not in {"previous_day", "lead_hours"}:
            raise ValueError(f"Unsupported cutoff mode: {self.mode!r}")
        if self.lead_hours < 0:
            raise ValueError("cutoff lead hours must be non-negative")

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)

    def cutoff_for(self, delivery_start_utc: pd.Timestamp | datetime) -> pd.Timestamp:
        if not isinstance(delivery_start_utc, pd.Timestamp):
            delivery_start_utc = pd.Timestamp(delivery_start_utc)
        if delivery_start_utc.tzinfo is None:
            delivery_start_utc = delivery_start_utc.tz_localize("UTC")
        start = delivery_start_utc.tz_convert(UTC)
        if self.mode == "previous_day":
            local_date = start.tz_convert(self.tz).date()
            cutoff_local = datetime.combine(
                local_date - timedelta(days=1), self.local_time, tzinfo=self.tz
            )
            return pd.Timestamp(cutoff_local.astimezone(UTC))
        return start - pd.Timedelta(hours=self.lead_hours)

    @property
    def identifier(self) -> str:
        if self.mode == "previous_day":
            return f"previous_day@{self.local_time.strftime('%H:%M')}[{self.timezone_name}]"
        return f"lead_hours={self.lead_hours:g}[absolute]"

    def describe(self) -> str:
        if self.mode == "previous_day":
            return (
                f"Latest forecast published on or before "
                f"{self.local_time.strftime('%H:%M')} {self.timezone_name} on the calendar day "
                f"before delivery. This is a 24-hour lead to the start of the delivery date for "
                f"the default 00:00 policy. It is an analytical assumption, not a verified market "
                f"gate-closure time."
            )
        return (
            f"Latest forecast published at least {self.lead_hours:g} hours before the delivery "
            "interval starts. This is an analytical assumption, not a verified market "
            "gate-closure time."
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.identifier,
            "mode": self.mode,
            "local_time": self.local_time.strftime("%H:%M"),
            "lead_hours": self.lead_hours,
            "timezone": self.timezone_name,
            "description": self.describe(),
            "is_analytical_assumption": True,
            "eligibility_boundary": "publish_time_utc <= cutoff_utc (inclusive)",
            "selection_rule": (
                "Among eligible records for the same delivery interval, select the greatest "
                "publish_time. Duplicate (delivery interval, publish time) records with "
                "conflicting values are excluded during validation; any remaining tie is "
                "broken by the highest forecast MW, deterministically."
            ),
        }


def expected_intervals(start: date, end: date, tz: ZoneInfo) -> pd.DataFrame:
    """All valid half-hour delivery intervals between two local dates, inclusive.

    Uses local-day boundaries so DST days (46/50 periods) are handled correctly.
    January 2026 has 31 days × 48 periods = 1,488 intervals.
    """
    if end < start:
        raise ValueError("end must be on or after start")
    rows: list[dict[str, object]] = []
    cursor = start
    while cursor <= end:
        local_start = datetime.combine(cursor, time(0, 0), tzinfo=tz)
        next_local = datetime.combine(cursor + timedelta(days=1), time(0, 0), tzinfo=tz)
        utc_start = local_start.astimezone(UTC)
        utc_end = next_local.astimezone(UTC)
        step = timedelta(minutes=30)
        period = 1
        current = utc_start
        while current < utc_end:
            local = current.astimezone(tz)
            rows.append(
                {
                    "interval_start_utc": pd.Timestamp(current),
                    "delivery_date_local": cursor.isoformat(),
                    "local_start": local.isoformat(),
                    "settlement_period": period,
                }
            )
            current += step
            period += 1
        cursor += timedelta(days=1)
    frame = pd.DataFrame(rows)
    frame["interval_start_utc"] = pd.to_datetime(frame["interval_start_utc"], utc=True)
    return frame


def apply_cutoff(
    expanded_forecasts: pd.DataFrame, intervals: pd.DataFrame, policy: CutoffPolicy
) -> pd.DataFrame:
    """Annotate every forecast record with the cutoff and its eligibility."""
    if expanded_forecasts.empty:
        result = expanded_forecasts.copy()
        result["cutoff_utc"] = pd.Series(dtype="datetime64[ns, UTC]")
        result["eligible"] = pd.Series(dtype="bool")
        return result
    cutoff_map = {
        pd.Timestamp(row.interval_start_utc): policy.cutoff_for(pd.Timestamp(row.interval_start_utc))
        for row in intervals.itertuples(index=False)
    }
    result = expanded_forecasts.copy()
    result["cutoff_utc"] = result["interval_start_utc"].map(cutoff_map)
    if result["cutoff_utc"].isna().any():
        missing = int(result["cutoff_utc"].isna().sum())
        raise ValueError(f"Could not derive a cutoff for {missing} forecast record(s)")
    result["eligible"] = result["publish_time_utc"] <= result["cutoff_utc"]
    return result


def _latest_per_interval(frame: pd.DataFrame, value_column: str, prefix: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "interval_start_utc",
                f"{prefix}_mw",
                f"{prefix}_publish_time_utc",
                f"{prefix}_lead_hours",
                f"{prefix}_source_target_hour_utc",
            ]
        )
    ordered = frame.sort_values(
        ["interval_start_utc", "publish_time_utc", value_column],
        ascending=[True, True, True],
    )
    latest = ordered.groupby("interval_start_utc", as_index=False).tail(1).copy()
    latest[f"{prefix}_lead_hours"] = (
        latest["interval_start_utc"] - latest["publish_time_utc"]
    ).dt.total_seconds() / 3600.0
    latest = latest.rename(
        columns={
            value_column: f"{prefix}_mw",
            "publish_time_utc": f"{prefix}_publish_time_utc",
            "source_target_hour_utc": f"{prefix}_source_target_hour_utc",
        }
    )
    return latest[
        [
            "interval_start_utc",
            f"{prefix}_mw",
            f"{prefix}_publish_time_utc",
            f"{prefix}_lead_hours",
            f"{prefix}_source_target_hour_utc",
        ]
    ]


def select_forecast_vintages(
    expanded_forecasts: pd.DataFrame,
    intervals: pd.DataFrame,
    policy: CutoffPolicy,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (annotated forecasts, decision-time selection, latest selection).

    Selection is purely information-time based. Actual generation is not passed
    into this module, which structurally prevents accuracy-based leakage.
    """
    annotated = apply_cutoff(expanded_forecasts, intervals, policy)
    eligible = annotated[annotated["eligible"]]
    decision = _latest_per_interval(eligible, "forecast_mw", "decision_forecast")
    latest = _latest_per_interval(annotated, "forecast_mw", "latest_forecast")
    return annotated, decision, latest
