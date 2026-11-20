"""Relational data models for Spotter trip plans, route candidates, checkpoints, and forecast slices."""

from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


def generate_plan_id() -> str:
    """Return a 22-character URL-safe opaque identifier with 128 bits of entropy."""
    return secrets.token_urlsafe(16)[:22]


def default_plan_expires_at():
    """Compute default plan expiry timestamp from validated runtime configuration."""
    ttl = int(getattr(settings, "PLAN_RESULT_TTL_SECONDS", 3600))
    return timezone.now() + timedelta(seconds=ttl)


class Plan(models.Model):
    """Owner-scoped weather-aware truck trip plan."""

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        ROUTING = "routing", "Routing"
        SAMPLING_WEATHER = "sampling_weather", "Sampling Weather"
        SCORING = "scoring", "Scoring"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    class DataMode(models.TextChoices):
        FIXTURE = "fixture", "Fixture"
        LIVE = "live", "Live"

    ACTIVE_STATUSES = frozenset(
        {
            Status.QUEUED,
            Status.ROUTING,
            Status.SAMPLING_WEATHER,
            Status.SCORING,
        }
    )

    id = models.CharField(
        primary_key=True,
        max_length=22,
        default=generate_plan_id,
        editable=False,
    )
    owner_scope = models.CharField(max_length=128, db_index=True)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.QUEUED,
        db_index=True,
    )
    data_mode = models.CharField(
        max_length=16,
        choices=DataMode.choices,
        default=DataMode.FIXTURE,
    )
    policy_version = models.CharField(max_length=64, default="risk-policy-v1")

    origin_label = models.CharField(max_length=200)
    origin_lat = models.FloatField()
    origin_lon = models.FloatField()
    destination_label = models.CharField(max_length=200)
    destination_lat = models.FloatField()
    destination_lon = models.FloatField()

    departure_at = models.DateTimeField()
    departure_timezone = models.CharField(max_length=64, default="UTC")
    load_weight_lb = models.DecimalField(max_digits=10, decimal_places=2)
    display_checkpoint_miles = models.IntegerField(default=25)

    recommendation_status = models.CharField(max_length=64, blank=True, default="")
    recommended_route_id = models.CharField(max_length=64, null=True, blank=True)
    recommendation_reason = models.TextField(blank=True, default="")

    result_payload = models.JSONField(default=dict, blank=True)
    forecast_metadata = models.JSONField(default=dict, blank=True)
    warnings = models.JSONField(default=list, blank=True)

    error_code = models.CharField(max_length=64, blank=True, default="")
    error_message = models.TextField(blank=True, default="")

    idempotency_key = models.CharField(max_length=128, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(default=default_plan_expires_at, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["id", "expires_at", "owner_scope"], name="plan_scoped_lookup_idx"),
            models.Index(fields=["owner_scope", "status"], name="plan_owner_status_idx"),
            models.Index(fields=["owner_scope", "idempotency_key"], name="plan_owner_idem_idx"),
            models.Index(fields=["status", "created_at"], name="plan_status_created_idx"),
        ]

    def __str__(self) -> str:
        return f"Plan({self.id}, status={self.status}, mode={self.data_mode})"

    @property
    def is_expired(self) -> bool:
        return bool(timezone.now() >= self.expires_at)


class RouteCandidate(models.Model):
    """Normalized truck route candidate evaluated within a Plan."""

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="routes")
    route_key = models.CharField(max_length=64)
    provider_route_id = models.CharField(max_length=128, blank=True, default="")
    fingerprint = models.CharField(max_length=128)
    distance_m = models.FloatField()
    duration_seconds = models.FloatField()
    eta_method = models.CharField(max_length=64, default="proportional_approximation")

    severe_miles = models.FloatField(default=0.0)
    high_miles = models.FloatField(default=0.0)
    no_travel_miles = models.FloatField(default=0.0)
    unknown_miles = models.FloatField(default=0.0)
    weighted_average_risk = models.FloatField(null=True, blank=True)
    eligible = models.BooleanField(default=False)
    coverage_fraction = models.FloatField(default=0.0)
    provider_warnings = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["route_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "fingerprint"],
                name="uniq_route_candidate_plan_fingerprint",
            ),
        ]

    def __str__(self) -> str:
        return f"RouteCandidate({self.plan_id}:{self.route_key}, eligible={self.eligible})"


class Checkpoint(models.Model):
    """Internal scoring checkpoint sampled along a RouteCandidate."""

    route = models.ForeignKey(RouteCandidate, on_delete=models.CASCADE, related_name="checkpoints")
    checkpoint_index = models.IntegerField()
    cumulative_distance_m = models.FloatField()
    lat = models.FloatField()
    lon = models.FloatField()
    eta_at = models.DateTimeField(null=True, blank=True)
    weather_valid_at = models.DateTimeField(null=True, blank=True)

    wind_mph = models.FloatField(null=True, blank=True)
    rain_in_per_hr = models.FloatField(null=True, blank=True)
    snow_in_per_hr = models.FloatField(null=True, blank=True)
    risk_severity = models.CharField(max_length=32, default="unknown")
    weather_status = models.CharField(max_length=32, default="missing")
    risk_reasons = models.JSONField(default=list, blank=True)
    is_display_checkpoint = models.BooleanField(default=False)

    class Meta:
        ordering = ["checkpoint_index"]
        constraints = [
            models.UniqueConstraint(
                fields=["route", "checkpoint_index"],
                name="uniq_checkpoint_route_index",
            ),
        ]
        indexes = [
            models.Index(fields=["route", "checkpoint_index"], name="checkpoint_route_order_idx"),
        ]

    def __str__(self) -> str:
        return f"Checkpoint({self.route_id}#{self.checkpoint_index}, {self.risk_severity})"


class PlanJob(models.Model):
    """Execution tracking and retry supervision record for a Plan."""

    plan = models.OneToOneField(Plan, on_delete=models.CASCADE, related_name="job")
    status = models.CharField(
        max_length=32,
        choices=Plan.Status.choices,
        default=Plan.Status.QUEUED,
        db_index=True,
    )
    attempts = models.IntegerField(default=0)
    idempotency_key = models.CharField(max_length=128, null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "created_at"], name="planjob_status_created_idx"),
        ]

    def __str__(self) -> str:
        return f"PlanJob({self.plan_id}, status={self.status}, attempts={self.attempts})"


class ForecastSliceCache(models.Model):
    """Cached wall-clock corridor weather slice for a Plan at a specific hour_offset (0..48)."""

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="forecast_slices")
    hour_offset = models.IntegerField()
    valid_at = models.DateTimeField()
    coverage_fraction = models.FloatField(default=0.0)
    coverage_complete = models.BooleanField(default=False)
    data_origin = models.CharField(max_length=64, default="open_meteo")
    payload = models.JSONField(default=dict)
    expires_at = models.DateTimeField(default=default_plan_expires_at, db_index=True)

    class Meta:
        ordering = ["hour_offset"]
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "hour_offset"],
                name="uniq_forecast_slice_plan_hour",
            ),
        ]

    def __str__(self) -> str:
        return f"ForecastSliceCache({self.plan_id}+{self.hour_offset}h)"
