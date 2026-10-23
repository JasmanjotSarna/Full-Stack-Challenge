from __future__ import annotations

from datetime import date, datetime, timezone

import httpx
import pytest

from app.core.config import Settings
from app.data.elexon_client import ElexonAPIError, ElexonClient

ROWS = [
    {
        "dataset": "FUELHH",
        "startTime": "2026-01-01T00:00:00Z",
        "publishTime": "2026-01-01T02:00:00Z",
        "generation": 1000,
        "fuelType": "WIND",
    }
]


def make_settings(**overrides) -> Settings:
    base = {
        "elexon_max_retries": 2,
        "elexon_min_interval": 0.0,
        "elexon_backoff_base": 0.001,
        "elexon_window_days": 6,
        "elexon_base_url": "https://example.test/bmrs/api/v1",
    }
    base.update(overrides)
    return Settings(**base)


def test_get_dataset_validates_envelope_and_returns_rows():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(200, json={"data": ROWS})

    with ElexonClient(make_settings(), transport=httpx.MockTransport(handler)) as client:
        rows = client.get_dataset("FUELHH", {"fuelType": "WIND"})
    assert rows == ROWS
    assert len(seen) == 1
    assert seen[0].params["fuelType"] == "WIND"


def test_transient_errors_are_retried():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(503, text="busy")
        return httpx.Response(200, json={"data": ROWS})

    with ElexonClient(make_settings(), transport=httpx.MockTransport(handler)) as client:
        rows = client.get_dataset("FUELHH", {})
    assert rows == ROWS
    assert calls["count"] == 2


def test_retry_after_header_is_honoured():
    sleeps: list[float] = []
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429, headers={"Retry-After": "2"}, text="slow down")
        return httpx.Response(200, json={"data": ROWS})

    with ElexonClient(
        make_settings(elexon_max_retries=1),
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
    ) as client:
        client.get_dataset("FUELHH", {})
    assert sleeps == [2.0]


def test_non_transient_4xx_is_not_retried():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(404, json={"message": "no such dataset"})

    with ElexonClient(make_settings(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ElexonAPIError) as error:
            client.get_dataset("FUELHH", {})
    assert calls["count"] == 1
    assert "404" in str(error.value)


def test_exhausted_retries_raise_instead_of_returning_empty_data():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    with ElexonClient(
        make_settings(elexon_max_retries=1), transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(ElexonAPIError, match="failed after 2 attempts"):
            client.get_dataset("FUELHH", {})


def test_wrong_dataset_in_payload_is_rejected():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{**ROWS[0], "dataset": "WINDFOR"}]})

    with ElexonClient(make_settings(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ElexonAPIError, match="contained a record for"):
            client.get_dataset("FUELHH", {})


def test_missing_required_fields_are_rejected():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"dataset": "FUELHH"}]})

    with ElexonClient(make_settings(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ElexonAPIError, match="missing fields"):
            client.get_dataset("FUELHH", {})


def test_non_list_data_is_rejected():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"not": "a list"}})

    with ElexonClient(make_settings(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ElexonAPIError, match="non-list"):
            client.get_dataset("FUELHH", {})


def test_fuelhh_requests_are_chunked_into_six_day_windows():
    urls: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(request.url)
        return httpx.Response(200, json={"data": []})

    with ElexonClient(make_settings(), transport=httpx.MockTransport(handler)) as client:
        client.fetch_actual_wind(date(2026, 1, 1), date(2026, 1, 19))
    assert len(urls) == 4
    assert urls[0].params["settlementDateFrom"] == "2026-01-01"
    assert urls[0].params["settlementDateTo"] == "2026-01-06"
    assert urls[-1].params["settlementDateFrom"] == "2026-01-19"
    assert urls[-1].params["settlementDateTo"] == "2026-01-19"
    assert all("settlementDate" not in url.params for url in urls)


def test_windfor_requests_use_publication_time_and_chunk():
    urls: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(request.url)
        return httpx.Response(200, json={"data": []})

    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 14, tzinfo=timezone.utc)
    with ElexonClient(make_settings(), transport=httpx.MockTransport(handler)) as client:
        client.fetch_wind_forecasts(start, end)
    assert len(urls) == 3
    assert urls[0].params["publishDateTimeFrom"] == "2026-01-01T00:00:00Z"
    assert urls[0].params["publishDateTimeTo"] == "2026-01-07T00:00:00Z"
    assert "startTimeFrom" not in urls[0].params


def test_reversed_actual_range_is_rejected():
    with ElexonClient(make_settings(), transport=httpx.MockTransport(lambda r: httpx.Response(200))) as client:
        with pytest.raises(ValueError):
            client.fetch_actual_wind(date(2026, 1, 2), date(2026, 1, 1))


def test_reversed_forecast_window_is_rejected():
    with ElexonClient(make_settings(), transport=httpx.MockTransport(lambda r: httpx.Response(200))) as client:
        with pytest.raises(ValueError):
            client.fetch_wind_forecasts(
                datetime(2026, 1, 2, tzinfo=timezone.utc),
                datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
