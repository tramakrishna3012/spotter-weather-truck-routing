import { ENV } from '../config/env';
import type {
  ApiErrorDetail,
  ApiErrorEnvelope,
  DataMode,
  ForecastCorridorPoint,
  ForecastSliceResponse,
  GeocodeResponse,
  GeoLocation,
  HealthReadyResponse,
  PlanRequestPayload,
  PlanResponse,
  Severity,
} from '../types/plan';

const SESSION_STORAGE_KEY = 'spotter.session.token';

export class SpotterApiError extends Error {
  readonly status: number;
  readonly detail: ApiErrorDetail;

  constructor(status: number, detail: ApiErrorDetail) {
    super(detail.message);
    this.name = 'SpotterApiError';
    this.status = status;
    this.detail = detail;
  }
}

function generateUuid(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  const bytes = new Uint8Array(16);
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < 16; i += 1) {
      bytes[i] = Math.floor(Math.random() * 256);
    }
  }
  bytes[6] = ((bytes[6] ?? 0) & 0x0f) | 0x40;
  bytes[8] = ((bytes[8] ?? 0) & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

/**
 * Reads the server-issued signed guest session token from sessionStorage only (NEVER in URL).
 * Returns null until the backend issues a signed token via X-Spotter-Session.
 */
export function getSessionToken(): string | null {
  try {
    const existing = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
    return existing && existing.trim().length >= 8 ? existing.trim() : null;
  } catch {
    return null;
  }
}

function persistSessionToken(token: string | null): void {
  if (!token || token.trim().length < 8) return;
  try {
    window.sessionStorage.setItem(SESSION_STORAGE_KEY, token.trim());
  } catch {
    // Ignore storage restriction in private browsing contexts
  }
}

function buildUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${ENV.apiBaseUrl}${normalizedPath}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function normalizeErrorDetail(status: number, body: unknown): ApiErrorDetail {
  if (isRecord(body) && isRecord(body.error)) {
    const err = body.error as Partial<ApiErrorEnvelope['error']>;
    return {
      code: typeof err.code === 'string' ? err.code : `HTTP_${status}`,
      message:
        typeof err.message === 'string' && err.message.length > 0
          ? err.message
          : defaultMessageForStatus(status),
      retryable: typeof err.retryable === 'boolean' ? err.retryable : status >= 500 || status === 429,
      request_id: typeof err.request_id === 'string' ? err.request_id : null,
      details: Array.isArray(err.details) ? err.details : [],
    };
  }

  if (isRecord(body) && typeof body.detail === 'string') {
    return {
      code: `HTTP_${status}`,
      message: body.detail,
      retryable: status >= 500 || status === 429,
      request_id: null,
      details: [],
    };
  }

  return {
    code: `HTTP_${status}`,
    message: defaultMessageForStatus(status),
    retryable: status >= 500 || status === 429 || status === 0,
    request_id: null,
    details: [],
  };
}

function defaultMessageForStatus(status: number): string {
  switch (status) {
    case 400:
    case 422:
      return 'Some trip inputs could not be validated. Review the highlighted fields and try again.';
    case 401:
    case 403:
      return 'Your planning session could not be verified. Re-submit to start a fresh session.';
    case 404:
      return 'This route plan is no longer available or has expired.';
    case 429:
      return 'Too many planning requests right now. Wait a moment and try again.';
    case 502:
    case 503:
    case 504:
      return 'Routing or weather service is temporarily unavailable. Try again shortly.';
    default:
      return 'We could not complete this request. Try again.';
  }
}

async function requestJson<T>(
  path: string,
  options: {
    method?: 'GET' | 'POST' | 'DELETE';
    body?: unknown;
    signal?: AbortSignal;
    idempotencyKey?: string;
  } = {},
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
  };

  const sessionToken = getSessionToken();
  if (sessionToken) {
    headers['X-Spotter-Session'] = sessionToken;
  }

  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }
  if (options.idempotencyKey) {
    headers['Idempotency-Key'] = options.idempotencyKey;
  }

  let response: Response;
  try {
    response = await fetch(buildUrl(path), {
      method: options.method ?? 'GET',
      headers,
      credentials: 'same-origin',
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: options.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw err;
    }
    throw new SpotterApiError(0, {
      code: 'NETWORK_ERROR',
      message: 'Could not reach the Spotter routing service. Check your connection and try again.',
      retryable: true,
      request_id: null,
      details: [],
    });
  }

  const returnedSession = response.headers.get('X-Spotter-Session');
  if (returnedSession) {
    persistSessionToken(returnedSession);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  let parsedBody: unknown = null;
  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    try {
      parsedBody = await response.json();
    } catch {
      parsedBody = null;
    }
  }

  if (!response.ok) {
    throw new SpotterApiError(response.status, normalizeErrorDetail(response.status, parsedBody));
  }

  return parsedBody as T;
}

