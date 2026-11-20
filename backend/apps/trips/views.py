"""Versioned DRF views for Spotter health, geocoding, trip planning, and forecast slices."""

from __future__ import annotations

import logging
from datetime import UTC, timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db import connection, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.trips.models import Plan, PlanJob
from apps.trips.serializers import (
    CreatePlanSerializer,
    ForecastSliceQuerySerializer,
    GeocodeQuerySerializer,
    PlanDetailQuerySerializer,
)
from config.exceptions import ApiDomainError
from domain.risk.policy import POLICY_VERSION
from infrastructure.cache.keys import build_forecast_slice_cache_key
from infrastructure.security.scope import (
    create_guest_session_token,
    verify_guest_session_token,
)

logger = logging.getLogger("spotter.api.views")


def _extract_raw_session_token(request: Request) -> str | None:
    header_token = request.headers.get(settings.SESSION_HEADER_NAME)
    if isinstance(header_token, str) and header_token.strip():
        return header_token.strip()
    cookie_token = request.COOKIES.get(settings.SESSION_COOKIE_NAME)
    if isinstance(cookie_token, str) and cookie_token.strip():
        return cookie_token.strip()
    return None


def _resolve_owner_scope(request: Request) -> str | None:
    raw_token = _extract_raw_session_token(request)
    if not raw_token:
        return None
    return verify_guest_session_token(raw_token, settings.SECRET_KEY)


def _attach_guest_session(response: Response, signed_token: str) -> None:
    """Emit the signed guest session token in both header and HttpOnly SameSite=Lax cookie."""
    response[settings.SESSION_HEADER_NAME] = signed_token
    max_age = max(int(getattr(settings, "PLAN_RESULT_TTL_SECONDS", 3600)) * 2, 86400)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=signed_token,
        max_age=max_age,
        httponly=True,
        secure=bool(getattr(settings, "SESSION_COOKIE_SECURE", False)),
        samesite=getattr(settings, "SESSION_COOKIE_SAMESITE", "Lax"),
        path="/",
    )


def _get_scoped_plan_or_404(request: Request, plan_id: str) -> Plan:
    """Fetch an unexpired Plan scoped strictly to the caller's verified owner_scope.

    Missing session, unknown ID, cross-session ID, and expired plans all return the
    exact same 404 PLAN_NOT_FOUND response to prevent plan ID enumeration.
    """
    owner_scope = getattr(request, "spotter_owner_scope", None) or _resolve_owner_scope(request)
    if not owner_scope:
        raise ApiDomainError(
            code="PLAN_NOT_FOUND",
            message="The requested plan was not found or has expired.",
            status_code=status.HTTP_404_NOT_FOUND,
            retryable=False,
        )

    plan = (
        Plan.objects.filter(
            id=plan_id,
            owner_scope=owner_scope,
            expires_at__gt=timezone.now(),
        )
        .prefetch_related("routes__checkpoints")
        .first()
    )
    if not isinstance(plan, Plan):
        raise ApiDomainError(
            code="PLAN_NOT_FOUND",
            message="The requested plan was not found or has expired.",
            status_code=status.HTTP_404_NOT_FOUND,
            retryable=False,
        )
    return plan


def _format_pending_payload(plan: Plan) -> dict[str, Any]:
    return {
        "plan_id": plan.id,
        "state": plan.status,
        "data_mode": plan.data_mode,
        "policy_version": plan.policy_version,
        "poll_after_seconds": int(getattr(settings, "POLL_AFTER_SECONDS", 2)),
        "status_url": f"/api/v1/plans/{plan.id}",
        "created_at": plan.created_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "updated_at": plan.updated_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
    }


def _same_plan_parameters(plan: Plan, validated: dict[str, Any]) -> bool:
    origin = validated["origin"]
    dest = validated["destination"]
    dep_utc = validated["departure_at"]["utc"]
    load_lb = Decimal(str(validated["load_weight_lb"])).quantize(Decimal("0.01"))
    return bool(
        abs(plan.origin_lat - float(origin["latitude"])) < 1e-5
        and abs(plan.origin_lon - float(origin["longitude"])) < 1e-5
        and abs(plan.destination_lat - float(dest["latitude"])) < 1e-5
        and abs(plan.destination_lon - float(dest["longitude"])) < 1e-5
        and abs((plan.departure_at.astimezone(UTC) - dep_utc).total_seconds()) < 1.0
        and plan.load_weight_lb.quantize(Decimal("0.01")) == load_lb
    )


