"""Pure Python routing geometry, sampling, ETA, and Voronoi segmentation domain package."""

from domain.routing.eta import TimingSpan, estimate_checkpoint_etas
from domain.routing.polyline import (
    compute_cumulative_distances,
    decode_flexible_polyline,
    encode_flexible_polyline,
    haversine_meters,
    interpolate_point_at_distance,
    route_geometry_fingerprint,
    slice_polyline_by_distance,
)
from domain.routing.sampling import (
    SampledPoint,
    sample_route_points,
    select_display_checkpoint_indices,
)
from domain.routing.segments import RiskSegment, build_voronoi_risk_segments

__all__ = [
    "RiskSegment",
    "SampledPoint",
    "TimingSpan",
    "build_voronoi_risk_segments",
    "compute_cumulative_distances",
    "decode_flexible_polyline",
    "encode_flexible_polyline",
    "estimate_checkpoint_etas",
    "haversine_meters",
    "interpolate_point_at_distance",
    "route_geometry_fingerprint",
    "sample_route_points",
    "select_display_checkpoint_indices",
    "slice_polyline_by_distance",
]
