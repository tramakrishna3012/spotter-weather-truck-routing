import type { UnitSystem } from '../types/plan';

const METERS_PER_MILE = 1609.344;
const KM_PER_MILE = 1.609344;
const KPH_PER_MPH = 1.609344;
const MM_PER_INCH = 25.4;
const KG_PER_LB = 0.45359237;

export const NULL_DISPLAY = '—';

function isFiniteNumber(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

/**
 * Converts meters to user-facing distance string.
 * NEVER coerces null/undefined to 0.
 */
export function formatDistanceFromMeters(
  meters: number | null | undefined,
  units: UnitSystem = 'imperial',
): string {
  if (!isFiniteNumber(meters)) return NULL_DISPLAY;

  if (units === 'metric') {
    const km = meters / 1000;
    const formatted = new Intl.NumberFormat(undefined, {
      maximumFractionDigits: km >= 100 ? 0 : 1,
      minimumFractionDigits: km >= 100 ? 0 : 1,
    }).format(km);
    return `${formatted} km`;
  }

  const miles = meters / METERS_PER_MILE;
  const formatted = new Intl.NumberFormat(undefined, {
    maximumFractionDigits: miles >= 100 ? 0 : 1,
    minimumFractionDigits: miles >= 100 ? 0 : 1,
  }).format(miles);
  return `${formatted} mi`;
}

/**
 * Formats a mileage figure (e.g. severe_miles, high_miles) in selected display units.
 * NEVER coerces null/undefined to 0.
 */
export function formatMiles(
  miles: number | null | undefined,
  units: UnitSystem = 'imperial',
): string {
  if (!isFiniteNumber(miles)) return NULL_DISPLAY;

  if (units === 'metric') {
    const km = miles * KM_PER_MILE;
    const formatted = new Intl.NumberFormat(undefined, {
      maximumFractionDigits: 1,
      minimumFractionDigits: km === 0 ? 0 : 1,
    }).format(km);
    return `${formatted} km`;
  }

  const formatted = new Intl.NumberFormat(undefined, {
    maximumFractionDigits: 1,
    minimumFractionDigits: miles === 0 ? 0 : 1,
  }).format(miles);
  return `${formatted} mi`;
}

/**
 * Formats duration in seconds (e.g., "4 hr 18 min", "42 min").
 * NEVER coerces null/undefined to 0.
 */
export function formatDuration(seconds: number | null | undefined): string {
  if (!isFiniteNumber(seconds) || seconds < 0) return NULL_DISPLAY;

  const totalMinutes = Math.round(seconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  if (hours === 0) {
    return `${minutes} min`;
  }
  if (minutes === 0) {
    return `${hours} hr`;
  }
  return `${hours} hr ${minutes} min`;
}

/**
 * Formats load weight. Input is always lb per API contract.
 */
export function formatWeightLb(
  weightLb: number | null | undefined,
  units: UnitSystem = 'imperial',
): string {
  if (!isFiniteNumber(weightLb)) return NULL_DISPLAY;

  if (units === 'metric') {
    const kg = Math.round(weightLb * KG_PER_LB);
    return `${new Intl.NumberFormat(undefined).format(kg)} kg`;
  }

  return `${new Intl.NumberFormat(undefined).format(Math.round(weightLb))} lb`;
}

/**
 * Formats wind speed with explicit units. NEVER coerces null to 0.
 */
export function formatWind(
  windMph: number | null | undefined,
  units: UnitSystem = 'imperial',
): string {
  if (!isFiniteNumber(windMph)) return NULL_DISPLAY;

  if (units === 'metric') {
    const kph = windMph * KPH_PER_MPH;
    return `${Math.round(kph)} km/h`;
  }

  return `${Math.round(windMph)} mph`;
}

/**
 * Formats rain rate with explicit units. NEVER coerces null to 0.
 */
export function formatRain(
  rainInPerHr: number | null | undefined,
  units: UnitSystem = 'imperial',
): string {
  if (!isFiniteNumber(rainInPerHr)) return NULL_DISPLAY;

  if (units === 'metric') {
    const mm = rainInPerHr * MM_PER_INCH;
    const formatted = new Intl.NumberFormat(undefined, {
      minimumFractionDigits: mm === 0 ? 0 : 1,
      maximumFractionDigits: 1,
    }).format(mm);
    return `${formatted} mm/hr`;
  }

  const formatted = new Intl.NumberFormat(undefined, {
    minimumFractionDigits: rainInPerHr === 0 ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(rainInPerHr);
  return `${formatted} in/hr`;
}

/**
 * Formats snow rate with explicit units. NEVER coerces null to 0.
 */
export function formatSnow(
  snowInPerHr: number | null | undefined,
  units: UnitSystem = 'imperial',
): string {
  if (!isFiniteNumber(snowInPerHr)) return NULL_DISPLAY;

  if (units === 'metric') {
    const cm = (snowInPerHr * MM_PER_INCH) / 10;
    const formatted = new Intl.NumberFormat(undefined, {
      minimumFractionDigits: cm === 0 ? 0 : 1,
      maximumFractionDigits: 1,
    }).format(cm);
    return `${formatted} cm/hr`;
  }

  const formatted = new Intl.NumberFormat(undefined, {
    minimumFractionDigits: snowInPerHr === 0 ? 0 : 1,
    maximumFractionDigits: 2,
  }).format(snowInPerHr);
  return `${formatted} in/hr`;
}

/**
 * Formats backend weighted average risk score (two decimals).
 * NEVER coerces null to 0.
 */
export function formatAverageRisk(score: number | null | undefined): string {
  if (!isFiniteNumber(score)) return NULL_DISPLAY;
  return new Intl.NumberFormat(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(score);
}

/**
 * Formats coverage fraction (0..1) as an integer percentage.
 */
export function formatCoveragePercent(fraction: number | null | undefined): string {
  if (!isFiniteNumber(fraction)) return NULL_DISPLAY;
  const clamped = Math.max(0, Math.min(1, fraction));
  return `${Math.round(clamped * 100)}%`;
}

/**
 * Formats an ISO timestamp with explicit weekday, date, time, and timezone abbreviation.
 * Example: "Tue, Nov 20 · 9:30 AM EST"
 */
export function formatTimestampWithZone(
  isoString: string | null | undefined,
  timeZone?: string | null,
): string {
  if (!isoString) return NULL_DISPLAY;
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return NULL_DISPLAY;

  const resolvedTz = timeZone && isValidTimeZone(timeZone) ? timeZone : getLocalTimeZone();

  try {
    const datePart = new Intl.DateTimeFormat('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      timeZone: resolvedTz,
    }).format(date);

    const timePart = new Intl.DateTimeFormat('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      timeZoneName: 'short',
      timeZone: resolvedTz,
    }).format(date);

    return `${datePart} · ${timePart}`;
  } catch {
    return date.toISOString();
  }
}

export function getLocalTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}

export function isValidTimeZone(tz: string): boolean {
  try {
    Intl.DateTimeFormat(undefined, { timeZone: tz });
    return true;
  } catch {
    return false;
  }
}

/**
 * Formats a Date object as a local ISO-8601 string WITH explicit numeric timezone offset
 * (e.g. "2026-11-20T09:00:00-05:00") for the backend departure_at contract.
 */
export function formatLocalDateTimeInput(date: Date): { date: string; time: string } {
  const pad = (n: number) => String(n).padStart(2, '0');
  return {
    date: `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`,
    time: `${pad(date.getHours())}:${pad(date.getMinutes())}`,
  };
}

export function buildOffsetIsoTimestamp(dateStr: string, timeStr: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateStr) || !/^\d{2}:\d{2}$/.test(timeStr)) {
    return null;
  }
  const localDate = new Date(`${dateStr}T${timeStr}:00`);
  if (Number.isNaN(localDate.getTime())) {
    return null;
  }
  const offsetMinutes = -localDate.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? '+' : '-';
  const absOffset = Math.abs(offsetMinutes);
  const pad = (n: number) => String(n).padStart(2, '0');
  const offsetStr = `${sign}${pad(Math.floor(absOffset / 60))}:${pad(absOffset % 60)}`;
  return `${dateStr}T${timeStr}:00${offsetStr}`;
}

export function formatReasonCode(reason: string): string {
  const cleaned = reason.trim();
  if (!cleaned) return '';
  if (cleaned.includes(' ')) return cleaned;
  return cleaned
    .toLowerCase()
    .split('_')
    .map((part, idx) => (idx === 0 ? part.charAt(0).toUpperCase() + part.slice(1) : part))
    .join(' ');
}
