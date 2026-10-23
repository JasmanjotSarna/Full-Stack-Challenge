import type { SummaryResponse } from "../types/api";
import { formatLead, formatNumber, formatPercent, formatSigned } from "../utils/format";

interface KpiGridProps {
  summary: SummaryResponse;
}

export function KpiGrid({ summary }: KpiGridProps) {
  const { metrics, data_quality: quality, lead_time: lead, revision } = summary;

  return (
    <section className="kpi-grid" aria-label="Forecast accuracy summary">
      <article className="kpi-card accent-teal">
        <div className="kpi-label" title="Mean absolute error of decision-time forecast vs actual">
          MAE
        </div>
        <div className="kpi-value tabular">
          {formatNumber(metrics.mae_mw)}
          <span className="unit">MW</span>
        </div>
        <div className="kpi-foot">
          <span>Mean absolute error</span>
        </div>
        <div className="kpi-bar">
          <span style={{ width: `${barWidth(metrics.mae_mw, metrics.wape_pct)}%` }} />
        </div>
      </article>

      <article className="kpi-card accent-navy">
        <div className="kpi-label" title="Root mean squared error; penalises large misses">
          RMSE
        </div>
        <div className="kpi-value tabular">
          {formatNumber(metrics.rmse_mw)}
          <span className="unit">MW</span>
        </div>
        <div className="kpi-foot">
          <span>Root mean squared</span>
        </div>
        <div className="kpi-bar">
          <span style={{ width: `${barWidth(metrics.rmse_mw, metrics.wape_pct)}%` }} />
        </div>
      </article>

      <article className="kpi-card accent-amber">
        <div
          className="kpi-label"
          title="Mean(forecast − actual). Positive = forecast exceeded actual generation"
        >
          Bias
        </div>
        <div className="kpi-value tabular">
          {formatSigned(metrics.bias_mw)}
          <span className="unit">MW</span>
        </div>
        <div className="kpi-foot">
          <span>{biasDirection(metrics.bias_mw)}</span>
        </div>
        <div className="kpi-bar">
          <span
            style={{
              width: `${barWidth(metrics.bias_mw, metrics.wape_pct)}%`,
              background: "var(--amber)",
            }}
          />
        </div>
      </article>

      <article className="kpi-card accent-teal">
        <div className="kpi-label" title="sum(|error|) / sum(actual). Robust to low-generation periods">
          WAPE
        </div>
        <div className="kpi-value tabular">
          {formatPercent(metrics.wape_pct, 2)}
        </div>
        <div className="kpi-foot">
          <span>Weighted absolute error</span>
        </div>
        <div className="kpi-bar">
          <span style={{ width: `${barWidth(metrics.wape_pct, null)}%` }} />
        </div>
      </article>

      <article className="kpi-card accent-blue">
        <div
          className="kpi-label"
          title="Coverage = intervals with actual and eligible forecast, divided by expected intervals"
        >
          Coverage
        </div>
        <div className="kpi-value tabular">{formatPercent(metrics.coverage_pct, 2)}</div>
        <div className="kpi-foot">
          <span className="strong">
            {formatNumber(quality.matched_intervals)} /{" "}
            {formatNumber(quality.expected_intervals)}
          </span>
          <span>intervals</span>
        </div>
        <div className="kpi-bar">
          <span style={{ width: `${Math.min(100, metrics.coverage_pct ?? 0)}%` }} />
        </div>
      </article>

      <article className="kpi-card accent-navy">
        <div
          className="kpi-label"
          title="Decision-time forecast lead to the start of each delivery interval"
        >
          Lead time
        </div>
        <div className="kpi-value tabular">
          {formatNumber(lead.median_hours, 1)}
          <span className="unit">h median</span>
        </div>
        <div className="kpi-foot">
          <span>
            {formatLead(lead.min_hours)} – {formatLead(lead.max_hours)}
          </span>
        </div>
        <div className="kpi-bar">
          <span
            style={{
              width: `${barWidth(metrics.mape_pct, null)}%`,
              background: "var(--blue)",
            }}
          />
        </div>
        <span className="sr-only">
          MAPE {formatPercent(metrics.mape_pct, 2)} across {metrics.mape_sample_count} intervals;
          mean absolute post-cutoff revision {formatNumber(revision.mean_abs_revision_mw)} MW.
        </span>
      </article>
    </section>
  );
}

function barWidth(value: number | null, ceiling: number | null): number {
  if (value === null || !Number.isFinite(value)) return 0;
  const denominator = ceiling && ceiling > 0 ? ceiling : 100;
  return Math.max(3, Math.min(100, (Math.abs(value) / denominator) * 100));
}

function biasDirection(value: number | null): string {
  if (value === null) return "Not defined";
  if (value > 0) return "Overforecast on average";
  if (value < 0) return "Underforecast on average";
  return "Unbiased on average";
}
