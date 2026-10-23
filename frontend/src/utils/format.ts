const LONDON = "Europe/London";

const numberFormatter = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 });
const oneDecimalFormatter = new Intl.NumberFormat("en-GB", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
const twoDecimalFormatter = new Intl.NumberFormat("en-GB", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (digits === 1) return oneDecimalFormatter.format(value);
  if (digits === 2) return twoDecimalFormatter.format(value);
  return numberFormatter.format(value);
}

export function formatSigned(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const formatted = formatNumber(Math.abs(value), digits);
  if (value > 0) return `+${formatted}`;
  if (value < 0) return `−${formatted}`;
  return formatted;
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${formatNumber(value, digits)}%`;
}

export function parseUtc(iso: string): Date {
  return new Date(iso);
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = parseUtc(iso);
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: LONDON,
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export function formatInterval(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = parseUtc(iso);
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: LONDON,
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: LONDON,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(parseUtc(iso));
}

export function formatFullDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: LONDON,
    weekday: "short",
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(parseUtc(iso));
}

export function formatDateLong(dateString: string): string {
  if (!dateString) return "—";
  const date = new Date(`${dateString}T12:00:00Z`);
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "UTC",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(date);
}

export function formatDayShort(dateString: string): string {
  if (!dateString) return "—";
  const date = new Date(`${dateString}T12:00:00Z`);
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "UTC",
    day: "2-digit",
    month: "short",
  }).format(date);
}

export function formatRefresh(iso: string | null | undefined): string {
  if (!iso) return "Not available";
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: LONDON,
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(parseUtc(iso));
}

export function statusLabel(status: string): string {
  switch (status) {
    case "matched":
      return "Matched";
    case "missing_forecast":
      return "Missing forecast";
    case "missing_actual":
      return "Missing actual";
    case "missing_both":
      return "Missing both";
    default:
      return status;
  }
}

export function directionLabel(error: number | null | undefined): string {
  if (error === null || error === undefined || Number.isNaN(error)) return "No error";
  if (error > 0) return "Overforecast";
  if (error < 0) return "Underforecast";
  return "Exact";
}

export function formatLead(hours: number | null | undefined): string {
  if (hours === null || hours === undefined || Number.isNaN(hours)) return "—";
  return `${formatNumber(hours, 1)} h`;
}
