"""Robust Elexon BMRS API client.

Verified behaviour (checked against the live API and official documentation):
* Base URL: https://data.elexon.co.uk/bmrs/api/v1
* FUELHH accepts ``settlementDateFrom`` / ``settlementDateTo`` (max 7 days,
  inclusive) and ``fuelType``. The plain ``settlementDate`` parameter does not
  filter the collection endpoint, so it is intentionally not used.
* WINDFOR accepts ``publishDateTimeFrom`` / ``publishDateTimeTo`` (max 7 days,
  inclusive). Delivery-time filters do not work on this endpoint; historical
  vintages are retrieved by publication time.
* Both return ``{"data": [...]}``. No authentication is required.

The client validates HTTP status, response shape and dataset identity, retries
transient failures with exponential backoff and never turns an error into an
empty dataset.
"""

from __future__ import annotations

import random
import time
from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

from ..core.config import Settings, get_settings
from ..core.logging import get_logger

logger = get_logger(__name__)

TRANSIENT_STATUS = {408, 425, 429, 500, 502, 503, 504}


class ElexonAPIError(RuntimeError):
    """Raised when Elexon data cannot be retrieved or fails validation."""

    def __init__(self, message: str, *, url: str | None = None, status: int | None = None):
        super().__init__(message)
        self.url = url
        self.status = status


