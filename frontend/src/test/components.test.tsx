import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AlignedDataTable } from "../components/AlignedDataTable";
import { KpiGrid } from "../components/KpiGrid";
import type { SummaryResponse, TimeseriesPoint } from "../types/api";

const summary: SummaryResponse = {
  period: { start: "2026-01-01", end: "2026-01-31", timezone: "Europe/London" },
  resolution: "30m",
  metrics: {
    sample_count: 1364,
    expected_intervals: 1488,
    coverage_pct: 91.6667,
    mae_mw: 2218.7977,
    rmse_mw: 2690.3571,
    bias_mw: 1890.6246,
    wape_pct: 19.2113,
    mape_pct: 23.6431,
    mape_sample_count: 1364,
    mape_excluded_count: 0,
    mape_min_actual_mw: 100,
    wape_undefined_reason: null,
    mape_undefined_reason: null,
  },
  data_quality: {
    expected_intervals: 1488,
    matched_intervals: 1364,
    missing_forecast_intervals: 124,
    missing_actual_intervals: 0,
    missing_both_intervals: 0,
    valid_pairs: 1364,
  },
  cutoff_policy: {
    id: "previous_day@00:00[Europe/London]",
    mode: "previous_day",
    local_time: "00:00",
    lead_hours: 24,
    timezone: "Europe/London",
    description: "Analytical assumption",
    is_analytical_assumption: true,
    eligibility_boundary: "publish_time_utc <= cutoff_utc (inclusive)",
    selection_rule: "Latest eligible",
  },
  lead_time: { sample_count: 1364, min_hours: 25.5, median_hours: 36.25, max_hours: 47 },
  revision: {
    sample_count: 1364,
    mean_abs_revision_mw: 1188.2097,
    max_abs_revision_mw: 5139,
    mean_signed_revision_mw: -318.2185,
    note: "Hindsight only",
  },
  sign_convention: "forecast − actual",
  forecast_alignment: "hourly_step_hold_to_half_hour",
  notes: [],
};

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

describe("KpiGrid", () => {
  it("renders the real metric values with units and direction", () => {
    render(<KpiGrid summary={summary} />);
    expect(screen.getByText("2,219")).toBeInTheDocument();
    expect(screen.getByText("2,690")).toBeInTheDocument();
    expect(screen.getByText("+1,891")).toBeInTheDocument();
    expect(screen.getByText("19.21%")).toBeInTheDocument();
    expect(screen.getByText("91.67%")).toBeInTheDocument();
    expect(screen.getByText("Overforecast on average")).toBeInTheDocument();
    expect(screen.getByText("36.3")).toBeInTheDocument();
  });

  it("shows an em dash rather than zero when a metric is undefined", () => {
    const undefinedSummary: SummaryResponse = {
      ...summary,
      metrics: { ...summary.metrics, mae_mw: null, bias_mw: null, mape_pct: null },
    };
    render(<KpiGrid summary={undefinedSummary} />);
    expect(screen.getByText("Not defined")).toBeInTheDocument();
  });
});

describe("AlignedDataTable", () => {
  const rows = [
    point({ interval_start_utc: "2026-01-01T00:00:00Z", delivery_date: "2026-01-01" }),
    point({
      interval_start_utc: "2026-01-02T00:00:00Z",
      interval_start_local: "2026-01-02T00:00:00+00:00",
      delivery_date: "2026-01-02",
      status: "missing_forecast",
      decision_forecast_mw: null,
      error_mw: null,
      abs_error_mw: null,
      decision_forecast_publish_time_utc: null,
    }),
  ];

  it("renders nulls as em dashes and shows the status label", () => {
    render(
      <AlignedDataTable
        points={rows}
        range={{ start: "2026-01-01", end: "2026-01-02" }}
        onInspect={() => {}}
      />,
    );
    const missingRow = screen.getByLabelText(/Inspect interval 02 Jan, 00:00/i);
    expect(within(missingRow).getByText("Missing forecast")).toBeInTheDocument();
    expect(within(missingRow).getAllByText("—").length).toBeGreaterThan(0);
  });

  it("opens the vintage audit when a row is clicked", () => {
    const onInspect = vi.fn();
    render(
      <AlignedDataTable
        points={rows}
        range={{ start: "2026-01-01", end: "2026-01-02" }}
        onInspect={onInspect}
      />,
    );
    fireEvent.click(screen.getByLabelText(/Inspect interval 01 Jan, 00:00/i));
    expect(onInspect).toHaveBeenCalledWith(rows[0]);
  });

  it("filters to only missing forecasts", () => {
    render(
      <AlignedDataTable
        points={rows}
        range={{ start: "2026-01-01", end: "2026-01-02" }}
        onInspect={() => {}}
      />,
    );
    fireEvent.change(screen.getByLabelText("Filter by status"), {
      target: { value: "missing_forecast" },
    });
    expect(screen.queryByLabelText(/Inspect interval 01 Jan, 00:00/i)).not.toBeInTheDocument();
    const missingRow = screen.getByLabelText(/Inspect interval 02 Jan, 00:00/i);
    expect(within(missingRow).getByText("Missing forecast")).toBeInTheDocument();
  });
});
