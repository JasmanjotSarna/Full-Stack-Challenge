from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.analysis_service import AnalysisService


def client(service: AnalysisService) -> TestClient:
    return TestClient(create_app(service=service, settings=service.settings))


def test_health_reports_test_data_and_dataset(leakage_service):
    with client(leakage_service) as http:
        response = http.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["dataset_available"] is True
    assert body["test_data"] is True
    assert body["real_source_data"] is False


def test_metadata_exposes_cutoff_and_sources(leakage_service):
    with client(leakage_service) as http:
        response = http.get("/api/v1/metadata")
    assert response.status_code == 200
    body = response.json()
    assert body["cutoff_policy"]["id"] == "previous_day@00:00[Europe/London]"
    assert body["cutoff_policy"]["is_analytical_assumption"] is True
    assert {source["dataset"] for source in body["sources"]} == {"FUELHH", "WINDFOR"}
    assert body["dataset"]["test_data"] is True


def test_summary_never_uses_a_post_cutoff_forecast(leakage_service):
    """The late vintage is perfect. If it leaked, MAE would be 0 instead of 200."""
    with client(leakage_service) as http:
        response = http.get(
            "/api/v1/summary", params={"start_date": "2026-01-02", "end_date": "2026-01-02"}
        )
    assert response.status_code == 200
    metrics = response.json()["metrics"]
    assert metrics["sample_count"] == 48
    assert metrics["mae_mw"] == 200.0
    assert metrics["bias_mw"] == 200.0
    assert metrics["rmse_mw"] == 200.0
    assert metrics["wape_pct"] == 20.0


