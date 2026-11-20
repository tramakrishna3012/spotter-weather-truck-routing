"""Shared pytest fixtures and deterministic test isolation for Spotter backend."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def isolated_cache() -> Iterator[None]:
    """Ensure Django cache (throttling, route/weather/slice cache) is clean per test."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client() -> APIClient:
    """Return a fresh DRF APIClient instance."""
    return APIClient()


@pytest.fixture
def valid_departure_iso() -> str:
    """Return a deterministic upcoming UTC departure timestamp within serializer bounds."""
    dt = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)
    return dt.isoformat().replace("+00:00", "Z")


@pytest.fixture
def denver_to_slc_payload(valid_departure_iso: str) -> dict[str, Any]:
    """Canonical Denver -> Salt Lake City trip payload for integration tests."""
    return {
        "origin": {
            "label": "Denver, CO",
            "latitude": 39.7392,
            "longitude": -104.9903,
        },
        "destination": {
            "label": "Salt Lake City, UT",
            "latitude": 40.7608,
            "longitude": -111.8910,
        },
        "departure_at": valid_departure_iso,
        "load_weight_lb": 36000,
        "display_checkpoint_miles": 25,
    }


@pytest.fixture
def nyc_to_phl_payload(valid_departure_iso: str) -> dict[str, Any]:
    """Canonical New York -> Philadelphia trip payload for integration tests."""
    return {
        "origin": {
            "label": "New York, NY",
            "latitude": 40.7128,
            "longitude": -74.0060,
        },
        "destination": {
            "label": "Philadelphia, PA",
            "latitude": 39.9526,
            "longitude": -75.1652,
        },
        "departure_at": valid_departure_iso,
        "load_weight_lb": 22000,
        "display_checkpoint_miles": 25,
    }


@pytest.fixture
def fixed_utc_now() -> datetime:
    """Fixed UTC reference timestamp for deterministic unit and provider tests."""
    return datetime(2026, 11, 20, 12, 0, 0, tzinfo=UTC)
