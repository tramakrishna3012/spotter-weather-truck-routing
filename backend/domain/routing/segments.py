"""Voronoi midpoint route risk segmentation over distance axis."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from domain.risk.classifier import ClassificationResult
from domain.risk.policy import Severity
from domain.routing.polyline import compute_cumulative_distances, slice_polyline_by_distance
from domain.routing.sampling import SampledPoint


@dataclass(frozen=True)
class RiskSegment:
    """A continuous route interval attributed to one checkpoint classification."""

    from_distance_m: float
    to_distance_m: float
    severity: Severity
    status: str
    reason_codes: tuple[str, ...]
    coordinates: list[list[float]]


def build_voronoi_risk_segments(
    coords_lat_lon: Sequence[tuple[float, float]],
    points: Sequence[SampledPoint],
    classifications: Sequence[ClassificationResult],
    total_distance_m: float,
) -> list[RiskSegment]:
    """Partition [0, total_distance_m] into Voronoi midpoint risk segments.

    Point 0 owns [0, mid(p0, p1)], interior point i owns [mid(p_{i-1}, p_i), mid(p_i, p_{i+1})],
    and final point n-1 owns [mid(p_{n-2}, p_{n-1}), total_distance_m].
    Every nonzero meter along the route is accounted for exactly once.
    """
    if len(coords_lat_lon) < 2:
        raise ValueError("coords_lat_lon must contain at least 2 points.")
    if len(points) < 2:
        raise ValueError("At least 2 sampled checkpoints (origin and destination) are required.")
    if len(points) != len(classifications):
        raise ValueError(
            f"points ({len(points)}) and classifications ({len(classifications)}) must match."
        )
    if not math.isfinite(total_distance_m) or total_distance_m <= 0.0:
        raise ValueError(
            f"total_distance_m must be finite and positive, got {total_distance_m!r}."
        )

    for idx in range(1, len(points)):
        if points[idx].cumulative_distance_m < points[idx - 1].cumulative_distance_m:
            raise ValueError("Sampled points must be ordered by non-decreasing cumulative distance.")

    cum_dists = compute_cumulative_distances(coords_lat_lon)
    geom_total_m = cum_dists[-1]
    if geom_total_m <= 0.0:
        raise ValueError("Route geometry has zero length.")

    scale = geom_total_m / total_distance_m
    n = len(points)
    segments: list[RiskSegment] = []

    for i in range(n):
        start_m = (
            0.0
            if i == 0
            else (points[i - 1].cumulative_distance_m + points[i].cumulative_distance_m) / 2.0
        )
        end_m = (
            total_distance_m
            if i == n - 1
            else (points[i].cumulative_distance_m + points[i + 1].cumulative_distance_m) / 2.0
        )
        start_m = max(0.0, min(start_m, total_distance_m))
        end_m = max(start_m, min(end_m, total_distance_m))

        geom_start = start_m * scale
        geom_end = end_m * scale
        coords_geojson = slice_polyline_by_distance(coords_lat_lon, cum_dists, geom_start, geom_end)
        cls = classifications[i]

        segments.append(
            RiskSegment(
                from_distance_m=start_m,
                to_distance_m=end_m,
                severity=cls.severity,
                status=cls.status,
                reason_codes=cls.reasons,
                coordinates=coords_geojson,
            )
        )

    return segments
