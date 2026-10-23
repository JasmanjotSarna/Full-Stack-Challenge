import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TooltipContentProps } from "recharts";

import type { TimeseriesPoint } from "../types/api";
import { formatDayShort, formatFullDateTime } from "../utils/format";
import { ChartTooltip, mw, signedMw, type TooltipRow } from "./ChartTooltip";

interface ForecastChartProps {
  points: TimeseriesPoint[];
}

interface ChartRow {
  x: string;
  actual: number | null;
  decision: number | null;
  latest: number | null;
  error: number | null;
  status: string;
}

export function ForecastChart({ points }: ForecastChartProps) {
  const data: ChartRow[] = points.map((point) => ({
    x: point.interval_start_utc,
    actual: point.actual_mw,
    decision: point.decision_forecast_mw,
    latest: point.latest_forecast_mw,
    error: point.error_mw,
    status: point.status,
  }));

  return (
    <section className="panel mb-14" aria-label="Actual versus forecast wind generation">
      <div className="panel-head with-border">
        <div>
          <h2 className="panel-title">Actual vs decision-time forecast</h2>
          <p className="panel-sub">
            National wind generation in MW. The decision-time line is the latest vintage available
            at the cutoff; the latest line is hindsight only and never used in metrics. Gaps are
            preserved â€” no forward fill.
          </p>
        </div>
        <div className="chart-legend" aria-hidden="true">
          <span className="legend-item">
            <span className="legend-swatch" style={{ background: "#0e7a6d" }} />
            Actual
          </span>
          <span className="legend-item">
            <span className="legend-swatch" style={{ background: "#b45309" }} />
            Decision-time forecast
          </span>
          <span className="legend-item">
            <span className="legend-swatch dashed" />
            Latest vintage (hindsight)
          </span>
        </div>
      </div>
      <div className="panel-body">
        <div className="chart-frame" style={{ height: 370 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
              <CartesianGrid stroke="#e6edf5" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="x"
                tick={{ fontSize: 11, fill: "#5b6d82" }}
                tickLine={false}
                axisLine={{ stroke: "#c3d0df" }}
                minTickGap={48}
                tickFormatter={(value: string) => formatDayShort(value.slice(0, 10))}
              />
              <YAxis
                tick={{ fontSize: 11, fill: "#5b6d82" }}
                tickLine={false}
                axisLine={false}
                width={56}
                tickFormatter={(value: number) => `${Math.round(value / 1000)}k`}
                label={{
                  value: "MW",
                  angle: -90,
                  position: "insideLeft",
                  style: { fontSize: 11, fill: "#8796a8" },
                }}
              />
              <Tooltip content={(props) => <ForecastTooltip {...props} />} />
              <Legend wrapperStyle={{ display: "none" }} />
              <Line
                type="linear"
                dataKey="actual"
                name="Actual"
                stroke="#0e7a6d"
                strokeWidth={1.8}
                dot={false}
                isAnimationActive={false}
                connectNulls={false}
              />
              <Line
                type="linear"
                dataKey="decision"
                name="Decision-time forecast"
                stroke="#b45309"
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
                connectNulls={false}
              />
              <Line
                type="linear"
                dataKey="latest"
                name="Latest vintage (hindsight)"
                stroke="#8494a7"
                strokeWidth={1.2}
                strokeDasharray="4 3"
                dot={false}
                isAnimationActive={false}
                connectNulls={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className="axis-note">
          Europe/London delivery time. Half-hourly actuals; hourly WINDFOR forecasts step-held onto
          both half-hours. Hover for exact values and the interval error.
        </p>
      </div>
    </section>
  );
}

function ForecastTooltip({ active, payload }: TooltipContentProps) {
  if (!active || !payload || payload.length === 0) return null;
  const row = payload[0]?.payload as ChartRow | undefined;
  if (!row) return null;
  const rows: TooltipRow[] = [
    { label: "Actual", value: mw(row.actual) },
    { label: "Decision forecast", value: mw(row.decision) },
    { label: "Latest (hindsight)", value: mw(row.latest) },
  ];
  if (row.error !== null) {
    rows.push({
      label: "Error (forecast âˆ’ actual)",
      value: signedMw(row.error),
    });
  }
  return (
    <ChartTooltip
      title={formatFullDateTime(row.x)}
      rows={rows}
      note={
        row.status === "matched"
          ? undefined
          : `Status: ${row.status.replace(/_/g, " ")}. Excluded from accuracy metrics.`
      }
    />
  );
}
