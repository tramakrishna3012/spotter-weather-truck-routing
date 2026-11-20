"""End-to-end Spotter trip planning orchestration, caching, scoring, and forecast slicing."""

from __future__ import annotations

import copy
import logging
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import status as http_status

from apps.trips.models import Checkpoint, ForecastSliceCache, Plan, PlanJob, RouteCandidate
from config.exceptions import ApiDomainError
from domain.recommendation.ranker import (
    RecommendationOutcome,
    RouteRankingInput,
    RouteRiskScore,
    rank_and_recommend,
    score_route,
)
from domain.risk.classifier import (
    ClassificationResult,
    WeatherReading,
    classify_conservative_window,
    classify_weather,
)
from domain.risk.policy import DEFAULT_RISK_POLICY, SEVERITY_RANK, RiskPolicy, Severity
from domain.routing.eta import TimingSpan, estimate_checkpoint_etas
from domain.routing.polyline import route_geometry_fingerprint
from domain.routing.sampling import (
    SampledPoint,
    sample_route_points,
    select_display_checkpoint_indices,
)
from domain.routing.segments import RiskSegment, build_voronoi_risk_segments
from infrastructure.cache.keys import (
    build_forecast_slice_cache_key,
    build_route_cache_key,
    build_weather_cache_key,
)
from infrastructure.observability.metrics import (
    record_plan_completed,
    record_plan_started,
)
from providers.ports import (
    GeoLocation,
    HourlyForecastPoint,
    ProviderError,
    ProviderRoute,
    RouteProvider,
    WeatherProvider,
)

logger = logging.getLogger("spotter.planning.orchestrator")

_MAX_HEATMAP_CORRIDOR_POINTS = 90
_ROUTE_KEY_SUFFIXES = ("a", "b", "c", "d", "e")


