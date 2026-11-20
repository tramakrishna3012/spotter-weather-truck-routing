"""Deterministic fixture truck routing provider for local dev and automated testing.

Always declares `data_mode = "fixture"` and attaches an explicit warning noting that
geometries are sample fixture corridors, never live HERE truck routing data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from domain.risk.units import miles_to_meters
from domain.routing.eta import TimingSpan
from domain.routing.polyline import (
    compute_cumulative_distances,
    haversine_meters,
    route_geometry_fingerprint,
)
from providers.ports import GeoLocation, ProviderRoute

FIXTURE_ROUTE_WARNING = "Fixture mode: sample routing geometry, not live HERE data."


@dataclass(frozen=True)
class _CorridorVariant:
    label: str
    waypoints: tuple[tuple[float, float], ...]
    avg_speed_mph: float


@dataclass(frozen=True)
class _CuratedCorridor:
    origin_coord: tuple[float, float]
    dest_coord: tuple[float, float]
    variants: tuple[_CorridorVariant, ...]


_CURATED_CORRIDORS: tuple[_CuratedCorridor, ...] = (
    # New York, NY <-> Philadelphia, PA (3 corridors)
    _CuratedCorridor(
        origin_coord=(40.7128, -74.0060),
        dest_coord=(39.9526, -75.1652),
        variants=(
            _CorridorVariant(
                label="I-95 / NJ Turnpike Corridor",
                waypoints=(
                    (40.6650, -74.2100),
                    (40.5050, -74.3650),
                    (40.2950, -74.6350),
                    (40.1350, -74.8250),
                ),
                avg_speed_mph=54.0,
            ),
            _CorridorVariant(
                label="US-1 / I-295 Bypass",
                waypoints=(
                    (40.6900, -74.2900),
                    (40.5500, -74.5100),
                    (40.3550, -74.6600),
                    (40.1950, -74.8800),
                ),
                avg_speed_mph=50.0,
            ),
            _CorridorVariant(
                label="I-78 / PA-309 Inland Freight Route",
                waypoints=(
                    (40.6800, -74.4500),
                    (40.6250, -74.8500),
                    (40.5600, -75.3400),
                    (40.2450, -75.2600),
                ),
                avg_speed_mph=53.0,
            ),
        ),
    ),
    # Chicago, IL <-> Detroit, MI (3 corridors)
    _CuratedCorridor(
        origin_coord=(41.8781, -87.6298),
        dest_coord=(42.3314, -83.0458),
        variants=(
            _CorridorVariant(
                label="I-94 Direct Freight Corridor",
                waypoints=(
                    (41.6150, -87.2200),
                    (41.9650, -86.4400),
                    (42.2650, -85.5850),
                    (42.2850, -84.4050),
                    (42.2700, -83.7350),
                ),
                avg_speed_mph=58.0,
            ),
            _CorridorVariant(
                label="I-80 / I-69 Southern Corridor",
                waypoints=(
                    (41.6200, -87.1100),
                    (41.6800, -86.1800),
                    (41.7350, -85.0050),
                    (41.9950, -84.0850),
                ),
                avg_speed_mph=57.0,
            ),
            _CorridorVariant(
                label="I-196 / I-96 Northern Michigan Corridor",
                waypoints=(
                    (41.7800, -86.7500),
                    (42.4050, -86.1800),
                    (42.8850, -85.6200),
                    (42.7250, -84.5500),
                    (42.5050, -83.6200),
                ),
                avg_speed_mph=56.0,
            ),
        ),
    ),
    # Denver, CO <-> Salt Lake City, UT (3 corridors — winter mountain storm test)
    _CuratedCorridor(
        origin_coord=(39.7392, -104.9903),
        dest_coord=(40.7608, -111.8910),
        variants=(
            _CorridorVariant(
                label="I-80 Southern Wyoming Corridor",
                waypoints=(
                    (40.5850, -105.0200),
                    (41.1400, -104.8200),
                    (41.7900, -107.2350),
                    (41.5850, -109.2200),
                    (41.2650, -110.9600),
                ),
                avg_speed_mph=56.0,
            ),
            _CorridorVariant(
                label="I-70 / US-6 Mountain Pass Corridor",
                waypoints=(
                    (39.6400, -106.3700),
                    (39.5500, -107.3250),
                    (39.0650, -108.5500),
                    (39.5950, -110.8100),
                    (40.1150, -111.6550),
                ),
                avg_speed_mph=49.0,
            ),
            _CorridorVariant(
                label="US-287 / I-80 Northern High-Plains Bypass",
                waypoints=(
                    (40.8200, -105.2800),
                    (41.8900, -105.7500),
                    (42.1900, -107.5600),
                    (41.9800, -109.7500),
                    (41.5200, -111.3200),
                ),
                avg_speed_mph=53.0,
            ),
        ),
    ),
    # Dallas, TX <-> Houston, TX (2 corridors — exercises honest 2-route result)
    _CuratedCorridor(
        origin_coord=(32.7767, -96.7970),
        dest_coord=(29.7604, -95.3698),
        variants=(
            _CorridorVariant(
                label="I-45 Direct Freight Corridor",
                waypoints=(
                    (32.0950, -96.4650),
                    (31.4600, -96.0550),
                    (30.7200, -95.5500),
                ),
                avg_speed_mph=60.0,
            ),
            _CorridorVariant(
                label="I-35W / US-290 Western Corridor",
                waypoints=(
                    (31.9950, -97.1200),
                    (31.1100, -97.0200),
                    (30.4250, -96.4500),
                    (30.0800, -95.8800),
                ),
                avg_speed_mph=56.0,
            ),
        ),
    ),
    # Seattle, WA <-> Portland, OR (2 corridors — exercises honest 2-route result)
    _CuratedCorridor(
        origin_coord=(47.6062, -122.3321),
        dest_coord=(45.5152, -122.6784),
        variants=(
            _CorridorVariant(
                label="I-5 Direct Corridor",
                waypoints=(
                    (47.0379, -122.9007),
                    (46.6550, -122.9500),
                    (46.1350, -122.9350),
                ),
                avg_speed_mph=56.0,
            ),
            _CorridorVariant(
                label="I-90 / US-97 / WA-14 Eastern Detour",
                waypoints=(
                    (47.4100, -121.4100),
                    (46.6020, -120.5060),
                    (45.6900, -120.8500),
                    (45.6350, -121.9400),
                ),
                avg_speed_mph=52.0,
            ),
        ),
    ),
    # Los Angeles, CA <-> Phoenix, AZ (3 corridors)
    _CuratedCorridor(
        origin_coord=(34.0522, -118.2437),
        dest_coord=(33.4484, -112.0740),
        variants=(
            _CorridorVariant(
                label="I-10 Desert Freight Corridor",
                waypoints=(
                    (34.0600, -117.3000),
                    (33.7200, -116.2150),
                    (33.6100, -114.5950),
                    (33.4850, -113.3200),
                ),
                avg_speed_mph=61.0,
            ),
            _CorridorVariant(
                label="I-15 / I-40 / US-93 Northern Corridor",
                waypoints=(
                    (34.8950, -117.0200),
                    (34.8400, -115.6100),
                    (34.7250, -114.1200),
                    (34.1850, -112.8900),
                ),
                avg_speed_mph=58.0,
            ),
            _CorridorVariant(
                label="I-8 Southern Corridor",
                waypoints=(
                    (33.2400, -117.1800),
                    (32.7900, -115.5600),
                    (32.6950, -114.6200),
                    (32.9450, -112.7100),
                ),
                avg_speed_mph=57.0,
            ),
        ),
    ),
)


def _subdivide_polyline(
    anchors: list[tuple[float, float]],
    target_step_m: float = 8_000.0,
) -> tuple[tuple[float, float], ...]:
    """Densify anchor waypoints smoothly so map lines and checkpoint slices look clean."""
    dense: list[tuple[float, float]] = [anchors[0]]
    for idx in range(1, len(anchors)):
        lat0, lon0 = anchors[idx - 1]
        lat1, lon1 = anchors[idx]
        seg_m = haversine_meters(lat0, lon0, lat1, lon1)
        steps = max(2, min(40, int(math.ceil(seg_m / target_step_m))))
        for step in range(1, steps + 1):
            t = step / steps
            dense.append((lat0 + (lat1 - lat0) * t, lon0 + (lon1 - lon0) * t))
    return tuple(dense)


def _generate_curved_corridor(
    origin: tuple[float, float],
    dest: tuple[float, float],
    *,
    lateral_fraction: float,
    num_interior: int = 16,
) -> tuple[tuple[float, float], ...]:
    """Generate a smooth deterministic arc between two coordinates."""
    lat0, lon0 = origin
    lat1, lon1 = dest
    d_lat = lat1 - lat0
    d_lon = lon1 - lon0
    # Perpendicular vector scaled by cosine of mid-latitude to stay visually balanced.
    mid_lat_rad = math.radians((lat0 + lat1) / 2.0)
    cos_lat = max(0.25, math.cos(mid_lat_rad))
    perp_lat = -d_lon * cos_lat
    perp_lon = d_lat / cos_lat

    pts: list[tuple[float, float]] = [origin]
    for i in range(1, num_interior + 1):
        t = i / (num_interior + 1)
        # Smooth sinusoidal bow with slight asymmetry for highway realism.
        bow = math.sin(math.pi * t) * lateral_fraction * (1.0 + 0.12 * math.sin(2.0 * math.pi * t))
        lat = max(-89.5, min(89.5, lat0 + d_lat * t + perp_lat * bow))
        lon = max(-179.5, min(179.5, lon0 + d_lon * t + perp_lon * bow))
        pts.append((lat, lon))
    pts.append(dest)
    return tuple(pts)


def _build_timing_spans(
    coords: tuple[tuple[float, float], ...],
    total_distance_m: float,
    avg_speed_mph: float,
) -> tuple[tuple[TimingSpan, ...], float]:
    """Build piecewise TimingSpans with slightly slower urban endpoints and faster highway cruise."""
    cum_dists = compute_cumulative_distances(coords)
    geom_total = cum_dists[-1]
    if geom_total <= 0.0:
        raise ValueError("Fixture route geometry has zero length.")

    scale = total_distance_m / geom_total
    avg_speed_mps = miles_to_meters(avg_speed_mph) / 3600.0
    spans: list[TimingSpan] = [TimingSpan(offset_distance_m=0.0, duration_seconds=0.0)]
    elapsed = 0.0
    prev_d = 0.0

    for idx in range(1, len(cum_dists)):
        d = cum_dists[idx] * scale
        delta_d = max(0.0, d - prev_d)
        if delta_d <= 0.0:
            continue
        mid_frac = ((prev_d + d) / 2.0) / total_distance_m
        # Slower near origin/destination (0.82x), faster in highway middle (1.06x).
        speed_factor = 0.82 + 0.24 * math.sin(math.pi * mid_frac)
        elapsed += delta_d / (avg_speed_mps * speed_factor)
        spans.append(TimingSpan(offset_distance_m=d, duration_seconds=elapsed))
        prev_d = d

    return tuple(spans), elapsed


def _find_curated_corridor(
    origin: GeoLocation,
    destination: GeoLocation,
    match_radius_m: float = 45_000.0,
) -> tuple[_CuratedCorridor, bool] | None:
    o = (origin.latitude, origin.longitude)
    d = (destination.latitude, destination.longitude)
    for corridor in _CURATED_CORRIDORS:
        forward = (
            haversine_meters(o[0], o[1], corridor.origin_coord[0], corridor.origin_coord[1])
            <= match_radius_m
            and haversine_meters(d[0], d[1], corridor.dest_coord[0], corridor.dest_coord[1])
            <= match_radius_m
        )
        if forward:
            return corridor, False
        reverse = (
            haversine_meters(o[0], o[1], corridor.dest_coord[0], corridor.dest_coord[1])
            <= match_radius_m
            and haversine_meters(d[0], d[1], corridor.origin_coord[0], corridor.origin_coord[1])
            <= match_radius_m
        )
        if reverse:
            return corridor, True
    return None


class FixtureRouteProvider:
    """Deterministic fixture route provider for development and automated testing."""

    provider_name = "fixture_routing"
    data_mode = "fixture"

    def __init__(self, *, default_speed_mph: float = 55.0) -> None:
        if not math.isfinite(default_speed_mph) or default_speed_mph <= 0.0:
            raise ValueError("default_speed_mph must be finite and positive.")
        self._default_speed_mph = float(default_speed_mph)

    def get_truck_routes(
        self,
        origin: GeoLocation,
        destination: GeoLocation,
        departure_utc: datetime,
        max_routes: int,
    ) -> list[ProviderRoute]:
        if departure_utc.tzinfo is None or departure_utc.utcoffset() is None:
            raise ValueError("departure_utc must be timezone-aware.")
        if max_routes < 1:
            raise ValueError(f"max_routes must be >= 1, got {max_routes!r}.")

        straight_m = haversine_meters(
            origin.latitude, origin.longitude, destination.latitude, destination.longitude
        )
        if straight_m < 100.0:
            return []

        o_coord = (origin.latitude, origin.longitude)
        d_coord = (destination.latitude, destination.longitude)

        routes: list[ProviderRoute] = []
        seen_fps: set[str] = set()

        matched = _find_curated_corridor(origin, destination)
        if matched is not None:
            corridor, is_reversed = matched
            for idx, variant in enumerate(corridor.variants):
                if len(routes) >= max_routes:
                    break
                mid_pts = tuple(reversed(variant.waypoints)) if is_reversed else variant.waypoints
                anchors = [o_coord, *mid_pts, d_coord]
                coords = _subdivide_polyline(anchors)
                cum = compute_cumulative_distances(coords)
                # Realistic road-network circuity multiplier over piecewise anchor polyline.
                distance_m = cum[-1] * 1.07
                timing_spans, duration_s = _build_timing_spans(
                    coords, distance_m, variant.avg_speed_mph
                )
                fp = route_geometry_fingerprint(coords)
                if fp in seen_fps:
                    continue
                seen_fps.add(fp)
                routes.append(
                    ProviderRoute(
                        provider_route_id=f"fixture-route-{idx + 1}",
                        coordinates_lat_lon=coords,
                        distance_m=distance_m,
                        duration_seconds=duration_s,
                        timing_spans=timing_spans,
                        warnings=(FIXTURE_ROUTE_WARNING,),
                        provider_name=self.provider_name,
                        summary_label=variant.label,
                    )
                )
            return routes

        # Generic deterministic corridor generator for arbitrary US/global coordinate pairs.
        short_trip = straight_m < miles_to_meters(25)
        specs: tuple[tuple[str, float, float, float], ...] = (
            ("Primary Freight Corridor", 0.03, 1.12, self._default_speed_mph + 2.0),
            ("Northern / Left Alternate", 0.16, 1.18, self._default_speed_mph - 1.0),
            ("Southern / Right Alternate", -0.18, 1.22, self._default_speed_mph - 3.0),
        )
        if short_trip:
            specs = specs[:2]

        for idx, (label, bow, circuity, speed_mph) in enumerate(specs):
            if len(routes) >= max_routes:
                break
            coords = _generate_curved_corridor(o_coord, d_coord, lateral_fraction=bow)
            cum = compute_cumulative_distances(coords)
            distance_m = cum[-1] * circuity
            timing_spans, duration_s = _build_timing_spans(coords, distance_m, speed_mph)
            fp = route_geometry_fingerprint(coords)
            if fp in seen_fps:
                continue
            seen_fps.add(fp)
            routes.append(
                ProviderRoute(
                    provider_route_id=f"fixture-route-{idx + 1}",
                    coordinates_lat_lon=coords,
                    distance_m=distance_m,
                    duration_seconds=duration_s,
                    timing_spans=timing_spans,
                    warnings=(FIXTURE_ROUTE_WARNING,),
                    provider_name=self.provider_name,
                    summary_label=label,
                )
            )

        return routes
