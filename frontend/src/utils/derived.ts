import type { TimeseriesPoint } from "../types/api";

export interface HistogramBin {
  lower: number;
  upper: number;
  count: number;
  positive: boolean;
  label: string;
}

function niceStep(raw: number): number {
  if (!Number.isFinite(raw) || raw <= 0) return 1;
  const magnitude = Math.pow(10, Math.floor(Math.log10(raw)));
  const normalised = raw / magnitude;
  const nice = normalised <= 1 ? 1 : normalised <= 2 ? 2 : normalised <= 2.5 ? 2.5 : normalised <= 5 ? 5 : 10;
  return nice * magnitude;
}

export function buildHistogram(values: number[], targetBins = 21): HistogramBin[] {
  const clean = values.filter((value) => Number.isFinite(value));
  if (clean.length === 0) return [];
  const maxAbs = Math.max(...clean.map((value) => Math.abs(value)));
  if (maxAbs === 0) {
    return [{ lower: -1, upper: 1, count: clean.length, positive: false, label: "0" }];
  }
  const step = niceStep((maxAbs * 2) / Math.max(8, targetBins - 1));
  const bound = Math.ceil(maxAbs / step) * step;
  const binCount = Math.max(2, Math.round((bound * 2) / step));
  const bins: HistogramBin[] = [];
  for (let index = 0; index < binCount; index += 1) {
    const lower = -bound + index * step;
    const upper = lower + step;
    bins.push({
      lower,
      upper,
      count: 0,
      positive: lower + step / 2 > 0,
      label: `${Math.round(lower)}–${Math.round(upper)}`,
    });
  }
  for (const value of clean) {
    let index = Math.floor((value + bound) / step);
    if (index >= bins.length) index = bins.length - 1;
    if (index < 0) index = 0;
    bins[index].count += 1;
  }
  return bins;
}

export type SortKey =
  | "interval_start_utc"
  | "actual_mw"
  | "decision_forecast_mw"
  | "error_mw"
  | "abs_error_mw"
  | "decision_forecast_lead_hours";

export type SortDirection = "asc" | "desc";

export function sortRows(
  rows: TimeseriesPoint[],
  key: SortKey,
  direction: SortDirection,
): TimeseriesPoint[] {
  const factor = direction === "asc" ? 1 : -1;
  return [...rows].sort((left, right) => {
    const a = left[key];
    const b = right[key];
    if (a === null || a === undefined) return b === null || b === undefined ? 0 : 1;
    if (b === null || b === undefined) return -1;
    if (typeof a === "number" && typeof b === "number") return (a - b) * factor;
    return String(a).localeCompare(String(b)) * factor;
  });
}

export function filterRows(
  rows: TimeseriesPoint[],
  filters: { status: string; query: string },
): TimeseriesPoint[] {
  const query = filters.query.trim().toLowerCase();
  return rows.filter((row) => {
    if (filters.status !== "all" && row.status !== filters.status) return false;
    if (!query) return true;
    return (
      row.delivery_date.includes(query) ||
      row.interval_start_local.toLowerCase().includes(query) ||
      row.status.toLowerCase().includes(query)
    );
  });
}

export function paginate<T>(rows: T[], page: number, pageSize: number): T[] {
  const start = Math.max(0, (page - 1) * pageSize);
  return rows.slice(start, start + pageSize);
}

export function totalPages(total: number, pageSize: number): number {
  return Math.max(1, Math.ceil(total / pageSize));
}

export interface DateRange {
  start: string;
  end: string;
}

export const MONTH_START = "2026-01-01";
export const MONTH_END = "2026-01-31";

export const RANGE_PRESETS: Array<{ label: string; start: string; end: string }> = [
  { label: "Full month", start: MONTH_START, end: MONTH_END },
  { label: "1–7 Jan", start: "2026-01-01", end: "2026-01-07" },
  { label: "8–14 Jan", start: "2026-01-08", end: "2026-01-14" },
  { label: "15–21 Jan", start: "2026-01-15", end: "2026-01-21" },
  { label: "22–31 Jan", start: "2026-01-22", end: "2026-01-31" },
];

export function clampRange(start: string, end: string): DateRange {
  const safeStart = start < MONTH_START ? MONTH_START : start > MONTH_END ? MONTH_END : start;
  const safeEnd = end < MONTH_START ? MONTH_START : end > MONTH_END ? MONTH_END : end;
  if (safeStart > safeEnd) return { start: safeEnd, end: safeStart };
  return { start: safeStart, end: safeEnd };
}
