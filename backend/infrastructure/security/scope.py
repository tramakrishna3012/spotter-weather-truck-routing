"""HMAC-SHA256 signed opaque guest session tokens for plan ownership isolation.

Prevents cross-session plan enumeration without requiring full user sign-in.
Tokens are formatted as `<scope_id>.<hex_hmac_sha256>` and verified in constant time.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_TOKEN_SEPARATOR = "."
_MIN_SCOPE_ID_LENGTH = 16
_SIGNATURE_HEX_LENGTH = 64


def _compute_signature(scope_id: str, secret_key: str) -> str:
    mac = hmac.new(
        key=secret_key.encode("utf-8"),
        msg=scope_id.encode("utf-8"),
        digestmod=hashlib.sha256,
    )
    return mac.hexdigest()


def create_guest_session_token(secret_key: str) -> tuple[str, str]:
    """Generate a signed guest session token and its opaque owner scope ID.

    Returns:
        (signed_token, scope_id) where `signed_token` is sent to the client
        (HTTP-only cookie or header) and `scope_id` is stored on owned plans.
    """
    if not isinstance(secret_key, str) or not secret_key.strip():
        raise ValueError("secret_key must be a non-empty string.")

    scope_id = secrets.token_urlsafe(24)
    signature = _compute_signature(scope_id, secret_key)
    signed_token = f"{scope_id}{_TOKEN_SEPARATOR}{signature}"
    return signed_token, scope_id


def verify_guest_session_token(token: str, secret_key: str) -> str | None:
    """Verify a signed guest session token in constant time and return its scope ID.

    Returns None for missing, malformed, or tampered tokens.
    """
    if not isinstance(token, str) or not isinstance(secret_key, str):
        return None
    if not token or not secret_key.strip():
        return None

    parts = token.strip().split(_TOKEN_SEPARATOR)
    if len(parts) != 2:
        return None

    scope_id, provided_sig = parts
    if len(scope_id) < _MIN_SCOPE_ID_LENGTH or len(provided_sig) != _SIGNATURE_HEX_LENGTH:
        return None

    expected_sig = _compute_signature(scope_id, secret_key)
    if not hmac.compare_digest(provided_sig, expected_sig):
        return None

    return scope_id
