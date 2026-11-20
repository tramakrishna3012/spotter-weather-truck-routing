"""Deterministic, collision-resistant SHA-256 cache keys for routing and weather data.

Keys normalize coordinate precision, provider identity, data mode, policy version,
and serialization schema version so incompatible results are never mixed across
different modes, policies, or route parameters.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

CACHE_SCHEMA_VERSION = "v1"


def _round_coord(value: float, precision: int) -> float:
    if not math.isfinite(value):
        raise ValueError(f"Coordinate must be finite, got {value!r}.")
    if precision < 0 or precision > 8:
        raise ValueError(f"coord_precision must be between 0 and 8, got {precision!r}.")
    return round(float(value), precision)


def _hash_payload(namespace: str, schema_version: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"spotter:{namespace}:{schema_version}:{digest}"


def build_route_cache_key(
    *,
    provider: str,
    data_mode: str,
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    departure_bucket_iso: str,
    max_routes: int,
    transport_mode: str = "truck",
    coord_precision: int = 4,
    schema_version: str = CACHE_SCHEMA_VERSION,
) -> str:
    """Build a deterministic cache key for truck routing responses."""
    payload = {
        "provider": provider.strip().lower(),
        "data_mode": data_mode.strip().lower(),
        "transport_mode": transport_mode.strip().lower(),
        "origin": [
            _round_coord(origin_lat, coord_precision),
            _round_coord(origin_lon, coord_precision),
        ],
        "destination": [
            _round_coord(dest_lat, coord_precision),
            _round_coord(dest_lon, coord_precision),
        ],
        "departure_bucket": departure_bucket_iso.strip(),
        "max_routes": int(max_routes),
        "coord_precision": int(coord_precision),
        "schema_version": schema_version,
    }
    return _hash_payload("route", schema_version, payload)


def build_weather_cache_key(
    *,
    provider: str,
    data_mode: str,
    lat: float,
    lon: float,
    start_bucket_iso: str,
    end_bucket_iso: str,
    coord_precision: int = 3,
    schema_version: str = CACHE_SCHEMA_VERSION,
) -> str:
    """Build a deterministic cache key for hourly weather forecast queries."""
    payload = {
        "provider": provider.strip().lower(),
        "data_mode": data_mode.strip().lower(),
        "coord": [
            _round_coord(lat, coord_precision),
            _round_coord(lon, coord_precision),
        ],
        "start_bucket": start_bucket_iso.strip(),
        "end_bucket": end_bucket_iso.strip(),
        "coord_precision": int(coord_precision),
        "schema_version": schema_version,
    }
    return _hash_payload("weather", schema_version, payload)


def build_forecast_slice_cache_key(
    *,
    plan_id: str,
    hour_offset: int,
    policy_version: str,
    data_mode: str,
    schema_version: str = CACHE_SCHEMA_VERSION,
) -> str:
    """Build a deterministic cache key for a wall-clock corridor forecast slice."""
    payload = {
        "plan_id": plan_id.strip(),
        "hour_offset": int(hour_offset),
        "policy_version": policy_version.strip(),
        "data_mode": data_mode.strip().lower(),
        "schema_version": schema_version,
    }
    return _hash_payload("forecast_slice", schema_version, payload)
