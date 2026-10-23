import type { HealthResponse, MetadataResponse } from "../types/api";
import { formatRefresh } from "../utils/format";

interface AppHeaderProps {
  metadata: MetadataResponse | null;
  health: HealthResponse | null;
  loading: boolean;
  onReload: () => void;
}

function statusClass(health: HealthResponse | null, error: boolean): string {
  if (error) return "status-dot error";
  if (!health || health.status !== "ok") return "status-dot warn";
  return "status-dot";
}

export function AppHeader({ metadata, health, loading, onReload }: AppHeaderProps) {
  const ready = Boolean(health?.dataset_available);
  const testData = Boolean(metadata?.dataset.test_data);
  const refreshed = metadata?.dataset.last_successful_refresh;

  return (
    <header className="topbar">
      <div className="topbar-inner">
        <div className="brand">
          <div className="logo-mark" aria-hidden="true">
            <svg width="21" height="21" viewBox="0 0 24 24" fill="none">
              <path
                d="M3 14.5c3.4 0 3.4-4 6.8-4s3.4 4 6.8 4 3.4-4 4.4-4"
                stroke="#eafffb"
                strokeWidth="1.8"
                strokeLinecap="round"
              />
              <path
                d="M3 9c2.4 0 2.4-2.5 4.8-2.5S10.2 9 12.6 9s2.4-2.5 4.8-2.5S19.8 9 21 9"
                stroke="#8fe3d5"
                strokeWidth="1.6"
                strokeLinecap="round"
                opacity="0.8"
              />
              <path
                d="M5 19h11"
                stroke="#eafffb"
                strokeWidth="1.6"
                strokeLinecap="round"
                opacity="0.65"
              />
            </svg>
          </div>
          <div className="brand-text">
            <h1>WindScope</h1>
            <p>UK wind forecast intelligence</p>
          </div>
        </div>

        <div className="topbar-actions">
          <span className="data-status" title="Backend status and data provenance">
            <span className={statusClass(health, false)} aria-hidden="true" />
            {ready
              ? `Elexon data ready · ${formatRefresh(refreshed)}`
              : health
                ? "Dataset unavailable"
                : "Connecting to API…"}
            {testData ? " · TEST DATA" : ""}
          </span>
          <button
            type="button"
            className="btn btn-ghost-light"
            onClick={onReload}
            disabled={loading}
            title="Re-fetch all endpoints; does not download new Elexon data"
          >
            {loading ? "Loading…" : "Reload view"}
          </button>
        </div>
      </div>
    </header>
  );
}