def _to_iso_z(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_iso_utc(raw: str | None) -> datetime | None:
    if not raw:
        return None
    normalized = raw[:-1] + "+00:00" if raw.endswith(("Z", "z")) else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _floor_hour_utc(dt: datetime) -> datetime:
    utc = dt.astimezone(UTC)
    return utc.replace(minute=0, second=0, microsecond=0)


def _ceil_hour_utc(dt: datetime) -> datetime:
    floored = _floor_hour_utc(dt)
    if dt.astimezone(UTC) > floored:
        return floored + timedelta(hours=1)
    return floored


def _bucket_departure_15m(dt: datetime) -> str:
    utc = dt.astimezone(UTC)
    floored_minute = (utc.minute // 15) * 15
    bucketed = utc.replace(minute=floored_minute, second=0, microsecond=0)
    return bucketed.strftime("%Y-%m-%dT%H:%MZ")


def _coord_key(lat: float, lon: float) -> tuple[float, float]:
    return (round(float(lat), 3), round(float(lon), 3))


def _serialize_provider_route(route: ProviderRoute) -> dict[str, Any]:
    return {
        "provider_route_id": route.provider_route_id,
        "coordinates_lat_lon": [[lat, lon] for lat, lon in route.coordinates_lat_lon],
        "distance_m": route.distance_m,
        "duration_seconds": route.duration_seconds,
        "timing_spans": [
            {"offset_distance_m": s.offset_distance_m, "duration_seconds": s.duration_seconds}
            for s in route.timing_spans
        ],
        "warnings": list(route.warnings),
        "provider_name": route.provider_name,
        "summary_label": route.summary_label,
    }


def _deserialize_provider_route(raw: dict[str, Any]) -> ProviderRoute:
    return ProviderRoute(
        provider_route_id=str(raw["provider_route_id"]),
        coordinates_lat_lon=tuple((float(pt[0]), float(pt[1])) for pt in raw["coordinates_lat_lon"]),
        distance_m=float(raw["distance_m"]),
        duration_seconds=float(raw["duration_seconds"]),
        timing_spans=tuple(
            TimingSpan(
                offset_distance_m=float(s["offset_distance_m"]),
                duration_seconds=float(s["duration_seconds"]),
            )
            for s in raw.get("timing_spans", [])
        ),
        warnings=tuple(str(w) for w in raw.get("warnings", [])),
        provider_name=str(raw.get("provider_name", "")),
        summary_label=str(raw.get("summary_label", "")),
    )


def _serialize_forecast_point(point: HourlyForecastPoint) -> dict[str, Any]:
    return {
        "latitude": point.latitude,
        "longitude": point.longitude,
        "issued_at": _to_iso_z(point.issued_at),
        "provider_name": point.provider_name,
        "data_mode": point.data_mode,
        "warnings": list(point.warnings),
        "readings": [
            {
                "wind_mph": str(r.wind_mph) if r.wind_mph is not None else None,
                "rain_in_per_hr": str(r.rain_in_per_hr) if r.rain_in_per_hr is not None else None,
                "snow_in_per_hr": str(r.snow_in_per_hr) if r.snow_in_per_hr is not None else None,
                "valid_at": _to_iso_z(r.valid_at),
                "issued_at": _to_iso_z(r.issued_at),
                "status": r.status,
            }
            for r in point.readings
        ],
    }


def _deserialize_forecast_point(raw: dict[str, Any]) -> HourlyForecastPoint:
    issued_at = _parse_iso_utc(raw.get("issued_at")) or timezone.now().astimezone(UTC)
    readings = tuple(
        WeatherReading(
            wind_mph=Decimal(r["wind_mph"]) if r.get("wind_mph") is not None else None,
            rain_in_per_hr=(
                Decimal(r["rain_in_per_hr"]) if r.get("rain_in_per_hr") is not None else None
            ),
            snow_in_per_hr=(
                Decimal(r["snow_in_per_hr"]) if r.get("snow_in_per_hr") is not None else None
            ),
            valid_at=_parse_iso_utc(r.get("valid_at")),
            issued_at=_parse_iso_utc(r.get("issued_at")),
            status=str(r.get("status", "known")),
        )
        for r in raw.get("readings", [])
    )
    return HourlyForecastPoint(
        latitude=float(raw["latitude"]),
        longitude=float(raw["longitude"]),
        issued_at=issued_at,
        provider_name=str(raw.get("provider_name", "")),
        data_mode=str(raw.get("data_mode", "")),
        readings=readings,
        warnings=tuple(str(w) for w in raw.get("warnings", [])),
    )


def _select_representative_reading(
    readings: Sequence[WeatherReading],
    load_weight_lb: Decimal,
    policy: RiskPolicy,
) -> WeatherReading:
    """Pick the conservative driving reading from a bracketing window for display telemetry."""
    if len(readings) == 1:
        return readings[0]

    best_reading = readings[0]
    best_rank = -1
    for reading in readings:
        res = classify_weather(reading, load_weight_lb, policy)
        if res.severity == Severity.UNKNOWN:
            return reading
        rank = SEVERITY_RANK.get(res.severity, -1)
        if rank > best_rank:
            best_rank = rank
            best_reading = reading
        elif rank == best_rank:
            cur_wind = reading.wind_mph or Decimal("0")
            best_wind = best_reading.wind_mph or Decimal("0")
            if cur_wind > best_wind:
                best_reading = reading
    return best_reading


def _checkpoint_to_dto(
    *,
    route_key: str,
    checkpoint_index: int,
    cumulative_distance_m: float,
    lat: float,
    lon: float,
    eta_at: datetime | None,
    weather_valid_at: datetime | None,
    wind_mph: float | None,
    rain_in_per_hr: float | None,
    snow_in_per_hr: float | None,
    risk_severity: str,
    risk_reasons: Sequence[str],
    weather_status: str,
    forecast_issued_at: datetime | None,
) -> dict[str, Any]:
    return {
        "id": f"{route_key}-cp-{checkpoint_index}",
        "index": checkpoint_index,
        "cumulative_distance_m": round(float(cumulative_distance_m), 2),
        "lat": round(float(lat), 6),
        "lon": round(float(lon), 6),
        "eta_at": _to_iso_z(eta_at),
        "weather_valid_at": _to_iso_z(weather_valid_at),
        "wind_mph": round(float(wind_mph), 2) if wind_mph is not None else None,
        "rain_in_per_hr": round(float(rain_in_per_hr), 3) if rain_in_per_hr is not None else None,
        "snow_in_per_hr": round(float(snow_in_per_hr), 3) if snow_in_per_hr is not None else None,
        "risk_severity": risk_severity,
        "risk_reasons": list(risk_reasons),
        "weather_status": weather_status,
        "forecast_issued_at": _to_iso_z(forecast_issued_at),
    }


def _segment_to_dto(segment: RiskSegment) -> dict[str, Any]:
    return {
        "from_distance_m": round(float(segment.from_distance_m), 2),
        "to_distance_m": round(float(segment.to_distance_m), 2),
        "severity": segment.severity.value,
        "status": segment.status,
        "reason_codes": list(segment.reason_codes),
        "coordinates": segment.coordinates,
    }


def _risk_score_to_dto(score: RouteRiskScore) -> dict[str, Any]:
    return {
        "severe_miles": round(score.severe_miles, 3),
        "high_miles": round(score.high_miles, 3),
        "moderate_miles": round(score.moderate_miles, 3),
        "low_miles": round(score.low_miles, 3),
        "no_travel_miles": round(score.no_travel_miles, 3),
        "unknown_miles": round(score.unknown_miles, 3),
        "weighted_average_risk": (
            round(score.weighted_average_risk, 4)
            if score.weighted_average_risk is not None
            else None
        ),
        "eligible": score.eligible,
        "coverage_fraction": round(score.coverage_fraction, 4),
        "ineligibility_reasons": list(score.ineligibility_reasons),
    }


def _downsample_corridor_coords(
    coords: Sequence[tuple[float, float]],
    max_points: int = _MAX_HEATMAP_CORRIDOR_POINTS,
) -> list[tuple[float, float]]:
    if len(coords) <= max_points:
        return list(coords)
    step = (len(coords) - 1) / (max_points - 1)
    indices = sorted({round(i * step) for i in range(max_points)})
    return [coords[i] for i in indices]


class PlanningOrchestrator:
    """Executes deterministic weather-aware truck route planning and forecast slicing."""

    def __init__(
        self,
        *,
        route_provider: RouteProvider | None = None,
        weather_provider: WeatherProvider | None = None,
        policy: RiskPolicy = DEFAULT_RISK_POLICY,
        source: str = "api",
    ) -> None:
        self._route_provider = route_provider
        self._weather_provider = weather_provider
        self._policy = policy
        self._source = source

    def _get_route_provider(self) -> RouteProvider:
        if self._route_provider is None:
            from services.planning.composition import build_route_provider

            self._route_provider = build_route_provider()
        return self._route_provider

    def _get_weather_provider(self) -> WeatherProvider:
        if self._weather_provider is None:
            from services.planning.composition import build_weather_provider

            self._weather_provider = build_weather_provider()
        return self._weather_provider

    def _fetch_routes_cached(
        self,
        origin: GeoLocation,
        destination: GeoLocation,
        departure_utc: datetime,
        max_routes: int,
    ) -> list[ProviderRoute]:
        provider = self._get_route_provider()
        cache_key = build_route_cache_key(
            provider=provider.provider_name,
            data_mode=provider.data_mode,
            origin_lat=origin.latitude,
            origin_lon=origin.longitude,
            dest_lat=destination.latitude,
            dest_lon=destination.longitude,
            departure_bucket_iso=_bucket_departure_15m(departure_utc),
            max_routes=max_routes,
        )

        cached = cache.get(cache_key)
        if isinstance(cached, list):
            try:
                return [_deserialize_provider_route(item) for item in cached]
            except (KeyError, TypeError, ValueError):
                logger.warning("Ignoring corrupt cached route payload")

        routes = provider.get_truck_routes(
            origin=origin,
            destination=destination,
            departure_utc=departure_utc,
            max_routes=max_routes,
        )
        ttl = int(getattr(settings, "ROUTE_CACHE_TTL_SECONDS", 1800))
        try:
            cache.set(cache_key, [_serialize_provider_route(r) for r in routes], timeout=ttl)
        except Exception:
            logger.warning("Failed to cache route provider response")
        return routes

    def _validate_and_deduplicate_routes(
        self,
        raw_routes: Sequence[ProviderRoute],
        max_routes: int,
    ) -> list[tuple[ProviderRoute, str]]:
        unique: list[tuple[ProviderRoute, str]] = []
        seen_fingerprints: set[str] = set()

        for route in raw_routes:
            if len(route.coordinates_lat_lon) < 2:
                continue
            if route.distance_m <= 0.0 or route.duration_seconds <= 0.0:
                continue
            try:
                fp = route_geometry_fingerprint(route.coordinates_lat_lon)
            except ValueError:
                continue
            if fp in seen_fingerprints:
                continue
            seen_fingerprints.add(fp)
            unique.append((route, fp))
            if len(unique) >= max_routes:
                break

        return unique

    def _fetch_weather_cached(
        self,
        unique_coords: Sequence[tuple[float, float]],
        start_utc: datetime,
        end_utc: datetime,
    ) -> tuple[dict[tuple[float, float], HourlyForecastPoint], list[str]]:
        provider = self._get_weather_provider()
        start_bucket = _floor_hour_utc(start_utc).strftime("%Y-%m-%dT%H:00Z")
        end_bucket = _ceil_hour_utc(end_utc).strftime("%Y-%m-%dT%H:00Z")

        results: dict[tuple[float, float], HourlyForecastPoint] = {}
        missing_coords: list[tuple[float, float]] = []
        key_by_coord: dict[tuple[float, float], str] = {}

        for lat, lon in unique_coords:
            ck = _coord_key(lat, lon)
            cache_key = build_weather_cache_key(
                provider=provider.provider_name,
                data_mode=provider.data_mode,
                lat=ck[0],
                lon=ck[1],
                start_bucket_iso=start_bucket,
                end_bucket_iso=end_bucket,
            )
            key_by_coord[ck] = cache_key

        cached_map = cache.get_many(list(key_by_coord.values()))
        for ck, cache_key in key_by_coord.items():
            raw = cached_map.get(cache_key)
            if isinstance(raw, dict):
                try:
                    results[ck] = _deserialize_forecast_point(raw)
                    continue
                except (KeyError, TypeError, ValueError):
                    pass
            missing_coords.append(ck)

        warnings: list[str] = []
        if missing_coords:
            try:
                fetched = provider.get_hourly_forecasts(
                    coordinates_lat_lon=missing_coords,
                    start_utc=start_utc,
                    end_utc=end_utc,
                )
            except ProviderError as exc:
                logger.warning(
                    "Weather provider error; degrading plan to unknown coverage",
                    extra={
                        "provider": exc.provider,
                        "error_code": exc.code,
                        "retryable": exc.retryable,
                    },
                )
                warnings.append(
                    "Weather forecast service was temporarily unavailable; routes are shown "
                    "with unknown weather coverage and cannot be recommended safely."
                )
                return results, warnings

            ttl = int(getattr(settings, "WEATHER_CACHE_TTL_SECONDS", 900))
            to_cache: dict[str, dict[str, Any]] = {}
            for coord_pair, forecast_point in zip(missing_coords, fetched, strict=False):
                ck = _coord_key(coord_pair[0], coord_pair[1])
                results[ck] = forecast_point
                to_cache[key_by_coord[ck]] = _serialize_forecast_point(forecast_point)

            if to_cache:
                try:
                    cache.set_many(to_cache, timeout=ttl)
                except Exception:
                    logger.warning("Failed to write weather forecasts to cache")

        return results, warnings

    def _build_forecast_slices(
        self,
        *,
        plan: Plan,
        corridor_coords: Sequence[tuple[float, float]],
        weather_by_coord: dict[tuple[float, float], HourlyForecastPoint],
        forecast_issued_at: datetime | None,
        forecast_valid_until: datetime | None,
        data_origin: str,
    ) -> list[ForecastSliceCache]:
        departure_utc = plan.departure_at.astimezone(UTC)
        max_slider_hours = int(getattr(settings, "FORECAST_SLIDER_HOURS", 48))
        max_horizon_hours = int(getattr(settings, "FORECAST_MAX_HORIZON_HOURS", 168))
        horizon_limit = (
            forecast_issued_at + timedelta(hours=max_horizon_hours)
            if forecast_issued_at is not None
            else None
        )
        sampled_corridor = _downsample_corridor_coords(corridor_coords)
        slices: list[ForecastSliceCache] = []

        for hour_offset in range(max_slider_hours + 1):
            valid_at = departure_utc + timedelta(hours=hour_offset)
            points_payload: list[dict[str, Any]] = []
            known_count = 0
            out_of_range_count = 0

            beyond_horizon = (
                (forecast_valid_until is not None and valid_at > forecast_valid_until)
                or (horizon_limit is not None and valid_at > horizon_limit)
            )

            for lat, lon in sampled_corridor:
                ck = _coord_key(lat, lon)
                forecast_point = weather_by_coord.get(ck)
                if beyond_horizon:
                    out_of_range_count += 1
                    continue

                if forecast_point is None:
                    reading = WeatherReading(
                        wind_mph=None,
                        rain_in_per_hr=None,
                        snow_in_per_hr=None,
                        valid_at=None,
                        issued_at=forecast_issued_at,
                        status="missing",
                    )
                    cls = classify_weather(reading, plan.load_weight_lb, self._policy)
                else:
                    bracket = forecast_point.readings_for_timestamp(valid_at)
                    if not bracket:
                        out_of_range_count += 1
                        continue
                    cls = classify_conservative_window(bracket, plan.load_weight_lb, self._policy)
                    reading = _select_representative_reading(
                        bracket, plan.load_weight_lb, self._policy
                    )

                if cls.severity != Severity.UNKNOWN:
                    known_count += 1
                    weight = SEVERITY_RANK.get(cls.severity, 0) / 4.0
                else:
                    weight = 0.0

                points_payload.append(
                    {
                        "lat": round(lat, 5),
                        "lon": round(lon, 5),
                        "severity": cls.severity.value,
                        "status": cls.status,
                        "intensity": round(weight, 3),
                        "wind_mph": (
                            round(float(reading.wind_mph), 2)
                            if reading.wind_mph is not None
                            else None
                        ),
                        "rain_in_per_hr": (
                            round(float(reading.rain_in_per_hr), 3)
                            if reading.rain_in_per_hr is not None
                            else None
                        ),
                        "snow_in_per_hr": (
                            round(float(reading.snow_in_per_hr), 3)
                            if reading.snow_in_per_hr is not None
                            else None
                        ),
                        "reasons": list(cls.reasons),
                    }
                )

            total_corridor = len(sampled_corridor)
            coverage_fraction = (known_count / total_corridor) if total_corridor > 0 else 0.0
            all_out_of_range = total_corridor > 0 and out_of_range_count == total_corridor
            coverage_complete = total_corridor > 0 and known_count == total_corridor

            payload = {
                "plan_id": plan.id,
                "hour_offset": hour_offset,
                "reference_kind": "departure_instant",
                "reference_time": _to_iso_z(departure_utc),
                "valid_at": _to_iso_z(valid_at),
                "issued_at": _to_iso_z(forecast_issued_at),
                "data_mode": plan.data_mode,
                "data_origin": data_origin,
                "policy_version": self._policy.version,
                "coverage_fraction": round(coverage_fraction, 4),
                "coverage_complete": coverage_complete,
                "out_of_range": all_out_of_range,
                "points": points_payload,
            }
            slices.append(
                ForecastSliceCache(
                    plan=plan,
                    hour_offset=hour_offset,
                    valid_at=valid_at,
                    coverage_fraction=round(coverage_fraction, 4),
                    coverage_complete=coverage_complete,
                    data_origin=data_origin,
                    payload=payload,
                    expires_at=plan.expires_at,
                )
            )
        return slices

    def execute_plan(self, plan: Plan) -> Plan:
        """Execute the full routing -> sampling -> weather -> scoring -> ranking pipeline."""
        route_provider = self._get_route_provider()
        weather_provider = self._get_weather_provider()
        data_mode = route_provider.data_mode

        record_plan_started(data_mode=data_mode, source=self._source)

        now = timezone.now()
        Plan.objects.filter(id=plan.id).update(
            status=Plan.Status.ROUTING,
            data_mode=data_mode,
            policy_version=self._policy.version,
            updated_at=now,
        )
        PlanJob.objects.filter(plan_id=plan.id).update(
            status=Plan.Status.ROUTING,
            attempts=F("attempts") + 1,
            started_at=now,
        )
        plan.status = Plan.Status.ROUTING
        plan.data_mode = data_mode
        plan.policy_version = self._policy.version

        origin = GeoLocation(
            label=plan.origin_label,
            latitude=plan.origin_lat,
            longitude=plan.origin_lon,
        )
        destination = GeoLocation(
            label=plan.destination_label,
            latitude=plan.destination_lat,
            longitude=plan.destination_lon,
        )
        departure_utc = plan.departure_at.astimezone(UTC)
        max_routes = int(getattr(settings, "PLAN_MAX_ROUTES", 3))

        try:
            raw_routes = self._fetch_routes_cached(
                origin=origin,
                destination=destination,
                departure_utc=departure_utc,
                max_routes=max_routes,
            )
        except ProviderError as exc:
            failed_at = timezone.now()
            Plan.objects.filter(id=plan.id).exclude(status=Plan.Status.CANCELED).update(
                status=Plan.Status.FAILED,
                error_code=exc.code,
                error_message="Routing provider failed to return routes for this trip.",
                updated_at=failed_at,
            )
            PlanJob.objects.filter(plan_id=plan.id).update(
                status=Plan.Status.FAILED,
                error_code=exc.code,
                completed_at=failed_at,
            )
            record_plan_completed(
                status="failed",
                data_mode=data_mode,
                source=self._source,
            )
            raise
        unique_routes = self._validate_and_deduplicate_routes(raw_routes, max_routes=max_routes)

        plan_warnings: list[str] = []
        if data_mode == "fixture":
            plan_warnings.append(
                "Fixture mode active: routes and weather forecasts are deterministic sample data, "
                "not live operational telemetry."
            )

        # Terminal no_routes outcome when provider yields zero valid truck routes.
        if not unique_routes:
            outcome = rank_and_recommend([])
            generated_at = timezone.now().astimezone(UTC)
            forecast_meta = {
                "issued_at": None,
                "valid_until": None,
                "timezone": "UTC",
                "reference_kind": "departure_instant",
                "reference_time": _to_iso_z(departure_utc),
                "slider_max_hours": int(getattr(settings, "FORECAST_SLIDER_HOURS", 48)),
                "coverage_complete": False,
            }
            result_payload = {
                "plan_id": plan.id,
                "state": Plan.Status.COMPLETED,
                "generated_at": _to_iso_z(generated_at),
                "data_mode": data_mode,
                "policy_version": self._policy.version,
                "origin": {
                    "label": plan.origin_label,
                    "latitude": plan.origin_lat,
                    "longitude": plan.origin_lon,
                },
                "destination": {
                    "label": plan.destination_label,
                    "latitude": plan.destination_lat,
                    "longitude": plan.destination_lon,
                },
                "departure_at": _to_iso_z(departure_utc),
                "departure_timezone": plan.departure_timezone,
                "load_weight_lb": float(plan.load_weight_lb),
                "display_checkpoint_miles": plan.display_checkpoint_miles,
                "recommendation_status": outcome.recommendation_status,
                "recommended_route_id": None,
                "recommendation_reason": outcome.recommendation_reason,
                "routes": [],
                "forecast": forecast_meta,
                "warnings": plan_warnings,
            }
            with transaction.atomic():
                plan.routes.all().delete()
                plan.forecast_slices.all().delete()
                plan.status = Plan.Status.COMPLETED
                plan.recommendation_status = outcome.recommendation_status
                plan.recommended_route_id = None
                plan.recommendation_reason = outcome.recommendation_reason
                plan.result_payload = result_payload
                plan.forecast_metadata = forecast_meta
                plan.warnings = plan_warnings
                plan.save()
                PlanJob.objects.filter(plan_id=plan.id).update(
                    status=Plan.Status.COMPLETED,
                    completed_at=generated_at,
                )
            record_plan_completed(
                status=outcome.recommendation_status,
                data_mode=data_mode,
                source=self._source,
            )
            return plan

        if len(unique_routes) < max_routes:
            plan_warnings.append(
                f"Routing provider returned {len(unique_routes)} distinct truck "
                f"route{'s' if len(unique_routes) != 1 else ''} (up to {max_routes} requested)."
            )

        # Sample internal scoring checkpoints and compute ETAs.
        internal_spacing_miles = int(getattr(settings, "INTERNAL_SCORING_MILES", 10))
        max_checkpoints = int(getattr(settings, "MAX_CHECKPOINTS_PER_ROUTE", 600))

        prepared_routes: list[dict[str, Any]] = []
        all_etas: list[datetime] = []
        unique_corridor_coords: list[tuple[float, float]] = []
        seen_coords: set[tuple[float, float]] = set()

        for idx, (provider_route, fingerprint) in enumerate(unique_routes):
            route_key = (
                f"route-{_ROUTE_KEY_SUFFIXES[idx]}"
                if idx < len(_ROUTE_KEY_SUFFIXES)
                else f"route-{idx + 1}"
            )
            sampled_points = sample_route_points(
                provider_route.coordinates_lat_lon,
                spacing_miles=internal_spacing_miles,
                total_distance_m=provider_route.distance_m,
                max_checkpoints=max_checkpoints,
            )
            etas, eta_method = estimate_checkpoint_etas(
                points=sampled_points,
                departure_utc=departure_utc,
                total_distance_m=provider_route.distance_m,
                total_duration_seconds=provider_route.duration_seconds,
                cumulative_timing=provider_route.timing_spans or None,
            )
            display_indices = set(
                select_display_checkpoint_indices(
                    sampled_points,
                    display_spacing_miles=plan.display_checkpoint_miles,
                    total_distance_m=provider_route.distance_m,
                )
            )
            all_etas.extend(etas)
            for pt in sampled_points:
                ck = _coord_key(pt.lat, pt.lon)
                if ck not in seen_coords:
                    seen_coords.add(ck)
                    unique_corridor_coords.append(ck)

            prepared_routes.append(
                {
                    "route_key": route_key,
                    "provider_route": provider_route,
                    "fingerprint": fingerprint,
                    "sampled_points": sampled_points,
                    "etas": etas,
                    "eta_method": eta_method,
                    "display_indices": display_indices,
                }
            )

        # Fetch batched hourly weather covering all ETAs +/- 1h and the 0..48h corridor slider.
        Plan.objects.filter(id=plan.id).update(
            status=Plan.Status.SAMPLING_WEATHER,
            updated_at=timezone.now(),
        )
        PlanJob.objects.filter(plan_id=plan.id).update(status=Plan.Status.SAMPLING_WEATHER)
        plan.status = Plan.Status.SAMPLING_WEATHER

        slider_hours = int(getattr(settings, "FORECAST_SLIDER_HOURS", 48))
        min_eta = min(all_etas) if all_etas else departure_utc
        max_eta = max(all_etas) if all_etas else departure_utc
        window_start = _floor_hour_utc(min(min_eta, departure_utc) - timedelta(hours=1))
        window_end = _ceil_hour_utc(
            max(max_eta + timedelta(hours=1), departure_utc + timedelta(hours=slider_hours))
        )

        weather_by_coord, weather_warnings = self._fetch_weather_cached(
            unique_coords=unique_corridor_coords,
            start_utc=window_start,
            end_utc=window_end,
        )
        plan_warnings.extend(weather_warnings)

        # Collect conservative forecast freshness and horizon bounds.
        issued_times = [fp.issued_at.astimezone(UTC) for fp in weather_by_coord.values()]
        forecast_issued_at: datetime | None = min(issued_times) if issued_times else None
        latest_valid_times = [
            r.valid_at.astimezone(UTC)
            for fp in weather_by_coord.values()
            for r in fp.readings
            if r.valid_at is not None
        ]
        forecast_valid_until: datetime | None = (
            max(latest_valid_times) if latest_valid_times else None
        )
        max_horizon_hours = int(getattr(settings, "FORECAST_MAX_HORIZON_HOURS", 168))
        horizon_cutoff = (
            forecast_issued_at + timedelta(hours=max_horizon_hours)
            if forecast_issued_at is not None
            else None
        )

        # Classify checkpoints, build Voronoi segments, and score each route.
        Plan.objects.filter(id=plan.id).update(
            status=Plan.Status.SCORING,
            updated_at=timezone.now(),
        )
        PlanJob.objects.filter(plan_id=plan.id).update(status=Plan.Status.SCORING)
        plan.status = Plan.Status.SCORING

        ranking_inputs: list[RouteRankingInput] = []
        evaluated_by_key: dict[str, dict[str, Any]] = {}

        for item in prepared_routes:
            route_key = item["route_key"]
            provider_route = item["provider_route"]
            sampled_points = item["sampled_points"]
            etas = item["etas"]
            eta_method = item["eta_method"]
            display_indices = item["display_indices"]

            classifications: list[ClassificationResult] = []
            checkpoint_records: list[dict[str, Any]] = []

            for pt, eta in zip(sampled_points, etas, strict=True):
                ck = _coord_key(pt.lat, pt.lon)
                forecast_point = weather_by_coord.get(ck)

                if horizon_cutoff is not None and eta > horizon_cutoff:
                    readings: tuple[WeatherReading, ...] = (
                        WeatherReading(
                            wind_mph=None,
                            rain_in_per_hr=None,
                            snow_in_per_hr=None,
                            valid_at=None,
                            issued_at=forecast_issued_at,
                            status="out_of_range",
                        ),
                    )
                    point_issued_at = forecast_issued_at
                elif forecast_point is not None:
                    bracket = forecast_point.readings_for_timestamp(eta)
                    point_issued_at = forecast_point.issued_at
                    if bracket:
                        readings = bracket
                    else:
                        readings = (
                            WeatherReading(
                                wind_mph=None,
                                rain_in_per_hr=None,
                                snow_in_per_hr=None,
                                valid_at=None,
                                issued_at=forecast_point.issued_at,
                                status="out_of_range",
                            ),
                        )
                else:
                    readings = (
                        WeatherReading(
                            wind_mph=None,
                            rain_in_per_hr=None,
                            snow_in_per_hr=None,
                            valid_at=None,
                            issued_at=None,
                            status="missing",
                        ),
                    )
                    point_issued_at = None

                cls = classify_conservative_window(readings, plan.load_weight_lb, self._policy)
                rep = _select_representative_reading(readings, plan.load_weight_lb, self._policy)
                classifications.append(cls)

                checkpoint_records.append(
                    {
                        "checkpoint_index": pt.index,
                        "cumulative_distance_m": pt.cumulative_distance_m,
                        "lat": pt.lat,
                        "lon": pt.lon,
                        "eta_at": eta,
                        "weather_valid_at": rep.valid_at,
                        "wind_mph": float(rep.wind_mph) if rep.wind_mph is not None else None,
                        "rain_in_per_hr": (
                            float(rep.rain_in_per_hr) if rep.rain_in_per_hr is not None else None
                        ),
                        "snow_in_per_hr": (
                            float(rep.snow_in_per_hr) if rep.snow_in_per_hr is not None else None
                        ),
                        "risk_severity": cls.severity.value,
                        "weather_status": rep.status if cls.severity == Severity.UNKNOWN else cls.status,
                        "risk_reasons": list(cls.reasons),
                        "is_display_checkpoint": pt.index in display_indices,
                        "forecast_issued_at": point_issued_at,
                    }
                )

            segments = build_voronoi_risk_segments(
                coords_lat_lon=provider_route.coordinates_lat_lon,
                points=sampled_points,
                classifications=classifications,
                total_distance_m=provider_route.distance_m,
            )
            risk_score = score_route(segments, total_distance_m=provider_route.distance_m)

            ranking_inputs.append(
                RouteRankingInput(
                    route_id=route_key,
                    duration_seconds=provider_route.duration_seconds,
                    distance_m=provider_route.distance_m,
                    risk=risk_score,
                )
            )
            evaluated_by_key[route_key] = {
                "route_key": route_key,
                "provider_route": provider_route,
                "fingerprint": item["fingerprint"],
                "eta_method": eta_method,
                "risk_score": risk_score,
                "segments": segments,
                "checkpoints": checkpoint_records,
            }

        outcome = rank_and_recommend(ranking_inputs)

        # Operator kill-switch for incident rollback (docs/14_DEPLOYMENT_AND_OPERATIONS.md).
        if (
            not bool(getattr(settings, "ENABLE_RECOMMENDATIONS", True))
            and outcome.recommendation_status == "recommended"
        ):
            outcome = RecommendationOutcome(
                recommendation_status="recommendations_disabled",
                recommended_route_id=None,
                recommendation_reason=(
                    "Automated route recommendations are temporarily paused by operator policy."
                ),
                ordered_route_ids=outcome.ordered_route_ids,
            )
            plan_warnings.append("Automated route recommendations are currently disabled.")

        ordered_route_dtos: list[dict[str, Any]] = []
        all_routes_covered = True

        for route_key in outcome.ordered_route_ids:
            ev = evaluated_by_key[route_key]
            provider_route = ev["provider_route"]
            risk_score = ev["risk_score"]
            segments = ev["segments"]
            checkpoints_data: list[dict[str, Any]] = ev["checkpoints"]

            if risk_score.coverage_fraction < 1.0:
                all_routes_covered = False

            display_checkpoints_dto = [
                _checkpoint_to_dto(
                    route_key=route_key,
                    checkpoint_index=cp["checkpoint_index"],
                    cumulative_distance_m=cp["cumulative_distance_m"],
                    lat=cp["lat"],
                    lon=cp["lon"],
                    eta_at=cp["eta_at"],
                    weather_valid_at=cp["weather_valid_at"],
                    wind_mph=cp["wind_mph"],
                    rain_in_per_hr=cp["rain_in_per_hr"],
                    snow_in_per_hr=cp["snow_in_per_hr"],
                    risk_severity=cp["risk_severity"],
                    risk_reasons=cp["risk_reasons"],
                    weather_status=cp["weather_status"],
                    forecast_issued_at=cp["forecast_issued_at"],
                )
                for cp in checkpoints_data
                if cp["is_display_checkpoint"]
            ]

            ordered_route_dtos.append(
                {
                    "id": route_key,
                    "summary_label": provider_route.summary_label or route_key,
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [round(lon, 6), round(lat, 6)]
                            for lat, lon in provider_route.coordinates_lat_lon
                        ],
                    },
                    "distance_m": round(float(provider_route.distance_m), 2),
                    "duration_seconds": round(float(provider_route.duration_seconds), 2),
                    "risk": _risk_score_to_dto(risk_score),
                    "checkpoints": display_checkpoints_dto,
                    "risk_segments": [_segment_to_dto(seg) for seg in segments],
                    "eta_method": ev["eta_method"],
                    "provider_warnings": list(provider_route.warnings),
                }
            )

        generated_at = timezone.now().astimezone(UTC)
        forecast_meta = {
            "issued_at": _to_iso_z(forecast_issued_at),
            "valid_until": _to_iso_z(forecast_valid_until),
            "timezone": "UTC",
            "reference_kind": "departure_instant",
            "reference_time": _to_iso_z(departure_utc),
            "slider_max_hours": slider_hours,
            "coverage_complete": all_routes_covered and bool(weather_by_coord),
        }

        result_payload = {
            "plan_id": plan.id,
            "state": Plan.Status.COMPLETED,
            "generated_at": _to_iso_z(generated_at),
            "data_mode": data_mode,
            "policy_version": self._policy.version,
            "origin": {
                "label": plan.origin_label,
                "latitude": plan.origin_lat,
                "longitude": plan.origin_lon,
            },
            "destination": {
                "label": plan.destination_label,
                "latitude": plan.destination_lat,
                "longitude": plan.destination_lon,
            },
            "departure_at": _to_iso_z(departure_utc),
            "departure_timezone": plan.departure_timezone,
            "load_weight_lb": float(plan.load_weight_lb),
            "display_checkpoint_miles": plan.display_checkpoint_miles,
            "recommendation_status": outcome.recommendation_status,
            "recommended_route_id": outcome.recommended_route_id,
            "recommendation_reason": outcome.recommendation_reason,
            "routes": ordered_route_dtos,
            "forecast": forecast_meta,
            "warnings": list(dict.fromkeys(plan_warnings)),
        }

        forecast_slices = self._build_forecast_slices(
            plan=plan,
            corridor_coords=unique_corridor_coords,
            weather_by_coord=weather_by_coord,
            forecast_issued_at=forecast_issued_at,
            forecast_valid_until=forecast_valid_until,
            data_origin=weather_provider.provider_name,
        )

        with transaction.atomic():
            plan.routes.all().delete()
            plan.forecast_slices.all().delete()

            for route_key in outcome.ordered_route_ids:
                ev = evaluated_by_key[route_key]
                provider_route = ev["provider_route"]
                risk_score = ev["risk_score"]
                rc = RouteCandidate.objects.create(
                    plan=plan,
                    route_key=route_key,
                    provider_route_id=provider_route.provider_route_id,
                    fingerprint=ev["fingerprint"],
                    distance_m=provider_route.distance_m,
                    duration_seconds=provider_route.duration_seconds,
                    eta_method=ev["eta_method"],
                    severe_miles=risk_score.severe_miles,
                    high_miles=risk_score.high_miles,
                    no_travel_miles=risk_score.no_travel_miles,
                    unknown_miles=risk_score.unknown_miles,
                    weighted_average_risk=risk_score.weighted_average_risk,
                    eligible=risk_score.eligible,
                    coverage_fraction=risk_score.coverage_fraction,
                    provider_warnings=list(provider_route.warnings),
                )
                Checkpoint.objects.bulk_create(
                    [
                        Checkpoint(
                            route=rc,
                            checkpoint_index=cp["checkpoint_index"],
                            cumulative_distance_m=cp["cumulative_distance_m"],
                            lat=cp["lat"],
                            lon=cp["lon"],
                            eta_at=cp["eta_at"],
                            weather_valid_at=cp["weather_valid_at"],
                            wind_mph=cp["wind_mph"],
                            rain_in_per_hr=cp["rain_in_per_hr"],
                            snow_in_per_hr=cp["snow_in_per_hr"],
                            risk_severity=cp["risk_severity"],
                            weather_status=cp["weather_status"],
                            risk_reasons=cp["risk_reasons"],
                            is_display_checkpoint=cp["is_display_checkpoint"],
                        )
                        for cp in ev["checkpoints"]
                    ]
                )

            if forecast_slices:
                ForecastSliceCache.objects.bulk_create(forecast_slices)

            plan.status = Plan.Status.COMPLETED
            plan.recommendation_status = outcome.recommendation_status
            plan.recommended_route_id = outcome.recommended_route_id
            plan.recommendation_reason = outcome.recommendation_reason
            plan.result_payload = result_payload
            plan.forecast_metadata = forecast_meta
            plan.warnings = result_payload["warnings"]
            plan.save()

            PlanJob.objects.filter(plan_id=plan.id).update(
                status=Plan.Status.COMPLETED,
                completed_at=generated_at,
                error_code="",
            )

        # Warm cache for initial slice (hour_offset=0) to speed up first render.
        if forecast_slices:
            first_slice = forecast_slices[0]
            slice_key = build_forecast_slice_cache_key(
                plan_id=plan.id,
                hour_offset=first_slice.hour_offset,
                policy_version=plan.policy_version,
                data_mode=plan.data_mode,
            )
            ttl = int(getattr(settings, "WEATHER_CACHE_TTL_SECONDS", 900))
            try:
                cache.set(slice_key, first_slice.payload, timeout=ttl)
            except Exception:
                logger.warning("Failed to warm initial forecast slice cache")

        record_plan_completed(
            status=outcome.recommendation_status,
            data_mode=data_mode,
            source=self._source,
        )
        return plan

    @staticmethod
    def format_plan_response(
        plan: Plan,
        *,
        display_checkpoint_miles: int | None = None,
    ) -> dict[str, Any]:
        """Return completed plan DTO, optionally re-filtering display checkpoints without altering risk."""
        raw_payload = copy.deepcopy(plan.result_payload)
        payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
        target_spacing = (
            int(display_checkpoint_miles)
            if display_checkpoint_miles is not None
            else int(plan.display_checkpoint_miles)
        )
        if target_spacing == int(plan.display_checkpoint_miles) or not payload.get("routes"):
            return payload

        forecast_issued_at = _parse_iso_utc((plan.forecast_metadata or {}).get("issued_at"))
        routes_by_key = {rc.route_key: rc for rc in plan.routes.all()}

        for route_dto in payload["routes"]:
            route_key = route_dto["id"]
            rc = routes_by_key.get(route_key)
            if rc is None:
                continue
            all_checkpoints = list(rc.checkpoints.all())
            if not all_checkpoints:
                continue

            sampled = [
                SampledPoint(
                    index=idx,
                    cumulative_distance_m=cp.cumulative_distance_m,
                    lat=cp.lat,
                    lon=cp.lon,
                    is_endpoint=(idx == 0 or idx == len(all_checkpoints) - 1),
                )
                for idx, cp in enumerate(all_checkpoints)
            ]
            selected_positions = set(
                select_display_checkpoint_indices(
                    sampled,
                    display_spacing_miles=target_spacing,
                    total_distance_m=rc.distance_m,
                )
            )
            route_dto["checkpoints"] = [
                _checkpoint_to_dto(
                    route_key=route_key,
                    checkpoint_index=cp.checkpoint_index,
                    cumulative_distance_m=cp.cumulative_distance_m,
                    lat=cp.lat,
                    lon=cp.lon,
                    eta_at=cp.eta_at,
                    weather_valid_at=cp.weather_valid_at,
                    wind_mph=cp.wind_mph,
                    rain_in_per_hr=cp.rain_in_per_hr,
                    snow_in_per_hr=cp.snow_in_per_hr,
                    risk_severity=cp.risk_severity,
                    risk_reasons=cp.risk_reasons,
                    weather_status=cp.weather_status,
                    forecast_issued_at=forecast_issued_at,
                )
                for pos, cp in enumerate(all_checkpoints)
                if pos in selected_positions
            ]

        payload["display_checkpoint_miles"] = target_spacing
        return payload

    def get_forecast_slice(self, plan: Plan, *, hour_offset: int) -> dict[str, Any]:
        """Return a wall-clock corridor weather heatmap slice relative to departure_at."""
        departure_utc = plan.departure_at.astimezone(UTC)
        valid_at = departure_utc + timedelta(hours=hour_offset)

        forecast_meta = plan.forecast_metadata or {}
        valid_until = _parse_iso_utc(forecast_meta.get("valid_until"))
        if valid_until is not None and valid_at > valid_until:
            raise ApiDomainError(
                code="FORECAST_OUT_OF_RANGE",
                message=(
                    f"Forecast at +{hour_offset}h ({_to_iso_z(valid_at)}) is beyond the "
                    f"available forecast horizon ({_to_iso_z(valid_until)})."
                ),
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                retryable=False,
            )

        cache_key = build_forecast_slice_cache_key(
            plan_id=plan.id,
            hour_offset=hour_offset,
            policy_version=plan.policy_version,
            data_mode=plan.data_mode,
        )
        cached_payload = cache.get(cache_key)
        if isinstance(cached_payload, dict):
            if cached_payload.get("out_of_range"):
                raise ApiDomainError(
                    code="FORECAST_OUT_OF_RANGE",
                    message=(
                        f"Forecast at +{hour_offset}h ({_to_iso_z(valid_at)}) is outside the "
                        "provider forecast horizon."
                    ),
                    status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                    retryable=False,
                )
            return cached_payload

        slice_record = ForecastSliceCache.objects.filter(
            plan=plan,
            hour_offset=hour_offset,
        ).first()
        if slice_record is not None:
            payload = dict(slice_record.payload)
            ttl = int(getattr(settings, "WEATHER_CACHE_TTL_SECONDS", 900))
            try:
                cache.set(cache_key, payload, timeout=ttl)
            except Exception:
                logger.warning("Failed to populate forecast slice cache")

            if payload.get("out_of_range"):
                raise ApiDomainError(
                    code="FORECAST_OUT_OF_RANGE",
                    message=(
                        f"Forecast at +{hour_offset}h ({_to_iso_z(valid_at)}) is outside the "
                        "provider forecast horizon."
                    ),
                    status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                    retryable=False,
                )
            return payload

        # Honest unavailable response (never fabricated placeholder points).
        return {
            "plan_id": plan.id,
            "hour_offset": hour_offset,
            "reference_kind": "departure_instant",
            "reference_time": _to_iso_z(departure_utc),
            "valid_at": _to_iso_z(valid_at),
            "issued_at": forecast_meta.get("issued_at"),
            "data_mode": plan.data_mode,
            "data_origin": "unavailable",
            "policy_version": plan.policy_version,
            "coverage_fraction": 0.0,
            "coverage_complete": False,
            "out_of_range": False,
            "points": [],
        }
