import { useCallback, useState } from "react";

import { AlignedDataTable } from "./components/AlignedDataTable";
import { AppHeader } from "./components/AppHeader";
import { DailyAccuracyChart } from "./components/DailyAccuracyChart";
import { ErrorDistribution } from "./components/ErrorDistribution";
import { ExtremeErrors } from "./components/ExtremeErrors";
import { FilterBar } from "./components/FilterBar";
import { Footer } from "./components/Footer";
import { ForecastChart } from "./components/ForecastChart";
import { HourlyProfileChart } from "./components/HourlyProfileChart";
import { KpiGrid } from "./components/KpiGrid";
import { MethodologyPanel } from "./components/MethodologyPanel";
import { PolicyStrip } from "./components/PolicyStrip";
import { QualityPanel } from "./components/QualityPanel";
import { DashboardSkeleton, StatePanel } from "./components/StatePanel";
import { VintageModal } from "./components/VintageModal";
import { useDashboardData } from "./hooks/useDashboardData";
import { useMetadata } from "./hooks/useMetadata";
import type { Resolution, TimeseriesPoint } from "./types/api";
import { MONTH_END, MONTH_START, type DateRange } from "./utils/derived";
import { formatDateLong } from "./utils/format";

export default function App() {
  const [range, setRange] = useState<DateRange>({ start: MONTH_START, end: MONTH_END });
  const [resolution, setResolution] = useState<Resolution>("30m");
  const [inspected, setInspected] = useState<TimeseriesPoint | null>(null);

  const dashboard = useDashboardData(range, resolution);
  const metadata = useMetadata();

  const reloadAll = useCallback(() => {
    dashboard.retry();
    metadata.retry();
  }, [dashboard, metadata]);

  const data = dashboard.data;
  const policy = data?.summary.cutoff_policy ?? metadata.metadata?.cutoff_policy;

  return (
    <div className="app-shell">
      <AppHeader
        metadata={metadata.metadata}
        health={metadata.health}
        loading={dashboard.loading || metadata.loading}
        onReload={reloadAll}
      />

      <main className="container">
        <PolicyStrip policy={policy} loading={metadata.loading} />

        {data ? (
          <>
            <FilterBar
              range={range}
              resolution={resolution}
              sampleCount={data.summary.metrics.sample_count}
              expectedCount={data.summary.metrics.expected_intervals}
              refreshing={dashboard.refreshing}
              onRangeChange={setRange}
              onResolutionChange={setResolution}
            />

            {dashboard.error ? (
              <div className="callout amber" role="alert" style={{ marginBottom: 14 }}>
                <strong>Refresh failed.</strong> {dashboard.error} The last successful view is still
                shown below.
              </div>
            ) : null}

            <div className="section-heading">
              <h2>Operations snapshot</h2>
              <p>
                {formatDateLong(range.start)}
                {range.start === range.end ? "" : ` – ${formatDateLong(range.end)}`} ·{" "}
                {resolution === "30m" ? "half-hourly" : "hourly"} · Europe/London
              </p>
            </div>

            <KpiGrid summary={data.summary} />

            <ForecastChart points={data.timeseries.points} />

            <div className="section-heading">
              <h2>Where the forecast misses</h2>
              <p>Distribution, calendar pattern and the largest decision-time misses.</p>
            </div>

            <div className="grid-3">
              <ErrorDistribution points={data.timeseries.points} />
              <DailyAccuracyChart data={data.daily} />
              <HourlyProfileChart data={data.hourly} />
            </div>

            <div className="grid-2">
              <ExtremeErrors
                title="Largest underforecasts"
                response={data.underforecast}
                direction="underforecast"
              />
              <ExtremeErrors
                title="Largest overforecasts"
                response={data.overforecast}
                direction="overforecast"
              />
            </div>

            <div className="section-heading">
              <h2>Audit trail</h2>
              <p>Inspect any interval, then export exactly what you see.</p>
            </div>

            <AlignedDataTable
              points={data.timeseries.points}
              range={range}
              onInspect={setInspected}
            />

            <div className="section-heading">
              <h2>Trust &amp; definitions</h2>
              <p>Provenance, completeness and every analytical assumption in one place.</p>
            </div>

            <div className="stack">
              <QualityPanel summary={data.summary} metadata={metadata.metadata} />
              <MethodologyPanel metadata={metadata.metadata} />
            </div>
          </>
        ) : dashboard.error ? (
          <StatePanel
            title="The WindScope API is unavailable"
            message={dashboard.error}
            detail={`Expected API base: ${import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"}`}
            tone="error"
            actionLabel="Retry"
            onAction={reloadAll}
          />
        ) : (
          <DashboardSkeleton />
        )}
      </main>

      <Footer metadata={metadata.metadata} health={metadata.health} />

      {inspected ? (
        <VintageModal
          deliveryDate={inspected.delivery_date}
          intervalStartUtc={inspected.interval_start_utc}
          onClose={() => setInspected(null)}
        />
      ) : null}
    </div>
  );
}
