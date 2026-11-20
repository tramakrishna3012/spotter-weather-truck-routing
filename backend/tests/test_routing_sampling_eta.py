"""Unit tests for HERE Flexible Polyline decoding, checkpoint sampling, ETA, and Voronoi segments."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from domain.risk.classifier import ClassificationResult
from domain.risk.policy import Severity
from domain.risk.units import miles_to_meters
from domain.routing.eta import TimingSpan, estimate_checkpoint_etas
from domain.routing.polyline import (
    compute_cumulative_distances,
    decode_flexible_polyline,
    encode_flexible_polyline,
    route_geometry_fingerprint,
)
from domain.routing.sampling import (
    SampledPoint,
    sample_route_points,
    select_display_checkpoint_indices,
)
from domain.routing.segments import build_voronoi_risk_segments

pytestmark = pytest.mark.unit


def _make_cls(severity: Severity, reason: str = "test_reason") -> ClassificationResult:
    status = (
        "no_travel"
        if severity == Severity.NO_TRAVEL
        else ("unknown" if severity == Severity.UNKNOWN else "known")
    )
    return ClassificationResult(
        severity=severity,
        status=status,
        reasons=(reason,),
        wind_severity=severity,
        rain_severity=Severity.LOW,
        snow_severity=Severity.LOW,
    )


def _straight_corridor(lat_start: float, lon_start: float, lat_end: float, lon_end: float, n: int = 20) -> list[tuple[float, float]]:
    return [
        (
            lat_start + (lat_end - lat_start) * (i / (n - 1)),
            lon_start + (lon_end - lon_start) * (i / (n - 1)),
        )
        for i in range(n)
    ]


class TestFlexiblePolyline:
    """Official HERE Flexible Polyline 2D and 3D test vectors and error rejection."""

    def test_official_2d_test_vector(self) -> None:
        # Official HERE Flexible Polyline spec 2D vector (precision=5)
        encoded = "BFoz5xJ67i1B1B7PzIhaxL7Y"
        decoded = decode_flexible_polyline(encoded)
        expected = [
            (50.10228, 8.69821),
            (50.10201, 8.69567),
            (50.10063, 8.69150),
            (50.09878, 8.68752),
        ]
        assert len(decoded) == len(expected)
        for (lat, lon), (exp_lat, exp_lon) in zip(decoded, expected, strict=True):
            assert lat == pytest.approx(exp_lat, abs=1e-5)
            assert lon == pytest.approx(exp_lon, abs=1e-5)

    def test_3d_elevation_decoding(self) -> None:
        # Official HERE 3D vector with elevation (third_dim=3, altitude) and round-trip check
        coords = [
            (39.73920, -104.99030),
            (39.64000, -106.37000),
            (40.76080, -111.89100),
        ]
        elevations = [1609.0, 2850.5, 1288.0]
        encoded_3d = encode_flexible_polyline(
            coords,
            precision=5,
            third_dim=3,
            third_dim_values=elevations,
            third_dim_precision=1,
        )
        decoded = decode_flexible_polyline(encoded_3d)
        assert len(decoded) == len(coords)
        for (lat, lon), (exp_lat, exp_lon) in zip(decoded, coords, strict=True):
            assert lat == pytest.approx(exp_lat, abs=1e-5)
            assert lon == pytest.approx(exp_lon, abs=1e-5)

        # Official HERE 3D spec vector: BlBoz5xJ67i1BU1B7PUzIhaUxL7YU
        official_3d = decode_flexible_polyline("BlBoz5xJ67i1BU1B7PUzIhaUxL7YU")
        assert len(official_3d) == 4
        assert official_3d[0] == pytest.approx((50.10228, 8.69821), abs=1e-5)
        assert official_3d[-1] == pytest.approx((50.09878, 8.68752), abs=1e-5)

    @pytest.mark.parametrize("bad_input", ["", "!!!", "BFoz5xJ67i1", "BFoz5xJ67i1B1B7"])
    def test_invalid_or_truncated_polyline_rejected(self, bad_input: str) -> None:
        with pytest.raises(ValueError):
            decode_flexible_polyline(bad_input)

    def test_geometry_fingerprint_is_deterministic_and_vertex_density_invariant(self) -> None:
        # Along a meridian, linear lat interpolation matches geodesic arc-length exactly.
        coarse = [(40.0, -75.0), (41.0, -75.0)]
        dense = _straight_corridor(40.0, -75.0, 41.0, -75.0, n=50)
        distinct = [(40.0, -75.0), (40.5, -75.6), (41.0, -75.0)]
        assert route_geometry_fingerprint(coarse) == route_geometry_fingerprint(coarse)
        assert route_geometry_fingerprint(coarse) == route_geometry_fingerprint(dense)
        assert route_geometry_fingerprint(coarse) != route_geometry_fingerprint(distinct)


class TestRouteSampling:
    """Internal scoring checkpoint sampling and display checkpoint selection."""

    def test_endpoints_guaranteed_once_and_spacing_accurate(self) -> None:
        coords = _straight_corridor(39.7392, -104.9903, 40.7608, -111.8910, n=30)
        total_m = miles_to_meters(52.0)
        pts = sample_route_points(coords, spacing_miles=10.0, total_distance_m=total_m)

        # 0, 10, 20, 30, 40, 50, 52 miles -> 7 points
        assert len(pts) == 7
        assert pts[0].cumulative_distance_m == 0.0
        assert pts[0].is_endpoint is True
        assert pts[-1].cumulative_distance_m == pytest.approx(total_m, abs=1e-6)
        assert pts[-1].is_endpoint is True
        assert sum(1 for p in pts if p.is_endpoint) == 2
        # Monotonic distances
        for i in range(1, len(pts)):
            assert pts[i].cumulative_distance_m > pts[i - 1].cumulative_distance_m

    def test_route_shorter_than_spacing_returns_both_endpoints_once(self) -> None:
        coords = [(40.7128, -74.0060), (40.7580, -73.9855)]
        total_m = miles_to_meters(4.2)
        pts = sample_route_points(coords, spacing_miles=10.0, total_distance_m=total_m)
        assert len(pts) == 2
        assert pts[0].cumulative_distance_m == 0.0
        assert pts[1].cumulative_distance_m == pytest.approx(total_m, abs=1e-6)
        assert pts[0].is_endpoint and pts[1].is_endpoint

    def test_adaptive_max_checkpoints_cap_preserves_endpoints(self) -> None:
        coords = _straight_corridor(34.0, -118.0, 40.7, -74.0, n=50)
        total_m = miles_to_meters(2800.0)
        pts = sample_route_points(
            coords,
            spacing_miles=10.0,
            total_distance_m=total_m,
            max_checkpoints=50,
        )
        assert len(pts) == 50
        assert pts[0].cumulative_distance_m == 0.0
        assert pts[0].is_endpoint is True
        assert pts[-1].cumulative_distance_m == pytest.approx(total_m, abs=1e-6)
        assert pts[-1].is_endpoint is True

    def test_rejects_invalid_geometry_and_nonpositive_distance(self) -> None:
        with pytest.raises(ValueError):
            sample_route_points([(40.0, -74.0)], spacing_miles=10.0)
        with pytest.raises(ValueError):
            sample_route_points([(40.0, -74.0), (40.0, -74.0)], spacing_miles=10.0)
        with pytest.raises(ValueError):
            sample_route_points([(40.0, -74.0), (41.0, -74.0)], spacing_miles=10.0, total_distance_m=0.0)
        with pytest.raises(ValueError):
            sample_route_points([(40.0, -74.0), (41.0, -74.0)], spacing_miles=10.0, total_distance_m=-100.0)
        with pytest.raises(ValueError):
            sample_route_points([(40.0, -74.0), (41.0, -74.0)], spacing_miles=0.0)

    def test_display_checkpoint_indices_always_include_endpoints(self) -> None:
        coords = _straight_corridor(39.7392, -104.9903, 40.7608, -111.8910, n=30)
        total_m = miles_to_meters(150.0)
        pts = sample_route_points(coords, spacing_miles=10.0, total_distance_m=total_m)

        idx_10 = select_display_checkpoint_indices(pts, 10, total_m)
        idx_25 = select_display_checkpoint_indices(pts, 25, total_m)
        idx_50 = select_display_checkpoint_indices(pts, 50, total_m)

        for indices in (idx_10, idx_25, idx_50):
            assert indices[0] == 0
            assert indices[-1] == len(pts) - 1
            assert indices == sorted(set(indices))

        assert len(idx_10) > len(idx_25) > len(idx_50)


class TestEtaEstimation:
    """Provider cumulative timing vs proportional approximation and timezone/DST handling."""

    def test_provider_timing_uses_piecewise_spans(self) -> None:
        total_m = 100_000.0
        pts = [
            SampledPoint(0, 0.0, 40.0, -74.0, True),
            SampledPoint(1, 50_000.0, 40.5, -74.5, False),
            SampledPoint(2, 100_000.0, 41.0, -75.0, True),
        ]
        # First half takes 3000s (slow urban), second half takes 1000s (fast highway)
        spans = (
            TimingSpan(0.0, 0.0),
            TimingSpan(50_000.0, 3000.0),
            TimingSpan(100_000.0, 4000.0),
        )
        dep = datetime(2026, 11, 20, 12, 0, 0, tzinfo=UTC)
        etas, method = estimate_checkpoint_etas(
            points=pts,
            departure_utc=dep,
            total_distance_m=total_m,
            total_duration_seconds=4000.0,
            cumulative_timing=spans,
        )
        assert method == "provider_timing"
        assert etas == [
            dep,
            dep + timedelta(seconds=3000),
            dep + timedelta(seconds=4000),
        ]

    def test_proportional_approximation_fallback(self) -> None:
        total_m = 100_000.0
        pts = [
            SampledPoint(0, 0.0, 40.0, -74.0, True),
            SampledPoint(1, 25_000.0, 40.25, -74.25, False),
            SampledPoint(2, 100_000.0, 41.0, -75.0, True),
        ]
        dep = datetime(2026, 11, 20, 12, 0, 0, tzinfo=UTC)
        etas, method = estimate_checkpoint_etas(
            points=pts,
            departure_utc=dep,
            total_distance_m=total_m,
            total_duration_seconds=4000.0,
            cumulative_timing=None,
        )
        assert method == "proportional_approximation"
        assert etas == [
            dep,
            dep + timedelta(seconds=1000),
            dep + timedelta(seconds=4000),
        ]

    def test_dst_and_non_utc_offset_preservation(self) -> None:
        # US Spring-forward DST transition: 2026-03-08 01:30 EST (-05:00) == 06:30 UTC.
        # Adding 2 hours elapsed travel time must be 08:30 UTC (04:30 EDT, NOT 03:30).
        ny_tz = ZoneInfo("America/New_York")
        dep_local = datetime(2026, 3, 8, 1, 30, 0, tzinfo=ny_tz)
        pts = [
            SampledPoint(0, 0.0, 40.7128, -74.0060, True),
            SampledPoint(1, 100_000.0, 39.9526, -75.1652, True),
        ]
        etas, _ = estimate_checkpoint_etas(
            points=pts,
            departure_utc=dep_local,
            total_distance_m=100_000.0,
            total_duration_seconds=7200.0,
        )
        assert etas[0] == datetime(2026, 3, 8, 6, 30, 0, tzinfo=UTC)
        assert etas[1] == datetime(2026, 3, 8, 8, 30, 0, tzinfo=UTC)
        assert etas[1].astimezone(ny_tz).hour == 4
        assert etas[1].astimezone(ny_tz).utcoffset() == timedelta(hours=-4)

    def test_naive_departure_rejected(self) -> None:
        pts = [SampledPoint(0, 0.0, 40.0, -74.0, True)]
        with pytest.raises(ValueError, match="timezone-aware"):
            estimate_checkpoint_etas(
                points=pts,
                departure_utc=datetime(2026, 11, 20, 12, 0, 0),
                total_distance_m=1000.0,
                total_duration_seconds=60.0,
            )


class TestVoronoiRiskSegments:
    """Exact distance conservation and partial final segment attribution."""

    def test_exact_mileage_conservation_and_partial_final_segment(self) -> None:
        coords = _straight_corridor(40.0, -75.0, 40.3, -74.7, n=10)
        # 23-mile route with 10-mile spacing -> checkpoints at 0, 10, 20, 23 mi
        # Voronoi bounds: [0, 5], [5, 15], [15, 21.5], [21.5, 23]
        total_m = miles_to_meters(23.0)
        pts = sample_route_points(coords, spacing_miles=10.0, total_distance_m=total_m)
        assert len(pts) == 4

        classifications = [
            _make_cls(Severity.LOW),
            _make_cls(Severity.MODERATE),
            _make_cls(Severity.HIGH),
            _make_cls(Severity.SEVERE),
        ]
        segments = build_voronoi_risk_segments(
            coords_lat_lon=coords,
            points=pts,
            classifications=classifications,
            total_distance_m=total_m,
        )
        assert len(segments) == 4

        expected_mile_lengths = [5.0, 10.0, 6.5, 1.5]
        for seg, exp_mi in zip(segments, expected_mile_lengths, strict=True):
            assert (seg.to_distance_m - seg.from_distance_m) == pytest.approx(
                miles_to_meters(exp_mi), abs=1e-6
            )
            assert len(seg.coordinates) >= 2
            # GeoJSON [lon, lat] order
            assert -180.0 <= seg.coordinates[0][0] <= -70.0
            assert 39.0 <= seg.coordinates[0][1] <= 41.0

        # Exact conservation and contiguous boundaries
        assert segments[0].from_distance_m == 0.0
        assert segments[-1].to_distance_m == pytest.approx(total_m, abs=1e-9)
        for i in range(1, len(segments)):
            assert segments[i].from_distance_m == pytest.approx(segments[i - 1].to_distance_m, abs=1e-9)
        total_accounted = sum(seg.to_distance_m - seg.from_distance_m for seg in segments)
        assert total_accounted == pytest.approx(total_m, abs=1e-9)

    def test_compute_cumulative_distances_monotonic(self) -> None:
        coords = _straight_corridor(40.0, -75.0, 41.0, -74.0, n=5)
        cum = compute_cumulative_distances(coords)
        assert cum[0] == 0.0
        assert len(cum) == 5
        assert all(cum[i] > cum[i - 1] for i in range(1, len(cum)))
