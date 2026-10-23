"""Validation and normalization of raw Elexon records into typed frames.

Invalid records are never silently converted to zero. Every rejection is
counted and surfaced in the API metadata / data-quality panel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from ..core.config import SCOPE_END, SCOPE_START, SCOPE_TIMEZONE

SCOPE_TZ = ZoneInfo(SCOPE_TIMEZONE)
SCOPE_START_UTC = datetime.combine(SCOPE_START, time(0, 0), tzinfo=SCOPE_TZ).astimezone(ZoneInfo("UTC"))
SCOPE_END_UTC = datetime.combine(date(2026, 2, 1), time(0, 0), tzinfo=SCOPE_TZ).astimezone(ZoneInfo("UTC"))
MAX_PLAUSIBLE_MW = 100_000.0


@dataclass
class NormalizationReport:
    dataset: str
    received: int = 0
    accepted: int = 0
    rejected_malformed: int = 0
    rejected_out_of_scope: int = 0
    rejected_fuel_type: int = 0
    rejected_implausible: int = 0
    duplicates_collapsed: int = 0
    conflicts_dropped: int = 0
    revisions_collapsed: int = 0
    warnings: list[str] = field(default_factory=list)
    _warning_set: set[str] = field(default_factory=set, repr=False)

    def warn(self, message: str) -> None:
        if message not in self._warning_set:
            self._warning_set.add(message)
            self.warnings.append(message)

    def as_dict(self) -> dict[str, object]:
        return {
            "dataset": self.dataset,
            "received": self.received,
            "accepted": self.accepted,
            "rejected_malformed": self.rejected_malformed,
            "rejected_out_of_scope": self.rejected_out_of_scope,
            "rejected_fuel_type": self.rejected_fuel_type,
            "rejected_implausible": self.rejected_implausible,
            "duplicates_collapsed": self.duplicates_collapsed,
            "conflicts_dropped": self.conflicts_dropped,
            "revisions_collapsed": self.revisions_collapsed,
            "warnings": list(self.warnings),
        }


def _empty_frame(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame({column: pd.Series(dtype="object") for column in columns})


def _parse_timestamps(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce", format="ISO8601")


def normalize_actuals(
    rows: list[dict], report: NormalizationReport | None = None
) -> tuple[pd.DataFrame, NormalizationReport]:
    """Normalize FUELHH WIND records.

    Output columns: interval_start_utc, actual_mw, actual_publish_time_utc,
    source_fuel_type, source_settlement_date, source_settlement_period.
    """
    report = report or NormalizationReport(dataset="FUELHH")
    report.received = len(rows)
    if not rows:
        report.warn("No FUELHH records were returned for the requested January 2026 scope.")
        return _empty_frame(
            [
                "interval_start_utc",
                "actual_mw",
                "actual_publish_time_utc",
                "source_fuel_type",
                "source_settlement_date",
                "source_settlement_period",
            ]
        ), report

    frame = pd.DataFrame(rows)
    required = {"startTime", "publishTime", "generation", "fuelType"}
    missing_columns = required.difference(frame.columns)
    if missing_columns:
        raise ValueError(f"FUELHH response missing required columns: {sorted(missing_columns)}")

    report.rejected_fuel_type = int((frame["fuelType"] != "WIND").sum())
    frame = frame[frame["fuelType"] == "WIND"].copy()

    frame["interval_start_utc"] = _parse_timestamps(frame["startTime"])
    frame["actual_publish_time_utc"] = _parse_timestamps(frame["publishTime"])
    frame["actual_mw"] = pd.to_numeric(frame["generation"], errors="coerce")

    malformed = (
        frame["interval_start_utc"].isna()
        | frame["actual_publish_time_utc"].isna()
        | frame["actual_mw"].isna()
        | ~np.isfinite(frame["actual_mw"])
    )
    # Half-hourly data must start on :00 or :30.
    valid_time = frame["interval_start_utc"].notna()
    malformed |= valid_time & (
        ~frame["interval_start_utc"].dt.minute.isin([0, 30])
        | (frame["interval_start_utc"].dt.second != 0)
    )
    report.rejected_malformed = int(malformed.sum())
    if report.rejected_malformed:
        report.warn(
            f"Rejected {report.rejected_malformed} malformed FUELHH record(s) "
            "(unparseable timestamps, non-numeric/NaN generation, or off-grid period starts)."
        )
    frame = frame[~malformed].copy()

    plausible = (frame["actual_mw"] >= 0) & (frame["actual_mw"] <= MAX_PLAUSIBLE_MW)
    report.rejected_implausible = int((~plausible).sum())
    if report.rejected_implausible:
        report.warn(
            f"Rejected {report.rejected_implausible} FUELHH record(s) with generation outside "
            f"the plausible range 0–{MAX_PLAUSIBLE_MW:,.0f} MW."
        )
    frame = frame[plausible].copy()

    in_scope = (frame["interval_start_utc"] >= SCOPE_START_UTC) & (
        frame["interval_start_utc"] < SCOPE_END_UTC
    )
    report.rejected_out_of_scope = int((~in_scope).sum())
    frame = frame[in_scope].copy()

    frame["source_fuel_type"] = frame["fuelType"].astype(str)
    frame["source_settlement_date"] = frame.get("settlementDate")
    frame["source_settlement_period"] = frame.get("settlementPeriod")

    # Conflicting duplicates at the same (delivery interval, publish time) are
    # ambiguous. Drop the whole pair rather than guessing which value is right.
    conflict = frame.groupby(["interval_start_utc", "actual_publish_time_utc"])[
        "actual_mw"
    ].transform("nunique") > 1
    if bool(conflict.any()):
        dropped_intervals = int(frame.loc[conflict, "interval_start_utc"].nunique())
        report.conflicts_dropped += dropped_intervals
        report.warn(
            f"Dropped {dropped_intervals} actual delivery interval(s) with conflicting "
            "values published at the same timestamp."
        )
        frame = frame[~conflict].copy()

    before = len(frame)
    frame = frame.sort_values(["interval_start_utc", "actual_publish_time_utc"]).drop_duplicates(
        ["interval_start_utc", "actual_publish_time_utc"], keep="last"
    )
    report.duplicates_collapsed += before - len(frame)

    # The same delivery interval can be republished (revision). Keep the latest
    # publication; this is the value a post-delivery analysis should use.
    before = len(frame)
    frame = frame.drop_duplicates(["interval_start_utc"], keep="last")
    report.revisions_collapsed += before - len(frame)

    frame = frame.sort_values("interval_start_utc").reset_index(drop=True)
    report.accepted = len(frame)

    # Cross-check the source settlement metadata against the timestamp.
    if {"settlementDate", "settlementPeriod"}.issubset(frame.columns):
        local = frame["interval_start_utc"].dt.tz_convert(SCOPE_TZ)
        expected_date = local.dt.strftime("%Y-%m-%d")
        expected_period = local.dt.hour * 2 + (local.dt.minute // 30) + 1
        mismatch = (frame["settlementDate"].astype(str) != expected_date) | (
            pd.to_numeric(frame["settlementPeriod"], errors="coerce") != expected_period
        )
        if bool(mismatch.any()):
            report.warn(
                f"{int(mismatch.sum())} FUELHH record(s) had settlement metadata that did not "
                "match the UTC startTime; the UTC startTime was treated as authoritative."
            )

    return frame[
        [
            "interval_start_utc",
            "actual_mw",
            "actual_publish_time_utc",
            "source_fuel_type",
            "source_settlement_date",
            "source_settlement_period",
        ]
    ], report


def normalize_forecasts(
    rows: list[dict], report: NormalizationReport | None = None
) -> tuple[pd.DataFrame, NormalizationReport]:
    """Normalize WINDFOR records.

    Output columns: target_hour_utc, forecast_mw, publish_time_utc.
    All vintages are retained for revision analysis and the vintage inspector.
    """
    report = report or NormalizationReport(dataset="WINDFOR")
    report.received = len(rows)
    if not rows:
        report.warn("No WINDFOR records were returned for the requested publication window.")
        return _empty_frame(["target_hour_utc", "forecast_mw", "publish_time_utc"]), report

    frame = pd.DataFrame(rows)
    required = {"publishTime", "startTime", "generation"}
    missing_columns = required.difference(frame.columns)
    if missing_columns:
        raise ValueError(f"WINDFOR response missing required columns: {sorted(missing_columns)}")

    frame["target_hour_utc"] = _parse_timestamps(frame["startTime"])
    frame["publish_time_utc"] = _parse_timestamps(frame["publishTime"])
    frame["forecast_mw"] = pd.to_numeric(frame["generation"], errors="coerce")

    malformed = (
        frame["target_hour_utc"].isna()
        | frame["publish_time_utc"].isna()
        | frame["forecast_mw"].isna()
        | ~np.isfinite(frame["forecast_mw"])
    )
    valid_time = frame["target_hour_utc"].notna()
    malformed |= valid_time & (
        (frame["target_hour_utc"].dt.minute != 0)
        | (frame["target_hour_utc"].dt.second != 0)
    )
    report.rejected_malformed = int(malformed.sum())
    if report.rejected_malformed:
        report.warn(
            f"Rejected {report.rejected_malformed} malformed WINDFOR record(s) "
            "(unparseable timestamps, non-numeric/NaN generation, or non-hourly targets)."
        )
    frame = frame[~malformed].copy()

    plausible = (frame["forecast_mw"] >= 0) & (frame["forecast_mw"] <= MAX_PLAUSIBLE_MW)
    report.rejected_implausible = int((~plausible).sum())
    if report.rejected_implausible:
        report.warn(
            f"Rejected {report.rejected_implausible} WINDFOR record(s) with generation outside "
            f"the plausible range 0–{MAX_PLAUSIBLE_MW:,.0f} MW."
        )
    frame = frame[plausible].copy()

    in_scope = (frame["target_hour_utc"] >= SCOPE_START_UTC) & (
        frame["target_hour_utc"] < SCOPE_END_UTC
    )
    report.rejected_out_of_scope = int((~in_scope).sum())
    frame = frame[in_scope].copy()

    conflict = frame.groupby(["target_hour_utc", "publish_time_utc"])[
        "forecast_mw"
    ].transform("nunique") > 1
    if bool(conflict.any()):
        pairs = int(
            frame.loc[conflict, ["target_hour_utc", "publish_time_utc"]]
            .drop_duplicates()
            .shape[0]
        )
        report.conflicts_dropped += pairs
        report.warn(
            f"Dropped {pairs} forecast vintage(s) with conflicting values at the same "
            "target hour and publication timestamp."
        )
        frame = frame[~conflict].copy()

    before = len(frame)
    frame = frame.drop_duplicates(["target_hour_utc", "publish_time_utc"], keep="last")
    report.duplicates_collapsed += before - len(frame)

    frame = frame.sort_values(["target_hour_utc", "publish_time_utc"]).reset_index(drop=True)
    report.accepted = len(frame)
    return frame[["target_hour_utc", "forecast_mw", "publish_time_utc"]], report


def expand_to_half_hourly(forecasts: pd.DataFrame) -> pd.DataFrame:
    """Step-hold each hourly forecast onto both half-hours beginning in that hour.

    This is an explicit, documented alignment assumption required because FUELHH is
    half-hourly while WINDFOR is hourly. No interpolation is performed.
    """
    if forecasts.empty:
        return pd.DataFrame(
            {
                "interval_start_utc": pd.Series(dtype="datetime64[ns, UTC]"),
                "forecast_mw": pd.Series(dtype="float64"),
                "publish_time_utc": pd.Series(dtype="datetime64[ns, UTC]"),
                "source_target_hour_utc": pd.Series(dtype="datetime64[ns, UTC]"),
            }
        )
    first = forecasts.rename(columns={"target_hour_utc": "interval_start_utc"})
    second = first.copy()
    second["interval_start_utc"] = second["interval_start_utc"] + pd.Timedelta(minutes=30)
    expanded = pd.concat([first, second], ignore_index=True)
    expanded["source_target_hour_utc"] = expanded["interval_start_utc"].dt.floor("h")
    return expanded.sort_values(["interval_start_utc", "publish_time_utc"]).reset_index(
        drop=True
    )
