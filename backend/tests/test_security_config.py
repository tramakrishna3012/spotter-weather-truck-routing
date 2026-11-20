"""Security, fail-closed runtime configuration, session signing, and log scrubbing tests."""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.logging import StructuredJsonFormatter, scrub_text, scrub_value
from config.settings import validate_runtime_settings
from infrastructure.security.scope import (
    create_guest_session_token,
    verify_guest_session_token,
)

pytestmark = pytest.mark.security


def _valid_production_settings() -> dict[str, Any]:
    return {
        "APP_ENV": "production",
        "DATA_MODE": "live",
        "DEBUG": False,
        "SECRET_KEY": "p9X!kL2#vQ8$mN4^zR7*wT1&bF6@cH3%jD5+sG0=",
        "ALLOWED_HOSTS": ["api.spotter.example.com"],
        "CORS_ALLOWED_ORIGINS": ["https://app.spotter.example.com"],
        "FRONTEND_ORIGIN": "https://app.spotter.example.com",
        "HERE_API_KEY": "here-live-prod-api-key-value",
        "HERE_ROUTING_BASE_URL": "https://router.hereapi.com/v8",
        "HERE_GEOCODING_BASE_URL": "https://geocode.search.hereapi.com/v1",
        "OPEN_METEO_BASE_URL": "https://api.open-meteo.com/v1",
        "DATABASE_URL": "postgresql://spotter:strongpass@db.internal:5432/spotter",
        "REDIS_URL": "redis://redis.internal:6379/0",
        "ENABLE_ASYNC_PLANNING": True,
        "SESSION_COOKIE_SECURE": True,
    }


