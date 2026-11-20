"""Typed provider interfaces (ports) and normalized provider DTOs."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from domain.risk.classifier import WeatherReading
from domain.routing.eta import TimingSpan


class ProviderError(Exception):
    """Typed error raised by external provider adapters and the resilient HTTP client."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        provider: str,
        retryable: bool = False,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.provider = provider
        self.retryable = retryable
        self.status_code = status_code

    def __repr__(self) -> str:
        return (
            f"ProviderError(code={self.code!r}, provider={self.provider!r}, "
            f"retryable={self.retryable!r}, status_code={self.status_code!r})"
        )


@dataclass(frozen=True)
class GeoLocation:
    """Normalized geographic location candidate or resolved trip endpoint."""

    label: str
    latitude: float
    longitude: float
    provider_id: str | None = None
    country_code: str | None = None
    region: str | None = None
    locality: str | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class ProviderRoute:
    """Normalized truck route candidate returned by a RouteProvider."""

    provider_route_id: str
    coordinates_lat_lon: tuple[tuple[float, float], ...]
    distance_m: float
    duration_seconds: float
    timing_spans: tuple[TimingSpan, ...] = ()
    warnings: tuple[str, ...] = ()
    provider_name: str = ""
    summary_label: str = ""


@dataclass(frozen=True)
class HourlyForecastPoint:
    """Normalized hourly weather forecast time series for one coordinate."""

    latitude: float
    longitude: float
    issued_at: datetime
    provider_name: str
    data_mode: str
    readings: tuple[WeatherReading, ...]
    warnings: tuple[str, ...] = ()

    def readings_for_timestamp(self, target_utc: datetime) -> tuple[WeatherReading, ...]:
        """Return the exact or bracketing hourly readings covering `target_utc`.

        For conservative classification between hourly forecast bins, returns both
        adjacent hourly bins `(floor_bin, ceil_bin)` when `target_utc` lies strictly
        between consecutive hours (<= 3600s apart). Returns an empty tuple when
        `target_utc` is outside the forecast horizon or readings lack valid timestamps.
        """
        if target_utc.tzinfo is None or target_utc.utcoffset() is None:
            raise ValueError("target_utc must be timezone-aware.")
        ts = target_utc.astimezone(UTC)

        dated: list[tuple[datetime, WeatherReading]] = [
            (r.valid_at.astimezone(UTC), r)
            for r in self.readings
            if r.valid_at is not None and r.valid_at.tzinfo is not None
        ]
        if not dated:
            return ()

        dated.sort(key=lambda item: item[0])
        if ts < dated[0][0] or ts > dated[-1][0]:
            return ()

        for idx, (bin_time, reading) in enumerate(dated):
            if bin_time == ts:
                return (reading,)
            if bin_time > ts:
                prev_time, prev_reading = dated[idx - 1]
                gap_seconds = (bin_time - prev_time).total_seconds()
                if gap_seconds <= 3600.0 + 1e-6:
                    return (prev_reading, reading)
                # Gap larger than 1 hour indicates missing intermediate forecast hour.
                return ()

        return ()


@runtime_checkable
class RouteProvider(Protocol):
    """Port for truck-aware routing and route alternatives."""

    provider_name: str
    data_mode: str

    def get_truck_routes(
        self,
        origin: GeoLocation,
        destination: GeoLocation,
        departure_utc: datetime,
        max_routes: int,
    ) -> list[ProviderRoute]: ...


@runtime_checkable
class GeocodingProvider(Protocol):
    """Port for address/place search and disambiguation."""

    provider_name: str
    data_mode: str

    def search(self, query: str, limit: int = 5) -> list[GeoLocation]: ...


@runtime_checkable
class WeatherProvider(Protocol):
    """Port for batched hourly weather forecasts."""

    provider_name: str
    data_mode: str

    def get_hourly_forecasts(
        self,
        coordinates_lat_lon: Sequence[tuple[float, float]],
        start_utc: datetime,
        end_utc: datetime,
    ) -> list[HourlyForecastPoint]: ...
