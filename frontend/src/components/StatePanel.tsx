interface StatePanelProps {
  title: string;
  message: string;
  detail?: string | null;
  tone?: "error" | "info";
  actionLabel?: string;
  onAction?: () => void;
}

export function StatePanel({
  title,
  message,
  detail,
  tone = "info",
  actionLabel,
  onAction,
}: StatePanelProps) {
  return (
    <div className="state-panel" role={tone === "error" ? "alert" : "status"}>
      <div className={`state-icon${tone === "error" ? " error" : ""}`} aria-hidden="true">
        {tone === "error" ? "!" : "…"}
      </div>
      <h2 className="state-title">{title}</h2>
      <p className="state-message">{message}</p>
      {detail ? <div className="state-detail">{detail}</div> : null}
      {actionLabel && onAction ? (
        <button type="button" className="btn btn-primary" onClick={onAction}>
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading dashboard">
      <div className="loading-grid">
        {Array.from({ length: 6 }).map((_, index) => (
          <div className="skeleton kpi" key={index} />
        ))}
      </div>
      <div className="skeleton panel" style={{ marginBottom: 14 }} />
      <div className="loading-grid">
        {Array.from({ length: 3 }).map((_, index) => (
          <div className="skeleton panel" key={index} />
        ))}
      </div>
    </div>
  );
}
