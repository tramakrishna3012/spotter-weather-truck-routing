"""HERE Flexible Polyline decoding, geodesic distances, interpolation, slicing, and fingerprinting.

Pure Python stdlib implementation adhering to the official HERE Flexible Polyline
specification (version 1, 2D and 3D headers, zigzag delta varints).
"""

from __future__ import annotations

import hashlib
import math
from bisect import bisect_right
from collections.abc import Sequence

FORMAT_VERSION = 1
EARTH_RADIUS_M = 6_371_008.8

_ENCODING_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
_DECODING_TABLE: tuple[int, ...] = tuple(
    _ENCODING_ALPHABET.find(chr(code)) if code < 128 else -1 for code in range(128)
)


def _decode_unsigned_varint(encoded: str, index: int) -> tuple[int, int]:
    result = 0
    shift = 0
    length = len(encoded)

    while index < length:
        char_code = ord(encoded[index])
        if char_code >= 128:
            raise ValueError(f"Invalid non-ASCII character in flexible polyline at index {index}.")
        value = _DECODING_TABLE[char_code]
        if value < 0:
            raise ValueError(f"Invalid flexible polyline character {encoded[index]!r} at index {index}.")
        index += 1

        result |= (value & 0x1F) << shift
        if (value & 0x20) == 0:
            return result, index
        shift += 5
        if shift > 65:
            raise ValueError("Flexible polyline varint overflow.")

    raise ValueError("Truncated flexible polyline varint.")


def _to_signed_zigzag(unsigned: int) -> int:
    if unsigned & 1:
        return ~(unsigned >> 1)
    return unsigned >> 1


def _encode_unsigned_varint(value: int, out: list[str]) -> None:
    while value > 0x1F:
        out.append(_ENCODING_ALPHABET[(value & 0x1F) | 0x20])
        value >>= 5
    out.append(_ENCODING_ALPHABET[value])


def _encode_signed_zigzag(value: int, out: list[str]) -> None:
    encoded = ((~value) << 1) | 1 if value < 0 else value << 1
    _encode_unsigned_varint(encoded, out)


def decode_flexible_polyline(encoded: str) -> list[tuple[float, float]]:
    """Decode a HERE Flexible Polyline string into a list of (lat, lon) tuples.

    Supports both 2D and 3D headers (elevation/altitude/level/custom third dimension
    is parsed and discarded to return normalized 2D (lat, lon) coordinates).
    """
    if not isinstance(encoded, str) or not encoded:
        raise ValueError("Flexible polyline input must be a non-empty string.")

    index = 0
    version, index = _decode_unsigned_varint(encoded, index)
    if version != FORMAT_VERSION:
        raise ValueError(f"Unsupported flexible polyline version: {version}.")

    header, index = _decode_unsigned_varint(encoded, index)
    if (header >> 11) != 0:
        raise ValueError("Invalid flexible polyline header reserved bits.")

    precision = header & 0x0F
    third_dim = (header >> 4) & 0x07
    if third_dim in (4, 5):
        raise ValueError(f"Unsupported reserved third dimension code: {third_dim}.")

    factor = float(10**precision)
    coords: list[tuple[float, float]] = []
    last_lat = 0
    last_lon = 0
    last_z = 0
    length = len(encoded)

    while index < length:
        raw_lat, index = _decode_unsigned_varint(encoded, index)
        last_lat += _to_signed_zigzag(raw_lat)

        if index >= length:
            raise ValueError("Truncated flexible polyline: missing longitude delta.")
        raw_lon, index = _decode_unsigned_varint(encoded, index)
        last_lon += _to_signed_zigzag(raw_lon)

        if third_dim != 0:
            if index >= length:
                raise ValueError("Truncated flexible polyline: missing third-dimension delta.")
            raw_z, index = _decode_unsigned_varint(encoded, index)
            last_z += _to_signed_zigzag(raw_z)

        lat = last_lat / factor
        lon = last_lon / factor
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            raise ValueError(f"Decoded coordinate out of bounds: ({lat}, {lon}).")
        coords.append((lat, lon))

    return coords


