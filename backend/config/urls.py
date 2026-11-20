"""Root URL configuration for Spotter backend."""

from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


def metrics_view(_request: HttpRequest) -> HttpResponse:
    """Expose Prometheus-formatted application metrics."""
    from infrastructure.observability.metrics import render_prometheus_text

    body = render_prometheus_text()
    return HttpResponse(body, content_type="text/plain; version=0.0.4; charset=utf-8")


urlpatterns = [
    path("api/v1/", include("apps.trips.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
]

if getattr(settings, "ENABLE_METRICS_ENDPOINT", False):
    urlpatterns.append(path("metrics", metrics_view, name="prometheus-metrics"))
