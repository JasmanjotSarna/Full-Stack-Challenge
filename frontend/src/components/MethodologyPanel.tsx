import type { MetadataResponse } from "../types/api";

interface MethodologyPanelProps {
  metadata: MetadataResponse | null;
}

export function MethodologyPanel({ metadata }: MethodologyPanelProps) {
  if (!metadata) {
    return null;
  }
  const policy = metadata.metrics_policy;

  return (
    <section className="panel" aria-label="Methodology and sources">
      <div className="panel-head with-border">
        <div>
          <h2 className="panel-title">Methodology &amp; sources</h2>
          <p className="panel-sub">
            Definitions are fixed for every endpoint and export. This product analyses forecast
            accuracy only; it does not model demand, prices or procurement volumes.
          </p>
        </div>
      </div>
      <div className="panel-body">
        <div className="grid-2">
          <div>
            <h3 className="filter-label" style={{ marginBottom: 8 }}>
              Metric definitions
            </h3>
            <dl className="definition-list">
              <dt>MAE</dt>
              <dd>{policy.mae}</dd>
              <dt>RMSE</dt>
              <dd>{policy.rmse}</dd>
              <dt>Bias</dt>
              <dd>{policy.bias}</dd>
              <dt>WAPE</dt>
              <dd>{policy.wape}</dd>
              <dt>MAPE</dt>
              <dd>{policy.mape}</dd>
              <dt>Coverage</dt>
              <dd>{policy.coverage}</dd>
              <dt>Missing data</dt>
              <dd>{policy.missing_policy}</dd>
            </dl>
          </div>
          <div>
            <h3 className="filter-label" style={{ marginBottom: 8 }}>
              Official sources
            </h3>
            <div className="source-list" style={{ marginBottom: 14 }}>
              {metadata.sources.map((source) => (
                <div className="source-item" key={source.dataset}>
                  <div className="source-name">
                    {source.dataset} — {source.name}
                  </div>
                  <div className="source-desc">{source.description}</div>
                  <a
                    className="source-desc"
                    href={source.url}
                    target="_blank"
                    rel="noreferrer noopener"
                  >
                    {source.url}
                  </a>
                </div>
              ))}
            </div>
            <h3 className="filter-label" style={{ marginBottom: 8 }}>
              Assumptions
            </h3>
            <ul className="assumption-list">
              {metadata.assumptions.map((assumption) => (
                <li key={assumption}>{assumption}</li>
              ))}
            </ul>
          </div>
        </div>
        <div className="callout" style={{ marginTop: 14 }}>
          <strong>Scope: </strong>
          {metadata.scope.description} All timestamps are handled in {metadata.scope.timezone}; API
          values that carry an instant are ISO-8601 UTC.
        </div>
      </div>
    </section>
  );
}
