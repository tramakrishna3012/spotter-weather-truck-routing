"""Structured API exception handling conforming to docs/07_API_CONTRACT.md."""

from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions as drf_exceptions
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_default_exception_handler

from config.logging import get_request_id

logger = logging.getLogger("spotter.api.exceptions")


class ApiDomainError(Exception):
    """Structured application error that maps directly to the API error envelope."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        retryable: bool = False,
        details: list[dict[str, Any]] | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.details = details or []
        self.retry_after = retry_after


def build_error_envelope(
    *,
    code: str,
    message: str,
    retryable: bool = False,
    details: list[dict[str, Any]] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Construct the canonical Spotter error response payload."""
    return {
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable,
            "request_id": request_id or get_request_id(),
            "details": details if details is not None else [],
        }
    }


def _flatten_validation_details(data: Any, prefix: str = "") -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    if isinstance(data, dict):
        for key, value in data.items():
            field_name = f"{prefix}.{key}" if prefix else str(key)
            details.extend(_flatten_validation_details(value, prefix=field_name))
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                details.extend(_flatten_validation_details(item, prefix=prefix))
            else:
                details.append(
                    {
                        "field": prefix or "non_field_errors",
                        "message": str(item),
                    }
                )
    else:
        details.append(
            {
                "field": prefix or "non_field_errors",
                "message": str(data),
            }
        )
    return details


def _provider_error_to_response(exc: Exception, request_id: str) -> Response:
    provider = getattr(exc, "provider", "upstream")
    code = getattr(exc, "code", None) or "PROVIDER_UNAVAILABLE"
    retryable = bool(getattr(exc, "retryable", True))
    upstream_status = getattr(exc, "status_code", None)

    if code in {"PROVIDER_TIMEOUT", "TIMEOUT"} or upstream_status == 504:
        http_status = status.HTTP_504_GATEWAY_TIMEOUT
        public_code = "PROVIDER_TIMEOUT"
        message = f"The upstream {provider} service timed out. Please retry shortly."
    elif upstream_status == 429 or code == "PROVIDER_RATE_LIMITED":
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
        public_code = "PROVIDER_RATE_LIMITED"
        message = f"The upstream {provider} service is temporarily rate-limited. Please retry shortly."
    elif upstream_status in {502, 503}:
        http_status = upstream_status
        public_code = str(code).upper()
        message = f"The upstream {provider} service is temporarily unavailable."
    elif upstream_status == 400 or code in {
        "PROVIDER_BAD_RESPONSE",
        "PROVIDER_INVALID_JSON",
        "PROVIDER_INVALID_SCHEMA",
        "PROVIDER_REDIRECT_BLOCKED",
        "PROVIDER_RESPONSE_TOO_LARGE",
        "PROVIDER_REQUEST_REJECTED",
    }:
        http_status = status.HTTP_502_BAD_GATEWAY
        public_code = str(code).upper()
        message = f"The upstream {provider} service returned an invalid response."
    else:
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
        public_code = str(code).upper()
        message = f"Unable to reach the upstream {provider} service right now."

    logger.warning(
        "Provider error handled",
        extra={
            "provider": provider,
            "error_code": public_code,
            "http_status": http_status,
            "retryable": retryable,
        },
    )
    return Response(
        build_error_envelope(
            code=public_code,
            message=message,
            retryable=retryable,
            details=[{"provider": str(provider)}],
            request_id=request_id,
        ),
        status=http_status,
    )


def structured_exception_handler(exc: Exception, context: dict[str, Any]) -> Response:
    """Translate all exceptions into the documented structured error envelope."""
    request = context.get("request")
    request_id = getattr(request, "request_id", None) or get_request_id()

    if isinstance(exc, ApiDomainError):
        response = Response(
            build_error_envelope(
                code=exc.code,
                message=exc.message,
                retryable=exc.retryable,
                details=exc.details,
                request_id=request_id,
            ),
            status=exc.status_code,
        )
        if exc.retry_after is not None:
            response["Retry-After"] = str(exc.retry_after)
        return response

    # Import lazily to avoid circular imports during early Django setup.
    try:
        from providers.ports import ProviderError
    except ImportError:
        ProviderError = None  # type: ignore[assignment,misc]

    if ProviderError is not None and isinstance(exc, ProviderError):
        return _provider_error_to_response(exc, request_id)

    if isinstance(exc, drf_exceptions.ValidationError):
        details = _flatten_validation_details(exc.detail)
        return Response(
            build_error_envelope(
                code="VALIDATION_ERROR",
                message="One or more request fields failed validation.",
                retryable=False,
                details=details,
                request_id=request_id,
            ),
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    if isinstance(exc, drf_exceptions.ParseError):
        return Response(
            build_error_envelope(
                code="MALFORMED_REQUEST",
                message="Request body could not be parsed as valid JSON.",
                retryable=False,
                details=[],
                request_id=request_id,
            ),
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, drf_exceptions.Throttled):
        wait_seconds = int(exc.wait) if exc.wait is not None else None
        details = [{"retry_after_seconds": wait_seconds}] if wait_seconds is not None else []
        response = Response(
            build_error_envelope(
                code="RATE_LIMITED",
                message="Too many requests. Please wait before trying again.",
                retryable=True,
                details=details,
                request_id=request_id,
            ),
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
        if wait_seconds is not None:
            response["Retry-After"] = str(wait_seconds)
        return response

    if isinstance(exc, (drf_exceptions.NotFound, Http404)):
        return Response(
            build_error_envelope(
                code="NOT_FOUND",
                message="The requested resource was not found.",
                retryable=False,
                details=[],
                request_id=request_id,
            ),
            status=status.HTTP_404_NOT_FOUND,
        )

    if isinstance(exc, (drf_exceptions.PermissionDenied, DjangoPermissionDenied)):
        return Response(
            build_error_envelope(
                code="FORBIDDEN",
                message="You do not have permission to access this resource.",
                retryable=False,
                details=[],
                request_id=request_id,
            ),
            status=status.HTTP_403_FORBIDDEN,
        )

    if isinstance(exc, drf_exceptions.NotAuthenticated):
        return Response(
            build_error_envelope(
                code="UNAUTHORIZED",
                message="Authentication or a valid session token is required.",
                retryable=False,
                details=[],
                request_id=request_id,
            ),
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if isinstance(exc, drf_exceptions.MethodNotAllowed):
        return Response(
            build_error_envelope(
                code="METHOD_NOT_ALLOWED",
                message=f"HTTP method {getattr(request, 'method', '')} is not allowed on this endpoint.",
                retryable=False,
                details=[],
                request_id=request_id,
            ),
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    # Let DRF handle any other APIException subclass, then normalize into envelope.
    drf_response = drf_default_exception_handler(exc, context)
    if drf_response is not None:
        return Response(
            build_error_envelope(
                code="API_ERROR",
                message="The request could not be processed.",
                retryable=drf_response.status_code >= 500,
                details=_flatten_validation_details(drf_response.data),
                request_id=request_id,
            ),
            status=drf_response.status_code,
        )

    # Unexpected internal error: log safely without leaking stack traces to clients.
    logger.exception(
        "Unhandled server exception",
        extra={
            "path": getattr(request, "path", ""),
            "method": getattr(request, "method", ""),
        },
    )
    return Response(
        build_error_envelope(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected internal error occurred. Please retry or contact support with the request ID.",
            retryable=True,
            details=[],
            request_id=request_id,
        ),
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
