"""Deterministic spatially and temporally coherent fixture weather forecast provider.

Always declares `data_mode = "fixture"` and attaches an explicit warning noting that
readings are deterministic synthetic development data, never live Open-Meteo forecasts.

Includes distinct regional weather corridors so local development and automated tests
can exercise Low, Moderate, High, Severe, No-Travel, payload wind overrides, and smooth
0-48h corridor heatmap evolution.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from domain.risk.classifier import WeatherReading
from providers.ports import HourlyForecastPoint

FIXTURE_WEATHER_WARNING = (
    "Fixture mode: deterministic synthetic forecast, not live Open-Meteo data."
)


def _floor_hour_utc(dt: datetime) -> datetime:
    utc = dt.astimezone(UTC)
    return utc.replace(minute=0, second=0, microsecond=0)


def _ceil_hour_utc(dt: datetime) -> datetime:
    floored = _floor_hour_utc(dt)
    if dt.astimezone(UTC) > floored:
        return floored + timedelta(hours=1)
    return floored


def _gaussian(distance: float, sigma: float) -> float:
    return math.exp(-0.5 * (distance / sigma) ** 2)


def _synthesize_weather(
    lat: float,
    lon: float,
    valid_at: datetime,
    anchor_utc: datetime,
) -> tuple[Decimal, Decimal, Decimal]:
    """Compute smooth, deterministic (wind_mph, rain_in_per_hr, snow_in_per_hr).

    Uses continuous spatial/temporal wave and Gaussian storm-cell kernels so adjacent
    route checkpoints and consecutive forecast hours vary smoothly for map animations.
    """
    hour_offset = (valid_at - anchor_utc).total_seconds() / 3600.0
    # Smooth ambient baseline (Low conditions across general US geography).
    phase = 0.45 * lat + 0.35 * lon - 0.14 * hour_offset
    wind = 11.0 + 7.0 * (0.5 + 0.5 * math.sin(phase))
    rain = max(0.0, 0.04 * math.sin(0.6 * lat - 0.5 * lon - 0.18 * hour_offset))
    snow = 0.0

    # 1. Rocky Mountain / I-70 Winter Storm Corridor (Denver <-> Salt Lake City).
    #    Intense blizzard cell over Colorado mountain passes (around lat 39.55, lon -107.0)
    #    creating Severe / No-Travel snow (> 3.0 in/hr) on I-70 while I-80 & northern bypass
    #    stay primarily Moderate/High/Low so route comparison is dramatic and honest.
    rocky_cell_lon = -107.1 + 0.03 * hour_offset
    rocky_dist = math.hypot((lat - 39.55) * 1.6, (lon - rocky_cell_lon) * 0.75)
    rocky_intensity = _gaussian(rocky_dist, 1.15)
    if rocky_intensity > 0.05:
        snow += 3.35 * rocky_intensity
        wind += 22.0 * rocky_intensity

    # Secondary lighter snow band along southern Wyoming I-80 (~41.5, -108.0).
    wy_dist = math.hypot((lat - 41.55) * 1.4, (lon - (-108.2 + 0.04 * hour_offset)) * 0.65)
    wy_intensity = _gaussian(wy_dist, 1.3)
    if wy_intensity > 0.05:
        snow += 1.15 * wy_intensity
        wind += 16.0 * wy_intensity

    # 2. Midwest / Great Plains Crosswind Corridor (Chicago <-> Detroit & Central Plains).
    #    Wind gusts reach 37-49 mph along northern/direct bands to exercise exact payload
    #    overrides (>30,000 lb -> No Travel at 45-54 mph; >40,000 lb -> Severe at 35-44 mph).
    midwest_lat = 42.15 + 0.15 * math.sin(0.12 * hour_offset)
    midwest_lon = -85.6 + 0.06 * hour_offset
    mw_dist = math.hypot((lat - midwest_lat) * 1.8, (lon - midwest_lon) * 0.6)
    mw_intensity = _gaussian(mw_dist, 1.25)
    if mw_intensity > 0.05:
        wind += 34.0 * mw_intensity
        rain += 0.18 * mw_intensity

    # 3. Northeast / Mid-Atlantic Moving Rain Squall (New York <-> Philadelphia / Boston).
    #    Produces Low -> Moderate -> High -> Severe rain bands (0.10 to 0.62 in/hr) that
    #    drift steadily northeast over 48 hours for corridor slider visualization.
    ne_lat = 40.30 + 0.025 * hour_offset
    ne_lon = -74.65 + 0.045 * hour_offset
    ne_dist = math.hypot((lat - ne_lat) * 2.2, (lon - ne_lon) * 1.8)
    ne_intensity = _gaussian(ne_dist, 0.75)
    if ne_intensity > 0.05:
        rain += 0.58 * ne_intensity
        wind += 18.0 * ne_intensity

    # 4. General traveling frontal band across the continental US so arbitrary trips still
    #    exhibit realistic spatial/temporal Moderate and High weather pockets.
    front_lon = -98.0 + 0.28 * (hour_offset % 48.0)
    front_dist = abs(lon - front_lon + 0.35 * (lat - 36.0))
    front_intensity = _gaussian(front_dist, 2.2) * (0.5 + 0.5 * math.cos(0.4 * lat))
    if front_intensity > 0.08:
        rain += 0.32 * front_intensity
        wind += 14.0 * front_intensity

    wind_dec = Decimal(f"{max(0.0, wind):.2f}")
    rain_dec = Decimal(f"{max(0.0, rain):.3f}")
    snow_dec = Decimal(f"{max(0.0, snow):.3f}")
    return wind_dec, rain_dec, snow_dec


class FixtureWeatherProvider:
    """Deterministic synthetic weather provider for local dev and integration tests."""

    provider_name = "fixture_weather"
    data_mode = "fixture"

    def __init__(self, *, max_horizon_hours: int = 168) -> None:
        if max_horizon_hours < 1:
            raise ValueError(f"max_horizon_hours must be >= 1, got {max_horizon_hours!r}.")
        self._max_horizon_hours = int(max_horizon_hours)

    def get_hourly_forecasts(
        self,
        coordinates_lat_lon: Sequence[tuple[float, float]],
        start_utc: datetime,
        end_utc: datetime,
    ) -> list[HourlyForecastPoint]:
        if start_utc.tzinfo is None or start_utc.utcoffset() is None:
            raise ValueError("start_utc must be timezone-aware.")
        if end_utc.tzinfo is None or end_utc.utcoffset() is None:
            raise ValueError("end_utc must be timezone-aware.")

        start = _floor_hour_utc(start_utc)
        end = _ceil_hour_utc(end_utc)
        if end < start:
            raise ValueError("end_utc must be >= start_utc.")

        if not coordinates_lat_lon:
            return []

        total_hours = int((end - start).total_seconds() // 3600)
        bounded_hours = min(total_hours, self._max_horizon_hours)
        issued_at = start

        points: list[HourlyForecastPoint] = []
        for lat, lon in coordinates_lat_lon:
            if not (
                math.isfinite(lat)
                and math.isfinite(lon)
                and -90.0 <= lat <= 90.0
                and -180.0 <= lon <= 180.0
            ):
                raise ValueError(f"Invalid coordinate: ({lat}, {lon}).")

            readings: list[WeatherReading] = []
            for h in range(bounded_hours + 1):
                valid_at = start + timedelta(hours=h)
                wind_mph, rain_in, snow_in = _synthesize_weather(lat, lon, valid_at, start)
                readings.append(
                    WeatherReading(
                        wind_mph=wind_mph,
                        rain_in_per_hr=rain_in,
                        snow_in_per_hr=snow_in,
                        valid_at=valid_at,
                        issued_at=issued_at,
                        status="known",
                    )
                )

            points.append(
                HourlyForecastPoint(
                    latitude=lat,
                    longitude=lon,
                    issued_at=issued_at,
                    provider_name=self.provider_name,
                    data_mode=self.data_mode,
                    readings=tuple(readings),
                    warnings=(FIXTURE_WEATHER_WARNING,),
                )
            )

        return points