def test_timeseries_preserves_selected_and_latest_vintages(leakage_service):
    with client(leakage_service) as http:
        response = http.get(
            "/api/v1/timeseries", params={"start_date": "2026-01-02", "end_date": "2026-01-02"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 48
    point = body["points"][0]
    assert point["decision_forecast_mw"] == 1200.0
    assert point["latest_forecast_mw"] == 1000.0
    assert point["error_mw"] == 200.0
    assert point["decision_forecast_is_latest"] is False
    assert point["status"] == "matched"


def test_hourly_resolution_aggregates_half_hours(leakage_service):
    with client(leakage_service) as http:
        response = http.get(
            "/api/v1/timeseries",
            params={"start_date": "2026-01-02", "end_date": "2026-01-02", "resolution": "1h"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 24
    assert body["points"][0]["decision_forecast_mw"] == 1200.0


def test_missing_forecasts_are_reported_and_not_backfilled(test_service):
    with client(test_service) as http:
        response = http.get(
            "/api/v1/summary", params={"start_date": "2026-01-03", "end_date": "2026-01-03"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["data_quality"]["matched_intervals"] == 4
    assert body["data_quality"]["missing_forecast_intervals"] == 44
    assert body["data_quality"]["valid_pairs"] == 4
    assert body["metrics"]["coverage_pct"] == 8.3333


def test_accuracy_grouping_and_errors(leakage_service):
    with client(leakage_service) as http:
        daily = http.get(
            "/api/v1/accuracy",
            params={"start_date": "2026-01-02", "end_date": "2026-01-02", "group_by": "day"},
        )
        hourly = http.get(
            "/api/v1/accuracy",
            params={"start_date": "2026-01-02", "end_date": "2026-01-02", "group_by": "hour"},
        )
        errors = http.get(
            "/api/v1/errors",
            params={"start_date": "2026-01-02", "end_date": "2026-01-02", "limit": 3},
        )
    assert daily.status_code == 200
    assert daily.json()["groups"][0]["mae_mw"] == 200.0
    assert len(hourly.json()["groups"]) == 24
    assert errors.status_code == 200
    assert errors.json()["count"] == 3
    assert all(row["error_mw"] == 200.0 for row in errors.json()["errors"])


def test_vintages_endpoint_marks_post_cutoff_rows_ineligible(leakage_service):
    with client(leakage_service) as http:
        response = http.get(
            "/api/v1/forecast-vintages",
            params={
                "delivery_date": "2026-01-02",
                "interval_start": "2026-01-02T00:00:00Z",
            },
        )
        day_response = http.get(
            "/api/v1/forecast-vintages", params={"delivery_date": "2026-01-02"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["cutoff_utc"] == "2026-01-01T00:00:00Z"
    assert body["selected_publish_time_utc"] == "2025-12-31T22:30:00Z"
    by_time = {row["publish_time_utc"]: row for row in body["vintages"]}
    assert by_time["2025-12-31T22:30:00Z"]["eligible"] is True
    assert by_time["2025-12-31T22:30:00Z"]["is_selected"] is True
    assert by_time["2026-01-01T12:00:00Z"]["eligible"] is False
    assert by_time["2026-01-01T12:00:00Z"]["is_selected"] is False
    assert day_response.status_code == 200
    assert len(day_response.json()["intervals"]) == 48


def test_out_of_scope_requests_are_rejected(leakage_service):
    with client(leakage_service) as http:
        response = http.get(
            "/api/v1/summary", params={"start_date": "2026-02-01", "end_date": "2026-02-02"}
        )
        reversed_range = http.get(
            "/api/v1/summary", params={"start_date": "2026-01-05", "end_date": "2026-01-01"}
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"
    assert reversed_range.status_code == 400


def test_invalid_resolution_returns_validation_envelope(leakage_service):
    with client(leakage_service) as http:
        response = http.get("/api/v1/summary", params={"resolution": "5m"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_vintages_requires_a_delivery_date(leakage_service):
    with client(leakage_service) as http:
        response = http.get("/api/v1/forecast-vintages")
    assert response.status_code == 422


def test_refresh_endpoint_is_disabled_by_default(leakage_service):
    with client(leakage_service) as http:
        response = http.post("/api/v1/refresh")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "dataset_unavailable"


def test_operational_headers_are_present(leakage_service):
    with client(leakage_service) as http:
        response = http.get("/api/v1/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "X-Process-Time-Ms" in response.headers


def test_root_endpoint_identifies_product(leakage_service):
    with client(leakage_service) as http:
        response = http.get("/")
    assert response.status_code == 200
    assert "WindScope" in response.json()["product"]
    assert response.json()["api"] == "/api/v1"


def test_openapi_contains_versioned_routes(leakage_service):
    with client(leakage_service) as http:
        spec = http.get("/openapi.json").json()
    paths = spec["paths"]
    for path in (
        "/api/v1/health",
        "/api/v1/metadata",
        "/api/v1/summary",
        "/api/v1/timeseries",
        "/api/v1/accuracy",
        "/api/v1/errors",
        "/api/v1/forecast-vintages",
        "/api/v1/refresh",
    ):
        assert path in paths


def test_degraded_service_returns_503_not_fake_data(monkeypatch, test_settings):
    from app.services.analysis_service import AnalysisService

    service = AnalysisService(None, None, test_settings, load_error="No dataset")
    with TestClient(create_app(service=service, settings=test_settings)) as http:
        health = http.get("/api/v1/health")
        summary = http.get("/api/v1/summary")
    assert health.status_code == 503
    assert health.json()["dataset_available"] is False
    assert summary.status_code == 503
    assert summary.json()["error"]["code"] == "dataset_unavailable"


def test_root_health_endpoint_alias(leakage_service):
    with client(leakage_service) as http:
        response = http.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_hourly_resolution_accuracy_and_errors(leakage_service):
    with client(leakage_service) as http:
        acc = http.get(
            "/api/v1/accuracy",
            params={"start_date": "2026-01-02", "end_date": "2026-01-02", "group_by": "hour", "resolution": "1h"},
        )
        err = http.get(
            "/api/v1/errors",
            params={"start_date": "2026-01-02", "end_date": "2026-01-02", "resolution": "1h"},
        )
    assert acc.status_code == 200
    assert len(acc.json()["groups"]) == 24
    assert err.status_code == 200
    assert err.json()["errors"][0]["interval_start_local"] is not None
