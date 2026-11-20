"""URL routes for Spotter v1 trips, geocoding, and health endpoints."""

from __future__ import annotations

from django.urls import path

from apps.trips.views import (
    GeocodeSearchView,
    HealthLiveView,
    HealthReadyView,
    PlanCancelView,
    PlanCreateView,
    PlanDetailView,
    PlanForecastSliceView,
)

urlpatterns = [
    path("health/live", HealthLiveView.as_view(), name="health-live"),
    path("health/ready", HealthReadyView.as_view(), name="health-ready"),
    path("geocode", GeocodeSearchView.as_view(), name="geocode-search"),
    path("plans", PlanCreateView.as_view(), name="plan-create"),
    path("plans/<str:plan_id>", PlanDetailView.as_view(), name="plan-detail"),
    path("plans/<str:plan_id>/cancel", PlanCancelView.as_view(), name="plan-cancel"),
    path("plans/<str:plan_id>/forecast", PlanForecastSliceView.as_view(), name="plan-forecast"),
]
