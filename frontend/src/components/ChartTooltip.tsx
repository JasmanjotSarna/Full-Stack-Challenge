import { formatNumber, formatSigned } from "../utils/format";

export interface TooltipRow {
  label: string;
  value: string;
  muted?: boolean;
}

interface ChartTooltipProps {
  title?: string;
  rows: TooltipRow[];
  note?: string;
}

/** Shared dark tooltip used by every Recharts panel for a consistent read. */
export function ChartTooltip({ title, rows, note }: ChartTooltipProps) {
  return (
    <div className="chart-tooltip">
      {title ? <div className="tooltip-title">{title}</div> : null}
      {rows.map((row) => (
        <div className="tooltip-row" key={row.label}>
          <span>{row.label}</span>
          <strong>{row.value}</strong>
        </div>
      ))}
      {note ? <div className="tooltip-note">{note}</div> : null}
    </div>
  );
}

export function mw(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${formatNumber(value)} MW`;
}

export function signedMw(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${formatSigned(value)} MW`;
}
