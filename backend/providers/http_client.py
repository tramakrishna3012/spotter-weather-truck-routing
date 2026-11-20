"""Hardened synchronous HTTP client with SSRF allowlist, byte cap, retries, and circuit breaker.

Security controls per docs/10_SECURITY.md:
- Strict configured host allowlist (never accepts arbitrary client-controlled hosts)
- follow_redirects=False (rejects unexpected 3xx redirects rather than hopping hosts)
- Streaming response size cap (max_response_bytes)
- Bounded exponential backoff with jitter on 429/5xx/timeouts
- Per-host circuit breaker
- Secret scrubbing on error logs and raised ProviderError messages
"""

from __future__ import annotations

import json
import logging
import random
import re
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from infrastructure.observability.metrics import MetricsRegistry, get_default_registry
from providers.ports import ProviderError

logger = logging.getLogger("spotter.providers.http")

_SECRET_QUERY_PARAM_RE = re.compile(
    r"([?&](?:apiKey|apikey|api_key|key|token|access_token)=)([^&\s]+)",
    re.IGNORECASE,
)


@dataclass
class _HostCircuitState:
    consecutive_failures: int = 0
    opened_until: float = 0.0


class ResilientHttpClient:
    """SSRF-guarded, retrying HTTP JSON client backed by httpx.Client."""

    def __init__(
        self,
        *,
        allowed_hosts: set[str] | frozenset[str],
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
        max_attempts: int,
        max_response_bytes: int,
        backoff_base_seconds: float = 0.5,
        backoff_max_seconds: float = 8.0,
        circuit_failure_threshold: int = 5,
        circuit_reset_seconds: float = 30.0,
        allow_insecure_http: bool = False,
        secret_values: Sequence[str] = (),
        client: httpx.Client | None = None,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        normalized_hosts = frozenset(h.strip().lower() for h in allowed_hosts if h and h.strip())
        if not normalized_hosts:
            raise ValueError("allowed_hosts must contain at least one hostname.")
        if connect_timeout_seconds <= 0.0 or read_timeout_seconds <= 0.0:
            raise ValueError("connect_timeout_seconds and read_timeout_seconds must be positive.")
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1.")
        if max_response_bytes < 1:
            raise ValueError("max_response_bytes must be >= 1.")
        if circuit_failure_threshold < 1:
            raise ValueError("circuit_failure_threshold must be >= 1.")
        if circuit_reset_seconds <= 0.0:
            raise ValueError("circuit_reset_seconds must be positive.")

        self._allowed_hosts = normalized_hosts
        self._connect_timeout = float(connect_timeout_seconds)
        self._read_timeout = float(read_timeout_seconds)
        self._max_attempts = int(max_attempts)
        self._max_response_bytes = int(max_response_bytes)
        self._backoff_base = float(backoff_base_seconds)
        self._backoff_max = float(backoff_max_seconds)
        self._circuit_threshold = int(circuit_failure_threshold)
        self._circuit_reset = float(circuit_reset_seconds)
        self._allow_insecure_http = bool(allow_insecure_http)
        self._secret_values = tuple(s for s in secret_values if s)
        self._metrics = metrics or get_default_registry()

        self._lock = threading.Lock()
        self._circuits: dict[str, _HostCircuitState] = {}

        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(
                connect=self._connect_timeout,
                read=self._read_timeout,
                write=self._read_timeout,
                pool=self._connect_timeout,
            ),
            follow_redirects=False,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> ResilientHttpClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def scrub_secrets(self, text: str) -> str:
        """Remove known secret values and credential query parameters from text."""
        scrubbed = _SECRET_QUERY_PARAM_RE.sub(r"\1[REDACTED]", text)
        for secret in self._secret_values:
            if secret:
                scrubbed = scrubbed.replace(secret, "[REDACTED]")
        return scrubbed

    def _validate_url(self, url: str, *, provider_name: str) -> str:
        parsed = urlparse(url)
        allowed_schemes = {"https", "http"} if self._allow_insecure_http else {"https"}
        if parsed.scheme.lower() not in allowed_schemes:
            raise ProviderError(
                code="PROVIDER_URL_SCHEME_BLOCKED",
                message=f"Disallowed URL scheme {parsed.scheme!r} for outbound provider request.",
                provider=provider_name,
                retryable=False,
            )
        if parsed.username or parsed.password:
            raise ProviderError(
                code="PROVIDER_URL_CREDENTIALS_BLOCKED",
                message="Embedded credentials in outbound provider URLs are disallowed.",
                provider=provider_name,
                retryable=False,
            )
        hostname = (parsed.hostname or "").strip().lower()
        if not hostname or hostname not in self._allowed_hosts:
            raise ProviderError(
                code="PROVIDER_HOST_NOT_ALLOWED",
                message=f"Outbound host {hostname!r} is not in the configured allowlist.",
                provider=provider_name,
                retryable=False,
            )
        return hostname

    def _check_circuit(self, host: str, *, provider_name: str) -> None:
        now = time.monotonic()
        with self._lock:
            state = self._circuits.get(host)
            if state is not None and state.opened_until > now:
                raise ProviderError(
                    code="PROVIDER_CIRCUIT_OPEN",
                    message=f"Provider circuit breaker is temporarily open for host {host}.",
                    provider=provider_name,
                    retryable=True,
                )

    def _record_success(self, host: str) -> None:
        with self._lock:
            state = self._circuits.get(host)
            if state is not None:
                state.consecutive_failures = 0
                state.opened_until = 0.0

    def _record_failure(self, host: str) -> None:
        now = time.monotonic()
        with self._lock:
            state = self._circuits.setdefault(host, _HostCircuitState())
            state.consecutive_failures += 1
            if state.consecutive_failures >= self._circuit_threshold:
                state.opened_until = now + self._circuit_reset
                state.consecutive_failures = 0

    def _compute_backoff(self, attempt: int, retry_after_header: str | None = None) -> float:
        if retry_after_header:
            try:
                parsed = float(retry_after_header.strip())
                if parsed >= 0.0:
                    return min(parsed, self._backoff_max)
            except ValueError:
                pass
        base: float = min(
            self._backoff_base * float(2 ** max(attempt - 1, 0)),
            self._backoff_max,
        )
        jitter = random.uniform(0.0, min(base * 0.5, 1.0))
        return float(min(base + jitter, self._backoff_max))

    def _read_bounded_bytes(self, response: httpx.Response, *, provider_name: str) -> bytes:
        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
                if declared > self._max_response_bytes:
                    raise ProviderError(
                        code="PROVIDER_RESPONSE_TOO_LARGE",
                        message="Provider response exceeded configured byte limit.",
                        provider=provider_name,
                        retryable=False,
                        status_code=response.status_code,
                    )
            except ValueError:
                pass

        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_bytes():
            total += len(chunk)
            if total > self._max_response_bytes:
                raise ProviderError(
                    code="PROVIDER_RESPONSE_TOO_LARGE",
                    message="Provider response exceeded configured byte limit while streaming.",
                    provider=provider_name,
                    retryable=False,
                    status_code=response.status_code,
                )
            chunks.append(chunk)
        return b"".join(chunks)

    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        provider_name: str = "provider",
        endpoint_name: str = "request",
    ) -> Any:
        """Perform a GET request with SSRF guard, bounded retries, and JSON decoding."""
        host = self._validate_url(url, provider_name=provider_name)
        self._check_circuit(host, provider_name=provider_name)

        last_error: ProviderError | None = None

        for attempt in range(1, self._max_attempts + 1):
            started = time.perf_counter()
            try:
                with self._client.stream(
                    "GET",
                    url,
                    params=params,
                    headers=headers,
                    follow_redirects=False,
                ) as response:
                    status = response.status_code

                    # Block unexpected 3xx redirects rather than following to arbitrary hosts.
                    if 300 <= status < 400:
                        self._metrics.record_provider_request(
                            provider=provider_name,
                            endpoint=endpoint_name,
                            outcome="redirect_blocked",
                        )
                        raise ProviderError(
                            code="PROVIDER_REDIRECT_BLOCKED",
                            message=f"Provider returned disallowed redirect status {status}.",
                            provider=provider_name,
                            retryable=False,
                            status_code=status,
                        )

                    if status == 429 or status >= 500:
                        retry_after = response.headers.get("retry-after")
                        self._record_failure(host)
                        self._metrics.record_provider_request(
                            provider=provider_name,
                            endpoint=endpoint_name,
                            outcome=f"http_{status}",
                        )
                        last_error = ProviderError(
                            code="PROVIDER_RATE_LIMITED" if status == 429 else "PROVIDER_UNAVAILABLE",
                            message=f"Provider {provider_name} returned HTTP {status}.",
                            provider=provider_name,
                            retryable=True,
                            status_code=status,
                        )
                        if attempt < self._max_attempts:
                            time.sleep(self._compute_backoff(attempt, retry_after))
                            continue
                        raise last_error

                    if status >= 400:
                        self._metrics.record_provider_request(
                            provider=provider_name,
                            endpoint=endpoint_name,
                            outcome=f"http_{status}",
                        )
                        raise ProviderError(
                            code="PROVIDER_REQUEST_REJECTED",
                            message=f"Provider {provider_name} rejected request with HTTP {status}.",
                            provider=provider_name,
                            retryable=False,
                            status_code=status,
                        )

                    raw_bytes = self._read_bounded_bytes(response, provider_name=provider_name)

                elapsed = time.perf_counter() - started
                self._metrics.observe_provider_latency(
                    provider=provider_name,
                    endpoint=endpoint_name,
                    duration_seconds=elapsed,
                )
                self._metrics.record_provider_request(
                    provider=provider_name,
                    endpoint=endpoint_name,
                    outcome="ok",
                )
                self._record_success(host)

                try:
                    return json.loads(raw_bytes.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ProviderError(
                        code="PROVIDER_INVALID_JSON",
                        message=f"Provider {provider_name} returned malformed JSON.",
                        provider=provider_name,
                        retryable=False,
                        status_code=status,
                    ) from exc

            except ProviderError:
                raise
            except httpx.TimeoutException as exc:
                elapsed = time.perf_counter() - started
                self._metrics.observe_provider_latency(
                    provider=provider_name,
                    endpoint=endpoint_name,
                    duration_seconds=elapsed,
                )
                self._metrics.record_provider_request(
                    provider=provider_name,
                    endpoint=endpoint_name,
                    outcome="timeout",
                )
                self._record_failure(host)
                safe_detail = self.scrub_secrets(str(exc))
                logger.warning(
                    "Provider timeout on %s/%s (attempt %d/%d): %s",
                    provider_name,
                    endpoint_name,
                    attempt,
                    self._max_attempts,
                    safe_detail,
                )
                last_error = ProviderError(
                    code="PROVIDER_TIMEOUT",
                    message=f"Provider {provider_name} request timed out.",
                    provider=provider_name,
                    retryable=True,
                )
                if attempt < self._max_attempts:
                    time.sleep(self._compute_backoff(attempt))
                    continue
                raise last_error from exc
            except httpx.HTTPError as exc:
                elapsed = time.perf_counter() - started
                self._metrics.observe_provider_latency(
                    provider=provider_name,
                    endpoint=endpoint_name,
                    duration_seconds=elapsed,
                )
                self._metrics.record_provider_request(
                    provider=provider_name,
                    endpoint=endpoint_name,
                    outcome="transport_error",
                )
                self._record_failure(host)
                safe_detail = self.scrub_secrets(str(exc))
                logger.warning(
                    "Provider transport error on %s/%s (attempt %d/%d): %s",
                    provider_name,
                    endpoint_name,
                    attempt,
                    self._max_attempts,
                    safe_detail,
                )
                last_error = ProviderError(
                    code="PROVIDER_TRANSPORT_ERROR",
                    message=f"Provider {provider_name} transport error occurred.",
                    provider=provider_name,
                    retryable=True,
                )
                if attempt < self._max_attempts:
                    time.sleep(self._compute_backoff(attempt))
                    continue
                raise last_error from exc

        assert last_error is not None
        raise last_error
