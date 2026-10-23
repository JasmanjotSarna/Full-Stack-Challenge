import type { CutoffPolicy } from "../types/api";

interface PolicyStripProps {
  policy: CutoffPolicy | undefined;
  loading: boolean;
}

export function PolicyStrip({ policy, loading }: PolicyStripProps) {
  if (loading && !policy) {
    return (
      <div className="policy-strip" role="status">
        <span className="assumption-tag">Decision cutoff</span>
        <span>Loading decision-cutoff policy…</span>
      </div>
    );
  }

  const label = policy
    ? `${policy.local_time} ${policy.timezone} on D-1`
    : "00:00 Europe/London on D-1";

  return (
    <div className="policy-strip">
      <span className="assumption-tag">Decision cutoff</span>
      <span>
        Latest <strong>WINDFOR</strong> vintage published on or before{" "}
        <strong>{label}</strong> — only those vintages feed every accuracy metric.
      </span>
      <span className="divider" aria-hidden="true" />
      <span>
        <strong>Analytical assumption</strong>, not a verified market gate-closure time.
        Configurable via <code>CUTOFF_MODE</code>, <code>CUTOFF_LOCAL_TIME</code>.
      </span>
    </div>
  );
}
