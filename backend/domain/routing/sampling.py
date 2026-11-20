"""Deterministic internal scoring and display checkpoint sampling along route geometry."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from domain.risk.units import miles_to_meters
from domain.routing.polyline import compute_cumulative_distances, interpolate_point_at_distance


@dataclass(frozen=True)
class SampledPoint:
    """A distance-indexed point sampled along a route polyline."""

    index: int
    cumulative_distance_m: float
    lat: float
    lon: float
    is_endpoint: bool


def sample_route_points(
    coords_lat_lon: Sequence[tuple[float, float]],
    spacing_miles: float,
    total_distance_m: float | None = None,
    max_checkpoints: int = 600,
) -> list[SampledPoint]:
    """Generate internal scoring checkpoints along a route at fixed spacing.

    Always includes origin (0.0 m) and destination (total_distance_m) exactly once,
    even when route length is shorter than spacing_miles. Adapts interior spacing safely
    when a very long route would otherwise exceed max_checkpoints while preserving both endpoints.
    """
    if len(coords_lat_lon) < 2:
        raise ValueError("Route geometry must contain at least 2 points.")
    if not math.isfinite(spacing_miles) or spacing_miles <= 0.0:
        raise ValueError(f"spacing_miles must be finite and positive, got {spacing_miles!r}.")
    if max_checkpoints < 2:
        raise ValueError(f"max_checkpoints must be >= 2, got {max_checkpoints!r}.")

    cum_dists = compute_cumulative_distances(coords_lat_lon)
    geom_total_m = cum_dists[-1]
    if not math.isfinite(geom_total_m) or geom_total_m <= 0.0:
        raise ValueError("Route geometry has zero or invalid total length.")

    effective_total_m = geom_total_m if total_distance_m is None else float(total_distance_m)
    if not math.isfinite(effective_total_m) or effective_total_m <= 0.0:
        raise ValueError(
            f"total_distance_m must be finite and positive, got {effective_total_m!r}."
        )

    spacing_m = miles_to_meters(spacing_miles)
    max_interior = max_checkpoints - 2

    distances_m: list[float] = [0.0]
    if effective_total_m / spacing_m > max_interior:
        # Adapt spacing evenly across interior stations so total count == max_checkpoints.
        step_m = effective_total_m / (max_interior + 1)
        for step_idx in range(1, max_interior + 1):
            distances_m.append(step_idx * step_m)
    else:
        step_idx = 1
        while True:
            dist = step_idx * spacing_m
            if dist >= effective_total_m - 1e-6:
                break
            distances_m.append(dist)
            step_idx += 1

    distances_m.append(effective_total_m)

    scale = geom_total_m / effective_total_m
    last_idx = len(distances_m) - 1
    sampled: list[SampledPoint] = []
    for idx, dist_m in enumerate(distances_m):
        geom_dist = dist_m * scale
        lat, lon = interpolate_point_at_distance(coords_lat_lon, cum_dists, geom_dist)
        sampled.append(
            SampledPoint(
                index=idx,
                cumulative_distance_m=dist_m,
                lat=lat,
                lon=lon,
                is_endpoint=(idx == 0 or idx == last_idx),
            )
        )
    return sampled


def select_display_checkpoint_indices(
    points: Sequence[SampledPoint],
    display_spacing_miles: int,
    total_distance_m: float,
) -> list[int]:
    """Select display checkpoint indices nearest to 0, spacing, 2*spacing, ..., total_distance_m.

    Display spacing affects only which markers are highlighted in the UI; it never alters
    internal scoring or ranking. Always includes first (0) and last (len(points) - 1) indices.
    """
    if not points:
        raise ValueError("points must not be empty.")
    if display_spacing_miles <= 0:
        raise ValueError(f"display_spacing_miles must be positive, got {display_spacing_miles!r}.")
    if not math.isfinite(total_distance_m) or total_distance_m <= 0.0:
        raise ValueError(
            f"total_distance_m must be finite and positive, got {total_distance_m!r}."
        )

    if len(points) <= 2:
        return list(range(len(points)))

    step_m = miles_to_meters(display_spacing_miles)
    targets: list[float] = [0.0]
    step_idx = 1
    while True:
        dist = step_idx * step_m
        if dist >= total_distance_m - 1e-6:
            break
        targets.append(dist)
        step_idx += 1
    targets.append(total_distance_m)

    selected: set[int] = {0, len(points) - 1}
    for target in targets:
        best_idx = min(
            range(len(points)),
            key=lambda i: (abs(points[i].cumulative_distance_m - target), i),
        )
        selected.add(best_idx)

    return sorted(selected)
