"""End-to-end Django/DRF integration tests for Spotter v1 API endpoints and session isolation."""

from __future__ import annotations

import copy
from datetime import UTC, timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.conf import settings as django_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.trips.models import Plan, PlanJob
from infrastructure.security.scope import create_guest_session_token

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _fixture_mode_settings(settings: Any) -> None:
    """Force deterministic synchronous fixture mode for API integration tests."""
    settings.DATA_MODE = "fixture"
    settings.ENABLE_ASYNC_PLANNING = False


class TestHealthAndSchemaEndpoints:
    """Health probes and OpenAPI schema generation."""

    def test_health_live_returns_ok(self, api_client: APIClient) -> None:
        resp = api_client.get("/api/v1/health/live")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "service": "spotter-api"}
        assert resp["X-Request-ID"]

    def test_health_ready_returns_ready(self, api_client: APIClient) -> None:
        resp = api_client.get("/api/v1/health/ready")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ready"
        assert body["data_mode"] == "fixture"
        assert body["checks"] == {
            "database": "ok",
            "cache": "ok",
            "providers": "ok",
        }

    def test_openapi_schema_endpoint_returns_valid_schema(self, api_client: APIClient) -> None:
        resp = api_client.get("/api/schema/", HTTP_ACCEPT="application/vnd.oai.openapi+json")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema["openapi"].startswith("3.")
        assert "/api/v1/plans" in schema["paths"]
        assert "/api/v1/geocode" in schema["paths"]
        assert "/api/v1/health/live" in schema["paths"]