function normalizeSeverity(raw: unknown): Severity {
  if (
    raw === 'low' ||
    raw === 'moderate' ||
    raw === 'high' ||
    raw === 'severe' ||
    raw === 'no_travel' ||
    raw === 'unknown'
  ) {
    return raw;
  }
  return 'unknown';
}

function normalizeDataMode(raw: unknown): DataMode | undefined {
  return raw === 'live' || raw === 'fixture' ? raw : undefined;
}

function normalizeGeoLocation(item: unknown): GeoLocation | null {
  if (!isRecord(item)) return null;
  const lat = typeof item.latitude === 'number' ? item.latitude : typeof item.lat === 'number' ? item.lat : null;
  const lon = typeof item.longitude === 'number' ? item.longitude : typeof item.lon === 'number' ? item.lon : null;
  const label = typeof item.label === 'string' ? item.label : typeof item.title === 'string' ? item.title : null;
  if (lat === null || lon === null || !label) return null;

  const derivedSubtitle = [item.locality, item.region, item.country_code]
    .filter((v): v is string => typeof v === 'string' && v.trim().length > 0)
    .join(', ');

  return {
    latitude: lat,
    longitude: lon,
    label,
    subtitle:
      typeof item.subtitle === 'string'
        ? item.subtitle
        : typeof item.address === 'string'
          ? item.address
          : derivedSubtitle || null,
    place_id:
      typeof item.place_id === 'string'
        ? item.place_id
        : typeof item.provider_id === 'string'
          ? item.provider_id
          : typeof item.id === 'string'
            ? item.id
            : null,
    country_code: typeof item.country_code === 'string' ? item.country_code : null,
  };
}

export async function searchGeocode(
  query: string,
  signal?: AbortSignal,
): Promise<GeocodeResponse> {
  const params = new URLSearchParams({ q: query.trim() });
  const raw = await requestJson<unknown>(`/api/v1/geocode?${params.toString()}`, { signal });

  if (Array.isArray(raw)) {
    return {
      results: raw.map(normalizeGeoLocation).filter((loc): loc is GeoLocation => loc !== null),
    };
  }

  if (isRecord(raw)) {
    const rawList = Array.isArray(raw.results)
      ? raw.results
      : Array.isArray(raw.items)
        ? raw.items
        : Array.isArray(raw.candidates)
          ? raw.candidates
          : [];
    return {
      results: rawList.map(normalizeGeoLocation).filter((loc): loc is GeoLocation => loc !== null),
      data_mode: normalizeDataMode(raw.data_mode),
    };
  }

  return { results: [] };
}

export async function createPlan(
  payload: PlanRequestPayload,
  signal?: AbortSignal,
): Promise<PlanResponse> {
  return requestJson<PlanResponse>('/api/v1/plans', {
    method: 'POST',
    body: payload,
    signal,
    idempotencyKey: generateUuid(),
  });
}

