import { describe, expect, it } from "vitest";

import type { TimeseriesPoint } from "../types/api";
import { buildCsvFilename, CSV_COLUMNS, toCsv } from "../utils/csv";

const row: TimeseriesPoint = {
  interval_start_utc: "2026-01-01T00:00:00Z",
  interval_start_local: "2026-01-01T00:00:00+00:00",
  delivery_date: "2026-01-01",
  settlement_period: 1,
  actual_mw: 1000,
  decision_forecast_mw: 1200,
  latest_forecast_mw: null,
  decision_forecast_publish_time_utc: "2025-12-30T22:30:00Z",
  decision_forecast_lead_hours: 25.5,
  latest_forecast_publish_time_utc: null,
  error_mw: 200,
  abs_error_mw: 200,
  status: "matched",
  decision_forecast_is_latest: false,
  forecast_alignment: "hourly_step_hold_to_half_hour",
};

describe("toCsv", () => {
  it("writes the documented header and one row per interval", () => {
    const csv = toCsv([row, { ...row, interval_start_utc: "2026-01-01T00:30:00Z" }]);
    const lines = csv.split("\r\n");
    expect(lines[0]).toBe(CSV_COLUMNS.join(","));
    expect(lines).toHaveLength(3);
  });

  it("preserves nulls as empty cells rather than zero", () => {
    const cells = toCsv([row]).split("\r\n")[1].split(",");
    const latestIndex = CSV_COLUMNS.indexOf("latest_forecast_mw");
    expect(cells[latestIndex]).toBe("");
  });

  it("quotes and escapes cells containing commas or quotes", () => {
    const csv = toCsv([{ ...row, status: 'matched,"quoted"' as TimeseriesPoint["status"] }]);
    expect(csv).toContain('"matched,""quoted"""');
  });

  it("builds a deterministic filename from the range", () => {
    expect(buildCsvFilename("2026-01-01", "2026-01-31")).toBe(
      "windscope-aligned-data_2026-01-01_2026-01-31.csv",
    );
  });
});