class TestRuntimeSettingsValidation:
    """Fail-closed startup validation for production and live-mode invariants."""

    def test_valid_production_configuration_passes(self) -> None:
        validate_runtime_settings(_valid_production_settings())

    @pytest.mark.parametrize(
        ("field", "bad_value"),
        [
            ("DEBUG", True),
            ("DATA_MODE", "fixture"),
            ("SECRET_KEY", ""),
            ("SECRET_KEY", "too-short-secret"),
            ("SECRET_KEY", "dev-only-spotter-ephemeral-local-secret-key-do-not-use-in-production"),
            ("SECRET_KEY", "django-insecure-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
            ("HERE_API_KEY", ""),
            ("DATABASE_URL", ""),
            ("DATABASE_URL", "sqlite:///db.sqlite3"),
            ("ALLOWED_HOSTS", []),
            ("ALLOWED_HOSTS", ["*"]),
            ("ALLOWED_HOSTS", ["api.spotter.example.com", "*"]),
            ("SESSION_COOKIE_SECURE", False),
            ("CORS_ALLOWED_ORIGINS", ["*"]),
        ],
    )
    def test_production_rejects_insecure_setting(self, field: str, bad_value: Any) -> None:
        cfg = _valid_production_settings()
        cfg[field] = bad_value
        with pytest.raises(ImproperlyConfigured):
            validate_runtime_settings(cfg)

    def test_live_mode_requires_here_api_key_even_outside_production(self) -> None:
        with pytest.raises(ImproperlyConfigured):
            validate_runtime_settings(
                {
                    "APP_ENV": "development",
                    "DATA_MODE": "live",
                    "HERE_API_KEY": "",
                }
            )

    def test_async_planning_requires_redis_url(self) -> None:
        with pytest.raises(ImproperlyConfigured):
            validate_runtime_settings(
                {
                    "APP_ENV": "development",
                    "DATA_MODE": "fixture",
                    "ENABLE_ASYNC_PLANNING": True,
                    "REDIS_URL": "",
                }
            )


class TestGuestSessionTokenSecurity:
    """HMAC-SHA256 guest session signing, verification, and tamper resistance."""

    def test_round_trip_create_and_verify(self) -> None:
        secret = "test-signing-secret-key-with-sufficient-entropy-12345"
        token, scope_id = create_guest_session_token(secret)
        assert "." in token
        assert verify_guest_session_token(token, secret) == scope_id

    def test_rejects_tampered_scope_tampered_sig_wrong_secret_and_malformed(self) -> None:
        secret = "primary-signing-secret-key-with-entropy-0001"
        other_secret = "different-signing-secret-key-with-entropy-9999"
        token, scope_id = create_guest_session_token(secret)
        raw_scope, raw_sig = token.split(".")

        # Wrong secret
        assert verify_guest_session_token(token, other_secret) is None

        # Tampered scope ID
        tampered_scope = f"{'A' if raw_scope[0] != 'A' else 'B'}{raw_scope[1:]}.{raw_sig}"
        assert verify_guest_session_token(tampered_scope, secret) is None

        # Tampered HMAC signature
        flipped_char = "0" if raw_sig[-1] != "0" else "1"
        tampered_sig = f"{raw_scope}.{raw_sig[:-1]}{flipped_char}"
        assert verify_guest_session_token(tampered_sig, secret) is None

        # Malformed / empty inputs
        for bad in ("", "no-dot", f"{scope_id}.", ".deadbeef", "short." + raw_sig):
            assert verify_guest_session_token(bad, secret) is None


class TestStructuredLogScrubber:
    """Ensure structured JSON logging redacts secrets, session tokens, and coordinates."""

    def test_scrub_text_redacts_apikey_and_session_tokens(self) -> None:
        raw = (
            "GET https://router.hereapi.com/v8/routes?apiKey=SECRET_HERE_123&mode=truck "
            "X-Spotter-Session: scope123.deadbeef "
            "Cookie: spotter_session=scope123.deadbeef "
            "Authorization: Bearer jwt.token.value"
        )
        cleaned = scrub_text(raw)
        assert "SECRET_HERE_123" not in cleaned
        assert "scope123.deadbeef" not in cleaned
        assert "jwt.token.value" not in cleaned
        assert "[REDACTED]" in cleaned

    def test_structured_json_formatter_redacts_secrets_and_coordinates(self) -> None:
        formatter = StructuredJsonFormatter()
        record = logging.LogRecord(
            name="spotter.security.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Calling provider with apiKey=SUPER_SECRET_KEY and X-Spotter-Session=sess_abc.1234",
            args=(),
            exc_info=None,
        )
        record.HERE_API_KEY = "MY_RAW_HERE_KEY"
        record.origin_lat = 39.7392
        record.origin_lon = -104.9903
        record.destination_lat = 40.7608
        record.destination_lon = -111.8910
        record.coordinates = [[39.7392, -104.9903]]
        record.safe_field = "visible-ok"

        rendered = formatter.format(record)
        parsed = json.loads(rendered)

        assert "SUPER_SECRET_KEY" not in rendered
        assert "sess_abc.1234" not in rendered
        assert "MY_RAW_HERE_KEY" not in rendered
        assert "39.7392" not in rendered
        assert "-104.9903" not in rendered
        assert "40.7608" not in rendered
        assert "-111.891" not in rendered

        assert parsed["HERE_API_KEY"] == "[REDACTED]"
        assert parsed["origin_lat"] == "[REDACTED]"
        assert parsed["origin_lon"] == "[REDACTED]"
        assert parsed["destination_lat"] == "[REDACTED]"
        assert parsed["destination_lon"] == "[REDACTED]"
        assert parsed["coordinates"] == "[REDACTED]"
        assert parsed["safe_field"] == "visible-ok"

    def test_scrub_value_nested_dict(self) -> None:
        nested = {
            "HERE_API_KEY": "secret-val",
            "x-spotter-session": "tok.sig",
            "polyline": "BFoz5xJ67i1B1B7PzIhaxL7Y",
            "status": "ok",
        }
        scrubbed = scrub_value("payload", nested)
        assert scrubbed["HERE_API_KEY"] == "[REDACTED]"
        assert scrubbed["x-spotter-session"] == "[REDACTED]"
        assert scrubbed["polyline"] == "[REDACTED]"
        assert scrubbed["status"] == "ok"