export async function getPlan(
  planId: string,
  signal?: AbortSignal,
  displayCheckpointMiles?: 10 | 25 | 50,
): Promise<PlanResponse> {
  const suffix = displayCheckpointMiles
    ? `?display_checkpoint_miles=${displayCheckpointMiles}`
    : '';
  return requestJson<PlanResponse>(`/api/v1/plans/${encodeURIComponent(planId)}${suffix}`, {
    method: 'GET',
    signal,
  });
}

function normalizeCorridorPoint(raw: unknown): ForecastCorridorPoint | null {
  if (!isRecord(raw)) return null;
  const lat = typeof raw.lat === 'number' ? raw.lat : typeof raw.latitude === 'number' ? raw.latitude : null;
  const lon = typeof raw.lon === 'number' ? raw.lon : typeof raw.longitude === 'number' ? raw.longitude : null;
  if (lat === null || lon === null) return null;

  return {
    lat,
    lon,
    severity: normalizeSeverity(raw.severity ?? raw.risk_severity),
    wind_mph: typeof raw.wind_mph === 'number' ? raw.wind_mph : null,
    rain_in_per_hr: typeof raw.rain_in_per_hr === 'number' ? raw.rain_in_per_hr : null,
    snow_in_per_hr: typeof raw.snow_in_per_hr === 'number' ? raw.snow_in_per_hr : null,
    weather_status: raw.weather_status === 'known' || raw.weather_status === 'unknown' ? raw.weather_status : undefined,
    risk_score: typeof raw.risk_score === 'number' ? raw.risk_score : null,
  };
}

export async function getForecastSlice(
  planId: string,
  hourOffset: number,
  signal?: AbortSignal,
): Promise<ForecastSliceResponse> {
  const clampedOffset = Math.max(0, Math.min(48, Math.round(hourOffset)));
  const raw = await requestJson<unknown>(
    `/api/v1/plans/${encodeURIComponent(planId)}/forecast?hour_offset=${clampedOffset}`,
    { method: 'GET', signal },
  );

  if (!isRecord(raw)) {
    throw new SpotterApiError(502, {
      code: 'INVALID_FORECAST_SLICE',
      message: 'Forecast slice response was malformed.',
      retryable: true,
    });
  }

  const rawPoints = Array.isArray(raw.points)
    ? raw.points
    : Array.isArray(raw.cells)
      ? raw.cells
      : [];

  return {
    hour_offset: typeof raw.hour_offset === 'number' ? raw.hour_offset : clampedOffset,
    valid_at: typeof raw.valid_at === 'string' ? raw.valid_at : '',
    reference_at:
      typeof raw.reference_at === 'string'
        ? raw.reference_at
        : typeof raw.reference_time === 'string'
          ? raw.reference_time
          : null,
    timezone: typeof raw.timezone === 'string' ? raw.timezone : null,
    points: rawPoints
      .map(normalizeCorridorPoint)
      .filter((pt): pt is ForecastCorridorPoint => pt !== null),
    coverage_fraction: typeof raw.coverage_fraction === 'number' ? raw.coverage_fraction : null,
    coverage_complete: typeof raw.coverage_complete === 'boolean' ? raw.coverage_complete : undefined,
    data_origin: typeof raw.data_origin === 'string' ? raw.data_origin : 'corridor_forecast',
    data_mode: normalizeDataMode(raw.data_mode),
  };
}

export async function cancelPlan(
  planId: string,
  signal?: AbortSignal,
): Promise<PlanResponse | undefined> {
  return requestJson<PlanResponse | undefined>(
    `/api/v1/plans/${encodeURIComponent(planId)}/cancel`,
    { method: 'POST', signal },
  );
}

export async function deletePlan(planId: string, signal?: AbortSignal): Promise<void> {
  await requestJson<void>(`/api/v1/plans/${encodeURIComponent(planId)}`, {
    method: 'DELETE',
    signal,
  });
}

export async function getHealthReady(signal?: AbortSignal): Promise<HealthReadyResponse> {
  return requestJson<HealthReadyResponse>('/api/v1/health/ready', { method: 'GET', signal });
}
