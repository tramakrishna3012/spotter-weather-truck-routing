"""Scoped DRF throttle classes protecting plan submission, geocoding, and forecast endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework.throttling import SimpleRateThrottle

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.views import APIView


class _ScopedClientThrottle(SimpleRateThrottle):
    """Rate-limit by verified owner scope when present, falling back to client IP."""

    def get_cache_key(self, request: Request, view: APIView) -> str | None:
        if getattr(view, "throttle_scope", None) != self.scope:
            return None

        ident = getattr(request, "spotter_owner_scope", None) or self.get_ident(request)
        return str(
            self.cache_format
            % {
                "scope": self.scope,
                "ident": ident,
            }
        )


class PlanSubmitThrottle(_ScopedClientThrottle):
    """Throttle for POST /api/v1/plans submissions."""

    scope = "plan_submit"


class GeocodeThrottle(_ScopedClientThrottle):
    """Throttle for GET /api/v1/geocode search queries."""

    scope = "geocode"


class ForecastThrottle(_ScopedClientThrottle):
    """Throttle for GET /api/v1/plans/{id}/forecast slice requests."""

    scope = "forecast"
