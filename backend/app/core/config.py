"""Application configuration.

All configuration is environment-driven. No secrets are required for the public
Elexon BMRS API; the optional admin token protects the refresh endpoint.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, time
from pathlib import Path
from zoneinfo import ZoneInfo

APP_NAME = "WindScope API"
APP_VERSION = "1.0.0"
DATASET_SCHEMA_VERSION = 1

# The analytical scope is fixed by the challenge and enforced by the API.
SCOPE_START = date(2026, 1, 1)
SCOPE_END = date(2026, 1, 31)
SCOPE_TIMEZONE = "Europe/London"

REPO_ROOT = Path(__file__).resolve().parents[3]


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else default


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except ValueError:
        return default


def _parse_hhmm(value: str, default: time) -> time:
    try:
        hour, minute = value.split(":")
        return time(int(hour), int(minute))
    except (ValueError, AttributeError):
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = APP_NAME
    app_version: str = APP_VERSION
    environment: str = field(default_factory=lambda: _env("ENVIRONMENT", "development"))
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO").upper())

    # Elexon BMRS
    elexon_base_url: str = field(
        default_factory=lambda: _env(
            "ELEXON_BASE_URL", "https://data.elexon.co.uk/bmrs/api/v1"
        ).rstrip("/")
    )
    elexon_connect_timeout: float = field(
        default_factory=lambda: _env_float("ELEXON_CONNECT_TIMEOUT_SECONDS", 10.0)
    )
    elexon_read_timeout: float = field(
        default_factory=lambda: _env_float("ELEXON_READ_TIMEOUT_SECONDS", 90.0)
    )
    elexon_max_retries: int = field(
        default_factory=lambda: _env_int("ELEXON_MAX_RETRIES", 4)
    )
    elexon_backoff_base: float = field(
        default_factory=lambda: _env_float("ELEXON_BACKOFF_BASE_SECONDS", 1.5)
    )
    elexon_min_interval: float = field(
        default_factory=lambda: _env_float("ELEXON_MIN_REQUEST_INTERVAL_SECONDS", 0.4)
    )
    # Elexon limits date filters to 7 days per request; we use 6 to stay safe.
    elexon_window_days: int = field(
        default_factory=lambda: min(max(_env_int("ELEXON_WINDOW_DAYS", 6), 1), 7)
    )

    # Data persistence
    data_dir: Path | None = field(
        default_factory=lambda: Path(_env("DATA_DIR", "")) if _env("DATA_DIR", "") else None
    )
    raw_dir: Path | None = field(
        default_factory=lambda: Path(_env("RAW_DATA_DIR", "")) if _env("RAW_DATA_DIR", "") else None
    )

    # Decision cutoff policy
    cutoff_mode: str = field(
        default_factory=lambda: _env("CUTOFF_MODE", "previous_day").lower()
    )
    cutoff_local_time: str = field(
        default_factory=lambda: _env("CUTOFF_LOCAL_TIME", "00:00")
    )
    cutoff_lead_hours: float = field(
        default_factory=lambda: _env_float("CUTOFF_LEAD_HOURS", 24.0)
    )
    forecast_timezone: str = field(
        default_factory=lambda: _env("FORECAST_TIMEZONE", SCOPE_TIMEZONE)
    )

    # Metric policy
    mape_min_actual_mw: float = field(
        default_factory=lambda: _env_float("MAPE_MIN_ACTUAL_MW", 100.0)
    )

    # Web
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            origin.strip()
            for origin in _env(
                "CORS_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080",
            ).split(",")
            if origin.strip()
        )
    )
    refresh_token: str | None = field(
        default_factory=lambda: _env("REFRESH_TOKEN", "") or None
    )
    allow_refresh_endpoint: bool = field(
        default_factory=lambda: _env("ALLOW_REFRESH_ENDPOINT", "false").lower()
        in {"1", "true", "yes"}
    )

    @property
    def timezone(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.forecast_timezone)
        except Exception:
            return ZoneInfo(SCOPE_TIMEZONE)

    @property
    def cutoff_local_clock(self) -> time:
        return _parse_hhmm(self.cutoff_local_time, time(0, 0))

    def resolved_data_dir(self) -> Path:
        if self.data_dir is not None:
            return self.data_dir
        candidates = [
            REPO_ROOT / "data" / "processed",
            Path(__file__).resolve().parents[2] / "data" / "processed",
            Path.cwd() / "data" / "processed",
            Path.cwd().parent / "data" / "processed",
            Path("/app/data/processed"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    def resolved_raw_dir(self) -> Path:
        if self.raw_dir is not None:
            return self.raw_dir
        return REPO_ROOT / "data" / "raw"

    def dataset_path(self) -> Path:
        return self.resolved_data_dir() / "windscope_january_2026.json.gz"

    def display_safe(self) -> dict[str, str | bool | float | None]:
        return {
            "environment": self.environment,
            "elexon_base_url": self.elexon_base_url,
            "cutoff_mode": self.cutoff_mode,
            "cutoff_local_time": self.cutoff_local_time,
            "cutoff_lead_hours": self.cutoff_lead_hours,
            "timezone": self.forecast_timezone,
            "cors_origins": ",".join(self.cors_origins),
            "refresh_endpoint_enabled": self.allow_refresh_endpoint,
        }


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings_cache() -> None:
    """Used by tests to re-read environment variables."""
    global _settings
    _settings = None
