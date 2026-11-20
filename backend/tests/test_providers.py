"""Respx-mocked HTTP contract tests for HERE Routing, HERE Geocoding, Open-Meteo, and ResilientHttpClient."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
import respx

from domain.routing.polyline import encode_flexible_polyline
from providers.geocoding.here_adapter import HereGeocodingProvider
from providers.http_client import ResilientHttpClient
from providers.ports import GeoLocation, ProviderError
from providers.routing.here_adapter import HereRouteProvider
from providers.weather.open_meteo_adapter import OpenMeteoWeatherProvider

pytestmark = pytest.mark.integration

_ORIGIN = GeoLocation(label="Denver, CO", latitude=39.7392, longitude=-104.9903)
_DEST = GeoLocation(label="Salt Lake City, UT", latitude=40.7608, longitude=-111.8910)
_DEP = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


def _make_http_client(
    *,
    allowed_hosts: set[str],
    max_attempts: int = 3,
    max_response_bytes: int = 2_000_000,
    circuit_failure_threshold: int = 3,
    circuit_reset_seconds: float = 30.0,
) -> ResilientHttpClient:
    return ResilientHttpClient(
        allowed_hosts=allowed_hosts,
        connect_timeout_seconds=2.0,
        read_timeout_seconds=5.0,
        max_attempts=max_attempts,
        max_response_bytes=max_response_bytes,
        backoff_base_seconds=0.01,
        backoff_max_seconds=0.05,
        circuit_failure_threshold=circuit_failure_threshold,
        circuit_reset_seconds=circuit_reset_seconds,
        secret_values=("test-here-secret",),
        client=httpx.Client(follow_redirects=False, trust_env=False),
    )


class TestHereRouteProvider:
    """Contract tests for HERE Routing API v8 truck adapter."""

    @respx.mock
    def test_sends_truck_params_decodes_polyline_spans_notices_and_deduplicates(self) -> None:
        poly_a = encode_flexible_polyline([(39.7392, -104.9903), (41.1400, -104.8200), (40.7608, -111.8910)])
        poly_b = encode_flexible_polyline([(39.7392, -104.9903), (39.5500, -107.3250), (40.7608, -111.8910)])

        route_mock = respx.get("https://router.hereapi.com/v8/routes").mock(
            return_value=httpx.Response(
                200,
                json={
                    "routes": [
                        {
                            "id": "here-r1",
                            "notices": [
                                {"code": "violatedTruckRestriction", "title": "Chain law advisory", "severity": "info"},
                            ],
                            "sections": [
                                {
                                    "polyline": poly_a,
                                    "travelSummary": {"length": 840000, "duration": 31000},
                                    "spans": [
                                        {"length": 400000, "duration": 15000},
                                        {"length": 440000, "duration": 16000},
                                    ],
                                    "notices": [
                                        {"code": "tollRoad", "title": "Toll segment", "severity": "info"},
                                    ],
                                }
                            ],
                        },
                        # Duplicate geometry of route 1 -> must be deduplicated
                        {
                            "id": "here-r1-dup",
                            "sections": [
                                {
                                    "polyline": poly_a,
                                    "travelSummary": {"length": 840000, "duration": 31050},
                                    "spans": [{"length": 840000, "duration": 31050}],
                                }
                            ],
                        },
                        # Distinct alternate route
                        {
                            "id": "here-r2",
                            "sections": [
                                {
                                    "polyline": poly_b,
                                    "travelSummary": {"length": 870000, "duration": 33500},
                                    "spans": [
                                        {"length": 300000, "duration": 12000},
                                        {"length": 570000, "duration": 21500},
                                    ],
                                }
                            ],
                        },
                    ]
                },
            )
        )

        with _make_http_client(allowed_hosts={"router.hereapi.com"}) as http:
            provider = HereRouteProvider(
                http_client=http,
                base_url="https://router.hereapi.com/v8",
                api_key="test-here-secret",
            )
            routes = provider.get_truck_routes(_ORIGIN, _DEST, _DEP, max_routes=3)

        assert route_mock.called
        req = route_mock.calls.last.request
        assert req.url.params["transportMode"] == "truck"
        assert req.url.params["alternatives"] == "2"
        assert req.url.params["departureTime"] == "2026-11-20T12:00:00Z"
        assert req.url.params["apiKey"] == "test-here-secret"

        # 3 returned by API, 1 was duplicate geometry -> 2 unique routes honestly returned
        assert len(routes) == 2
        assert routes[0].provider_route_id == "here-r1"
        assert routes[0].distance_m == 840000.0
        assert routes[0].duration_seconds == 31000.0
        assert len(routes[0].coordinates_lat_lon) == 3
        assert len(routes[0].timing_spans) == 3
        assert routes[0].timing_spans[-1].offset_distance_m == 840000.0
        assert routes[0].timing_spans[-1].duration_seconds == 31000.0
        assert any("Chain law advisory" in w for w in routes[0].warnings)
        assert any("Toll segment" in w for w in routes[0].warnings)
        assert routes[1].provider_route_id == "here-r2"

    @respx.mock
    @pytest.mark.parametrize("route_count", [0, 1, 2, 3])
    def test_handles_zero_one_two_three_routes_honestly(self, route_count: int) -> None:
        raw_routes: list[dict[str, Any]] = []
        for idx in range(route_count):
            poly = encode_flexible_polyline(
                [
                    (39.7392, -104.9903),
                    (39.7 + idx * 0.8, -108.0),
                    (40.7608, -111.8910),
                ]
            )
            raw_routes.append(
                {
                    "id": f"r-{idx}",
                    "sections": [
                        {
                            "polyline": poly,
                            "travelSummary": {"length": 800000 + idx * 10000, "duration": 30000 + idx * 500},
                        }
                    ],
                }
            )

        respx.get("https://router.hereapi.com/v8/routes").mock(
            return_value=httpx.Response(200, json={"routes": raw_routes})
        )

        with _make_http_client(allowed_hosts={"router.hereapi.com"}) as http:
            provider = HereRouteProvider(
                http_client=http,
                base_url="https://router.hereapi.com/v8",
                api_key="test-here-secret",
            )
            routes = provider.get_truck_routes(_ORIGIN, _DEST, _DEP, max_routes=3)

        assert len(routes) == route_count


class TestHereGeocodingProvider:
    """Contract tests for HERE Geocoding v1 adapter."""

    @respx.mock
    def test_returns_disambiguation_candidates(self) -> None:
        mock = respx.get("https://geocode.search.hereapi.com/v1/geocode").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "here:cm:il",
                            "title": "Springfield, IL, United States",
                            "address": {
                                "label": "Springfield, IL, United States",
                                "countryCode": "USA",
                                "stateCode": "IL",
                                "city": "Springfield",
                            },
                            "position": {"lat": 39.7817, "lng": -89.6501},
                            "scoring": {"queryScore": 0.98},
                        },
                        {
                            "id": "here:cm:mo",
                            "title": "Springfield, MO, United States",
                            "address": {
                                "label": "Springfield, MO, United States",
                                "countryCode": "USA",
                                "stateCode": "MO",
                                "city": "Springfield",
                            },
                            "position": {"lat": 37.2090, "lng": -93.2923},
                            "scoring": {"queryScore": 0.95},
                        },
                    ]
                },
            )
        )

        with _make_http_client(allowed_hosts={"geocode.search.hereapi.com"}) as http:
            provider = HereGeocodingProvider(
                http_client=http,
                base_url="https://geocode.search.hereapi.com/v1",
                api_key="test-here-secret",
            )
            results = provider.search("Springfield", limit=5)

        assert mock.called
        assert len(results) == 2
        assert results[0].label == "Springfield, IL, United States"
        assert results[0].region == "IL"
        assert results[0].confidence == pytest.approx(0.98)
        assert results[1].region == "MO"

    @respx.mock
    def test_handles_empty_results(self) -> None:
        respx.get("https://geocode.search.hereapi.com/v1/geocode").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        with _make_http_client(allowed_hosts={"geocode.search.hereapi.com"}) as http:
            provider = HereGeocodingProvider(
                http_client=http,
                base_url="https://geocode.search.hereapi.com/v1",
                api_key="test-here-secret",
            )
            assert provider.search("NowherevilleXYZ") == []
            assert provider.search("   ") == []


class TestOpenMeteoWeatherProvider:
    """Contract tests for Open-Meteo single/multi-point parsing, unit validation, and fail-closed readings."""

    @respx.mock
    def test_single_object_and_multi_point_list_with_unit_conversion(self) -> None:
        now_hour = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        t0 = now_hour.strftime("%Y-%m-%dT%H:00")
        t1 = (now_hour + timedelta(hours=1)).strftime("%Y-%m-%dT%H:00")

        single_payload = {
            "hourly_units": {
                "time": "iso8601",
                "wind_speed_10m": "km/h",
                "rain": "mm",
                "snowfall": "cm",
            },
            "hourly": {
                "time": [t0, t1],
                "wind_speed_10m": [16.09344, 88.51392],  # 10 mph, 55 mph
                "rain": [0.0, 25.4],  # 0 in/hr, 1 in/hr
                "snowfall": [0.0, 2.54],  # 0 in/hr, 1 in/hr
            },
        }
        respx.get("https://api.open-meteo.com/v1/forecast").mock(
            side_effect=[
                httpx.Response(200, json=single_payload),
                httpx.Response(200, json=[single_payload, single_payload]),
            ]
        )

        with _make_http_client(allowed_hosts={"api.open-meteo.com"}) as http:
            provider = OpenMeteoWeatherProvider(
                http_client=http,
                base_url="https://api.open-meteo.com/v1",
            )
            # Single coordinate -> single JSON object response
            one = provider.get_hourly_forecasts(
                [(39.7392, -104.9903)],
                now_hour,
                now_hour + timedelta(hours=2),
            )
            assert len(one) == 1
            assert len(one[0].readings) == 2
            assert one[0].readings[0].wind_mph == Decimal("10")
            assert one[0].readings[1].wind_mph == Decimal("55")
            assert one[0].readings[1].rain_in_per_hr == Decimal("1")
            assert one[0].readings[1].snow_in_per_hr == Decimal("1")
            assert one[0].readings[1].status == "known"

            # Multiple coordinates -> JSON array response
            two = provider.get_hourly_forecasts(
                [(39.7392, -104.9903), (40.7608, -111.8910)],
                now_hour,
                now_hour + timedelta(hours=2),
            )
            assert len(two) == 2

    @respx.mock
    def test_rejects_mismatched_array_lengths_and_unsupported_units(self) -> None:
        now_hour = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        t0 = now_hour.strftime("%Y-%m-%dT%H:00")
        t1 = (now_hour + timedelta(hours=1)).strftime("%Y-%m-%dT%H:00")

        respx.get("https://api.open-meteo.com/v1/forecast").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "hourly_units": {"wind_speed_10m": "km/h", "rain": "mm", "snowfall": "cm"},
                        "hourly": {
                            "time": [t0, t1],
                            "wind_speed_10m": [10.0],  # mismatch!
                            "rain": [0.0, 0.0],
                            "snowfall": [0.0, 0.0],
                        },
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "hourly_units": {"wind_speed_10m": "bogus_unit", "rain": "mm", "snowfall": "cm"},
                        "hourly": {
                            "time": [t0],
                            "wind_speed_10m": [10.0],
                            "rain": [0.0],
                            "snowfall": [0.0],
                        },
                    },
                ),
            ]
        )

        with _make_http_client(allowed_hosts={"api.open-meteo.com"}) as http:
            provider = OpenMeteoWeatherProvider(
                http_client=http,
                base_url="https://api.open-meteo.com/v1",
            )
            with pytest.raises(ProviderError) as err1:
                provider.get_hourly_forecasts([(39.7, -105.0)], now_hour, now_hour + timedelta(hours=1))
            assert err1.value.code == "PROVIDER_ARRAY_LENGTH_MISMATCH"

            with pytest.raises(ProviderError) as err2:
                provider.get_hourly_forecasts([(39.7, -105.0)], now_hour, now_hour + timedelta(hours=1))
            assert err2.value.code == "PROVIDER_UNSUPPORTED_UNITS"

    @respx.mock
    def test_never_coerces_null_or_negative_to_zero(self) -> None:
        now_hour = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        t0 = now_hour.strftime("%Y-%m-%dT%H:00")
        t1 = (now_hour + timedelta(hours=1)).strftime("%Y-%m-%dT%H:00")

        respx.get("https://api.open-meteo.com/v1/forecast").mock(
            return_value=httpx.Response(
                200,
                json={
                    "hourly_units": {"wind_speed_10m": "km/h", "rain": "mm", "snowfall": "cm"},
                    "hourly": {
                        "time": [t0, t1],
                        "wind_speed_10m": [None, -12.0],
                        "rain": [0.0, 0.0],
                        "snowfall": [0.0, 0.0],
                    },
                },
            )
        )

        with _make_http_client(allowed_hosts={"api.open-meteo.com"}) as http:
            provider = OpenMeteoWeatherProvider(
                http_client=http,
                base_url="https://api.open-meteo.com/v1",
            )
            pts = provider.get_hourly_forecasts(
                [(39.7, -105.0)], now_hour, now_hour + timedelta(hours=2)
            )
            r_null, r_neg = pts[0].readings
            assert r_null.status == "missing"
            assert r_null.wind_mph is None
            assert r_neg.status == "invalid"
            assert r_neg.wind_mph is None


class TestResilientHttpClient:
    """SSRF allowlist, redirect blocking, retry/backoff, and circuit breaker enforcement."""

    def test_ssrf_host_allowlist_and_scheme_rejection(self) -> None:
        with _make_http_client(allowed_hosts={"api.open-meteo.com"}) as http:
            with pytest.raises(ProviderError) as host_err:
                http.get_json("https://169.254.169.254/latest/meta-data/")
            assert host_err.value.code == "PROVIDER_HOST_NOT_ALLOWED"

            with pytest.raises(ProviderError) as scheme_err:
                http.get_json("http://api.open-meteo.com/v1/forecast")
            assert scheme_err.value.code == "PROVIDER_URL_SCHEME_BLOCKED"

            with pytest.raises(ProviderError) as cred_err:
                http.get_json("https://user:pass@api.open-meteo.com/v1/forecast")
            assert cred_err.value.code == "PROVIDER_URL_CREDENTIALS_BLOCKED"

    @respx.mock
    def test_blocks_3xx_redirects(self) -> None:
        respx.get("https://api.open-meteo.com/v1/forecast").mock(
            return_value=httpx.Response(302, headers={"Location": "https://evil.example.com/"})
        )
        with _make_http_client(allowed_hosts={"api.open-meteo.com"}) as http:
            with pytest.raises(ProviderError) as err:
                http.get_json("https://api.open-meteo.com/v1/forecast")
            assert err.value.code == "PROVIDER_REDIRECT_BLOCKED"
            assert err.value.status_code == 302

    @respx.mock
    def test_retries_with_backoff_on_429_and_503_then_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sleeps: list[float] = []
        monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))

        route = respx.get("https://api.open-meteo.com/v1/forecast").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "0.02"}),
                httpx.Response(503),
                httpx.Response(200, json={"ok": True}),
            ]
        )
        with _make_http_client(
            allowed_hosts={"api.open-meteo.com"},
            max_attempts=3,
            circuit_failure_threshold=5,
        ) as http:
            data = http.get_json("https://api.open-meteo.com/v1/forecast")

        assert data == {"ok": True}
        assert route.call_count == 3
        assert len(sleeps) == 2

    @respx.mock
    def test_circuit_breaker_trips_and_blocks_subsequent_calls(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(time, "sleep", lambda _s: None)
        route = respx.get("https://api.open-meteo.com/v1/forecast").mock(
            return_value=httpx.Response(503)
        )
        with _make_http_client(
            allowed_hosts={"api.open-meteo.com"},
            max_attempts=2,
            circuit_failure_threshold=2,
            circuit_reset_seconds=60.0,
        ) as http:
            with pytest.raises(ProviderError) as first_err:
                http.get_json("https://api.open-meteo.com/v1/forecast")
            assert first_err.value.code == "PROVIDER_UNAVAILABLE"
            assert route.call_count == 2

            # Next call must fail immediately with PROVIDER_CIRCUIT_OPEN without hitting network
            with pytest.raises(ProviderError) as cb_err:
                http.get_json("https://api.open-meteo.com/v1/forecast")
            assert cb_err.value.code == "PROVIDER_CIRCUIT_OPEN"
            assert cb_err.value.retryable is True
            assert route.call_count == 2
