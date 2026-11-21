"""HERE Routing API v8 truck routing adapter.

Follows docs/09_INTEGRATIONS_AND_SERVICES.md:
- Requests `transportMode=truck` and `alternatives=max(0, max_routes - 1)`.
- Never fabricates missing alternative routes.
- Never fabricates truck dimensions, axles, or gross vehicle weight from cargo load weight.
- Decodes flexible polylines, builds cumulative TimingSpans from spans/sections,
  preserves truck notices/warnings, and deduplicates geometrically identical routes.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from domain.routing.eta import TimingSpan
from domain.routing.polyline import decode_flexible_polyline, route_geometry_fingerprint
from providers.ports import GeoLocation, ProviderError, ProviderRoute

if TYPE_CHECKING:
    from providers.http_client import ResilientHttpClient


def _extract_notices(raw_notices: Any) -> list[str]:
    warnings: list[str] = []
    if not isinstance(raw_notices, list):
        return warnings
    for notice in raw_notices:
        if not isinstance(notice, dict):
            continue
        code = str(notice.get("code", "")).strip()
        title = str(notice.get("title", "")).strip()
        severity = str(notice.get("severity", "")).strip()
        if title and code:
            prefix = f"[{severity}] " if severity else ""
            warnings.append(f"{prefix}{code}: {title}")
        elif title:
            warnings.append(title)
        elif code:
            warnings.append(code)
    return warnings


class HereRouteProvider:
    """Live HERE Routing API v8 adapter for truck routes."""

    provider_name = "here_routing_v8"
    data_mode = "live"

    def __init__(
        self,
        *,
        http_client: ResilientHttpClient,
        base_url: str,
        api_key: str,
    ) -> None:
        if not base_url or not base_url.strip():
            raise ValueError("HERE routing base_url must be configured.")
        if not api_key or not api_key.strip():
            raise ValueError("HERE routing api_key must be configured.")
        self._http = http_client
        self._base_url = base_url.strip().rstrip("/")
        self._api_key = api_key.strip()

    def get_truck_routes(
        self,
        origin: GeoLocation,
        destination: GeoLocation,
        departure_utc: datetime,
        max_routes: int,
    ) -> list[ProviderRoute]:
        if departure_utc.tzinfo is None or departure_utc.utcoffset() is None:
            raise ValueError("departure_utc must be timezone-aware.")
        if max_routes < 1:
            raise ValueError(f"max_routes must be >= 1, got {max_routes!r}.")

        dep_iso = departure_utc.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        params = {
            "transportMode": "truck",
            "origin": f"{origin.latitude:.6f},{origin.longitude:.6f}",
            "destination": f"{destination.latitude:.6f},{destination.longitude:.6f}",
            "alternatives": str(max(0, max_routes - 1)),
            "return": "polyline,summary,travelSummary",
            "spans": "length,duration",
            "departureTime": dep_iso,
            "apiKey": self._api_key,
        }

        payload = self._http.get_json(
            f"{self._base_url}/routes",
            params=params,
            provider_name=self.provider_name,
            endpoint_name="routes",
        )

        if not isinstance(payload, dict):
            raise ProviderError(
                code="PROVIDER_INVALID_SCHEMA",
                message="HERE routing response root must be a JSON object.",
                provider=self.provider_name,
                retryable=False,
            )

        raw_routes = payload.get("routes")
        if raw_routes is None:
            return []
        if not isinstance(raw_routes, list):
            raise ProviderError(
                code="PROVIDER_INVALID_SCHEMA",
                message="HERE routing response 'routes' field must be a list.",
                provider=self.provider_name,
                retryable=False,
            )

        routes: list[ProviderRoute] = []
        seen_fingerprints: set[str] = set()

        for route_idx, raw_route in enumerate(raw_routes):
            parsed = self._parse_route(raw_route, route_idx)
            if parsed is None:
                continue
            fp = route_geometry_fingerprint(parsed.coordinates_lat_lon)
            if fp in seen_fingerprints:
                continue
            seen_fingerprints.add(fp)
            routes.append(parsed)
            if len(routes) >= max_routes:
                break

        return routes

    def _parse_route(self, raw_route: Any, route_idx: int) -> ProviderRoute | None:
        if not isinstance(raw_route, dict):
            return None

        sections = raw_route.get("sections")
        if not isinstance(sections, list) or not sections:
            return None

        coords: list[tuple[float, float]] = []
        total_distance_m = 0.0
        total_duration_s = 0.0
        timing_spans: list[TimingSpan] = [TimingSpan(offset_distance_m=0.0, duration_seconds=0.0)]
        warnings: list[str] = _extract_notices(raw_route.get("notices"))
        has_span_timing = True
        cum_span_dist = 0.0
        cum_span_dur = 0.0

        for section in sections:
            if not isinstance(section, dict):
                return None

            encoded_polyline = section.get("polyline")
            if not isinstance(encoded_polyline, str) or not encoded_polyline:
                return None
            try:
                section_coords = decode_flexible_polyline(encoded_polyline)
            except ValueError as exc:
                raise ProviderError(
                    code="PROVIDER_INVALID_POLYLINE",
                    message=f"Failed to decode HERE flexible polyline: {exc}",
                    provider=self.provider_name,
                    retryable=False,
                ) from exc

            if len(section_coords) < 2:
                continue
            if coords and coords[-1] == section_coords[0]:
                coords.extend(section_coords[1:])
            else:
                coords.extend(section_coords)

            summary = section.get("travelSummary") or section.get("summary")
            if not isinstance(summary, dict):
                return None

            sec_len = summary.get("length")
            sec_dur = summary.get("duration")
            if (
                not isinstance(sec_len, (int, float))
                or not isinstance(sec_dur, (int, float))
                or not math.isfinite(sec_len)
                or not math.isfinite(sec_dur)
                or sec_len <= 0
                or sec_dur <= 0
            ):
                return None

            total_distance_m += float(sec_len)
            total_duration_s += float(sec_dur)
            warnings.extend(_extract_notices(section.get("notices")))

            raw_spans = section.get("spans")
            if has_span_timing and isinstance(raw_spans, list) and raw_spans:
                section_spans_ok = True
                for sp in raw_spans:
                    if not isinstance(sp, dict):
                        section_spans_ok = False
                        break
                    sp_len = sp.get("length")
                    sp_dur = sp.get("duration")
                    if (
                        not isinstance(sp_len, (int, float))
                        or not isinstance(sp_dur, (int, float))
                        or not math.isfinite(sp_len)
                        or not math.isfinite(sp_dur)
                        or sp_len < 0
                        or sp_dur < 0
                    ):
                        section_spans_ok = False
                        break
                    cum_span_dist += float(sp_len)
                    cum_span_dur += float(sp_dur)
                    if cum_span_dist > timing_spans[-1].offset_distance_m:
                        timing_spans.append(
                            TimingSpan(
                                offset_distance_m=cum_span_dist,
                                duration_seconds=cum_span_dur,
                            )
                        )
                if not section_spans_ok:
                    has_span_timing = False
            else:
                # Fall back to section-level cumulative checkpoint when spans omit duration.
                cum_span_dist = total_distance_m
                cum_span_dur = total_duration_s
                if cum_span_dist > timing_spans[-1].offset_distance_m:
                    timing_spans.append(
                        TimingSpan(
                            offset_distance_m=cum_span_dist,
                            duration_seconds=cum_span_dur,
                        )
                    )

        if len(coords) < 2 or total_distance_m <= 0.0 or total_duration_s <= 0.0:
            return None

        provider_route_id = str(raw_route.get("id") or f"here-route-{route_idx + 1}")
        final_spans = tuple(timing_spans) if (has_span_timing and len(timing_spans) >= 2) else ()
        deduped_warnings = tuple(dict.fromkeys(warnings))

        return ProviderRoute(
            provider_route_id=provider_route_id,
            coordinates_lat_lon=tuple(coords),
            distance_m=total_distance_m,
            duration_seconds=total_duration_s,
            timing_spans=final_spans,
            warnings=deduped_warnings,
            provider_name=self.provider_name,
            summary_label=f"Truck Route {route_idx + 1}",
        )
