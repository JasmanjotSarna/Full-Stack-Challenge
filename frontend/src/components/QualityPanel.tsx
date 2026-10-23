import type { MetadataResponse, SummaryResponse } from "../types/api";
import {
  formatDateTime,
  formatLead,
  formatNumber,
  formatPercent,
  formatSigned,
} from "../utils/format";

interface QualityPanelProps {
  summary: SummaryResponse;
  metadata: MetadataResponse | null;
}

export function QualityPanel({ summary, metadata }: QualityPanelProps) {
  const quality = summary.data_quality;
  const warnings = metadata?.dataset.warnings ?? [];
  const validation = metadata?.dataset.validation as
    | Record<string, { received?: number; accepted?: number; warnings?: string[] }>
    | undefined;

  return (
    <section className="panel" aria-label="Data quality and cutoff audit">
      <div className="panel-head with-border">
        <div>
          <h2 className="panel-title">Data quality &amp; cutoff audit</h2>
          <p className="panel-sub">
            Missing forecasts are real gaps at the decision cutoff, not fetch failures. They are
            reported and excluded — never back-filled from a later vintage.
          </p>
        </div>
        <span className="data-status" style={{ background: "#f8fafc", color: "#25384d", borderColor: "#dce4ee" }}>
          <span className={quality.missing_forecast_intervals > 0 ? "status-dot warn" : "status-dot"} />
          {quality.missing_forecast_intervals > 0
            ? `${formatNumber(quality.missing_forecast_intervals)} gaps preserved`
            : "Complete coverage"}
        </span>
      </div>
      <div className="panel-body">
        <div className="fact-grid" style={{ marginBottom: 16 }}>
          <div className="fact">
            <div className="fact-label">Expected intervals</div>
            <div className="fact-value">{formatNumber(quality.expected_intervals)}</div>
            <div className="fact-note">Every settlement period in range</div>
          </div>
          <div className="fact">
            <div className="fact-label">Valid matched pairs</div>
            <div className="fact-value">{formatNumber(quality.valid_pairs)}</div>
            <div className="fact-note">Used in all accuracy metrics</div>
          </div>
          <div className="fact">
            <div className="fact-label">Missing forecast</div>
            <div className="fact-value">
              {formatNumber(quality.missing_forecast_intervals)}
              <small> intervals</small>
            </div>
            <div className="fact-note">No eligible vintage at cutoff</div>
          </div>
          <div className="fact">
            <div className="fact-label">Missing actual</div>
            <div className="fact-value">{formatNumber(quality.missing_actual_intervals)}</div>
            <div className="fact-note">FUELHH value absent</div>
          </div>
          <div className="fact">
            <div className="fact-label">Coverage</div>
            <div className="fact-value">{formatPercent(summary.metrics.coverage_pct, 2)}</div>
            <div className="fact-note">Valid pairs ÷ expected</div>
          </div>
          <div className="fact">
            <div className="fact-label">MAPE denominator</div>
            <div className="fact-value">
              {formatNumber(summary.metrics.mape_sample_count)}
              <small> / {formatNumber(summary.metrics.sample_count)}</small>
            </div>
            <div className="fact-note">
              Actual ≥ {formatNumber(summary.metrics.mape_min_actual_mw)} MW;{" "}
              {formatNumber(summary.metrics.mape_excluded_count)} excluded
            </div>
          </div>
        </div>

        <dl className="definition-list" style={{ marginBottom: 16 }}>
          <dt>Cutoff rule</dt>
          <dd>{summary.cutoff_policy.eligibility_boundary} · {summary.cutoff_policy.local_time} {summary.cutoff_policy.timezone} on D-1</dd>
          <dt>Selection</dt>
          <dd>{summary.cutoff_policy.selection_rule}</dd>
          <dt>Lead time</dt>
          <dd>
            {formatLead(summary.lead_time.min_hours)} to {formatLead(summary.lead_time.max_hours)};
            median {formatLead(summary.lead_time.median_hours)}
          </dd>
          <dt>Post-cutoff revision</dt>
          <dd>
            Mean absolute {formatNumber(summary.revision.mean_abs_revision_mw)} MW; mean signed{" "}
            {formatSigned(summary.revision.mean_signed_revision_mw)} MW (hindsight only)
          </dd>
          <dt>Forecast alignment</dt>
          <dd>
            {summary.forecast_alignment.replace(/_/g, " ")} — hourly WINDFOR step-held onto both
            half-hours; no interpolation
          </dd>
          <dt>Data generated</dt>
          <dd>{formatDateTime(metadata?.dataset.generated_at ?? null)}</dd>
        </dl>

        {validation ? (
          <div className="grid-2" style={{ marginBottom: warnings.length > 0 ? 14 : 0 }}>
            {Object.entries(validation).map(([source, report]) => (
              <div className="callout" key={source}>
                <strong style={{ textTransform: "uppercase", letterSpacing: "0.05em", fontSize: 11 }}>
                  {source}
                </strong>
                <div style={{ marginTop: 4 }}>
                  Received {formatNumber(report.received ?? null)} · accepted{" "}
                  {formatNumber(report.accepted ?? null)}
                </div>
              </div>
            ))}
          </div>
        ) : null}

        {warnings.length > 0 ? (
          <div className="callout amber">
            <strong>Dataset warning:</strong>
            <ul className="warning-list" style={{ marginTop: 6 }}>
              {warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </section>
  );
}
