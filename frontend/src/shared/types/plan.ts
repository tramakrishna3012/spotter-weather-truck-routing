import type { DisplaySpacingMiles } from '../config/env';

export type Severity =
  | 'low'
  | 'moderate'
  | 'high'
  | 'severe'
  | 'no_travel'
  | 'unknown';

export type WeatherStatus = 'known' | 'unknown';

export type RiskSegmentStatus = 'known' | 'unknown' | 'no_travel';

export type PlanLifecycleState =
  | 'queued'
  | 'routing'
  | 'sampling_weather'
  | 'scoring'
  | 'completed'
  | 'failed'
  | 'canceled';

export type RecommendationStatus =
  | 'recommended'
  | 'no_eligible_route'
  | 'incomplete_coverage'
  | 'no_routes'
  | 'unavailable';

export type DataMode = 'live' | 'fixture';

export type UnitSystem = 'imperial' | 'metric';

export interface GeoLocation {
  latitude: number;
  longitude: number;
  label: string;
  subtitle?: string | null;
  place_id?: string | null;
  country_code?: string | null;
}

export interface GeocodeResponse {
  results: GeoLocation[];
  data_mode?: DataMode;
}

export interface LineStringGeometry {
  type: 'LineString';
  coordinates: Array<[number, number]>;
}

export interface Checkpoint {
  id: string;
  cumulative_distance_m: number;
  lat: number;
  lon: number;
  eta_at: string;
  weather_valid_at: string | null;
  wind_mph: number | null;
  rain_in_per_hr: number | null;
  snow_in_per_hr: number | null;
  risk_severity: Severity;
  risk_reasons: string[];
  weather_status: WeatherStatus;
  forecast_issued_at: string | null;
}

export interface RiskSegment {
  from_distance_m: number;
  to_distance_m: number;
  severity: Severity;
  status: RiskSegmentStatus;
  reason_codes: string[];
  geometry?: LineStringGeometry | null;
  coordinates?: Array<[number, number]> | null;
}

export interface RouteRiskSummary {
  severe_miles: number | null;
  high_miles: number | null;
  no_travel_miles: number | null;
  unknown_miles: number | null;
  weighted_average_risk: number | null;
  eligible: boolean;
  coverage_fraction: number | null;
  ineligibility_reasons?: string[];
}

export interface RouteCandidate {
  id: string;
  label?: string;
  summary?: string | null;
  geometry: LineStringGeometry;
  distance_m: number;
  duration_seconds: number;
  risk: RouteRiskSummary;
  checkpoints: Checkpoint[];
  risk_segments: RiskSegment[];
  eta_method: string;
  provider_warnings: string[];
  rationale?: string | null;
}

export interface ForecastMetadata {
  issued_at: string | null;
  valid_until: string | null;
  reference_at?: string | null;
  reference_time?: string | null;
  timezone: string;
  coverage_complete: boolean;
  stale?: boolean;
}

export interface PlanWarning {
  code: string;
  message: string;
  severity?: 'info' | 'warning' | 'critical';
}

export interface PlanRequestPayload {
  origin: Pick<GeoLocation, 'latitude' | 'longitude' | 'label'>;
  destination: Pick<GeoLocation, 'latitude' | 'longitude' | 'label'>;
  departure_at: string;
  load_weight_lb: number;
  display_checkpoint_miles: DisplaySpacingMiles;
}

export interface PlanResponse {
  plan_id: string;
  state: PlanLifecycleState;
  poll_after_seconds?: number;
  status_url?: string;
  generated_at?: string;
  data_mode?: DataMode;
  policy_version?: string;
  recommendation_status?: RecommendationStatus;
  recommended_route_id?: string | null;
  recommendation_reason?: string | null;
  routes?: RouteCandidate[];
  forecast?: ForecastMetadata | null;
  warnings?: Array<string | PlanWarning>;
  error?: ApiErrorDetail | null;
  error_code?: string | null;
  error_message?: string | null;
}

export interface ForecastCorridorPoint {
  lat: number;
  lon: number;
  severity: Severity;
  wind_mph: number | null;
  rain_in_per_hr: number | null;
  snow_in_per_hr: number | null;
  weather_status?: WeatherStatus;
  risk_score?: number | null;
}

export interface ForecastSliceResponse {
  hour_offset: number;
  valid_at: string;
  reference_at?: string | null;
  timezone?: string | null;
  points: ForecastCorridorPoint[];
  coverage_fraction: number | null;
  coverage_complete?: boolean;
  data_origin: string;
  data_mode?: DataMode;
}

export interface ApiErrorDetail {
  code: string;
  message: string;
  retryable: boolean;
  request_id?: string | null;
  details?: Array<string | Record<string, unknown>>;
}

export interface ApiErrorEnvelope {
  error: ApiErrorDetail;
}

export interface HealthReadyResponse {
  status: string;
  data_mode?: DataMode;
  policy_version?: string;
}

/**
 * Explicit discriminated union of UI operational states (docs/03_FRONTEND_ENGINEERING.md).
 * Prevents impossible combinations of ad-hoc boolean flags.
 */
export type AppViewState =
  | { kind: 'idle' }
  | { kind: 'validating' }
  | { kind: 'geocoding' }
  | { kind: 'planning'; stage: PlanLifecycleState; planId: string | null }
  | { kind: 'results_eligible'; plan: PlanResponse }
  | { kind: 'partial_coverage'; plan: PlanResponse }
  | { kind: 'no_eligible_route'; plan: PlanResponse }
  | { kind: 'no_routes'; plan: PlanResponse }
  | { kind: 'stale'; plan: PlanResponse }
  | { kind: 'forecast_out_of_range'; error: ApiErrorDetail; plan?: PlanResponse }
  | { kind: 'provider_unavailable'; error: ApiErrorDetail }
  | { kind: 'failed'; error: ApiErrorDetail }
  | { kind: 'canceled'; message: string };