class _SessionAwareAPIView(APIView):
    """Base APIView that binds verified owner_scope onto the request before throttling."""

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        request.spotter_owner_scope = _resolve_owner_scope(request)  # type: ignore[attr-defined]
        super().initial(request, *args, **kwargs)


class HealthLiveView(APIView):
    """Liveness probe: process alive only; exposes no secrets or internals."""

    throttle_classes: list[Any] = []

    def get(self, _request: Request) -> Response:
        return Response(
            {
                "status": "ok",
                "service": "spotter-api",
            },
            status=status.HTTP_200_OK,
        )


class HealthReadyView(APIView):
    """Readiness probe: checks DB, cache, and provider config with minimal diagnostics."""

    throttle_classes: list[Any] = []

    def get(self, _request: Request) -> Response:
        checks: dict[str, str] = {}
        healthy = True

        # Database connectivity check
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            checks["database"] = "ok"
        except Exception:
            checks["database"] = "unavailable"
            healthy = False

        # Cache connectivity check
        try:
            ping_key = "spotter:health:ready_ping"
            cache.set(ping_key, "1", timeout=15)
            checks["cache"] = "ok" if cache.get(ping_key) == "1" else "unavailable"
            if checks["cache"] != "ok":
                healthy = False
        except Exception:
            checks["cache"] = "unavailable"
            healthy = False

        # Provider configuration readiness
        data_mode = str(getattr(settings, "DATA_MODE", "fixture")).lower()
        if data_mode == "live" and not getattr(settings, "HERE_API_KEY", ""):
            checks["providers"] = "misconfigured"
            healthy = False
        else:
            checks["providers"] = "ok"

        http_status = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(
            {
                "status": "ready" if healthy else "degraded",
                "data_mode": data_mode,
                "checks": checks,
            },
            status=http_status,
        )


class GeocodeSearchView(_SessionAwareAPIView):
    """GET /api/v1/geocode?q=...&limit=... place search for user-driven disambiguation."""

    throttle_scope = "geocode"

    def get(self, request: Request) -> Response:
        from services.planning.composition import build_geocoding_provider

        serializer = GeocodeQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        query: str = serializer.validated_data["q"]
        limit: int = serializer.validated_data["limit"]

        provider = build_geocoding_provider()
        locations = provider.search(query=query, limit=limit)

        results = [
            {
                "label": loc.label,
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "provider_id": loc.provider_id,
                "country_code": loc.country_code,
                "region": loc.region,
                "locality": loc.locality,
                "confidence": loc.confidence,
            }
            for loc in locations
        ]
        return Response(
            {
                "query": query,
                "data_mode": provider.data_mode,
                "provider": provider.provider_name,
                "results": results,
            },
            status=status.HTTP_200_OK,
        )


