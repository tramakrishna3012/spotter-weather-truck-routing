"""Strict DRF input serializers for Spotter trip planning, geocoding, and forecast endpoints."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

SUPPORTED_DISPLAY_CHECKPOINT_MILES = (10, 25, 50)
MIN_ORIGIN_DESTINATION_DISTANCE_M = 100.0
MAX_LOAD_WEIGHT_LB = 200_000.0
MAX_PAST_DEPARTURE_HOURS = 24
MAX_FUTURE_DEPARTURE_DAYS = 14


def _validate_finite_float(value: float, field_label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise serializers.ValidationError(f"{field_label} must be a finite number.")
    return float(value)


def _format_tz_offset(dt: datetime) -> str:
    offset = dt.utcoffset()
    if offset is None:
        return "UTC"
    total_minutes = int(offset.total_seconds() // 60)
    if total_minutes == 0:
        return "UTC"
    sign = "+" if total_minutes >= 0 else "-"
    abs_minutes = abs(total_minutes)
    hours, minutes = divmod(abs_minutes, 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


def _haversine_meters_fallback(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    try:
        from domain.routing.polyline import haversine_meters

        return float(haversine_meters(lat1, lon1, lat2, lon2))
    except ImportError:
        earth_radius_m = 6_371_008.8
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = (
            math.sin(dphi / 2.0) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
        )
        return 2.0 * earth_radius_m * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


class LocationInputSerializer(serializers.Serializer):
    """Validated geographic point with human-readable location label."""

    latitude = serializers.FloatField(min_value=-90.0, max_value=90.0)
    longitude = serializers.FloatField(min_value=-180.0, max_value=180.0)
    label = serializers.CharField(min_length=1, max_length=200, trim_whitespace=True)

    def validate_latitude(self, value: float) -> float:
        val = _validate_finite_float(value, "latitude")
        if val < -90.0 or val > 90.0:
            raise serializers.ValidationError("latitude must be between -90 and 90.")
        return val

    def validate_longitude(self, value: float) -> float:
        val = _validate_finite_float(value, "longitude")
        if val < -180.0 or val > 180.0:
            raise serializers.ValidationError("longitude must be between -180 and 180.")
        return val

    def validate_label(self, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise serializers.ValidationError("label must not be blank.")
        if len(cleaned) > 200:
            raise serializers.ValidationError("label must be at most 200 characters.")
        return cleaned


class CreatePlanSerializer(serializers.Serializer):
    """Strict input contract for POST /api/v1/plans."""

    origin = LocationInputSerializer(required=True)
    destination = LocationInputSerializer(required=True)
    departure_at = serializers.CharField(required=True)
    load_weight_lb = serializers.FloatField(required=True)
    display_checkpoint_miles = serializers.IntegerField(required=False)

    def validate_departure_at(self, value: str) -> dict[str, Any]:
        raw = str(value).strip()
        if not raw:
            raise serializers.ValidationError("departure_at is required.")
        iso_candidate = raw[:-1] + "+00:00" if raw.endswith(("Z", "z")) else raw
        try:
            parsed = datetime.fromisoformat(iso_candidate)
        except ValueError as exc:
            raise serializers.ValidationError(
                "departure_at must be a valid ISO 8601 datetime with timezone offset."
            ) from exc

        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise serializers.ValidationError(
                "departure_at must include an explicit timezone offset (e.g. 'Z' or '-05:00')."
            )

        now_utc = timezone.now().astimezone(UTC)
        parsed_utc = parsed.astimezone(UTC)

        min_allowed = now_utc - timedelta(hours=MAX_PAST_DEPARTURE_HOURS)
        max_allowed = now_utc + timedelta(days=MAX_FUTURE_DEPARTURE_DAYS)

        if parsed_utc < min_allowed:
            raise serializers.ValidationError(
                f"departure_at cannot be more than {MAX_PAST_DEPARTURE_HOURS} hours in the past."
            )
        if parsed_utc > max_allowed:
            raise serializers.ValidationError(
                f"departure_at cannot be more than {MAX_FUTURE_DEPARTURE_DAYS} days in the future."
            )

        return {
            "utc": parsed_utc,
            "timezone": _format_tz_offset(parsed),
            "raw": raw,
        }

    def validate_load_weight_lb(self, value: float) -> float:
        val = _validate_finite_float(value, "load_weight_lb")
        if val < 0.0:
            raise serializers.ValidationError("load_weight_lb must be >= 0.")
        if val > MAX_LOAD_WEIGHT_LB:
            raise serializers.ValidationError(
                f"load_weight_lb must be <= {int(MAX_LOAD_WEIGHT_LB)}."
            )
        return val

    def validate_display_checkpoint_miles(self, value: int) -> int:
        if isinstance(value, bool) or value not in SUPPORTED_DISPLAY_CHECKPOINT_MILES:
            raise serializers.ValidationError(
                "display_checkpoint_miles must be one of 10, 25, or 50."
            )
        return int(value)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        origin = attrs["origin"]
        destination = attrs["destination"]

        distance_m = _haversine_meters_fallback(
            origin["latitude"],
            origin["longitude"],
            destination["latitude"],
            destination["longitude"],
        )
        if distance_m <= MIN_ORIGIN_DESTINATION_DISTANCE_M:
            raise serializers.ValidationError(
                {
                    "destination": (
                        "Origin and destination must be distinct locations more than 100 meters apart."
                    )
                }
            )

        if "display_checkpoint_miles" not in attrs:
            attrs["display_checkpoint_miles"] = int(
                getattr(settings, "DEFAULT_DISPLAY_CHECKPOINT_MILES", 25)
            )

        return attrs


class GeocodeQuerySerializer(serializers.Serializer):
    """Query parameter validation for GET /api/v1/geocode."""

    q = serializers.CharField(min_length=2, max_length=120, trim_whitespace=True)
    limit = serializers.IntegerField(min_value=1, max_value=10, default=5, required=False)

    def validate_q(self, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise serializers.ValidationError("q must contain at least 2 non-space characters.")
        return cleaned


class ForecastSliceQuerySerializer(serializers.Serializer):
    """Query parameter validation for GET /api/v1/plans/{plan_id}/forecast."""

    hour_offset = serializers.IntegerField(min_value=0, default=0, required=False)

    def validate_hour_offset(self, value: int) -> int:
        max_slider_hours = int(getattr(settings, "FORECAST_SLIDER_HOURS", 48))
        if value < 0 or value > max_slider_hours:
            raise serializers.ValidationError(
                f"hour_offset must be an integer between 0 and {max_slider_hours}."
            )
        return int(value)


class PlanDetailQuerySerializer(serializers.Serializer):
    """Optional query parameter validation for GET /api/v1/plans/{plan_id}."""

    display_checkpoint_miles = serializers.IntegerField(required=False)

    def validate_display_checkpoint_miles(self, value: int) -> int:
        if isinstance(value, bool) or value not in SUPPORTED_DISPLAY_CHECKPOINT_MILES:
            raise serializers.ValidationError(
                "display_checkpoint_miles must be one of 10, 25, or 50."
            )
        return int(value)
