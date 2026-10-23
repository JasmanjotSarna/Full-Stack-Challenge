import { describe, expect, it } from "vitest";

import type { TimeseriesPoint } from "../types/api";
import { buildHistogram, clampRange, filterRows, paginate, sortRows, totalPages } from "../utils/derived";

function point(overrides: Partial<TimeseriesPoint>): TimeseriesPoint {
  return {
    interval_start_utc: "2026-01-01T00:00:00Z",
    interval_start_local: "2026-01-01T00:00:00+00:00",
    delivery_date: "2026-01-01",
    settlement_period: 1,
    actual_mw: 1000,
    decision_forecast_mw: 1200,
    latest_forecast_mw: 1100,
    decision_forecast_publish_time_utc: "2025-12-30T22:30:00Z",
    decision_forecast_lead_hours: 25.5,
    latest_forecast_publish_time_utc: "2026-01-01T22:30:00Z",
    error_mw: 200,
    abs_error_mw: 200,
    status: "matched",
    decision_forecast_is_latest: false,
    forecast_alignment: "hourly_step_hold_to_half_hour",
    ...overrides,
  };
}

describe("buildHistogram", () => {
  it("returns no bins for an empty input", () => {
    expect(buildHistogram([])).toEqual([]);
  });

  it("assigns every finite value to exactly one bin", () => {
    const bins = buildHistogram([-500, -100, 0, 100, 500, 1200], 10);
    expect(bins.reduce((total, bin) => total + bin.count, 0)).toBe(6);
    expect(bins.length).toBeGreaterThan(1);
    expect(bins.some((bin) => bin.positive)).toBe(true);
    expect(bins.some((bin) => !bin.positive)).toBe(true);
  });

  it("keeps all-zero errors in a single bin", () => {
    const bins = buildHistogram([0, 0, 0]);
    expect(bins).toHaveLength(1);
    expect(bins[0].count).toBe(3);
  });

  it("ignores non-finite values", () => {
    const bins = buildHistogram([100, Number.NaN, Number.POSITIVE_INFINITY]);
    expect(bins.reduce((total, bin) => total + bin.count, 0)).toBe(1);
  });
});

describe("sortRows", () => {
  it("sorts numbers and keeps nulls last in both directions", () => {
    const rows = [
      point({ interval_start_utc: "a", error_mw: 100 }),
      point({ interval_start_utc: "b", error_mw: null }),
      point({ interval_start_utc: "c", error_mw: -50 }),
    ];
    const ascending = sortRows(rows, "error_mw", "asc");
    expect(ascending.map((row) => row.error_mw)).toEqual([-50, 100, null]);
    const descending = sortRows(rows, "error_mw", "desc");
    expect(descending.map((row) => row.error_mw)).toEqual([100, -50, null]);
  });

  it("does not mutate the source array", () => {
    const rows = [point({ interval_start_utc: "b" }), point({ interval_start_utc: "a" })];
    sortRows(rows, "interval_start_utc", "asc");
    expect(rows[0].interval_start_utc).toBe("b");
  });
});

describe("filterRows", () => {
  const rows = [
    point({ interval_start_utc: "a", delivery_date: "2026-01-01", status: "matched" }),
    point({ interval_start_utc: "b", delivery_date: "2026-01-02", status: "missing_forecast" }),
  ];

  it("filters by status", () => {
    expect(filterRows(rows, { status: "missing_forecast", query: "" })).toHaveLength(1);
    expect(filterRows(rows, { status: "all", query: "" })).toHaveLength(2);
  });

  it("searches date, interval and status", () => {
    expect(filterRows(rows, { status: "all", query: "2026-01-02" })).toHaveLength(1);
    expect(filterRows(rows, { status: "all", query: "missing" })).toHaveLength(1);
    expect(filterRows(rows, { status: "all", query: "nope" })).toHaveLength(0);
  });
});

describe("pagination", () => {
  it("clamps pages and computes totals", () => {
    expect(totalPages(0, 25)).toBe(1);
    expect(totalPages(51, 25)).toBe(3);
    expect(paginate([1, 2, 3, 4, 5], 2, 2)).toEqual([3, 4]);
    expect(paginate([1, 2, 3], 0, 2)).toEqual([1, 2]);
  });
});

describe("clampRange", () => {
  it("clamps to January 2026 and swaps reversed inputs", () => {
    expect(clampRange("2025-12-01", "2026-02-01")).toEqual({
      start: "2026-01-01",
      end: "2026-01-31",
    });
    expect(clampRange("2026-01-20", "2026-01-05")).toEqual({
      start: "2026-01-05",
      end: "2026-01-20",
    });
  });
});
