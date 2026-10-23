"""WindScope FastAPI application entry point."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.routes import health, router
from .models.schemas import HealthResponse
from .core.config import Settings, get_settings
from .core.logging import configure_logging, get_logger
from .data.elexon_client import ElexonAPIError
from .services.analysis_service import AnalysisService, DatasetUnavailable, InvalidRequest

logger = get_logger(__name__)


def _error(status: int, code: str, message: str, details=None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details}},
    )


def create_app(
    service: AnalysisService | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging(settings.log_level)
        if getattr(app.state, "service", None) is None:
            app.state.service = AnalysisService.load(settings)
        if not app.state.service.available:
            logger.warning(
                "starting without dataset",
                extra={"event": "dataset_unavailable"},
            )
        yield

    app = FastAPI(
        title="WindScope API",
        version=settings.app_version,
        description=(
            "Forecast-intelligence API for national GB wind generation, January 2026. "
            "Selects the forecast that was available at a configurable day-ahead decision "
            "cutoff and measures its error against Elexon actuals. This is not a trading or "
            "demand-forecasting system."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.state.service = service

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Admin-Token"],
        max_age=600,
    )

    @app.middleware("http")
    async def operational_headers(request: Request, call_next):
        started = time.monotonic()
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Process-Time-Ms"] = str(
            round((time.monotonic() - started) * 1000, 2)
        )
        return response

    app.include_router(router)

    @app.get("/", include_in_schema=False)
    def root():
        return {
            "product": "WindScope — UK Wind Forecast Intelligence",
            "version": settings.app_version,
            "api": "/api/v1",
            "documentation": "/docs",
            "notice": (
                "Wind forecast accuracy analytics for January 2026. Not a procurement, demand "
                "or trading system."
            ),
        }

    @app.get(
        "/health",
        response_model=HealthResponse,
        responses={503: {"model": HealthResponse, "description": "Dataset not ready"}},
        tags=["operations"],
        summary="Service and dataset readiness (root alias)",
    )
    def root_health(request: Request, response: Response):
        return health(request, response)

    @app.exception_handler(InvalidRequest)
    async def invalid_request_handler(_request: Request, exc: InvalidRequest):
        return _error(400, "invalid_request", str(exc))

    @app.exception_handler(DatasetUnavailable)
    async def dataset_unavailable_handler(_request: Request, exc: DatasetUnavailable):
        return _error(503, "dataset_unavailable", str(exc))

    @app.exception_handler(ElexonAPIError)
    async def elexon_error_handler(_request: Request, exc: ElexonAPIError):
        logger.error("elexon upstream error", extra={"event": "elexon_upstream_error"})
        return _error(
            502,
            "upstream_error",
            f"Elexon data could not be retrieved: {exc}",
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, exc: RequestValidationError):
        details = [
            {"location": ".".join(str(part) for part in item.get("loc", [])), "message": item.get("msg")}
            for item in exc.errors()
        ]
        return _error(422, "validation_error", "One or more request parameters are invalid.", details)

    @app.exception_handler(HTTPException)
    async def http_error_handler(_request: Request, exc: HTTPException):
        return _error(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_request: Request, exc: Exception):
        logger.exception("unhandled error", extra={"event": "unhandled_error"})
        return _error(500, "internal_error", "An unexpected server error occurred.")

    return app


app = create_app()


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    logging.getLogger(__name__)
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
