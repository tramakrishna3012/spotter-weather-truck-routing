"""Risk assessment domain subpackage (pure Python stdlib only)."""

from domain.risk.classifier import (
    ClassificationResult,
    WeatherReading,
    classify_conservative_window,
    classify_weather,
)
from domain.risk.policy import (
    DEFAULT_RISK_POLICY,
    POLICY_VERSION,
    RISK_WEIGHT,
    SEVERITY_RANK,
    RiskPolicy,
    Severity,
)
from domain.risk.units import (
    METERS_PER_MILE,
    InvalidMeasurementError,
    UnitConversionError,
    convert_rain_to_in_per_hr,
    convert_snow_to_in_per_hr,
    convert_wind_to_mph,
    meters_to_miles,
    miles_to_meters,
    to_finite_nonnegative_decimal,
)

__all__ = [
    "ClassificationResult",
    "DEFAULT_RISK_POLICY",
    "InvalidMeasurementError",
    "METERS_PER_MILE",
    "POLICY_VERSION",
    "RISK_WEIGHT",
    "RiskPolicy",
    "SEVERITY_RANK",
    "Severity",
    "UnitConversionError",
    "WeatherReading",
    "classify_conservative_window",
    "classify_weather",
    "convert_rain_to_in_per_hr",
    "convert_snow_to_in_per_hr",
    "convert_wind_to_mph",
    "meters_to_miles",
    "miles_to_meters",
    "to_finite_nonnegative_decimal",
]
