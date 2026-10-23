export type Resolution = "30m" | "1h";
export type GroupBy = "day" | "week" | "hour" | "lead_time";

export interface Period {
  start: string;
  end: string;
  timezone: string;
}

export interface CutoffPolicy {
  id: string;
  mode: string;
  local_time: string;
  lead_hours: number;
  timezone: string;
  description: string;
  is_analytical_assumption: boolean;
  eligibility_boundary: string;
  selection_rule: string;
}

export interface Metrics {
  sample_count: number;
  expected_intervals: number;
  coverage_pct: number | null;
  mae_mw: number | null;
  rmse_mw: number | null;
  bias_mw: number | null;
  wape_pct: number | null;
  mape_pct: number | null;
  mape_sample_count: number;
  mape_excluded_count: number;
  mape_min_actual_mw: number;
  wape_undefined_reason: string | null;
  mape_undefined_reason: string | null;
}

export interface DataQuality {
  expected_intervals: number;
  matched_intervals: number;
  missing_forecast_intervals: number;
  missing_actual_intervals: number;
  missing_both_intervals: number;
  valid_pairs: number;
}

export interface LeadTime {
  sample_count: number;
  min_hours: number | null;
  median_hours: number | null;
  max_hours: number | null;
}

export interface Revision {
  sample_count: number;
  mean_abs_revision_mw: number | null;
  max_abs_revision_mw: number | null;
  mean_signed_revision_mw: number | null;
  note: string;
}

export interface SummaryResponse {
  period: Period;
  resolution: Resolution;
  metrics: Metrics;
  data_quality: DataQuality;
  cutoff_policy: CutoffPolicy;
  lead_time: LeadTime;
  revision: Revision;
  sign_convention: string;
  forecast_alignment: string;
  notes: string[];
}

export interface TimeseriesPoint {
  interval_start_utc: string;
  interval_start_local: string;
  delivery_date: string;
  settlement_period: number;
  actual_mw: number | null;
  decision_forecast_mw: number | null;
  latest_forecast_mw: number | null;
  decision_forecast_publish_time_utc: string | null;
  decision_forecast_lead_hours: number | null;
  latest_forecast_publish_time_utc: string | null;
  error_mw: number | null;
  abs_error_mw: number | null;
  status: "matched" | "missing_forecast" | "missing_actual" | "missing_both";
  decision_forecast_is_latest: boolean;
  forecast_alignment: string;
}

export interface TimeseriesResponse {
  period: Period;
  resolution: Resolution;
  count: number;
  points: TimeseriesPoint[];
  notes: string[];
}

export interface AccuracyGroup {
  group: string;
  label: string;
  expected_intervals: number;
  sample_count: number;
  mae_mw: number | null;
  rmse_mw: number | null;
  bias_mw: number | null;
  wape_pct: number | null;
  mape_pct: number | null;
  mape_sample_count: number;
  coverage_pct: number | null;
  missing_forecast_intervals: number;
  missing_actual_intervals: number;
}

export interface AccuracyResponse {
  period: Period;
  group_by: GroupBy;
  groups: AccuracyGroup[];
  sign_convention: string;
}

export interface ErrorInterval {
  interval_start_utc: string;
  interval_start_local: string;
  delivery_date: string;
  settlement_period: number;
  actual_mw: number | null;
  decision_forecast_mw: number | null;
  decision_forecast_publish_time_utc: string | null;
  decision_forecast_lead_hours: number | null;
  error_mw: number | null;
  abs_error_mw: number | null;
  direction: "overforecast" | "underforecast" | "exact";
}

export interface ErrorsResponse {
  period: Period;
  sort: "absolute_error" | "underforecast" | "overforecast";
  limit: number;
  count: number;
  errors: ErrorInterval[];
  sign_convention: string;
}

export interface Vintage {
  publish_time_utc: string;
  forecast_mw: number;
  eligible: boolean;
  is_selected: boolean;
  lead_hours: number;
}

export interface VintageInterval {
  interval_start_utc: string;
  interval_start_local: string;
  settlement_period: number;
  actual_mw: number | null;
  decision_forecast_mw: number | null;
  decision_forecast_publish_time_utc: string | null;
  status: string;
  available_vintages: number;
  eligible_vintages: number;
}

export interface VintagesResponse {
  delivery_date: string;
  timezone: string;
  cutoff_policy: CutoffPolicy;
  interval_start_utc: string | null;
  cutoff_utc: string | null;
  selected_publish_time_utc: string | null;
  vintages: Vintage[];
  intervals: VintageInterval[];
  note: string;
}

export interface DatasetMetadata {
  available: boolean;
  real_source_data: boolean;
  test_data: boolean;
  last_successful_refresh: string | null;
  generated_at: string | null;
  fetched_at: string | null;
  date_range: { start: string; end: string; timezone: string };
  actual_resolution: string;
  forecast_resolution: string;
  alignment: { method?: string; note?: string };
  completeness: Partial<DataQuality> & { coverage_pct?: number | null };
  validation: Record<string, unknown>;
  fetch: Record<string, unknown>;
  refresh_mode: string;
  warnings: string[];
}

export interface MetadataResponse {
  product: string;
  scope: { start: string; end: string; timezone: string; description: string };
  dataset: DatasetMetadata;
  cutoff_policy: CutoffPolicy;
  timezone: string;
  sources: Array<{
    dataset: string;
    name: string;
    url: string;
    description: string;
  }>;
  metrics_policy: Record<string, string>;
  assumptions: string[];
  warnings: string[];
}

export interface HealthResponse {
  status: "ok" | "degraded";
  service: string;
  version: string;
  environment: string;
  dataset_available: boolean;
  real_source_data: boolean;
  test_data: boolean;
  dataset_generated_at: string | null;
  last_successful_refresh: string | null;
  uptime_seconds: number;
  cutoff_policy: string;
}
