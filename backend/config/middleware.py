"""HTTP middleware for opaque request correlation IDs and safe request telemetry."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from config.logging import reset_request_id, set_request_id

logger = logging.getLogger("spotter.http")


class RequestIDMiddleware:
    """Attach an opaque UUID4 request_id to every request/response and log timing safely."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = str(uuid.uuid4())
        request.request_id = request_id  # type: ignore[attr-defined]
        token = set_request_id(request_id)
        started = time.perf_counter()

        try:
            response = self.get_response(request)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
            # Log path only (never query string, which may contain search terms/coords, or headers/tokens).
            status_code = getattr(locals().get("response"), "status_code", 500)
            logger.info(
                "HTTP request completed",
                extra={
                    "method": request.method,
                    "path": request.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )
            reset_request_id(token)

        response["X-Request-ID"] = request_id
        return response
