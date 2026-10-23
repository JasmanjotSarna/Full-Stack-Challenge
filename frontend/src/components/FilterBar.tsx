import type { Resolution } from "../types/api";
import {
  clampRange,
  MONTH_END,
  MONTH_START,
  RANGE_PRESETS,
  type DateRange,
} from "../utils/derived";
import { formatNumber } from "../utils/format";

interface FilterBarProps {
  range: DateRange;
  resolution: Resolution;
  sampleCount: number;
  expectedCount: number;
  refreshing: boolean;
  onRangeChange: (range: DateRange) => void;
  onResolutionChange: (resolution: Resolution) => void;
}

export function FilterBar({
  range,
  resolution,
  sampleCount,
  expectedCount,
  refreshing,
  onRangeChange,
  onResolutionChange,
}: FilterBarProps) {
  const activePreset = RANGE_PRESETS.find(
    (preset) => preset.start === range.start && preset.end === range.end,
  );

  return (
    <section className="filterbar" aria-label="Analysis filters">
      <div className="filter-group">
        <span className="filter-label">Period presets</span>
        <div className="preset-row">
          {RANGE_PRESETS.map((preset) => (
            <button
              key={preset.label}
              type="button"
              className={`chip${activePreset?.label === preset.label ? " active" : ""}`}
              onClick={() => onRangeChange({ start: preset.start, end: preset.end })}
              aria-pressed={activePreset?.label === preset.label}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      <div className="filter-group">
        <span className="filter-label">Delivery dates (Europe/London)</span>
        <div className="date-field">
          <input
            type="date"
            value={range.start}
            min={MONTH_START}
            max={MONTH_END}
            aria-label="Start delivery date"
            onChange={(event) =>
              onRangeChange(clampRange(event.target.value, range.end))
            }
          />
          <span>to</span>
          <input
            type="date"
            value={range.end}
            min={MONTH_START}
            max={MONTH_END}
            aria-label="End delivery date"
            onChange={(event) =>
              onRangeChange(clampRange(range.start, event.target.value))
            }
          />
        </div>
      </div>

      <div className="filter-group">
        <span className="filter-label">Granularity</span>
        <div className="segmented" role="group" aria-label="Time granularity">
          <button
            type="button"
            className={resolution === "30m" ? "active" : ""}
            aria-pressed={resolution === "30m"}
            onClick={() => onResolutionChange("30m")}
          >
            Settlement 30 min
          </button>
          <button
            type="button"
            className={resolution === "1h" ? "active" : ""}
            aria-pressed={resolution === "1h"}
            onClick={() => onResolutionChange("1h")}
          >
            Hourly
          </button>
        </div>
      </div>

      <div className="filter-spacer" />

      <span className="range-caption">
        {refreshing ? (
          <span className="refreshing">
            <span className="spinner" aria-hidden="true" />
            Updating…
          </span>
        ) : (
          <>
            <strong>{formatNumber(sampleCount)}</strong> valid matched intervals of{" "}
            <strong>{formatNumber(expectedCount)}</strong> expected
          </>
        )}
      </span>
    </section>
  );
}
