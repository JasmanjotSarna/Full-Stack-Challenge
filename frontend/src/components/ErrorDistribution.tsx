import { Bar, BarChart, Cell, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TooltipContentProps } from "recharts";

import type { TimeseriesPoint } from "../types/api";
import { buildHistogram } from "../utils/derived";
import { formatNumber } from "../utils/format";
import { ChartTooltip } from "./ChartTooltip";

interface ErrorDistributionProps {
  points: TimeseriesPoint[];
}

interface BinRow {
  label: string;
  count: number;
  positive: boolean;
}

export function ErrorDistribution({ points }: ErrorDistributionProps) {
  const errors = points
    .map((point) => point.error_mw)
    .filter((value): value is number => value !== null);
  const bins = buildHistogram(errors, 25);
  const data: BinRow[] = bins.map((bin) => ({
    label: bin.label,
    count: bin.count,
    positive: bin.positive,
  }));
  const maxCount = Math.max(...data.map((row) => row.count), 1);

  return (
    <section className="panel" aria-label="Forecast error distribution">
      <div className="panel-head with-border">
        <div>
          <h2 className="panel-title">Error distribution</h2>
          <p className="panel-sub">
            Count of intervals by error (forecast âˆ’ actual), MW. Amber is overforecast; blue is
            underforecast.
          </p>
        </div>
      </div>
      <div className="panel-body">
        {data.length === 0 ? (
          <div className="empty-inline">No matched intervals in the selected period.</div>
        ) : (
          <>
            <div className="chart-frame" style={{ height: 250 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid stroke="#e6edf5" strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 10, fill: "#8796a8" }}
                    tickLine={false}
                    axisLine={{ stroke: "#c3d0df" }}
                    interval={Math.max(2, Math.floor(data.length / 6))}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: "#5b6d82" }}
                    tickLine={false}
                    axisLine={false}
                    width={34}
                    allowDecimals={false}
                    domain={[0, Math.ceil(maxCount * 1.12)]}
                  />
                  <Tooltip
                    cursor={{ fill: "#eef3f8" }}
                    content={(props) => <BinTooltip {...props} total={errors.length} />}
                  />
                  <Bar dataKey="count" isAnimationActive={false} radius={[2, 2, 0, 0]}>
                    {data.map((row) => (
                      <Cell key={row.label} fill={row.positive ? "#c97a1a" : "#1d4ed8"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="axis-note">
              {formatNumber(errors.length)} matched intervals. Bins are equal-width across the
              observed range.
            </p>
          </>
        )}
      </div>
    </section>
  );
}

function BinTooltip({
  active,
  payload,
  total,
}: TooltipContentProps & { total: number }) {
  if (!active || !payload || payload.length === 0) return null;
  const row = payload[0]?.payload as BinRow | undefined;
  if (!row) return null;
  return (
    <ChartTooltip
      title={`Error ${row.label} MW`}
      rows={[
        { label: "Intervals", value: formatNumber(row.count) },
        {
          label: "Share of matched",
          value: `${((row.count / Math.max(total, 1)) * 100).toFixed(1)}%`,
        },
      ]}
      note={row.positive ? "Overforecast side" : "Underforecast side"}
    />
  );
}