class PlanCreateView(_SessionAwareAPIView):
    """POST /api/v1/plans — create and execute (or enqueue) a weather-aware truck route plan."""

    throttle_scope = "plan_submit"

    def post(self, request: Request) -> Response:
        from services.planning.orchestrator import PlanningOrchestrator
        from services.planning.tasks import execute_plan_job

        serializer = CreatePlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        owner_scope: str | None = getattr(request, "spotter_owner_scope", None)
        new_signed_token: str | None = None
        if not owner_scope:
            new_signed_token, owner_scope = create_guest_session_token(settings.SECRET_KEY)
            request.spotter_owner_scope = owner_scope  # type: ignore[attr-defined]

        raw_idem_key = request.headers.get("Idempotency-Key")
        idempotency_key: str | None = None
        if raw_idem_key is not None:
            idempotency_key = raw_idem_key.strip()
            if not idempotency_key:
                idempotency_key = None
            elif len(idempotency_key) > 128:
                raise ApiDomainError(
                    code="MALFORMED_REQUEST",
                    message="Idempotency-Key header must be at most 128 characters.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    retryable=False,
                )

        now = timezone.now()

        # Idempotency deduplication scoped strictly to owner_scope.
        if idempotency_key is not None:
            existing = (
                Plan.objects.filter(
                    owner_scope=owner_scope,
                    idempotency_key=idempotency_key,
                    expires_at__gt=now,
                )
                .prefetch_related("routes__checkpoints")
                .first()
            )
            if existing is not None:
                if not _same_plan_parameters(existing, validated):
                    raise ApiDomainError(
                        code="IDEMPOTENCY_CONFLICT",
                        message="Idempotency-Key was already used for a different trip request.",
                        status_code=status.HTTP_409_CONFLICT,
                        retryable=False,
                    )
                response = self._response_for_existing_plan(
                    existing,
                    display_checkpoint_miles=validated["display_checkpoint_miles"],
                )
                if new_signed_token is not None:
                    _attach_guest_session(response, new_signed_token)
                return response

        # Enforce concurrent in-flight plan cap per owner_scope.
        max_concurrent = int(getattr(settings, "MAX_CONCURRENT_PLANS_PER_SCOPE", 2))
        active_count = Plan.objects.filter(
            owner_scope=owner_scope,
            status__in=Plan.ACTIVE_STATUSES,
            expires_at__gt=now,
        ).count()
        if active_count >= max_concurrent:
            raise ApiDomainError(
                code="CONCURRENT_PLAN_LIMIT_EXCEEDED",
                message=(
                    f"You already have {active_count} plans in progress. "
                    "Please wait for a running plan to finish before starting another."
                ),
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                retryable=True,
                retry_after=int(getattr(settings, "POLL_AFTER_SECONDS", 2)),
            )

        origin = validated["origin"]
        destination = validated["destination"]
        dep_info = validated["departure_at"]
        ttl_seconds = int(getattr(settings, "PLAN_RESULT_TTL_SECONDS", 3600))

        with transaction.atomic():
            plan = Plan.objects.create(
                owner_scope=owner_scope,
                status=Plan.Status.QUEUED,
                data_mode=str(getattr(settings, "DATA_MODE", "fixture")).lower(),
                policy_version=POLICY_VERSION,
                origin_label=origin["label"],
                origin_lat=origin["latitude"],
                origin_lon=origin["longitude"],
                destination_label=destination["label"],
                destination_lat=destination["latitude"],
                destination_lon=destination["longitude"],
                departure_at=dep_info["utc"],
                departure_timezone=dep_info["timezone"],
                load_weight_lb=Decimal(str(validated["load_weight_lb"])).quantize(
                    Decimal("0.01")
                ),
                display_checkpoint_miles=int(validated["display_checkpoint_miles"]),
                idempotency_key=idempotency_key,
                expires_at=now + timedelta(seconds=ttl_seconds),
            )
            PlanJob.objects.create(
                plan=plan,
                status=Plan.Status.QUEUED,
                attempts=0,
                idempotency_key=idempotency_key,
            )

        if bool(getattr(settings, "ENABLE_ASYNC_PLANNING", False)):
            execute_plan_job.delay(plan.id, request_id=getattr(request, "request_id", None))
            response = Response(
                {
                    "plan_id": plan.id,
                    "state": Plan.Status.QUEUED,
                    "poll_after_seconds": int(getattr(settings, "POLL_AFTER_SECONDS", 2)),
                    "status_url": f"/api/v1/plans/{plan.id}",
                },
                status=status.HTTP_202_ACCEPTED,
            )
            if new_signed_token is not None:
                _attach_guest_session(response, new_signed_token)
            return response

        orchestrator = PlanningOrchestrator()
        completed_plan = orchestrator.execute_plan(plan)
        payload = orchestrator.format_plan_response(
            completed_plan,
            display_checkpoint_miles=completed_plan.display_checkpoint_miles,
        )
        response = Response(payload, status=status.HTTP_200_OK)
        if new_signed_token is not None:
            _attach_guest_session(response, new_signed_token)
        return response

    @staticmethod
    def _response_for_existing_plan(plan: Plan, *, display_checkpoint_miles: int) -> Response:
        from services.planning.orchestrator import PlanningOrchestrator

        if plan.status in Plan.ACTIVE_STATUSES:
            return Response(_format_pending_payload(plan), status=status.HTTP_202_ACCEPTED)
        if plan.status == Plan.Status.COMPLETED:
            payload = PlanningOrchestrator.format_plan_response(
                plan,
                display_checkpoint_miles=display_checkpoint_miles,
            )
            return Response(payload, status=status.HTTP_200_OK)
        if plan.status == Plan.Status.FAILED:
            return Response(
                {
                    "plan_id": plan.id,
                    "state": plan.status,
                    "data_mode": plan.data_mode,
                    "policy_version": plan.policy_version,
                    "error_code": plan.error_code,
                    "error_message": plan.error_message,
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {
                "plan_id": plan.id,
                "state": plan.status,
                "data_mode": plan.data_mode,
                "policy_version": plan.policy_version,
            },
            status=status.HTTP_200_OK,
        )


class PlanDetailView(_SessionAwareAPIView):
    """GET / DELETE /api/v1/plans/{plan_id} — owner-scoped plan retrieval and cleanup."""

    def get(self, request: Request, plan_id: str) -> Response:
        from services.planning.orchestrator import PlanningOrchestrator

        plan = _get_scoped_plan_or_404(request, plan_id)

        query_serializer = PlanDetailQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        requested_spacing = query_serializer.validated_data.get(
            "display_checkpoint_miles", plan.display_checkpoint_miles
        )

        if plan.status in Plan.ACTIVE_STATUSES:
            return Response(_format_pending_payload(plan), status=status.HTTP_200_OK)

        if plan.status == Plan.Status.COMPLETED:
            payload = PlanningOrchestrator.format_plan_response(
                plan,
                display_checkpoint_miles=requested_spacing,
            )
            return Response(payload, status=status.HTTP_200_OK)

        if plan.status == Plan.Status.FAILED:
            return Response(
                {
                    "plan_id": plan.id,
                    "state": plan.status,
                    "data_mode": plan.data_mode,
                    "policy_version": plan.policy_version,
                    "error_code": plan.error_code,
                    "error_message": plan.error_message,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "plan_id": plan.id,
                "state": plan.status,
                "data_mode": plan.data_mode,
                "policy_version": plan.policy_version,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request: Request, plan_id: str) -> Response:
        plan = _get_scoped_plan_or_404(request, plan_id)

        max_slider_hours = int(getattr(settings, "FORECAST_SLIDER_HOURS", 48))
        slice_keys = [
            build_forecast_slice_cache_key(
                plan_id=plan.id,
                hour_offset=offset,
                policy_version=plan.policy_version,
                data_mode=plan.data_mode,
            )
            for offset in range(max_slider_hours + 1)
        ]
        try:
            cache.delete_many(slice_keys)
        except Exception:
            logger.warning("Failed to purge forecast cache keys during plan delete")

        plan.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PlanCancelView(_SessionAwareAPIView):
    """POST /api/v1/plans/{plan_id}/cancel — idempotent cancellation for queued plans."""

    def post(self, request: Request, plan_id: str) -> Response:
        plan = _get_scoped_plan_or_404(request, plan_id)

        if plan.status == Plan.Status.CANCELED:
            return Response(
                {
                    "plan_id": plan.id,
                    "state": Plan.Status.CANCELED,
                    "canceled": True,
                    "message": "Plan is already canceled.",
                },
                status=status.HTTP_200_OK,
            )

        if plan.status == Plan.Status.QUEUED:
            now = timezone.now()
            with transaction.atomic():
                updated = Plan.objects.filter(
                    id=plan.id,
                    status=Plan.Status.QUEUED,
                ).update(status=Plan.Status.CANCELED, updated_at=now)
                if updated:
                    PlanJob.objects.filter(plan_id=plan.id).update(
                        status=Plan.Status.CANCELED,
                        completed_at=now,
                    )
                    return Response(
                        {
                            "plan_id": plan.id,
                            "state": Plan.Status.CANCELED,
                            "canceled": True,
                            "message": "Queued plan canceled.",
                        },
                        status=status.HTTP_200_OK,
                    )
            plan.refresh_from_db()

        # Honestly report that active in-flight provider calls or terminal plans are not aborted.
        return Response(
            {
                "plan_id": plan.id,
                "state": plan.status,
                "canceled": False,
                "message": (
                    f"Plan is currently '{plan.status}' and cannot be canceled while in progress "
                    "or after completion."
                ),
            },
            status=status.HTTP_200_OK,
        )


class PlanForecastSliceView(_SessionAwareAPIView):
    """GET /api/v1/plans/{plan_id}/forecast?hour_offset={0..48} — corridor heatmap slice."""

    throttle_scope = "forecast"

    def get(self, request: Request, plan_id: str) -> Response:
        from services.planning.orchestrator import PlanningOrchestrator

        plan = _get_scoped_plan_or_404(request, plan_id)

        if plan.status != Plan.Status.COMPLETED:
            raise ApiDomainError(
                code="PLAN_NOT_READY",
                message=f"Forecast slices are unavailable while plan state is '{plan.status}'.",
                status_code=status.HTTP_409_CONFLICT,
                retryable=plan.status in Plan.ACTIVE_STATUSES,
            )

        query_serializer = ForecastSliceQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        hour_offset: int = query_serializer.validated_data["hour_offset"]

        orchestrator = PlanningOrchestrator()
        slice_payload = orchestrator.get_forecast_slice(plan, hour_offset=hour_offset)
        return Response(slice_payload, status=status.HTTP_200_OK)
