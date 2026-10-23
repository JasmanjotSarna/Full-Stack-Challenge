"""Versioned REST API routes."""

from __future__ import annotations

import hmac
from datetime import date
from typing import Literal

from fastapi import APIRouter, Header, Query, Request, Response
from fastapi.responses import JSONResponse

from ..core.config import SCOPE_END, SCOPE_START
from ..services.analysis_service import AnalysisService, DatasetUnavailable, InvalidRequest
from ..models.schemas import (
    AccuracyResponse,
    ErrorResponse,
    ErrorsResponse,
    HealthResponse,
    MetadataResponse,
    RefreshResponse,
    SummaryResponse,
    TimeseriesResponse,
    VintagesResponse,
)

router = APIRouter(prefix="/api/v1")

RESPONSES = {
    400: {"model": ErrorResponse, "description": "Invalid request or out-of-scope period"},
    422: {"model": ErrorResponse, "description": "Parameter validation error"},
    503: {"model": ErrorResponse, "description": "Dataset or endpoint unavailable"},
}


def _service(request: Request) -> AnalysisService:
    service = getattr(request.app.state, "service", None)
    if service is None:
        service = AnalysisService.load()
        request.app.state.service = service
    return service


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "Dataset not ready"}},
    tags=["operations"],
    summary="Service and dataset readiness",
)
def health(request: Request, response: Response):
    payload = _service(request).health()
    if not payload["dataset_available"]:
        response.status_code = 503
    return payload


@router.get(
    "/metadata",
    response_model=MetadataResponse,
    responses=RESPONSES,
    tags=["operations"],
    summary="Dataset provenance, cutoff policy, completeness and assumptions",
)
def metadata(request: Request):
    return _service(request).metadata()


@router.get(
    "/summary",
    response_model=SummaryResponse,
    responses=RESPONSES,
    tags=["analysis"],
    summary="Forecast accuracy KPIs and data-quality counts",
)
def summary(
    request: Request,
    start_date: date = Query(default=SCOPE_START, description="Inclusive local delivery date"),
    end_date: date = Query(default=SCOPE_END, description="Inclusive local delivery date"),
    resolution: Literal["30m", "1h"] = Query(default="30m"),
):
    return _service(request).summary(start_date, end_date, resolution)


@router.get(
    "/timeseries",
    response_model=TimeseriesResponse,
    responses=RESPONSES,
    tags=["analysis"],
    summary="Aligned actuals, decision-time forecasts, latest vintages and errors",
)
def timeseries(
    request: Request,
    start_date: date = Query(default=SCOPE_START),
    end_date: date = Query(default=SCOPE_END),
    resolution: Literal["30m", "1h"] = Query(default="30m"),
):
    return _service(request).timeseries(start_date, end_date, resolution)


@router.get(
    "/accuracy",
    response_model=AccuracyResponse,
    responses=RESPONSES,
    tags=["analysis"],
    summary="Grouped accuracy metrics (day, ISO week, hour of day, lead-time bucket)",
)
def accuracy(
    request: Request,
    start_date: date = Query(default=SCOPE_START),
    end_date: date = Query(default=SCOPE_END),
    group_by: Literal["day", "week", "hour", "lead_time"] = Query(default="day"),
    resolution: Literal["30m", "1h"] = Query(default="30m"),
):
    return _service(request).accuracy(start_date, end_date, group_by, resolution)


@router.get(
    "/errors",
    response_model=ErrorsResponse,
    responses=RESPONSES,
    tags=["analysis"],
    summary="Largest forecast-error intervals",
)
def errors(
    request: Request,
    start_date: date = Query(default=SCOPE_START),
    end_date: date = Query(default=SCOPE_END),
    limit: int = Query(default=20, ge=1, le=500),
    sort: Literal["absolute_error", "underforecast", "overforecast"] = Query(
        default="absolute_error"
    ),
    resolution: Literal["30m", "1h"] = Query(default="30m"),
):
    return _service(request).errors(
        start_date, end_date, sort=sort, limit=limit, resolution=resolution
    )


@router.get(
    "/forecast-vintages",
    response_model=VintagesResponse,
    responses=RESPONSES,
    tags=["analysis"],
    summary="Forecast vintages for a delivery date, with cutoff eligibility",
)
def forecast_vintages(
    request: Request,
    delivery_date: date = Query(description="Local delivery date in January 2026"),
    interval_start: str | None = Query(
        default=None,
        description="Optional ISO-8601 delivery interval start; returns that interval's vintages",
    ),
):
    return _service(request).vintages(delivery_date, interval_start)


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    responses={**RESPONSES, 403: {"model": ErrorResponse}},
    tags=["operations"],
    summary="Administrative refresh from Elexon (disabled unless explicitly enabled)",
)
def refresh(
    request: Request,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
):
    service = _service(request)
    settings = service.settings
    if not settings.allow_refresh_endpoint or not settings.refresh_token:
        raise DatasetUnavailable(
            "The refresh endpoint is disabled. Rebuild the dataset with "
            "`python -m app.data.refresh` and redeploy, or enable ALLOW_REFRESH_ENDPOINT "
            "and set REFRESH_TOKEN."
        )
    if not x_admin_token or not hmac.compare_digest(x_admin_token, settings.refresh_token):
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "forbidden",
                    "message": "A valid X-Admin-Token header is required.",
                    "details": None,
                }
            },
        )
    from ..data.refresh import refresh as run_refresh

    result = run_refresh(output=settings.dataset_path())
    service.reload()
    return {
        "status": "ok",
        "message": "Dataset refreshed from Elexon and reloaded.",
        "generated_at": result.get("generated_at"),
        "completeness": result.get("completeness"),
    }
