"""HERE Geocoding & Autosuggest API v1 adapter with strict schema validation."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from providers.ports import GeoLocation, ProviderError

if TYPE_CHECKING:
    from providers.http_client import ResilientHttpClient


def _parse_here_items(payload: Any, *, provider_name: str, limit: int) -> list[GeoLocation]:
    if not isinstance(payload, dict):
        raise ProviderError(
            code="PROVIDER_INVALID_SCHEMA",
            message="HERE geocoding response root must be a JSON object.",
            provider=provider_name,
            retryable=False,
        )

    items = payload.get("items")
    if items is None:
        return []
    if not isinstance(items, list):
        raise ProviderError(
            code="PROVIDER_INVALID_SCHEMA",
            message="HERE geocoding response 'items' field must be a list.",
            provider=provider_name,
            retryable=False,
        )

    results: list[GeoLocation] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        position = item.get("position")
        if not isinstance(position, dict):
            continue
        lat = position.get("lat")
        lng = position.get("lng")
        if (
            not isinstance(lat, (int, float))
            or not isinstance(lng, (int, float))
            or isinstance(lat, bool)
            or isinstance(lng, bool)
            or not (math.isfinite(lat) and math.isfinite(lng))
            or not (-90.0 <= float(lat) <= 90.0 and -180.0 <= float(lng) <= 180.0)
        ):
            continue

        raw_address = item.get("address")
        address: dict[str, Any] = raw_address if isinstance(raw_address, dict) else {}
        raw_label = address.get("label") or item.get("title")
        if not isinstance(raw_label, str) or not raw_label.strip():
            continue

        raw_scoring = item.get("scoring")
        scoring: dict[str, Any] = raw_scoring if isinstance(raw_scoring, dict) else {}
        query_score = scoring.get("queryScore")
        confidence = (
            float(query_score)
            if isinstance(query_score, (int, float))
            and not isinstance(query_score, bool)
            and math.isfinite(query_score)
            else None
        )

        provider_id = item.get("id")
        country_code = address.get("countryCode")
        region = address.get("stateCode") or address.get("state")
        locality = address.get("city") or address.get("county")

        results.append(
            GeoLocation(
                label=raw_label.strip(),
                latitude=float(lat),
                longitude=float(lng),
                provider_id=str(provider_id).strip() if isinstance(provider_id, str) and provider_id.strip() else None,
                country_code=str(country_code).strip() if isinstance(country_code, str) and country_code.strip() else None,
                region=str(region).strip() if isinstance(region, str) and region.strip() else None,
                locality=str(locality).strip() if isinstance(locality, str) and locality.strip() else None,
                confidence=confidence,
            )
        )
        if len(results) >= limit:
            break

    return results


class HereGeocodingProvider:
    """Live HERE Geocoding & Autosuggest API v1 adapter."""

    provider_name = "here_geocoding_v1"
    data_mode = "live"

    def __init__(
        self,
        *,
        http_client: ResilientHttpClient,
        base_url: str,
        api_key: str,
    ) -> None:
        if not base_url or not base_url.strip():
            raise ValueError("HERE geocoding base_url must be configured.")
        if not api_key or not api_key.strip():
            raise ValueError("HERE geocoding api_key must be configured.")
        self._http = http_client
        self._base_url = base_url.strip().rstrip("/")
        self._api_key = api_key.strip()

    def search(self, query: str, limit: int = 5) -> list[GeoLocation]:
        """Resolve a free-text place query using HERE `/geocode` for user disambiguation."""
        cleaned = query.strip()
        if not cleaned:
            return []
        bounded_limit = max(1, min(int(limit), 20))

        payload = self._http.get_json(
            f"{self._base_url}/geocode",
            params={
                "q": cleaned,
                "limit": str(bounded_limit),
                "apiKey": self._api_key,
            },
            provider_name=self.provider_name,
            endpoint_name="geocode",
        )
        return _parse_here_items(payload, provider_name=self.provider_name, limit=bounded_limit)

    def autosuggest(
        self,
        query: str,
        *,
        at_lat: float,
        at_lon: float,
        limit: int = 5,
    ) -> list[GeoLocation]:
        """Fetch place autosuggestions around a reference coordinate via HERE `/autosuggest`."""
        cleaned = query.strip()
        if not cleaned:
            return []
        if not (
            math.isfinite(at_lat)
            and math.isfinite(at_lon)
            and -90.0 <= at_lat <= 90.0
            and -180.0 <= at_lon <= 180.0
        ):
            raise ValueError("at_lat and at_lon must be valid finite coordinates.")
        bounded_limit = max(1, min(int(limit), 20))

        payload = self._http.get_json(
            f"{self._base_url}/autosuggest",
            params={
                "q": cleaned,
                "at": f"{at_lat:.6f},{at_lon:.6f}",
                "limit": str(bounded_limit),
                "apiKey": self._api_key,
            },
            provider_name=self.provider_name,
            endpoint_name="autosuggest",
        )
        return _parse_here_items(payload, provider_name=self.provider_name, limit=bounded_limit)
