import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TooltipContentProps } from "recharts";

import type { AccuracyGroup, AccuracyResponse } from "../types/api";
import { formatDayShort, formatNumber, formatPercent } from "../utils/format";
import { ChartTooltip, mw, signedMw } from "./ChartTooltip";

interface DailyAccuracyChartProps {
  data: AccuracyResponse;
}

export function DailyAccuracyChart({ data }: DailyAccuracyChartProps) {
  return (
    <section className="panel" aria-label="Daily forecast accuracy">
      <div className="panel-head with-border">
        <div>
          <h2 className="panel-title">Daily accuracy</h2>
          <p className="panel-sub">
            MAE bars and signed bias line by Europe/London delivery date. Days with missing
            forecasts show lower coverage, not imputed error.
          </p>
        </div>
        <div className="chart-legend" aria-hidden="true">
          <span className="legend-item">
            <span className="legend-swatch block" style={{ background: "#0e7a6d" }} />
            MAE
          </span>
          <span className="legend-item">
            <span className="legend-swatch" style={{ background: "#b45309" }} />
            Bias
          </span>
        </div>
      </div>
      <div className="panel-body">
        <div className="chart-frame" style={{ height: 250 }}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data.groups} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="#e6edf5" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="group"
                tick={{ fontSize: 10, fill: "#8796a8" }}
                tickLine={false}
                axisLine={{ stroke: "#c3d0df" }}
                minTickGap={16}
                tickFormatter={(value: string) => formatDayShort(value)}
              />
              <YAxis
                tick={{ fontSize: 10, fill: "#5b6d82" }}
                tickLine={false}
                axisLine={false}
                width={44}
                tickFormatter={(value: number) => `${Math.round(value / 1000)}k`}
              />
              <Tooltip content={(props) => <DailyTooltip {...props} />} />
              <Bar dataKey="mae_mw" fill="#0e7a6d" isAnimationActive={false} radius={[2, 2, 0, 0]} />
              <Line
                type="monotone"
                dataKey="bias_mw"
                stroke="#b45309"
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <p className="axis-note">Y axis in MW. Bias above zero means the forecast ran high.</p>
      </div>
    </section>
  );
}

function DailyTooltip({ active, payload }: TooltipContentProps) {
  if (!active || !payload || payload.length === 0) return null;
  const group = payload[0]?.payload as AccuracyGroup | undefined;
  if (!group) return null;
  return (
    <ChartTooltip
      title={formatDayShort(group.group)}
      rows={[
        { label: "MAE", value: mw(group.mae_mw) },
        { label: "Bias", value: signedMw(group.bias_mw) },
        { label: "WAPE", value: formatPercent(group.wape_pct, 2) },
        {
          label: "Coverage",
          value: `${formatPercent(group.coverage_pct, 1)} (${formatNumber(group.sample_count)}/${formatNumber(group.expected_intervals)})`,
        },
        {
          label: "Missing forecasts",
          value: formatNumber(group.missing_forecast_intervals),
        },
      ]}
    />
  );
}
