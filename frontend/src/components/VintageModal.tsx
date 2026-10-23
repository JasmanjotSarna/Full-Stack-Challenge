import { useEffect, useState } from "react";

import { getVintages } from "../services/api";
import type { VintagesResponse } from "../types/api";
import {
  formatDateTime,
  formatFullDateTime,
  formatLead,
  formatNumber,
  formatSigned,
} from "../utils/format";

interface VintageModalProps {
  deliveryDate: string;
  intervalStartUtc: string;
  onClose: () => void;
}

export function VintageModal({ deliveryDate, intervalStartUtc, onClose }: VintageModalProps) {
  const [data, setData] = useState<VintagesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setError(null);
    getVintages(deliveryDate, intervalStartUtc, controller.signal)
      .then((response) => {
        if (!controller.signal.aborted) setData(response);
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setError(reason instanceof Error ? reason.message : "Vintages could not be loaded.");
      });
    return () => controller.abort();
  }, [deliveryDate, intervalStartUtc]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose]);

  const selected = data?.vintages.find((vintage) => vintage.is_selected);
  const actualVisible = data?.intervals.find(
    (interval) => interval.interval_start_utc === data.interval_start_utc,
  );

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="vintage-title"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="modal">
        <div className="modal-head">
          <div>
            <h2 className="modal-title" id="vintage-title">
              Forecast vintage audit
            </h2>
            <p className="modal-sub">
              {formatFullDateTime(intervalStartUtc)} · delivery date {deliveryDate} · Europe/London
            </p>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close audit">
            ✕
          </button>
        </div>
        <div className="modal-body">
          {error ? (
            <div className="callout amber">{error}</div>
          ) : !data ? (
            <div className="empty-inline">Loading vintages…</div>
          ) : (
            <>
              <div className="fact-grid" style={{ marginBottom: 14 }}>
                <div className="fact">
                  <div className="fact-label">Decision cutoff</div>
                  <div className="fact-value" style={{ fontSize: 13 }}>
                    {formatDateTime(data.cutoff_utc)}
                  </div>
                  <div className="fact-note">{data.cutoff_policy.id}</div>
                </div>
                <div className="fact">
                  <div className="fact-label">Selected vintage</div>
                  <div className="fact-value" style={{ fontSize: 13 }}>
                    {data.selected_publish_time_utc
                      ? formatDateTime(data.selected_publish_time_utc)
                      : "None eligible"}
                  </div>
                  <div className="fact-note">
                    {selected ? `${formatNumber(selected.forecast_mw)} MW` : "No forecast at cutoff"}
                  </div>
                </div>
                <div className="fact">
                  <div className="fact-label">Actual</div>
                  <div className="fact-value" style={{ fontSize: 13 }}>
                    {actualVisible ? `${formatNumber(actualVisible.actual_mw)} MW` : "—"}
                  </div>
                  <div className="fact-note">
                    {selected && actualVisible?.actual_mw != null
                      ? `Error ${formatSigned(selected.forecast_mw - actualVisible.actual_mw)} MW`
                      : "Hindsight values are shown for learning only"}
                  </div>
                </div>
              </div>

              <div className="callout teal" style={{ marginBottom: 14 }}>
                <strong>How to read this:</strong> only rows marked <em>eligible</em> existed at the
                cutoff. The selected row is the latest eligible vintage and is the only forecast used
                for this interval in every accuracy metric. Later rows are shown for hindsight
                revision analysis and were not used in the metrics.
              </div>

              <div className="table-wrap">
                <table className="vintage-table">
                  <caption className="sr-only">
                    WINDFOR vintages for the selected delivery interval, with cutoff eligibility
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Published (Europe/London)</th>
                      <th scope="col">Forecast MW</th>
                      <th scope="col">Lead to interval</th>
                      <th scope="col">Cutoff status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.vintages.length === 0 ? (
                      <tr>
                        <td colSpan={4}>
                          <div className="empty-inline">
                            No WINDFOR publication covers this interval.
                          </div>
                        </td>
                      </tr>
                    ) : (
                      data.vintages.map((vintage) => (
                        <tr
                          key={vintage.publish_time_utc}
                          className={
                            vintage.is_selected ? "selected" : vintage.eligible ? "" : "excluded"
                          }
                        >
                          <td>{formatDateTime(vintage.publish_time_utc)}</td>
                          <td className="forecast-value">{formatNumber(vintage.forecast_mw)}</td>
                          <td>{formatLead(vintage.lead_hours)}</td>
                          <td>
                            {vintage.is_selected ? (
                              <span className="mark selected">Selected</span>
                            ) : vintage.eligible ? (
                              <span className="mark eligible">Eligible</span>
                            ) : (
                              <span className="mark excluded">Post-cutoff</span>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
              <p className="axis-note">{data.note}</p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
