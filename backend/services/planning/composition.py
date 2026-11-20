"""Central composition root constructing provider adapters from validated settings.

Strictly enforces DATA_MODE separation:
- `fixture` -> deterministic local/test adapters (forbidden in production)
- `live` -> HERE Routing v8, HERE Geocoding v1, and Open-Meteo adapters behind ResilientHttpClient
Never silently falls back from live providers to fixture data.
"""

from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from providers.geocoding.fixture_adapter import FixtureGeocodingProvider
from providers.geocoding.here_adapter import HereGeocodingProvider
from providers.http_client import ResilientHttpClient
from providers.ports import GeocodingProvider, RouteProvider, WeatherProvider
from providers.routing.fixture_adapter import FixtureRouteProvider
from providers.routing.here_adapter import HereRouteProvider
from providers.weather.fixture_adapter import FixtureWeatherProvider
from providers.weather.open_meteo_adapter import OpenMeteoWeatherProvider

DEFAULT_MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MiB bounded provider response cap


def _extract_hostname(url: str, setting_name: str) -> str:
    hostname = (urlparse(url).hostname or "").strip().lower()
    if not hostname:
        raise ImproperlyConfigured(f"{setting_name} does not contain a valid hostname: {url!r}.")
    return hostname


def _resolve_data_mode() -> str:
    app_env = str(getattr(settings, "APP_ENV", "development")).lower()
    data_mode = str(getattr(settings, "DATA_MODE", "fixture")).lower()
    if app_env == "production" and data_mode != "live":
        raise ImproperlyConfigured(
            "DATA_MODE must be 'live' in production; fixture providers are forbidden."
        )
    if data_mode not in {"fixture", "live"}:
        raise ImproperlyConfigured(f"Unsupported DATA_MODE: {data_mode!r}.")
    return data_mode


def build_http_client(*, allowed_urls: list[tuple[str, str]]) -> ResilientHttpClient:
    """Build a hardened ResilientHttpClient restricted strictly to configured provider hosts."""
    allowed_hosts = {_extract_hostname(url, name) for name, url in allowed_urls}
    secret_values = tuple(
        val
        for val in (
            str(getattr(settings, "HERE_API_KEY", "") or ""),
            str(getattr(settings, "OPEN_METEO_API_KEY", "") or ""),
        )
        if val
    )
    app_env = str(getattr(settings, "APP_ENV", "development")).lower()
    return ResilientHttpClient(
        allowed_hosts=allowed_hosts,
        connect_timeout_seconds=float(getattr(settings, "PROVIDER_CONNECT_TIMEOUT_SECONDS", 5.0)),
        read_timeout_seconds=float(getattr(settings, "PROVIDER_READ_TIMEOUT_SECONDS", 20.0)),
        max_attempts=int(getattr(settings, "PROVIDER_MAX_ATTEMPTS", 3)),
        max_response_bytes=int(
            getattr(settings, "PROVIDER_MAX_RESPONSE_BYTES", DEFAULT_MAX_RESPONSE_BYTES)
        ),
        allow_insecure_http=(app_env in {"development", "test"}),
        secret_values=secret_values,
    )


def build_route_provider() -> RouteProvider:
    """Instantiate the configured truck RouteProvider."""
    data_mode = _resolve_data_mode()
    if data_mode == "fixture":
        return FixtureRouteProvider()

    base_url = str(getattr(settings, "HERE_ROUTING_BASE_URL", "")).strip()
    api_key = str(getattr(settings, "HERE_API_KEY", "")).strip()
    if not api_key:
        raise ImproperlyConfigured("HERE_API_KEY must be set when DATA_MODE='live'.")

    http_client = build_http_client(allowed_urls=[("HERE_ROUTING_BASE_URL", base_url)])
    return HereRouteProvider(
        http_client=http_client,
        base_url=base_url,
        api_key=api_key,
    )


def build_geocoding_provider() -> GeocodingProvider:
    """Instantiate the configured GeocodingProvider."""
    data_mode = _resolve_data_mode()
    if data_mode == "fixture":
        return FixtureGeocodingProvider()

    base_url = str(getattr(settings, "HERE_GEOCODING_BASE_URL", "")).strip()
    api_key = str(getattr(settings, "HERE_API_KEY", "")).strip()
    if not api_key:
        raise ImproperlyConfigured("HERE_API_KEY must be set when DATA_MODE='live'.")

    http_client = build_http_client(allowed_urls=[("HERE_GEOCODING_BASE_URL", base_url)])
    return HereGeocodingProvider(
        http_client=http_client,
        base_url=base_url,
        api_key=api_key,
    )


def build_weather_provider() -> WeatherProvider:
    """Instantiate the configured hourly WeatherProvider."""
    data_mode = _resolve_data_mode()
    max_horizon_hours = int(getattr(settings, "FORECAST_MAX_HORIZON_HOURS", 168))
    if data_mode == "fixture":
        return FixtureWeatherProvider(max_horizon_hours=max_horizon_hours)

    base_url = str(getattr(settings, "OPEN_METEO_BASE_URL", "")).strip()
    api_key = str(getattr(settings, "OPEN_METEO_API_KEY", "") or "").strip() or None
    max_forecast_days = max(1, min(16, (max_horizon_hours + 23) // 24))
    max_workers = int(getattr(settings, "PLANNING_CONCURRENCY", 4))

    http_client = build_http_client(allowed_urls=[("OPEN_METEO_BASE_URL", base_url)])
    return OpenMeteoWeatherProvider(
        http_client=http_client,
        base_url=base_url,
        max_forecast_days=max_forecast_days,
        max_workers=max_workers,
        api_key=api_key,
    )
