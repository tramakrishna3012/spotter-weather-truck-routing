"""Safety-sensitive weather hazard classifier and conservative window combiner.

Implements exact half-open threshold intervals, strict-greater payload wind overrides,
and fail-closed handling for missing, invalid, or out-of-range weather data.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from domain.risk.policy import DEFAULT_RISK_POLICY, SEVERITY_RANK, RiskPolicy, Severity
from domain.risk.units import InvalidMeasurementError, to_finite_nonnegative_decimal

VALID_READING_STATUSES = frozenset({"known", "missing", "out_of_range", "invalid"})


@dataclass(frozen=True)
class WeatherReading:
    """Normalized hourly weather observation/forecast in canonical imperial units."""

    wind_mph: Decimal | None
    rain_in_per_hr: Decimal | None
    snow_in_per_hr: Decimal | None
    valid_at: datetime | None
    issued_at: datetime | None
    status: str = "known"


@dataclass(frozen=True)
class ClassificationResult:
    """Deterministic classification output for a checkpoint or forecast window."""

    severity: Severity
    status: str  # "known", "unknown", "no_travel"
    reasons: tuple[str, ...]
    wind_severity: Severity
    rain_severity: Severity
    snow_severity: Severity
    override_applied: str | None = None


def _unknown_result(
    reasons: Sequence[str],
    *,
    wind_severity: Severity = Severity.UNKNOWN,
    rain_severity: Severity = Severity.UNKNOWN,
    snow_severity: Severity = Severity.UNKNOWN,
) -> ClassificationResult:
    unique_reasons = tuple(dict.fromkeys(reasons)) or ("unknown_weather",)
    return ClassificationResult(
        severity=Severity.UNKNOWN,
        status="unknown",
        reasons=unique_reasons,
        wind_severity=wind_severity,
        rain_severity=rain_severity,
        snow_severity=snow_severity,
        override_applied=None,
    )


def _classify_wind(
    wind_mph: Decimal,
    load_lb: Decimal,
    policy: RiskPolicy,
) -> tuple[Severity, str | None]:
    if wind_mph >= policy.wind_no_travel_mph:
        return Severity.NO_TRAVEL, None
    if wind_mph >= policy.wind_severe_mph:
        if load_lb > policy.load_severe_wind_no_travel_gt_lb:
            return Severity.NO_TRAVEL, "wind_45_54_load_over_30000_no_travel"
        return Severity.SEVERE, None
    if wind_mph >= policy.wind_high_mph:
        if load_lb > policy.load_high_wind_severe_gt_lb:
            return Severity.SEVERE, "wind_35_44_load_over_40000_severe"
        return Severity.HIGH, None
    if wind_mph >= policy.wind_moderate_mph:
        return Severity.MODERATE, None
    return Severity.LOW, None


def _classify_rain(rain_in_per_hr: Decimal, policy: RiskPolicy) -> Severity:
    if rain_in_per_hr > policy.rain_no_travel_gt_in_hr:
        return Severity.NO_TRAVEL
    if rain_in_per_hr >= policy.rain_severe_in_hr:
        return Severity.SEVERE
    if rain_in_per_hr >= policy.rain_high_in_hr:
        return Severity.HIGH
    if rain_in_per_hr >= policy.rain_moderate_in_hr:
        return Severity.MODERATE
    return Severity.LOW


def _classify_snow(snow_in_per_hr: Decimal, policy: RiskPolicy) -> Severity:
    if snow_in_per_hr > policy.snow_no_travel_gt_in_hr:
        return Severity.NO_TRAVEL
    if snow_in_per_hr >= policy.snow_severe_in_hr:
        return Severity.SEVERE
    if snow_in_per_hr >= policy.snow_high_in_hr:
        return Severity.HIGH
    if snow_in_per_hr >= policy.snow_moderate_in_hr:
        return Severity.MODERATE
    return Severity.LOW


def classify_weather(
    reading: WeatherReading,
    load_weight_lb: Decimal | float | int,
    policy: RiskPolicy = DEFAULT_RISK_POLICY,
) -> ClassificationResult:
    """Classify a single normalized WeatherReading against a versioned RiskPolicy.

    Fails closed to Severity.UNKNOWN on invalid load weight, non-known reading status,
    missing measurements, or negative/non-finite numeric values. Never coerces None to 0.
    """
    try:
        load_dec = to_finite_nonnegative_decimal(load_weight_lb, "load_weight_lb")
    except InvalidMeasurementError:
        return _unknown_result(("invalid_load_weight",))

    if load_dec is None:
        return _unknown_result(("missing_load_weight",))

    if reading.status != "known":
        normalized_status = (
            reading.status if reading.status in VALID_READING_STATUSES else "invalid"
        )
        return _unknown_result((f"weather_status_{normalized_status}",))

    errors: list[str] = []

    wind_dec: Decimal | None = None
    try:
        wind_dec = to_finite_nonnegative_decimal(reading.wind_mph, "wind_mph")
        if wind_dec is None:
            errors.append("missing_wind")
    except InvalidMeasurementError:
        errors.append("invalid_wind")

    rain_dec: Decimal | None = None
    try:
        rain_dec = to_finite_nonnegative_decimal(reading.rain_in_per_hr, "rain_in_per_hr")
        if rain_dec is None:
            errors.append("missing_rain")
    except InvalidMeasurementError:
        errors.append("invalid_rain")

    snow_dec: Decimal | None = None
    try:
        snow_dec = to_finite_nonnegative_decimal(reading.snow_in_per_hr, "snow_in_per_hr")
        if snow_dec is None:
            errors.append("missing_snow")
    except InvalidMeasurementError:
        errors.append("invalid_snow")

    if errors or wind_dec is None or rain_dec is None or snow_dec is None:
        wind_sev_partial = (
            _classify_wind(wind_dec, load_dec, policy)[0]
            if wind_dec is not None
            else Severity.UNKNOWN
        )
        rain_sev_partial = (
            _classify_rain(rain_dec, policy) if rain_dec is not None else Severity.UNKNOWN
        )
        snow_sev_partial = (
            _classify_snow(snow_dec, policy) if snow_dec is not None else Severity.UNKNOWN
        )
        return _unknown_result(
            errors,
            wind_severity=wind_sev_partial,
            rain_severity=rain_sev_partial,
            snow_severity=snow_sev_partial,
        )

    wind_sev, override_applied = _classify_wind(wind_dec, load_dec, policy)
    rain_sev = _classify_rain(rain_dec, policy)
    snow_sev = _classify_snow(snow_dec, policy)

    combined = max((wind_sev, rain_sev, snow_sev), key=lambda s: SEVERITY_RANK[s])

    reasons: list[str] = []
    if wind_sev != Severity.LOW:
        reasons.append(f"wind_{wind_sev.value}")
    if override_applied is not None:
        reasons.append(override_applied)
    if rain_sev != Severity.LOW:
        reasons.append(f"rain_{rain_sev.value}")
    if snow_sev != Severity.LOW:
        reasons.append(f"snow_{snow_sev.value}")
    if not reasons:
        reasons.append("all_conditions_low")

    result_status = "no_travel" if combined == Severity.NO_TRAVEL else "known"

    return ClassificationResult(
        severity=combined,
        status=result_status,
        reasons=tuple(dict.fromkeys(reasons)),
        wind_severity=wind_sev,
        rain_severity=rain_sev,
        snow_severity=snow_sev,
        override_applied=override_applied,
    )


def classify_conservative_window(
    readings: Sequence[WeatherReading],
    load_weight_lb: Decimal | float | int,
    policy: RiskPolicy = DEFAULT_RISK_POLICY,
) -> ClassificationResult:
    """Conservatively classify across neighboring hourly forecast bins.

    Fails closed to Severity.UNKNOWN if `readings` is empty or if ANY reading in the
    window classifies as UNKNOWN. Otherwise returns the worst severity across the window
    and preserves all contributing hazard and override reason codes.
    """
    if not readings:
        return _unknown_result(("missing_weather_window",))

    results = [classify_weather(reading, load_weight_lb, policy) for reading in readings]

    unknown_results = [res for res in results if res.severity == Severity.UNKNOWN]
    if unknown_results:
        unknown_reasons: list[str] = []
        for res in unknown_results:
            unknown_reasons.extend(res.reasons)
        return _unknown_result(unknown_reasons)

    worst_wind = max((res.wind_severity for res in results), key=lambda s: SEVERITY_RANK[s])
    worst_rain = max((res.rain_severity for res in results), key=lambda s: SEVERITY_RANK[s])
    worst_snow = max((res.snow_severity for res in results), key=lambda s: SEVERITY_RANK[s])
    worst_overall = max((res.severity for res in results), key=lambda s: SEVERITY_RANK[s])

    override_applied: str | None = None
    for res in results:
        if res.wind_severity == worst_wind and res.override_applied is not None:
            override_applied = res.override_applied
            break
    if override_applied is None:
        for res in results:
            if res.override_applied is not None:
                override_applied = res.override_applied
                break

    combined_reasons: list[str] = []
    for res in results:
        for reason in res.reasons:
            if reason != "all_conditions_low":
                combined_reasons.append(reason)
    if not combined_reasons:
        combined_reasons.append("all_conditions_low")

    status = "no_travel" if worst_overall == Severity.NO_TRAVEL else "known"
    return ClassificationResult(
        severity=worst_overall,
        status=status,
        reasons=tuple(dict.fromkeys(combined_reasons)),
        wind_severity=worst_wind,
        rain_severity=worst_rain,
        snow_severity=worst_snow,
        override_applied=override_applied,
    )