def encode_flexible_polyline(
    coords_lat_lon: Sequence[tuple[float, float]],
    *,
    precision: int = 5,
    third_dim: int = 0,
    third_dim_values: Sequence[float] | None = None,
    third_dim_precision: int = 0,
) -> str:
    """Encode (lat, lon) coordinates into a HERE Flexible Polyline v1 string."""
    if not (0 <= precision <= 15):
        raise ValueError("Precision must be between 0 and 15.")
    if third_dim not in (0, 1, 2, 3, 6, 7):
        raise ValueError(f"Invalid third_dim code: {third_dim}.")
    if third_dim != 0 and (
        third_dim_values is None or len(third_dim_values) != len(coords_lat_lon)
    ):
        raise ValueError("third_dim_values must match coordinates length when third_dim != 0.")

    out: list[str] = []
    _encode_unsigned_varint(FORMAT_VERSION, out)
    header = precision | (third_dim << 4) | (third_dim_precision << 7)
    _encode_unsigned_varint(header, out)

    factor = 10**precision
    z_factor = 10**third_dim_precision
    last_lat = 0
    last_lon = 0
    last_z = 0

    for idx, (lat, lon) in enumerate(coords_lat_lon):
        scaled_lat = round(lat * factor)
        scaled_lon = round(lon * factor)
        _encode_signed_zigzag(scaled_lat - last_lat, out)
        _encode_signed_zigzag(scaled_lon - last_lon, out)
        last_lat = scaled_lat
        last_lon = scaled_lon

        if third_dim != 0 and third_dim_values is not None:
            scaled_z = round(third_dim_values[idx] * z_factor)
            _encode_signed_zigzag(scaled_z - last_z, out)
            last_z = scaled_z

    return "".join(out)


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS-84 coordinates in meters."""
    for val in (lat1, lon1, lat2, lon2):
        if not math.isfinite(val):
            raise ValueError("Coordinates must be finite numbers.")
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    sin_half_phi = math.sin(d_phi / 2.0)
    sin_half_lambda = math.sin(d_lambda / 2.0)
    a = sin_half_phi * sin_half_phi + math.cos(phi1) * math.cos(phi2) * (
        sin_half_lambda * sin_half_lambda
    )
    a = min(1.0, max(0.0, a))
    return 2.0 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def compute_cumulative_distances(coords_lat_lon: Sequence[tuple[float, float]]) -> list[float]:
    """Compute cumulative geodesic distance in meters along a sequence of (lat, lon) points."""
    if not coords_lat_lon:
        raise ValueError("coords_lat_lon must not be empty.")
    cum: list[float] = [0.0]
    total = 0.0
    for idx in range(1, len(coords_lat_lon)):
        prev_lat, prev_lon = coords_lat_lon[idx - 1]
        cur_lat, cur_lon = coords_lat_lon[idx]
        total += haversine_meters(prev_lat, prev_lon, cur_lat, cur_lon)
        cum.append(total)
    return cum


def interpolate_point_at_distance(
    coords_lat_lon: Sequence[tuple[float, float]],
    cum_dists: Sequence[float],
    target_m: float,
) -> tuple[float, float]:
    """Interpolate (lat, lon) at a target cumulative distance along a polyline."""
    if not coords_lat_lon or len(coords_lat_lon) != len(cum_dists):
        raise ValueError("coords_lat_lon and cum_dists must be non-empty and equal length.")
    if not math.isfinite(target_m):
        raise ValueError("target_m must be finite.")

    if target_m <= cum_dists[0]:
        return coords_lat_lon[0]
    if target_m >= cum_dists[-1]:
        return coords_lat_lon[-1]

    right_idx = bisect_right(cum_dists, target_m)
    if right_idx >= len(coords_lat_lon):
        return coords_lat_lon[-1]
    left_idx = max(0, right_idx - 1)

    d0 = cum_dists[left_idx]
    d1 = cum_dists[right_idx]
    span = d1 - d0
    if span <= 0.0:
        return coords_lat_lon[left_idx]

    ratio = (target_m - d0) / span
    lat0, lon0 = coords_lat_lon[left_idx]
    lat1, lon1 = coords_lat_lon[right_idx]
    return (lat0 + (lat1 - lat0) * ratio, lon0 + (lon1 - lon0) * ratio)


def slice_polyline_by_distance(
    coords_lat_lon: Sequence[tuple[float, float]],
    cum_dists: Sequence[float],
    start_m: float,
    end_m: float,
) -> list[list[float]]:
    """Slice a polyline between [start_m, end_m] into GeoJSON [[lon, lat], ...] coordinates."""
    if len(coords_lat_lon) < 2 or len(coords_lat_lon) != len(cum_dists):
        raise ValueError("Polyline must have at least 2 points matching cum_dists.")
    if not (math.isfinite(start_m) and math.isfinite(end_m)):
        raise ValueError("start_m and end_m must be finite.")
    if end_m < start_m:
        raise ValueError(f"end_m ({end_m}) must be >= start_m ({start_m}).")

    total = cum_dists[-1]
    clamped_start = max(0.0, min(start_m, total))
    clamped_end = max(0.0, min(end_m, total))

    start_lat, start_lon = interpolate_point_at_distance(coords_lat_lon, cum_dists, clamped_start)
    end_lat, end_lon = interpolate_point_at_distance(coords_lat_lon, cum_dists, clamped_end)

    geojson: list[list[float]] = [[start_lon, start_lat]]

    first_interior = bisect_right(cum_dists, clamped_start)
    for idx in range(first_interior, len(coords_lat_lon)):
        dist = cum_dists[idx]
        if dist >= clamped_end:
            break
        lat, lon = coords_lat_lon[idx]
        pt = [lon, lat]
        if pt != geojson[-1]:
            geojson.append(pt)

    end_pt = [end_lon, end_lat]
    if end_pt != geojson[-1] or len(geojson) < 2:
        geojson.append(end_pt)

    return geojson


def route_geometry_fingerprint(coords_lat_lon: Sequence[tuple[float, float]]) -> str:
    """Compute a deterministic SHA-256 fingerprint of normalized distance-sampled route geometry.

    Sampling along arc length at 64 evenly spaced stations rounded to 4 decimals (~11 m)
    detects geometrically equivalent routes even when vertex density differs slightly,
    while keeping genuinely distinct route corridors separate.
    """
    if len(coords_lat_lon) < 2:
        raise ValueError("Route geometry must contain at least 2 coordinates.")

    cum_dists = compute_cumulative_distances(coords_lat_lon)
    total_m = cum_dists[-1]
    sample_count = 64

    tokens: list[str] = [f"len:{round(total_m / 50.0) * 50}"]
    for i in range(sample_count):
        target = (total_m * i) / (sample_count - 1) if total_m > 0 else 0.0
        lat, lon = interpolate_point_at_distance(coords_lat_lon, cum_dists, target)
        tokens.append(f"{lat:.4f},{lon:.4f}")

    payload = "|".join(tokens).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
