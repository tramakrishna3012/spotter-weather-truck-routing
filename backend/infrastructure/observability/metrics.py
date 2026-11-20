"""Thread-safe in-memory Prometheus metrics registry with bounded label cardinality.

Tracks:
- `plans_started_total{data_mode,source}`
- `plans_completed_total{status,data_mode,source}`
- `provider_requests_total{provider,endpoint,outcome}`
- `provider_latency_seconds{provider,endpoint}` (histogram)

Strictly enforces low-cardinality label keys/values (never trip/plan IDs or raw coords).
"""

from __future__ import annotations

import math
import re
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field

DEFAULT_LATENCY_BUCKETS: tuple[float, ...] = (
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    20.0,
)

_SAFE_LABEL_VALUE_RE = re.compile(r"[^a-zA-Z0-9_.:/-]")
_MAX_LABEL_LENGTH = 48


def _sanitize_label_value(value: str) -> str:
    cleaned = _SAFE_LABEL_VALUE_RE.sub("_", str(value).strip())[:_MAX_LABEL_LENGTH]
    return cleaned or "unknown"


def _escape_prometheus_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _format_labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    pairs = ",".join(f'{k}="{_escape_prometheus_label(v)}"' for k, v in labels)
    return "{" + pairs + "}"


@dataclass
class _HistogramState:
    buckets: tuple[float, ...]
    counts: list[int] = field(default_factory=list)
    total_count: int = 0
    total_sum: float = 0.0

    def __post_init__(self) -> None:
        if not self.counts:
            self.counts = [0 for _ in self.buckets]

    def observe(self, value: float) -> None:
        if not math.isfinite(value) or value < 0.0:
            return
        self.total_count += 1
        self.total_sum += value
        for idx, bound in enumerate(self.buckets):
            if value <= bound:
                self.counts[idx] += 1