def _iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ElexonClient:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep=time.sleep,
        monotonic=time.monotonic,
    ) -> None:
        self.settings = settings or get_settings()
        self._sleep = sleep
        self._monotonic = monotonic
        self._last_request = 0.0
        timeout = httpx.Timeout(
            connect=self.settings.elexon_connect_timeout,
            read=self.settings.elexon_read_timeout,
            write=self.settings.elexon_read_timeout,
            pool=self.settings.elexon_connect_timeout,
        )
        self._client = httpx.Client(
            base_url=self.settings.elexon_base_url,
            timeout=timeout,
            headers={
                "Accept": "application/json",
                "User-Agent": "WindScope/1.0 (forecast analytics; Elexon BMRS)",
            },
            transport=transport,
            follow_redirects=True,
        )

    def __enter__(self) -> "ElexonClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _throttle(self) -> None:
        elapsed = self._monotonic() - self._last_request
        wait = self.settings.elexon_min_interval - elapsed
        if wait > 0:
            self._sleep(wait)
        self._last_request = self._monotonic()

    def _request(self, path: str, params: dict[str, Any]) -> httpx.Response:
        last_error: Exception | None = None
        attempts = self.settings.elexon_max_retries + 1
        for attempt in range(1, attempts + 1):
            self._throttle()
            started = self._monotonic()
            try:
                response = self._client.get(path, params=params)
                duration_ms = round((self._monotonic() - started) * 1000)
                logger.info(
                    "elexon request",
                    extra={
                        "event": "elexon_request",
                        "url": str(response.request.url),
                        "status": response.status_code,
                        "attempt": attempt,
                        "duration_ms": duration_ms,
                    },
                )
                if response.status_code in TRANSIENT_STATUS:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after is None:
                        raise ElexonAPIError(
                            f"Elexon returned transient HTTP {response.status_code}",
                            url=str(response.request.url),
                            status=response.status_code,
                        )
                    raise _RetryAfter(
                        f"Elexon returned HTTP {response.status_code} with Retry-After",
                        url=str(response.request.url),
                        status=response.status_code,
                        retry_after=float(retry_after),
                    )
                if response.status_code >= 400:
                    detail = _safe_detail(response)
                    raise ElexonAPIError(
                        f"Elexon rejected the request (HTTP {response.status_code}): {detail}",
                        url=str(response.request.url),
                        status=response.status_code,
                    )
                return response
            except _RetryAfter as exc:
                last_error = exc
                delay = exc.retry_after
            except (ElexonAPIError, httpx.TransportError, httpx.TimeoutException) as exc:
                last_error = exc
                delay = self.settings.elexon_backoff_base ** attempt + random.uniform(0, 0.25)
                if isinstance(exc, ElexonAPIError) and exc.status is not None and exc.status < 500 and exc.status != 429:
                    # Non-transient 4xx: do not retry.
                    raise
            if attempt < attempts:
                logger.warning(
                    "elexon request retry",
                    extra={
                        "event": "elexon_retry",
                        "attempt": attempt,
                        "status": getattr(last_error, "status", None),
                    },
                )
                self._sleep(max(delay, 0.1))
        raise ElexonAPIError(
            f"Elexon request failed after {attempts} attempts: {last_error}",
            url=getattr(last_error, "url", None),
            status=getattr(last_error, "status", None),
        )

    def get_dataset(
        self,
        dataset: str,
        params: dict[str, Any],
        *,
        expected_fields: Iterable[str] = ("startTime", "generation"),
    ) -> list[dict[str, Any]]:
        response = self._request(f"/datasets/{dataset}", params)
        try:
            payload = response.json()
        except ValueError as exc:  # pragma: no cover - defensive
            raise ElexonAPIError(
                f"Elexon returned non-JSON content for {dataset}",
                url=str(response.request.url),
                status=response.status_code,
            ) from exc
        if not isinstance(payload, dict) or "data" not in payload:
            raise ElexonAPIError(
                f"Elexon response for {dataset} is missing the 'data' array",
                url=str(response.request.url),
                status=response.status_code,
            )
        rows = payload["data"]
        if not isinstance(rows, list):
            raise ElexonAPIError(
                f"Elexon response for {dataset} has a non-list 'data' value",
                url=str(response.request.url),
                status=response.status_code,
            )
        required = set(expected_fields)
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise ElexonAPIError(
                    f"Elexon response for {dataset} contains a non-object record at index {index}",
                    url=str(response.request.url),
                    status=response.status_code,
                )
            if row.get("dataset") not in (None, dataset):
                raise ElexonAPIError(
                    f"Elexon response for {dataset} contained a record for {row.get('dataset')!r}",
                    url=str(response.request.url),
                    status=response.status_code,
                )
            missing = required.difference(row)
            if missing:
                raise ElexonAPIError(
                    f"Elexon response for {dataset} is missing fields {sorted(missing)} at index {index}",
                    url=str(response.request.url),
                    status=response.status_code,
                )
        return rows

    # ------------------------------------------------------------------
    # Dataset-specific helpers
    # ------------------------------------------------------------------
    def fetch_actual_wind(self, start: date, end: date) -> list[dict[str, Any]]:
        """Fetch half-hourly WIND actuals for an inclusive settlement-date range."""
        if end < start:
            raise ValueError("end must be on or after start")
        records: list[dict[str, Any]] = []
        cursor = start
        while cursor <= end:
            window_end = min(cursor + timedelta(days=self.settings.elexon_window_days - 1), end)
            rows = self.get_dataset(
                "FUELHH",
                {
                    "settlementDateFrom": cursor.isoformat(),
                    "settlementDateTo": window_end.isoformat(),
                    "fuelType": "WIND",
                },
            )
            logger.info(
                "elexon FUELHH window fetched",
                extra={
                    "event": "dataset_window",
                    "dataset": "FUELHH",
                    "records": len(rows),
                },
            )
            records.extend(rows)
            cursor = window_end + timedelta(days=1)
        return records

    def fetch_wind_forecasts(
        self, publish_start: datetime, publish_end: datetime
    ) -> list[dict[str, Any]]:
        """Fetch WINDFOR runs by publication time (inclusive window)."""
        if publish_end < publish_start:
            raise ValueError("publish_end must be on or after publish_start")
        records: list[dict[str, Any]] = []
        cursor = publish_start.astimezone(timezone.utc)
        end = publish_end.astimezone(timezone.utc)
        step = timedelta(days=self.settings.elexon_window_days)
        while cursor <= end:
            window_end = min(cursor + step, end)
            rows = self.get_dataset(
                "WINDFOR",
                {
                    "publishDateTimeFrom": _iso_z(cursor),
                    "publishDateTimeTo": _iso_z(window_end),
                },
            )
            logger.info(
                "elexon WINDFOR window fetched",
                extra={
                    "event": "dataset_window",
                    "dataset": "WINDFOR",
                    "records": len(rows),
                },
            )
            records.extend(rows)
            if window_end >= end:
                break
            cursor = window_end + timedelta(seconds=1)
        return records


class _RetryAfter(ElexonAPIError):
    def __init__(self, *args: Any, retry_after: float, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.retry_after = retry_after


def _safe_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:300] if response.text else "no response body"
    if isinstance(body, dict):
        for key in ("detail", "title", "message"):
            if key in body:
                return str(body[key])[:300]
    return str(body)[:300]
