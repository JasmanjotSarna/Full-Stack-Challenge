"""Pydantic response models — the API contract."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class Period(BaseModel):
    start: str
    end: str
    timezone: str


class CutoffPolicyModel(BaseModel):
    id: str
    mode: str
    local_time: str
    lead_hours: float
    timezone: str
    description: str
    is_analytical_assumption: bool
    eligibility_boundary: str
    selection_rule: str


class Metrics(BaseModel):
    sample_count: int
    expected_intervals: int
    coverage_pct: float | None
    mae_mw: float | None
    rmse_mw: float | None
    bias_mw: float | None
    wape_pct: float | None
    mape_pct: float | None
    mape_sample_count: int
    mape_excluded_count: int
    mape_min_actual_mw: float
    wape_undefined_reason: str | None = None
    mape_undefined_reason: str | None = None


class DataQuality(BaseModel):
    expected_intervals: int
    matched_intervals: int
    missing_forecast_intervals: int
    missing_actual_intervals: int
    missing_both_intervals: int
    valid_pairs: int


class LeadTime(BaseModel):
    sample_count: int
    min_hours: float | None
    median_hours: float | None
    max_hours: float | None


class Revision(BaseModel):
    sample_count: int
    mean_abs_revision_mw: float | None
    max_abs_revision_mw: float | None
    mean_signed_revision_mw: float | None
    note: str


class SummaryResponse(BaseModel):
    period: Period
    resolution: Literal["30m", "1h"]
    metrics: Metrics
    data_quality: DataQuality
    cutoff_policy: CutoffPolicyModel
    lead_time: LeadTime
    revision: Revision
    sign_convention: str
    forecast_alignment: str
    notes: list[str]


class TimeseriesPoint(BaseModel):
    interval_start_utc: str
    interval_start_local: str
    delivery_date: str
    settlement_period: int
    actual_mw: float | None
    decision_forecast_mw: float | None
    latest_forecast_mw: float | None
    decision_forecast_publish_time_utc: str | None
    decision_forecast_lead_hours: float | None
    latest_forecast_publish_time_utc: str | None
    error_mw: float | None
    abs_error_mw: float | None
    status: str
    decision_forecast_is_latest: bool
    forecast_alignment: str


class TimeseriesResponse(BaseModel):
    period: Period
    resolution: Literal["30m", "1h"]
    count: int
    points: list[TimeseriesPoint]
    notes: list[str]


class AccuracyGroup(BaseModel):
    group: str
    label: str
    expected_intervals: int
    sample_count: int
    mae_mw: float | None
    rmse_mw: float | None
    bias_mw: float | None
    wape_pct: float | None
    mape_pct: float | None
    mape_sample_count: int
    coverage_pct: float | None
    missing_forecast_intervals: int
    missing_actual_intervals: int


class AccuracyResponse(BaseModel):
    period: Period
    group_by: Literal["day", "week", "hour", "lead_time"]
    groups: list[AccuracyGroup]
    sign_convention: str


class ErrorInterval(BaseModel):
    interval_start_utc: str
    interval_start_local: str
    delivery_date: str
    settlement_period: int
    actual_mw: float | None
    decision_forecast_mw: float | None
    decision_forecast_publish_time_utc: str | None
    decision_forecast_lead_hours: float | None
    error_mw: float | None
    abs_error_mw: float | None
    direction: str


class ErrorsResponse(BaseModel):
    period: Period
    sort: Literal["absolute_error", "underforecast", "overforecast"]
    limit: int
    count: int
    errors: list[ErrorInterval]
    sign_convention: str


class Vintage(BaseModel):
    publish_time_utc: str
    forecast_mw: float
    eligible: bool
    is_selected: bool
    lead_hours: float


class VintageInterval(BaseModel):
    interval_start_utc: str
    interval_start_local: str
    settlement_period: int
    actual_mw: float | None
    decision_forecast_mw: float | None
    decision_forecast_publish_time_utc: str | None
    status: str
    available_vintages: int
    eligible_vintages: int


class VintagesResponse(BaseModel):
    delivery_date: str
    timezone: str
    cutoff_policy: CutoffPolicyModel
    interval_start_utc: str | None = None
    cutoff_utc: str | None = None
    selected_publish_time_utc: str | None = None
    vintages: list[Vintage] = Field(default_factory=list)
    intervals: list[VintageInterval] = Field(default_factory=list)
    note: str


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    version: str
    environment: str
    dataset_available: bool
    real_source_data: bool
    test_data: bool
    dataset_generated_at: str | None
    last_successful_refresh: str | None
    uptime_seconds: float
    cutoff_policy: str


class MetadataResponse(BaseModel):
    product: str
    scope: dict[str, Any]
    dataset: dict[str, Any]
    cutoff_policy: CutoffPolicyModel
    timezone: str
    sources: list[dict[str, Any]]
    metrics_policy: dict[str, Any]
    assumptions: list[str]
    warnings: list[str]


class RefreshResponse(BaseModel):
    status: str
    message: str
    generated_at: str | None = None
    completeness: dict[str, Any] | None = None
