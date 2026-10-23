import type { TimeseriesPoint } from "../types/api";

export const CSV_COLUMNS = [
  "interval_start_utc",
  "interval_start_local",
  "delivery_date",
  "settlement_period",
  "actual_mw",
  "decision_forecast_mw",
  "latest_forecast_mw",
  "error_mw",
  "abs_error_mw",
  "decision_forecast_publish_time_utc",
  "decision_forecast_lead_hours",
  "status",
  "forecast_alignment",
] as const;

function escapeCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  const text = String(value);
  if (/[",\r\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

export function toCsv(rows: TimeseriesPoint[]): string {
  const header = CSV_COLUMNS.join(",");
  const body = rows.map((row) =>
    [
      row.interval_start_utc,
      row.interval_start_local,
      row.delivery_date,
      row.settlement_period,
      row.actual_mw,
      row.decision_forecast_mw,
      row.latest_forecast_mw,
      row.error_mw,
      row.abs_error_mw,
      row.decision_forecast_publish_time_utc,
      row.decision_forecast_lead_hours,
      row.status,
      row.forecast_alignment,
    ]
      .map(escapeCell)
      .join(","),
  );
  return [header, ...body].join("\r\n");
}

export function buildCsvFilename(start: string, end: string): string {
  return `windscope-aligned-data_${start}_${end}.csv`;
}

export function downloadCsv(filename: string, content: string): void {
  // Excel needs a UTF-8 BOM for non-ASCII characters in headers/values.
  const blob = new Blob([`\uFEFF${content}`], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}