class TestGeocodeEndpoint:
    """GET /api/v1/geocode disambiguation contract."""

    def test_geocode_springfield_returns_three_disambiguation_candidates(
        self, api_client: APIClient
    ) -> None:
        resp = api_client.get("/api/v1/geocode", {"q": "Springfield"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["query"] == "Springfield"
        assert body["data_mode"] == "fixture"
        assert len(body["results"]) == 3
        labels = {item["label"] for item in body["results"]}
        assert labels == {"Springfield, IL", "Springfield, MA", "Springfield, MO"}


class TestPlanLifecycleEndpoints:
    """Full lifecycle tests for POST/GET/DELETE plans, forecast slices, idempotency, and isolation."""

    def test_create_plan_denver_to_slc_and_nyc_to_phl(
        self,
        api_client: APIClient,
        denver_to_slc_payload: dict[str, Any],
        nyc_to_phl_payload: dict[str, Any],
    ) -> None:
        for trip_payload in (denver_to_slc_payload, nyc_to_phl_payload):
            client = APIClient()
            resp = client.post("/api/v1/plans", trip_payload, format="json")
            assert resp.status_code == 200
            body = resp.json()

            assert body["state"] == "completed"
            assert body["data_mode"] == "fixture"
            assert body["policy_version"] == "risk-policy-v1"
            assert body["plan_id"]
            assert len(body["routes"]) >= 2

            # Signed session emitted in BOTH header and HttpOnly cookie
            session_header = resp[django_settings.SESSION_HEADER_NAME]
            assert session_header
            cookie = resp.cookies[django_settings.SESSION_COOKIE_NAME]
            assert cookie.value == session_header
            assert bool(cookie["httponly"]) is True

            # Validate route structure: geometry, checkpoints, risk_segments, risk summary
            for route in body["routes"]:
                assert route["geometry"]["type"] == "LineString"
                assert len(route["geometry"]["coordinates"]) >= 2
                assert route["distance_m"] > 0
                assert route["duration_seconds"] > 0
                assert len(route["checkpoints"]) >= 2
                assert len(route["risk_segments"]) >= 2
                assert "severe_miles" in route["risk"]
                assert "high_miles" in route["risk"]
                assert "eligible" in route["risk"]

    def test_idempotency_replay_and_conflict(
        self,
        api_client: APIClient,
        nyc_to_phl_payload: dict[str, Any],
    ) -> None:
        idem_key = "idem-nyc-phl-001"
        first = api_client.post(
            "/api/v1/plans",
            nyc_to_phl_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=idem_key,
        )
        assert first.status_code == 200
        session_token = first[django_settings.SESSION_HEADER_NAME]
        first_plan_id = first.json()["plan_id"]

        # Exact replay with same session and same payload -> identical plan_id
        replay = api_client.post(
            "/api/v1/plans",
            nyc_to_phl_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=idem_key,
            HTTP_X_SPOTTER_SESSION=session_token,
        )
        assert replay.status_code == 200
        assert replay.json()["plan_id"] == first_plan_id

        # Same Idempotency-Key with different payload -> 409 IDEMPOTENCY_CONFLICT
        mutated = copy.deepcopy(nyc_to_phl_payload)
        mutated["load_weight_lb"] = 45000
        conflict = api_client.post(
            "/api/v1/plans",
            mutated,
            format="json",
            HTTP_IDEMPOTENCY_KEY=idem_key,
            HTTP_X_SPOTTER_SESSION=session_token,
        )
        assert conflict.status_code == 409
        err = conflict.json()["error"]
        assert err["code"] == "IDEMPOTENCY_CONFLICT"
        assert err["retryable"] is False

    @pytest.mark.parametrize(
        "mutator",
        [
            lambda p: p.update({"departure_at": "2026-11-20T12:00:00"}),  # naive datetime
            lambda p: p.update({"load_weight_lb": -100}),  # negative load
            lambda p: p.update({"display_checkpoint_miles": 15}),  # unsupported spacing
            lambda p: p.update({"destination": copy.deepcopy(p["origin"])}),  # origin == dest
            lambda p: p["origin"].update({"latitude": 95.0}),  # out-of-range latitude
            lambda p: p["destination"].update({"longitude": -181.0}),  # out-of-range longitude
        ],
    )
    def test_validation_errors_return_422_structured_envelope_without_tracebacks(
        self,
        api_client: APIClient,
        nyc_to_phl_payload: dict[str, Any],
        mutator: Any,
    ) -> None:
        payload = copy.deepcopy(nyc_to_phl_payload)
        mutator(payload)
        resp = api_client.post("/api/v1/plans", payload, format="json")
        assert resp.status_code == 422
        raw_text = resp.content.decode("utf-8")
        assert "Traceback" not in raw_text
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert body["error"]["retryable"] is False
        assert body["error"]["request_id"]
        assert len(body["error"]["details"]) >= 1

    def test_get_plan_display_spacing_invariance_and_cross_session_isolation(
        self,
        api_client: APIClient,
        denver_to_slc_payload: dict[str, Any],
    ) -> None:
        create_resp = api_client.post("/api/v1/plans", denver_to_slc_payload, format="json")
        assert create_resp.status_code == 200
        created = create_resp.json()
        plan_id = created["plan_id"]
        owner_token = create_resp[django_settings.SESSION_HEADER_NAME]

        # Query with 10, 25, and 50 mile display spacing
        responses: dict[int, dict[str, Any]] = {}
        for spacing in (10, 25, 50):
            r = APIClient().get(
                f"/api/v1/plans/{plan_id}",
                {"display_checkpoint_miles": spacing},
                HTTP_X_SPOTTER_SESSION=owner_token,
            )
            assert r.status_code == 200
            responses[spacing] = r.json()

        # Recommendation and risk metrics MUST remain completely identical across display spacings
        for spacing in (10, 25, 50):
            assert responses[spacing]["display_checkpoint_miles"] == spacing
            assert responses[spacing]["recommended_route_id"] == created["recommended_route_id"]
            assert responses[spacing]["recommendation_status"] == created["recommendation_status"]
            for route_base, route_var in zip(
                created["routes"], responses[spacing]["routes"], strict=True
            ):
                assert route_var["id"] == route_base["id"]
                assert route_var["risk"] == route_base["risk"]

        # Display checkpoint count strictly changes as spacing coarsens on long Denver->SLC corridor
        cp_counts = {
            spacing: len(responses[spacing]["routes"][0]["checkpoints"]) for spacing in (10, 25, 50)
        }
        assert cp_counts[10] > cp_counts[25] > cp_counts[50]

        # Cross-session isolation: missing session -> 404 PLAN_NOT_FOUND
        no_sess_resp = APIClient().get(f"/api/v1/plans/{plan_id}")
        assert no_sess_resp.status_code == 404
        assert no_sess_resp.json()["error"]["code"] == "PLAN_NOT_FOUND"

        # Different valid session -> 404 PLAN_NOT_FOUND
        other_token, _ = create_guest_session_token(django_settings.SECRET_KEY)
        other_sess_resp = APIClient().get(
            f"/api/v1/plans/{plan_id}",
            HTTP_X_SPOTTER_SESSION=other_token,
        )
        assert other_sess_resp.status_code == 404
        assert other_sess_resp.json()["error"]["code"] == "PLAN_NOT_FOUND"

    def test_forecast_slices_valid_and_out_of_range(
        self,
        api_client: APIClient,
        denver_to_slc_payload: dict[str, Any],
    ) -> None:
        create_resp = api_client.post("/api/v1/plans", denver_to_slc_payload, format="json")
        assert create_resp.status_code == 200
        plan_id = create_resp.json()["plan_id"]
        owner_token = create_resp[django_settings.SESSION_HEADER_NAME]

        for offset in (0, 24, 48):
            r = APIClient().get(
                f"/api/v1/plans/{plan_id}/forecast",
                {"hour_offset": offset},
                HTTP_X_SPOTTER_SESSION=owner_token,
            )
            assert r.status_code == 200
            body = r.json()
            assert body["plan_id"] == plan_id
            assert body["hour_offset"] == offset
            assert body["reference_kind"] == "departure_instant"
            assert body["valid_at"]
            assert body["coverage_fraction"] > 0.0
            assert isinstance(body["coverage_complete"], bool)
            assert len(body["points"]) > 0

        # Out-of-bounds slider hour_offset=99 -> 422
        bad = APIClient().get(
            f"/api/v1/plans/{plan_id}/forecast",
            {"hour_offset": 99},
            HTTP_X_SPOTTER_SESSION=owner_token,
        )
        assert bad.status_code == 422
        assert bad.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_cancel_and_delete_plan_lifecycle(
        self,
        api_client: APIClient,
        nyc_to_phl_payload: dict[str, Any],
    ) -> None:
        # 1. Completed plan: cancel honestly reports canceled=False, then DELETE removes it
        create_resp = api_client.post("/api/v1/plans", nyc_to_phl_payload, format="json")
        assert create_resp.status_code == 200
        plan_id = create_resp.json()["plan_id"]
        owner_token = create_resp[django_settings.SESSION_HEADER_NAME]

        cancel_completed = APIClient().post(
            f"/api/v1/plans/{plan_id}/cancel",
            HTTP_X_SPOTTER_SESSION=owner_token,
        )
        assert cancel_completed.status_code == 200
        assert cancel_completed.json()["canceled"] is False
        assert cancel_completed.json()["state"] == "completed"

        delete_resp = APIClient().delete(
            f"/api/v1/plans/{plan_id}",
            HTTP_X_SPOTTER_SESSION=owner_token,
        )
        assert delete_resp.status_code == 204

        after_delete = APIClient().get(
            f"/api/v1/plans/{plan_id}",
            HTTP_X_SPOTTER_SESSION=owner_token,
        )
        assert after_delete.status_code == 404
        assert after_delete.json()["error"]["code"] == "PLAN_NOT_FOUND"

        # 2. Queued plan: cancel transitions to CANCELED and is idempotent on repeat
        signed_token, scope_id = create_guest_session_token(django_settings.SECRET_KEY)
        now = timezone.now().astimezone(UTC)
        queued_plan = Plan.objects.create(
            owner_scope=scope_id,
            status=Plan.Status.QUEUED,
            data_mode=Plan.DataMode.FIXTURE,
            origin_label="New York, NY",
            origin_lat=40.7128,
            origin_lon=-74.0060,
            destination_label="Philadelphia, PA",
            destination_lat=39.9526,
            destination_lon=-75.1652,
            departure_at=now + timedelta(hours=2),
            departure_timezone="UTC",
            load_weight_lb=Decimal("25000.00"),
            display_checkpoint_miles=25,
            expires_at=now + timedelta(hours=1),
        )
        PlanJob.objects.create(plan=queued_plan, status=Plan.Status.QUEUED)

        cancel1 = APIClient().post(
            f"/api/v1/plans/{queued_plan.id}/cancel",
            HTTP_X_SPOTTER_SESSION=signed_token,
        )
        assert cancel1.status_code == 200
        assert cancel1.json()["canceled"] is True
        assert cancel1.json()["state"] == "canceled"

        # Idempotent second cancel
        cancel2 = APIClient().post(
            f"/api/v1/plans/{queued_plan.id}/cancel",
            HTTP_X_SPOTTER_SESSION=signed_token,
        )
        assert cancel2.status_code == 200
        assert cancel2.json()["canceled"] is True
        assert cancel2.json()["state"] == "canceled"
