import { useCallback, useEffect, useRef, useState } from "react";

import {
  getDailyAccuracy,
  getErrors,
  getHourlyAccuracy,
  getSummary,
  getTimeseries,
  type ApiError,
} from "../services/api";
import type {
  AccuracyResponse,
  ErrorsResponse,
  Resolution,
  SummaryResponse,
  TimeseriesResponse,
} from "../types/api";
import type { DateRange } from "../utils/derived";

export interface DashboardData {
  summary: SummaryResponse;
  timeseries: TimeseriesResponse;
  daily: AccuracyResponse;
  hourly: AccuracyResponse;
  underforecast: ErrorsResponse;
  overforecast: ErrorsResponse;
}

interface DashboardState {
  data: DashboardData | null;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
}

export function useDashboardData(range: DateRange, resolution: Resolution) {
  const [state, setState] = useState<DashboardState>({
    data: null,
    loading: true,
    refreshing: false,
    error: null,
  });
  const [nonce, setNonce] = useState(0);
  const requestId = useRef(0);

  useEffect(() => {
    const controller = new AbortController();
    const id = ++requestId.current;
    setState((previous) => ({
      ...previous,
      loading: previous.data === null,
      refreshing: previous.data !== null,
      error: null,
    }));
    Promise.all([
      getSummary(range.start, range.end, resolution, controller.signal),
      getTimeseries(range.start, range.end, resolution, controller.signal),
      getDailyAccuracy(range.start, range.end, resolution, controller.signal),
      getHourlyAccuracy(range.start, range.end, resolution, controller.signal),
      getErrors(range.start, range.end, "underforecast", 6, resolution, controller.signal),
      getErrors(range.start, range.end, "overforecast", 6, resolution, controller.signal),
    ])
      .then(([summary, timeseries, daily, hourly, underforecast, overforecast]) => {
        if (id !== requestId.current) return;
        setState({
          data: { summary, timeseries, daily, hourly, underforecast, overforecast },
          loading: false,
          refreshing: false,
          error: null,
        });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        if (id !== requestId.current) return;
        const message =
          error instanceof Error
            ? error.message
            : "The analysis could not be loaded. Please retry.";
        setState((previous) => ({
          data: previous.data,
          loading: false,
          refreshing: false,
          error: message,
        }));
      });
    return () => controller.abort();
  }, [range.start, range.end, resolution, nonce]);

  const retry = useCallback(() => setNonce((value) => value + 1), []);

  return { ...state, retry, apiError: null as ApiError | null };
}
