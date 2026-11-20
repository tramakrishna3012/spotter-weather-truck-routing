"""Checkpoint ETA estimation using provider cumulative timing or proportional fallback."""

from __future__ import annotations

import math
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from domain.routing.sampling import SampledPoint


@dataclass(frozen=True)
class TimingSpan:
    """Cumulative distance (meters) and elapsed travel duration (seconds) along a route."""

    offset_distance_m: float
    duration_seconds: float


def _is_valid_cumulative_timing(spans: Sequence[TimingSpan] | None) -> bool:
    if not spans or len(spans) < 2:
        return False

    prev_dist = -1.0
    prev_dur = -1.0
    for span in spans:
        if not (
            math.isfinite(span.offset_distance_m) and math.isfinite(span.duration_seconds)
        ):
            return False
        if span.offset_distance_m < 0.0 or span.duration_seconds < 0.0:
            return False
        if span.offset_distance_m < prev_dist or span.duration_seconds < prev_dur:
            return False
        prev_dist = span.offset_distance_m
        prev_dur = span.duration_seconds

    return spans[-1].offset_distance_m > 0.0 and spans[-1].duration_seconds > 0.0


def _interpolate_elapsed_seconds(
    spans: Sequence[TimingSpan],
    offsets: Sequence[float],
    target_offset_m: float,
) -> float:
    if target_offset_m <= offsets[0]:
        return spans[0].duration_seconds
    if target_offset_m >= offsets[-1]:
        return spans[-1].duration_seconds

    right_idx = bisect_right(offsets, target_offset_m)
    if right_idx >= len(spans):
        return spans[-1].duration_seconds
    left_idx = max(0, right_idx - 1)

    d0 = offsets[left_idx]
    d1 = offsets[right_idx]
    t0 = spans[left_idx].duration_seconds
    t1 = spans[right_idx].duration_seconds
    if d1 <= d0:
        return t1
    ratio = (target_offset_m - d0) / (d1 - d0)
    return t0 + (t1 - t0) * ratio


def estimate_checkpoint_etas(
    points: Sequence[SampledPoint],
    departure_utc: datetime,
    total_distance_m: float,
    total_duration_seconds: float,
    cumulative_timing: Sequence[TimingSpan] | None = None,
) -> tuple[list[datetime], str]:
    """Compute UTC ETA for each sampled checkpoint and declare the timing fidelity method.

    Uses provider cumulative timing spans when valid and monotonically non-decreasing,
    returning `eta_method="provider_timing"`. Otherwise falls back honestly to
    distance-proportional estimation and returns `eta_method="proportional_approximation"`.
    """
    if departure_utc.tzinfo is None or departure_utc.utcoffset() is None:
        raise ValueError("departure_utc must be timezone-aware.")
    if not math.isfinite(total_distance_m) or total_distance_m <= 0.0:
        raise ValueError(
            f"total_distance_m must be finite and positive, got {total_distance_m!r}."
        )
    if not math.isfinite(total_duration_seconds) or total_duration_seconds <= 0.0:
        raise ValueError(
            f"total_duration_seconds must be finite and positive, got {total_duration_seconds!r}."
        )

    dep_utc = departure_utc.astimezone(UTC)
    if not points:
        return [], "provider_timing" if _is_valid_cumulative_timing(cumulative_timing) else "proportional_approximation"

    if _is_valid_cumulative_timing(cumulative_timing) and cumulative_timing is not None:
        spans = list(cumulative_timing)
        if spans[0].offset_distance_m > 0.0:
            spans.insert(0, TimingSpan(offset_distance_m=0.0, duration_seconds=0.0))
        offsets = [s.offset_distance_m for s in spans]
        span_total_dist = offsets[-1]
        dist_scale = span_total_dist / total_distance_m

        etas = [
            dep_utc
            + timedelta(
                seconds=_interpolate_elapsed_seconds(
                    spans, offsets, pt.cumulative_distance_m * dist_scale
                )
            )
            for pt in points
        ]
        return etas, "provider_timing"

    etas = [
        dep_utc
        + timedelta(
            seconds=(max(0.0, min(pt.cumulative_distance_m, total_distance_m)) / total_distance_m)
            * total_duration_seconds
        )
        for pt in points
    ]
    return etas, "proportional_approximation"
