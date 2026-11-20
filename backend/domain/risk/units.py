"""Explicit unit conversion and numeric validation helpers for weather and distance.

All conversions use exact Decimal factors per docs/06_RISK_AND_RECOMMENDATION.md:
- 1 mile = 1609.344 meters (1.609344 km)
- 1 inch = 25.4 mm = 2.54 cm
- 1 knot = 1852 m/hr
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

METERS_PER_MILE = Decimal("1609.344")
KM_PER_MILE = Decimal("1.609344")
MM_PER_INCH = Decimal("25.4")
CM_PER_INCH = Decimal("2.54")
SECONDS_PER_HOUR = Decimal("3600")
METERS_PER_NAUTICAL_MILE = Decimal("1852")

_WIND_MPH_UNITS = frozenset({"mph", "mp/h", "mi/h"})
_WIND_KMH_UNITS = frozenset({"km/h", "kmh", "kph"})
_WIND_MPS_UNITS = frozenset({"m/s", "mps"})
_WIND_KNOT_UNITS = frozenset({"kn", "kt", "knots"})

_PRECIP_INCH_UNITS = frozenset({"in", "inch", "inches", "in/h", "in/hr"})
_PRECIP_MM_UNITS = frozenset({"mm", "mm/h", "mm/hr"})
_PRECIP_CM_UNITS = frozenset({"cm", "cm/h", "cm/hr"})


class UnitConversionError(ValueError):
    """Raised when a provider supplies an unsupported or missing measurement unit."""


class InvalidMeasurementError(ValueError):
    """Raised when a measurement is non-finite, negative, or unparseable."""


def _to_finite_decimal(value: float | int | Decimal | str, field_name: str) -> Decimal:
    if isinstance(value, bool):
        raise InvalidMeasurementError(f"{field_name} must be numeric, not bool.")
    try:
        dec = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError) as exc:
        raise InvalidMeasurementError(f"{field_name} is not a valid decimal: {value!r}.") from exc
    if not dec.is_finite():
        raise InvalidMeasurementError(f"{field_name} must be finite, got {value!r}.")
    return dec


def meters_to_miles(meters: float | Decimal) -> float:
    """Convert meters to miles using exact international mile factor."""
    dec = _to_finite_decimal(meters, "meters")
    return float(dec / METERS_PER_MILE)


def miles_to_meters(miles: float | Decimal) -> float:
    """Convert miles to meters using exact international mile factor."""
    dec = _to_finite_decimal(miles, "miles")
    return float(dec * METERS_PER_MILE)


def to_finite_nonnegative_decimal(
    value: float | int | Decimal | str | None,
    field_name: str,
) -> Decimal | None:
    """Validate and convert a scalar measurement to a finite non-negative Decimal.

    Returns None when value is None (never coerces None to zero).
    Raises InvalidMeasurementError for NaN, Infinity, negative numbers, bools, or invalid strings.
    """
    if value is None:
        return None
    dec = _to_finite_decimal(value, field_name)
    if dec < Decimal("0"):
        raise InvalidMeasurementError(f"{field_name} must be non-negative, got {dec}.")
    return dec


def _normalize_unit(unit: str, field_name: str) -> str:
    if not isinstance(unit, str) or not unit.strip():
        raise UnitConversionError(f"Missing or empty unit for {field_name}.")
    return unit.strip().lower()


def convert_wind_to_mph(
    value: float | int | Decimal | None,
    unit: str,
) -> Decimal | None:
    """Convert a wind speed measurement into mph using exact unit factors.

    Supports mph, mp/h, km/h, kmh, m/s, kn, and kt.
    Validates unit even when value is None to catch provider schema mismatches early.
    """
    normalized = _normalize_unit(unit, "wind")
    if normalized in _WIND_MPH_UNITS:
        factor_num, factor_den = Decimal("1"), Decimal("1")
    elif normalized in _WIND_KMH_UNITS:
        factor_num, factor_den = Decimal("1"), KM_PER_MILE
    elif normalized in _WIND_MPS_UNITS:
        factor_num, factor_den = SECONDS_PER_HOUR, METERS_PER_MILE
    elif normalized in _WIND_KNOT_UNITS:
        factor_num, factor_den = METERS_PER_NAUTICAL_MILE, METERS_PER_MILE
    else:
        raise UnitConversionError(f"Unsupported wind speed unit: {unit!r}.")

    dec = to_finite_nonnegative_decimal(value, "wind")
    if dec is None:
        return None
    return (dec * factor_num) / factor_den


def convert_rain_to_in_per_hr(
    value: float | int | Decimal | None,
    unit: str,
) -> Decimal | None:
    """Convert rainfall rate into inches/hour using exact metric/imperial factors.

    Supports in, inch, in/h, in/hr, mm, mm/h, mm/hr, cm, cm/h, cm/hr.
    """
    normalized = _normalize_unit(unit, "rain")
    if normalized in _PRECIP_INCH_UNITS:
        divisor = Decimal("1")
    elif normalized in _PRECIP_MM_UNITS:
        divisor = MM_PER_INCH
    elif normalized in _PRECIP_CM_UNITS:
        divisor = CM_PER_INCH
    else:
        raise UnitConversionError(f"Unsupported rain unit: {unit!r}.")

    dec = to_finite_nonnegative_decimal(value, "rain")
    if dec is None:
        return None
    return dec / divisor


def convert_snow_to_in_per_hr(
    value: float | int | Decimal | None,
    unit: str,
) -> Decimal | None:
    """Convert snowfall rate into inches/hour using exact metric/imperial factors.

    Supports in, inch, in/h, in/hr, cm, cm/h, cm/hr, mm, mm/h, mm/hr.
    """
    normalized = _normalize_unit(unit, "snow")
    if normalized in _PRECIP_INCH_UNITS:
        divisor = Decimal("1")
    elif normalized in _PRECIP_CM_UNITS:
        divisor = CM_PER_INCH
    elif normalized in _PRECIP_MM_UNITS:
        divisor = MM_PER_INCH
    else:
        raise UnitConversionError(f"Unsupported snow unit: {unit!r}.")

    dec = to_finite_nonnegative_decimal(value, "snow")
    if dec is None:
        return None
    return dec / divisor
