"""Open-Meteo batched hourly weather forecast adapter with strict unit and schema validation.

Follows docs/06_RISK_AND_RECOMMENDATION.md and docs/09_INTEGRATIONS_AND_SERVICES.md:
- Requests `hourly=wind_speed_10m,rain,snowfall`, `timezone=UTC`, `forecast_days=...`.
- Batches coordinates cleanly with bounded batch size and concurrency.
- Verifies `hourly_units` on EVERY response before converting via `domain.risk.units`.
- Never coerces None to 0; rejects negative/NaN/Inf as invalid readings (`status="invalid"`).
- Handles Open-Meteo's single-object vs JSON-array response shape cleanly.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from domain.risk.classifier import WeatherReading
from domain.risk.units import (
    InvalidMeasurementError,
    UnitConversionError,
    convert_rain_to_in_per_hr,
    convert_snow_to_in_per_hr,
    convert_wind_to_mph,
)
from providers.ports import HourlyForecastPoint, ProviderError

if TYPE_CHECKING:
    from providers.http_client import ResilientHttpClient


def _parse_utc_timestamp(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class OpenMeteoWeatherProvider:
    """Live Open-Meteo hourly forecast adapter supporting bounded coordinate batching."""

    provider_name = "open_meteo"
    data_mode = "live"

    def __init__(
        self,
        *,
        http_client: ResilientHttpClient,
        base_url: str,
        max_batch_size: int = 50,
        max_forecast_days: int = 7,
        max_workers: int = 4,
        api_key: str | None = None,
    ) -> None:
        if not base_url or not base_url.strip():
            raise ValueError("Open-Meteo base_url must be configured.")
        if max_batch_size < 1:
            raise ValueError(f"max_batch_size must be >= 1, got {max_batch_size!r}.")
        if max_forecast_days < 1 or max_forecast_days > 16:
            raise ValueError(f"max_forecast_days must be in [1, 16], got {max_forecast_days!r}.")
        if max_workers < 1:
            raise ValueError(f"max_workers must be >= 1, got {max_workers!r}.")

        self._http = http_client
        self._base_url = base_url.strip().rstrip("/")
        self._max_batch_size = int(max_batch_size)
        self._max_forecast_days = int(max_forecast_days)
        self._max_workers = int(max_workers)
        self._api_key = api_key.strip() if api_key and api_key.strip() else None

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

        start = start_utc.astimezone(UTC)
        end = end_utc.astimezone(UTC)
        if end < start:
            raise ValueError("end_utc must be >= start_utc.")

        if not coordinates_lat_lon:
            return []

        for lat, lon in coordinates_lat_lon:
            if not (
                math.isfinite(lat)
                and math.isfinite(lon)
                and -90.0 <= lat <= 90.0
                and -180.0 <= lon <= 180.0
            ):
                raise ValueError(f"Invalid coordinate: ({lat}, {lon}).")

        now_utc = datetime.now(UTC)
        days_ahead = max(1, int(math.ceil((end - now_utc).total_seconds() / 86400.0)) + 1)
        forecast_days = max(1, min(self._max_forecast_days, days_ahead))

        batches: list[list[tuple[float, float]]] = [
            list(coordinates_lat_lon[i : i + self._max_batch_size])
            for i in range(0, len(coordinates_lat_lon), self._max_batch_size)
        ]

        issued_at = now_utc
        if len(batches) == 1 or self._max_workers == 1:
            results: list[HourlyForecastPoint] = []
            for batch in batches:
                results.extend(self._fetch_batch(batch, forecast_days=forecast_days, issued_at=issued_at))
            return results

        worker_count = min(self._max_workers, len(batches))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [
                executor.submit(
                    self._fetch_batch,
                    batch,
                    forecast_days=forecast_days,
                    issued_at=issued_at,
                )
                for batch in batches
            ]
            ordered: list[HourlyForecastPoint] = []
            for fut in futures:
                ordered.extend(fut.result())
            return ordered

    def _fetch_batch(
        self,
        batch: list[tuple[float, float]],
        *,
        forecast_days: int,
        issued_at: datetime,
    ) -> list[HourlyForecastPoint]:
        params: dict[str, str] = {
            "latitude": ",".join(f"{lat:.5f}" for lat, _ in batch),
            "longitude": ",".join(f"{lon:.5f}" for _, lon in batch),
            "hourly": "wind_speed_10m,rain,snowfall",
            "timezone": "UTC",
            "forecast_days": str(forecast_days),
        }
        if self._api_key:
            params["apikey"] = self._api_key

        payload = self._http.get_json(
            f"{self._base_url}/forecast",
            params=params,
            provider_name=self.provider_name,
            endpoint_name="forecast",
        )

        # Open-Meteo returns a single JSON object for 1 coordinate, or a JSON array for >1.
        items: list[Any]
        if len(batch) == 1 and isinstance(payload, dict):
            items = [payload]
        elif isinstance(payload, list):
            items = payload
        else:
            raise ProviderError(
                code="PROVIDER_INVALID_SCHEMA",
                message="Unexpected Open-Meteo response shape for coordinate batch.",
                provider=self.provider_name,
                retryable=False,
            )

        if len(items) != len(batch):
            raise ProviderError(
                code="PROVIDER_BATCH_COUNT_MISMATCH",
                message=f"Open-Meteo returned {len(items)} locations for batch of {len(batch)}.",
                provider=self.provider_name,
                retryable=False,
            )

        return [
            self._parse_location_payload(item, requested_coord=coord, issued_at=issued_at)
            for item, coord in zip(items, batch, strict=True)
        ]

    def _parse_location_payload(
        self,
        item: Any,
        *,
        requested_coord: tuple[float, float],
        issued_at: datetime,
    ) -> HourlyForecastPoint:
        if not isinstance(item, dict):
            raise ProviderError(
                code="PROVIDER_INVALID_SCHEMA",
                message="Open-Meteo location entry must be a JSON object.",
                provider=self.provider_name,
                retryable=False,
            )

        units = item.get("hourly_units")
        hourly = item.get("hourly")
        if not isinstance(units, dict) or not isinstance(hourly, dict):
            raise ProviderError(
                code="PROVIDER_INVALID_SCHEMA",
                message="Open-Meteo response missing 'hourly_units' or 'hourly' object.",
                provider=self.provider_name,
                retryable=False,
            )

        wind_unit = units.get("wind_speed_10m")
        rain_unit = units.get("rain")
        snow_unit = units.get("snowfall")
        if not (
            isinstance(wind_unit, str)
            and isinstance(rain_unit, str)
            and isinstance(snow_unit, str)
        ):
            raise ProviderError(
                code="PROVIDER_MISSING_UNITS",
                message="Open-Meteo 'hourly_units' must specify wind_speed_10m, rain, and snowfall.",
                provider=self.provider_name,
                retryable=False,
            )

        # Fail fast if any declared provider unit is unrecognized.
        try:
            convert_wind_to_mph(None, wind_unit)
            convert_rain_to_in_per_hr(None, rain_unit)
            convert_snow_to_in_per_hr(None, snow_unit)
        except UnitConversionError as exc:
            raise ProviderError(
                code="PROVIDER_UNSUPPORTED_UNITS",
                message=str(exc),
                provider=self.provider_name,
                retryable=False,
            ) from exc

        times = hourly.get("time")
        winds = hourly.get("wind_speed_10m")
        rains = hourly.get("rain")
        snows = hourly.get("snowfall")
        if not (
            isinstance(times, list)
            and isinstance(winds, list)
            and isinstance(rains, list)
            and isinstance(snows, list)
        ):
            raise ProviderError(
                code="PROVIDER_INVALID_SCHEMA",
                message="Open-Meteo 'hourly' arrays must be lists for time, wind_speed_10m, rain, and snowfall.",
                provider=self.provider_name,
                retryable=False,
            )

        n = len(times)
        if n == 0 or len(winds) != n or len(rains) != n or len(snows) != n:
            raise ProviderError(
                code="PROVIDER_ARRAY_LENGTH_MISMATCH",
                message="Open-Meteo hourly arrays have empty or mismatched lengths.",
                provider=self.provider_name,
                retryable=False,
            )

        readings: list[WeatherReading] = []
        for idx in range(n):
            valid_at = _parse_utc_timestamp(times[idx])
            if valid_at is None:
                raise ProviderError(
                    code="PROVIDER_INVALID_TIMESTAMP",
                    message=f"Open-Meteo returned unparseable hourly timestamp at index {idx}.",
                    provider=self.provider_name,
                    retryable=False,
                )

            raw_w = winds[idx]
            raw_r = rains[idx]
            raw_s = snows[idx]

            if raw_w is None or raw_r is None or raw_s is None:
                # Never coerce missing provider measurements to zero.
                try:
                    w_val = convert_wind_to_mph(raw_w, wind_unit)
                    r_val = convert_rain_to_in_per_hr(raw_r, rain_unit)
                    s_val = convert_snow_to_in_per_hr(raw_s, snow_unit)
                    status = "missing"
                except InvalidMeasurementError:
                    w_val, r_val, s_val = None, None, None
                    status = "invalid"
                readings.append(
                    WeatherReading(
                        wind_mph=w_val,
                        rain_in_per_hr=r_val,
                        snow_in_per_hr=s_val,
                        valid_at=valid_at,
                        issued_at=issued_at,
                        status=status,
                    )
                )
                continue

            try:
                w_mph = convert_wind_to_mph(raw_w, wind_unit)
                r_in = convert_rain_to_in_per_hr(raw_r, rain_unit)
                s_in = convert_snow_to_in_per_hr(raw_s, snow_unit)
            except InvalidMeasurementError:
                readings.append(
                    WeatherReading(
                        wind_mph=None,
                        rain_in_per_hr=None,
                        snow_in_per_hr=None,
                        valid_at=valid_at,
                        issued_at=issued_at,
                        status="invalid",
                    )
                )
                continue

            readings.append(
                WeatherReading(
                    wind_mph=w_mph,
                    rain_in_per_hr=r_in,
                    snow_in_per_hr=s_in,
                    valid_at=valid_at,
                    issued_at=issued_at,
                    status="known",
                )
            )

        readings.sort(key=lambda r: r.valid_at or datetime.min.replace(tzinfo=UTC))
        req_lat, req_lon = requested_coord
        return HourlyForecastPoint(
            latitude=req_lat,
            longitude=req_lon,
            issued_at=issued_at,
            provider_name=self.provider_name,
            data_mode=self.data_mode,
            readings=tuple(readings),
            warnings=(),
        )
