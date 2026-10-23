import type {
  AccuracyResponse,
  ErrorsResponse,
  HealthResponse,
  MetadataResponse,
  Resolution,
  SummaryResponse,
  TimeseriesResponse,
  VintagesResponse,
} from "../types/api";

const RAW_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
export const API_BASE = RAW_BASE.replace(/\/+$/, "");

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;

  constructor(message: string, status: number, code = "api_error", details: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function request<T>(
  path: string,
  params: Record<string, string | number | undefined> = {},
  signal?: AbortSignal,
): Promise<T> {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  const queryString = query.toString();
  const url = `${API_BASE}${path}${queryString ? `?${queryString}` : ""}`;
  let response: Response;
  try {
    response = await fetch(url, {
      signal,
      headers: { Accept: "application/json" },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(
      `Cannot reach the WindScope API at ${API_BASE}. Check that the backend is running and VITE_API_BASE_URL is correct.`,
      0,
      "network_error",
    );
  }
  if (!response.ok) {
    let code = `http_${response.status}`;
    let message = `The API returned HTTP ${response.status}.`;
    let details: unknown = null;
    try {
      const payload = (await response.json()) as {
        error?: { code?: string; message?: string; details?: unknown };
      };
      if (payload.error) {
        code = payload.error.code ?? code;
        message = payload.error.message ?? message;
        details = payload.error.details ?? null;
      }
    } catch {
      // Non-JSON error body: keep the status-based message.
    }
    throw new ApiError(message, response.status, code, details);
  }
  return (await response.json()) as T;
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>("/api/v1/health", {}, signal);
}

export function getMetadata(signal?: AbortSignal): Promise<MetadataResponse> {
  return request<MetadataResponse>("/api/v1/metadata", {}, signal);
}

export function getSummary(
  start: string,
  end: string,
  resolution: Resolution,
  signal?: AbortSignal,
): Promise<SummaryResponse> {
  return request<SummaryResponse>(
    "/api/v1/summary",
    { start_date: start, end_date: end, resolution },
    signal,
  );
}

export function getTimeseries(
  start: string,
  end: string,
  resolution: Resolution,
  signal?: AbortSignal,
): Promise<TimeseriesResponse> {
  return request<TimeseriesResponse>(
    "/api/v1/timeseries",
    { start_date: start, end_date: end, resolution },
    signal,
  );
}

export function getDailyAccuracy(
  start: string,
  end: string,
  resolution: Resolution,
  signal?: AbortSignal,
): Promise<AccuracyResponse> {
  return request<AccuracyResponse>(
    "/api/v1/accuracy",
    { start_date: start, end_date: end, group_by: "day", resolution },
    signal,
  );
}

export function getHourlyAccuracy(
  start: string,
  end: string,
  resolution: Resolution,
  signal?: AbortSignal,
): Promise<AccuracyResponse> {
  return request<AccuracyResponse>(
    "/api/v1/accuracy",
    { start_date: start, end_date: end, group_by: "hour", resolution },
    signal,
  );
}

export function getErrors(
  start: string,
  end: string,
  sort: "absolute_error" | "underforecast" | "overforecast",
  limit: number,
  resolution: Resolution,
  signal?: AbortSignal,
): Promise<ErrorsResponse> {
  return request<ErrorsResponse>(
    "/api/v1/errors",
    { start_date: start, end_date: end, sort, limit, resolution },
    signal,
  );
}

export function getVintages(
  deliveryDate: string,
  intervalStart: string,
  signal?: AbortSignal,
): Promise<VintagesResponse> {
  return request<VintagesResponse>(
    "/api/v1/forecast-vintages",
    { delivery_date: deliveryDate, interval_start: intervalStart },
    signal,
  );
}
