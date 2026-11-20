"""Provider ports, resilient HTTP client, and live/fixture adapters."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from providers.ports import (
    GeocodingProvider,
    GeoLocation,
    HourlyForecastPoint,
    ProviderError,
    ProviderRoute,
    RouteProvider,
    WeatherProvider,
)

if TYPE_CHECKING:
    from providers.http_client import ResilientHttpClient

__all__ = [
    "GeoLocation",
    "GeocodingProvider",
    "HourlyForecastPoint",
    "ProviderError",
    "ProviderRoute",
    "ResilientHttpClient",
    "RouteProvider",
    "WeatherProvider",
]


def __getattr__(name: str) -> Any:
    if name == "ResilientHttpClient":
        from providers.http_client import ResilientHttpClient

        return ResilientHttpClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
