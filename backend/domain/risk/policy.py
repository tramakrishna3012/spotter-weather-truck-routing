"""Versioned safety-sensitive weather risk policy specification.

Thresholds follow docs/06_RISK_AND_RECOMMENDATION.md with exact Decimal values
and half-open interval semantics. Policy values must never be tuned dynamically.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

POLICY_VERSION = "risk-policy-v1"


class Severity(StrEnum):
    """Canonical hazard severity levels.

    UNKNOWN is explicitly separate from LOW and excluded from SEVERITY_RANK.
    """

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"
    NO_TRAVEL = "no_travel"
    UNKNOWN = "unknown"


SEVERITY_RANK: dict[Severity, int] = {
    Severity.LOW: 0,
    Severity.MODERATE: 1,
    Severity.HIGH: 2,
    Severity.SEVERE: 3,
    Severity.NO_TRAVEL: 4,
}

RISK_WEIGHT: dict[Severity, int] = {
    Severity.LOW: 0,
    Severity.MODERATE: 1,
    Severity.HIGH: 2,
    Severity.SEVERE: 3,
}


@dataclass(frozen=True)
class RiskPolicy:
    """Immutable versioned thresholds for weather risk classification and payload overrides."""

    version: str = POLICY_VERSION

    # Wind speed thresholds (mph):
    # <25 Low, [25, 35) Moderate, [35, 45) High, [45, 55) Severe, >=55 No Travel
    wind_moderate_mph: Decimal = Decimal("25")
    wind_high_mph: Decimal = Decimal("35")
    wind_severe_mph: Decimal = Decimal("45")
    wind_no_travel_mph: Decimal = Decimal("55")

    # Rain intensity thresholds (in/hr):
    # <0.10 Low, [0.10, 0.25) Moderate, [0.25, 0.50) High, [0.50, 1.00] Severe, >1.00 No Travel
    rain_moderate_in_hr: Decimal = Decimal("0.10")
    rain_high_in_hr: Decimal = Decimal("0.25")
    rain_severe_in_hr: Decimal = Decimal("0.50")
    rain_no_travel_gt_in_hr: Decimal = Decimal("1.00")

    # Snow intensity thresholds (in/hr):
    # <0.5 Low, [0.5, 1.0) Moderate, [1.0, 2.0) High, [2.0, 3.0] Severe, >3.0 No Travel
    snow_moderate_in_hr: Decimal = Decimal("0.5")
    snow_high_in_hr: Decimal = Decimal("1.0")
    snow_severe_in_hr: Decimal = Decimal("2.0")
    snow_no_travel_gt_in_hr: Decimal = Decimal("3.0")

    # Strictly greater (>) payload override thresholds (lb)
    load_severe_wind_no_travel_gt_lb: Decimal = Decimal("30000")
    load_high_wind_severe_gt_lb: Decimal = Decimal("40000")

    def __post_init__(self) -> None:
        if not self.version or not self.version.strip():
            raise ValueError("RiskPolicy.version must be a non-empty string.")
        if not (
            Decimal("0")
            < self.wind_moderate_mph
            < self.wind_high_mph
            < self.wind_severe_mph
            < self.wind_no_travel_mph
        ):
            raise ValueError("Wind thresholds must be strictly increasing positive Decimals.")
        if not (
            Decimal("0")
            < self.rain_moderate_in_hr
            < self.rain_high_in_hr
            < self.rain_severe_in_hr
            <= self.rain_no_travel_gt_in_hr
        ):
            raise ValueError("Rain thresholds must be strictly increasing positive Decimals.")
        if not (
            Decimal("0")
            < self.snow_moderate_in_hr
            < self.snow_high_in_hr
            < self.snow_severe_in_hr
            <= self.snow_no_travel_gt_in_hr
        ):
            raise ValueError("Snow thresholds must be strictly increasing positive Decimals.")
        if not (
            Decimal("0")
            <= self.load_severe_wind_no_travel_gt_lb
            <= self.load_high_wind_severe_gt_lb
        ):
            raise ValueError("Payload override thresholds must be non-negative and ordered.")


DEFAULT_RISK_POLICY = RiskPolicy()
