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
import { formatNumber } from "../utils/format";
import { ChartTooltip, mw, signedMw } from "./ChartTooltip";

interface HourlyProfileChartProps {
  data: AccuracyResponse;
}

export function HourlyProfileChart({ data }: HourlyProfileChartProps) {
  const groups = [...data.groups].sort((left, right) => Number(left.group) - Number(right.group));

  return (
    <section className="panel" aria-label="Accuracy by hour of day">
      <div className="panel-head with-border">
        <div>
          <h2 className="panel-title">Hour-of-day profile</h2>
          <p className="panel-sub">
            MAE and bias by local hour of day across the selected period. Useful for spotting
            morning-ramp and evening-peak weaknesses.
          </p>
        </div>
        <div className="chart-legend" aria-hidden="true">
          <span className="legend-item">
            <span className="legend-swatch block" style={{ background: "#1d4ed8" }} />
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
            <ComposedChart data={groups} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="#e6edf5" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="group"
                tick={{ fontSize: 10, fill: "#8796a8" }}
                tickLine={false}
                axisLine={{ stroke: "#c3d0df" }}
                interval={2}
                tickFormatter={(value: string) => `${value.padStart(2, "0")}:00`}
              />
              <YAxis
                tick={{ fontSize: 10, fill: "#5b6d82" }}
                tickLine={false}
                axisLine={false}
                width={44}
                tickFormatter={(value: number) => `${Math.round(value / 1000)}k`}
              />
              <Tooltip content={(props) => <HourlyTooltip {...props} />} />
              <Bar dataKey="mae_mw" fill="#1d4ed8" isAnimationActive={false} radius={[2, 2, 0, 0]} />
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
        <p className="axis-note">Y axis in MW; hour labels are Europe/London local time.</p>
      </div>
    </section>
  );
}

function HourlyTooltip({ active, payload }: TooltipContentProps) {
  if (!active || !payload || payload.length === 0) return null;
  const group = payload[0]?.payload as AccuracyGroup | undefined;
  if (!group) return null;
  return (
    <ChartTooltip
      title={group.label}
      rows={[
        { label: "MAE", value: mw(group.mae_mw) },
        { label: "Bias", value: signedMw(group.bias_mw) },
        { label: "RMSE", value: mw(group.rmse_mw) },
        {
          label: "Samples",
          value: `${formatNumber(group.sample_count)} of ${formatNumber(group.expected_intervals)}`,
        },
      ]}
    />
  );
}