class MetricsRegistry:
    """Thread-safe Prometheus text-format metrics registry."""

    def __init__(self, latency_buckets: tuple[float, ...] = DEFAULT_LATENCY_BUCKETS) -> None:
        if not latency_buckets or any(
            not math.isfinite(b) or b <= 0.0 for b in latency_buckets
        ):
            raise ValueError("latency_buckets must contain positive finite floats.")
        self._buckets = tuple(sorted(set(latency_buckets)))
        self._lock = threading.Lock()
        self._plans_started: dict[tuple[tuple[str, str], ...], int] = {}
        self._plans_completed: dict[tuple[tuple[str, str], ...], int] = {}
        self._provider_requests: dict[tuple[tuple[str, str], ...], int] = {}
        self._provider_latency: dict[tuple[tuple[str, str], ...], _HistogramState] = {}

    def record_plan_started(self, *, data_mode: str, source: str = "api") -> None:
        key = (
            ("data_mode", _sanitize_label_value(data_mode)),
            ("source", _sanitize_label_value(source)),
        )
        with self._lock:
            self._plans_started[key] = self._plans_started.get(key, 0) + 1

    def record_plan_completed(
        self,
        *,
        status: str,
        data_mode: str,
        source: str = "api",
    ) -> None:
        key = (
            ("data_mode", _sanitize_label_value(data_mode)),
            ("source", _sanitize_label_value(source)),
            ("status", _sanitize_label_value(status)),
        )
        with self._lock:
            self._plans_completed[key] = self._plans_completed.get(key, 0) + 1

    def record_provider_request(
        self,
        *,
        provider: str,
        endpoint: str,
        outcome: str,
    ) -> None:
        key = (
            ("endpoint", _sanitize_label_value(endpoint)),
            ("outcome", _sanitize_label_value(outcome)),
            ("provider", _sanitize_label_value(provider)),
        )
        with self._lock:
            self._provider_requests[key] = self._provider_requests.get(key, 0) + 1

    def observe_provider_latency(
        self,
        *,
        provider: str,
        endpoint: str,
        duration_seconds: float,
    ) -> None:
        key = (
            ("endpoint", _sanitize_label_value(endpoint)),
            ("provider", _sanitize_label_value(provider)),
        )
        with self._lock:
            state = self._provider_latency.get(key)
            if state is None:
                state = _HistogramState(buckets=self._buckets)
                self._provider_latency[key] = state
            state.observe(duration_seconds)

    def snapshot_counters(self) -> Mapping[str, dict[tuple[tuple[str, str], ...], int]]:
        with self._lock:
            return {
                "plans_started_total": dict(self._plans_started),
                "plans_completed_total": dict(self._plans_completed),
                "provider_requests_total": dict(self._provider_requests),
            }

    def reset(self) -> None:
        with self._lock:
            self._plans_started.clear()
            self._plans_completed.clear()
            self._provider_requests.clear()
            self._provider_latency.clear()

    def render_prometheus_text(self) -> str:
        """Render all registered counters and histograms in Prometheus exposition format."""
        lines: list[str] = []
        with self._lock:
            lines.append("# HELP plans_started_total Total number of route plans started.")
            lines.append("# TYPE plans_started_total counter")
            for labels, count in sorted(self._plans_started.items()):
                lines.append(f"plans_started_total{_format_labels(labels)} {count}")

            lines.append("# HELP plans_completed_total Total number of route plans completed.")
            lines.append("# TYPE plans_completed_total counter")
            for labels, count in sorted(self._plans_completed.items()):
                lines.append(f"plans_completed_total{_format_labels(labels)} {count}")

            lines.append("# HELP provider_requests_total Total outbound provider requests.")
            lines.append("# TYPE provider_requests_total counter")
            for labels, count in sorted(self._provider_requests.items()):
                lines.append(f"provider_requests_total{_format_labels(labels)} {count}")

            lines.append(
                "# HELP provider_latency_seconds Outbound provider request latency in seconds."
            )
            lines.append("# TYPE provider_latency_seconds histogram")
            for labels, hist in sorted(self._provider_latency.items()):
                for bound, bucket_count in zip(hist.buckets, hist.counts, strict=True):
                    bucket_labels = labels + (("le", f"{bound:g}"),)
                    lines.append(
                        f"provider_latency_seconds_bucket{_format_labels(bucket_labels)} {bucket_count}"
                    )
                inf_labels = labels + (("le", "+Inf"),)
                lines.append(
                    f"provider_latency_seconds_bucket{_format_labels(inf_labels)} {hist.total_count}"
                )
                lines.append(
                    f"provider_latency_seconds_sum{_format_labels(labels)} {hist.total_sum:.6f}"
                )
                lines.append(
                    f"provider_latency_seconds_count{_format_labels(labels)} {hist.total_count}"
                )

        return "\n".join(lines) + "\n"


_DEFAULT_REGISTRY = MetricsRegistry()


def get_default_registry() -> MetricsRegistry:
    return _DEFAULT_REGISTRY


def record_plan_started(*, data_mode: str, source: str = "api") -> None:
    _DEFAULT_REGISTRY.record_plan_started(data_mode=data_mode, source=source)


def record_plan_completed(*, status: str, data_mode: str, source: str = "api") -> None:
    _DEFAULT_REGISTRY.record_plan_completed(status=status, data_mode=data_mode, source=source)


def record_provider_request(*, provider: str, endpoint: str, outcome: str) -> None:
    _DEFAULT_REGISTRY.record_provider_request(
        provider=provider, endpoint=endpoint, outcome=outcome
    )


def observe_provider_latency(*, provider: str, endpoint: str, duration_seconds: float) -> None:
    _DEFAULT_REGISTRY.observe_provider_latency(
        provider=provider, endpoint=endpoint, duration_seconds=duration_seconds
    )


def render_prometheus_text() -> str:
    return _DEFAULT_REGISTRY.render_prometheus_text()


def reset_metrics() -> None:
    _DEFAULT_REGISTRY.reset()
