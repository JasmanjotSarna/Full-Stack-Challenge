import { useMemo, useState } from "react";

import type { TimeseriesPoint } from "../types/api";
import { buildCsvFilename, downloadCsv, toCsv } from "../utils/csv";
import {
  filterRows,
  paginate,
  sortRows,
  totalPages,
  type DateRange,
  type SortDirection,
  type SortKey,
} from "../utils/derived";
import {
  formatInterval,
  formatLead,
  formatNumber,
  formatSigned,
  statusLabel,
} from "../utils/format";

interface AlignedDataTableProps {
  points: TimeseriesPoint[];
  range: DateRange;
  onInspect: (point: TimeseriesPoint) => void;
}

const COLUMNS: Array<{ key: SortKey | null; label: string; numeric?: boolean }> = [
  { key: "interval_start_utc", label: "Interval (Europe/London)" },
  { key: null, label: "SP", numeric: true },
  { key: "actual_mw", label: "Actual MW", numeric: true },
  { key: "decision_forecast_mw", label: "Decision forecast MW", numeric: true },
  { key: null, label: "Latest MW", numeric: true },
  { key: "error_mw", label: "Error MW", numeric: true },
  { key: "decision_forecast_lead_hours", label: "Lead", numeric: true },
  { key: null, label: "Status" },
  { key: null, label: "Vintages" },
];

const PAGE_SIZES = [25, 50, 100];

export function AlignedDataTable({ points, range, onInspect }: AlignedDataTableProps) {
  const [status, setStatus] = useState("all");
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("interval_start_utc");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const filtered = useMemo(
    () => filterRows(points, { status, query }),
    [points, status, query],
  );
  const sorted = useMemo(
    () => sortRows(filtered, sortKey, sortDirection),
    [filtered, sortKey, sortDirection],
  );
  const pages = totalPages(sorted.length, pageSize);
  const currentPage = Math.min(page, pages);
  const rows = paginate(sorted, currentPage, pageSize);

  function applySort(key: SortKey) {
    if (key === sortKey) {
      setSortDirection((previous) => (previous === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDirection(key === "interval_start_utc" ? "asc" : "desc");
    }
    setPage(1);
  }

  function exportCsv() {
    downloadCsv(buildCsvFilename(range.start, range.end), toCsv(sorted));
  }

  return (
    <section className="panel" aria-label="Aligned half-hourly data">
      <div className="panel-head with-border">
        <div>
          <h2 className="panel-title">Aligned interval data</h2>
          <p className="panel-sub">
            Every expected settlement period in the selected range, preserving nulls. Click any row
            to audit the forecast vintages available before the cutoff.
          </p>
        </div>
        <div className="panel-toolbar">
          <button type="button" className="btn btn-sm" onClick={exportCsv} disabled={sorted.length === 0}>
            Export CSV ({formatNumber(sorted.length)})
          </button>
        </div>
      </div>
      <div className="panel-body">
        <div className="table-toolbar">
          <label className="sr-only" htmlFor="table-search">
            Search intervals
          </label>
          <input
            id="table-search"
            className="search-input"
            type="search"
            placeholder="Search date, interval or status…"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
          />
          <label className="sr-only" htmlFor="table-status">
            Filter by status
          </label>
          <select
            id="table-status"
            className="select-input"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
          >
            <option value="all">All statuses</option>
            <option value="matched">Matched</option>
            <option value="missing_forecast">Missing forecast</option>
            <option value="missing_actual">Missing actual</option>
            <option value="missing_both">Missing both</option>
          </select>
          <span className="record-count">
            {formatNumber(filtered.length)} of {formatNumber(points.length)} intervals
          </span>
        </div>

        <div className="table-wrap">
          <table className="data-table">
            <caption className="sr-only">
              Aligned actual and decision-time forecast wind generation by settlement period, with
              errors and status. Nulls are preserved.
            </caption>
            <thead>
              <tr>
                {COLUMNS.map((column) =>
                  column.key ? (
                    <th
                      key={column.label}
                      scope="col"
                      className={column.numeric ? "numeric" : undefined}
                      aria-sort={
                        sortKey === column.key
                          ? sortDirection === "asc"
                            ? "ascending"
                            : "descending"
                          : "none"
                      }
                    >
                      <button type="button" onClick={() => applySort(column.key as SortKey)}>
                        {column.label}
                        {sortKey === column.key ? (sortDirection === "asc" ? " ↑" : " ↓") : ""}
                      </button>
                    </th>
                  ) : (
                    <th key={column.label} scope="col" className={column.numeric ? "numeric" : undefined}>
                      {column.label}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={COLUMNS.length}>
                    <div className="empty-inline">No intervals match the current filters.</div>
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr
                    key={row.interval_start_utc}
                    onClick={() => onInspect(row)}
                    tabIndex={0}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        onInspect(row);
                      }
                    }}
                    aria-label={`Inspect interval ${formatInterval(row.interval_start_local)}`}
                  >
                    <td className="strong">{formatInterval(row.interval_start_local)}</td>
                    <td className="numeric muted">{row.settlement_period}</td>
                    <td className="numeric">{formatNumber(row.actual_mw)}</td>
                    <td className="numeric">{formatNumber(row.decision_forecast_mw)}</td>
                    <td className="numeric muted">{formatNumber(row.latest_forecast_mw)}</td>
                    <td
                      className={`numeric ${
                        row.error_mw === null
                          ? "muted"
                          : row.error_mw > 0
                            ? "error-positive"
                            : row.error_mw < 0
                              ? "error-negative"
                              : ""
                      }`}
                    >
                      {formatSigned(row.error_mw)}
                    </td>
                    <td className="numeric muted">
                      {formatLead(row.decision_forecast_lead_hours)}
                    </td>
                    <td>
                      <span
                        className={`status-badge ${
                          row.status === "matched"
                            ? "matched"
                            : row.status === "missing_both"
                              ? "missing-both"
                              : "missing"
                        }`}
                      >
                        {statusLabel(row.status)}
                      </span>
                    </td>
                    <td className="numeric muted">Inspect</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="pagination">
          <label>
            Rows per page{" "}
            <select
              className="select-input"
              value={pageSize}
              onChange={(event) => {
                setPageSize(Number(event.target.value));
                setPage(1);
              }}
            >
              {PAGE_SIZES.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={() => setPage(Math.max(1, currentPage - 1))}
            disabled={currentPage <= 1}
          >
            Previous
          </button>
          <span className="page-indicator">
            Page {currentPage} of {pages}
          </span>
          <button
            type="button"
            onClick={() => setPage(Math.min(pages, currentPage + 1))}
            disabled={currentPage >= pages}
          >
            Next
          </button>
        </div>
      </div>
    </section>
  );
}
