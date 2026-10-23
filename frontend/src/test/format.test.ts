import { describe, expect, it } from "vitest";

import {
  formatDateLong,
  formatDayShort,
  formatLead,
  formatNumber,
  formatPercent,
  formatSigned,
  statusLabel,
} from "../utils/format";

describe("formatNumber", () => {
  it("formats integers with thousands separators", () => {
    expect(formatNumber(1234567)).toBe("1,234,567");
  });

  it("returns an em dash for null, undefined and NaN", () => {
    expect(formatNumber(null)).toBe("—");
    expect(formatNumber(undefined)).toBe("—");
    expect(formatNumber(Number.NaN)).toBe("—");
  });

  it("supports one and two decimal places", () => {
    expect(formatNumber(12.345, 1)).toBe("12.3");
    expect(formatNumber(12.345, 2)).toBe("12.35");
  });
});

describe("formatSigned", () => {
  it("adds a plus sign for overforecast and a true minus for underforecast", () => {
    expect(formatSigned(250)).toBe("+250");
    expect(formatSigned(-250)).toBe("−250");
    expect(formatSigned(0)).toBe("0");
    expect(formatSigned(null)).toBe("—");
  });
});

describe("formatPercent", () => {
  it("formats with the requested precision and a percent sign", () => {
    expect(formatPercent(91.6667, 2)).toBe("91.67%");
    expect(formatPercent(null)).toBe("—");
  });
});

describe("date and lead formatting", () => {
  it("formats ISO instants in Europe/London", () => {
    expect(formatDayShort("2026-01-15")).toBe("15 Jan");
    expect(formatDateLong("2026-01-15")).toBe("15 January 2026");
  });

  it("formats lead hours to one decimal", () => {
    expect(formatLead(25.5)).toBe("25.5 h");
    expect(formatLead(null)).toBe("—");
  });
});

describe("labels", () => {
  it("maps audit statuses to readable labels", () => {
    expect(statusLabel("matched")).toBe("Matched");
    expect(statusLabel("missing_forecast")).toBe("Missing forecast");
    expect(statusLabel("missing_actual")).toBe("Missing actual");
    expect(statusLabel("missing_both")).toBe("Missing both");
    expect(statusLabel("other")).toBe("other");
  });
});
