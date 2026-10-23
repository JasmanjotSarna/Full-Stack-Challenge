import type { HealthResponse, MetadataResponse } from "../types/api";
import { formatRefresh } from "../utils/format";

interface FooterProps {
  metadata: MetadataResponse | null;
  health: HealthResponse | null;
}

export function Footer({ metadata, health }: FooterProps) {
  return (
    <footer className="footer">
      <div className="footer-inner">
        <div className="disclaimer">
          <strong>WindScope</strong> — independent wind-forecast accuracy analysis built for the
          REint Full Stack SWE Challenge. Uses only official Elexon FUELHH actuals and WINDFOR
          forecasts for national GB wind, delivery periods 1–31 January 2026. Not affiliated with
          Elexon. Not operational, trading or procurement advice.
        </div>
        <div>
          <div>
            <strong>Data refreshed:</strong>{" "}
            {formatRefresh(metadata?.dataset.last_successful_refresh)}
          </div>
          <div>
            <strong>API:</strong> {health?.service ?? "WindScope API"} v{health?.version ?? "1.0.0"}
          </div>
          <div>
            <strong>Dataset:</strong>{" "}
            {metadata?.dataset.test_data
              ? "TEST DATA"
              : metadata?.dataset.real_source_data
                ? "Official Elexon extract"
                : "Unavailable"}
          </div>
        </div>
      </div>
    </footer>
  );
}
