"""AppConfig for the Spotter trips application."""

from __future__ import annotations

from django.apps import AppConfig


class TripsConfig(AppConfig):
    """Django app configuration for weather-aware trip planning."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.trips"
    verbose_name = "Spotter Trip Planning"
