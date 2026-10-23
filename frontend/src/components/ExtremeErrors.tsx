import type { ErrorsResponse } from "../types/api";
import { formatInterval, formatLead, formatNumber, formatSigned } from "../utils/format";

interface ExtremeErrorsProps {
  title: string;
  response: ErrorsResponse;
  direction: "underforecast" | "overforecast";
}

export function ExtremeErrors({ title, response, direction }: ExtremeErrorsProps) {
  const rows = response.errors.filter((row) =>
    direction === "underforecast" ? (row.error_mw ?? 0) < 0 : (row.error_mw ?? 0) > 0,
  );

  return (
    <section className="panel" aria-label={title}>
      <div className="panel-head with-border">
        <div>
          <h2 className="panel-title">{title}</h2>
          <p className="panel-sub">
            {direction === "underforecast"
              ? "Actual generation beat the decision-time forecast by the most (MW)."
              : "The decision-time forecast exceeded actual generation by the most (MW)."}
          </p>
        </div>
      </div>
      <div className="panel-body">
        {rows.length === 0 ? (
          <div className="empty-inline">No intervals of this type in the selected period.</div>
        ) : (
          <div className="extreme-list">
            {rows.map((row) => (
              <div className="extreme-item" key={row.interval_start_utc}>
                <div>
                  <div className="extreme-when">{formatInterval(row.interval_start_local)}</div>
                  <div className="extreme-meta">
                    Actual {formatNumber(row.actual_mw)} MW · forecast{" "}
                    {formatNumber(row.decision_forecast_mw)} MW · lead{" "}
                    {formatLead(row.decision_forecast_lead_hours)}
                  </div>
                </div>
                <div className={`extreme-value ${direction === "underforecast" ? "under" : "over"}`}>
                  {formatSigned(row.error_mw)} MW
                  <small>{direction === "underforecast" ? "under" : "over"}</small>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
