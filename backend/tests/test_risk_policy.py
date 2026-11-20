"""Exhaustive unit tests for the Spotter safety-sensitive weather risk policy and unit conversions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from domain.risk.classifier import (
    WeatherReading,
    classify_conservative_window,
    classify_weather,
)
from domain.risk.policy import DEFAULT_RISK_POLICY, POLICY_VERSION, RiskPolicy, Severity
from domain.risk.units import (
    InvalidMeasurementError,
    UnitConversionError,
    convert_rain_to_in_per_hr,
    convert_snow_to_in_per_hr,
    convert_wind_to_mph,
    meters_to_miles,
    miles_to_meters,
)

pytestmark = pytest.mark.unit

_T0 = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


def _reading(
    *,
    wind: Any = Decimal("10"),
    rain: Any = Decimal("0"),
    snow: Any = Decimal("0"),
    valid_at: datetime | None = _T0,
    issued_at: datetime | None = _T0,
    status: str = "known",
) -> WeatherReading:
    return WeatherReading(
        wind_mph=wind,
        rain_in_per_hr=rain,
        snow_in_per_hr=snow,
        valid_at=valid_at,
        issued_at=issued_at,
        status=status,
    )


class TestWindThresholds:
    """Exact half-open wind boundary matrix from docs/06_RISK_AND_RECOMMENDATION.md."""

    @pytest.mark.parametrize(
        ("wind_mph", "expected"),
        [
            (Decimal("0"), Severity.LOW),
            (Decimal("24.999"), Severity.LOW),
            (Decimal("25"), Severity.MODERATE),
            (Decimal("34.999"), Severity.MODERATE),
            (Decimal("35"), Severity.HIGH),
            (Decimal("44.999"), Severity.HIGH),
            (Decimal("45"), Severity.SEVERE),
            (Decimal("54.999"), Severity.SEVERE),
            (Decimal("55"), Severity.NO_TRAVEL),
        ],
    )
    def test_wind_boundary_matrix(self, wind_mph: Decimal, expected: Severity) -> None:
        res = classify_weather(_reading(wind=wind_mph), load_weight_lb=Decimal("20000"))
        assert res.wind_severity == expected
        assert res.severity == expected
        assert res.override_applied is None
        expected_status = "no_travel" if expected == Severity.NO_TRAVEL else "known"
        assert res.status == expected_status


class TestRainThresholds:
    """Exact half-open rain boundary matrix preserving strict >1.00 No Travel."""

    @pytest.mark.parametrize(
        ("rain_in_hr", "expected"),
        [
            (Decimal("0"), Severity.LOW),
            (Decimal("0.0999"), Severity.LOW),
            (Decimal("0.10"), Severity.MODERATE),
            (Decimal("0.2499"), Severity.MODERATE),
            (Decimal("0.25"), Severity.HIGH),
            (Decimal("0.4999"), Severity.HIGH),
            (Decimal("0.50"), Severity.SEVERE),
            (Decimal("1.00"), Severity.SEVERE),
            (Decimal("1.0001"), Severity.NO_TRAVEL),
        ],
    )
    def test_rain_boundary_matrix(self, rain_in_hr: Decimal, expected: Severity) -> None:
        res = classify_weather(_reading(rain=rain_in_hr), load_weight_lb=Decimal("20000"))
        assert res.rain_severity == expected
        assert res.severity == expected
        assert res.status == ("no_travel" if expected == Severity.NO_TRAVEL else "known")


class TestSnowThresholds:
    """Exact half-open snow boundary matrix preserving strict >3.0 No Travel."""

    @pytest.mark.parametrize(
        ("snow_in_hr", "expected"),
        [
            (Decimal("0"), Severity.LOW),
            (Decimal("0.4999"), Severity.LOW),
            (Decimal("0.50"), Severity.MODERATE),
            (Decimal("0.9999"), Severity.MODERATE),
            (Decimal("1.0"), Severity.HIGH),
            (Decimal("1.9999"), Severity.HIGH),
            (Decimal("2.0"), Severity.SEVERE),
            (Decimal("3.0"), Severity.SEVERE),
            (Decimal("3.0001"), Severity.NO_TRAVEL),
        ],
    )
    def test_snow_boundary_matrix(self, snow_in_hr: Decimal, expected: Severity) -> None:
        res = classify_weather(_reading(snow=snow_in_hr), load_weight_lb=Decimal("20000"))
        assert res.snow_severity == expected
        assert res.severity == expected
        assert res.status == ("no_travel" if expected == Severity.NO_TRAVEL else "known")


class TestLoadWindOverrides:
    """Full 4x5 boundary matrix verifying strictly-greater (>) payload wind overrides."""

    @pytest.mark.parametrize(
        ("load_lb", "wind_mph", "expected_severity", "expected_override"),
        [
            # Load == 30000 lb: strict '>' so NO override triggers
            (Decimal("30000"), Decimal("35"), Severity.HIGH, None),
            (Decimal("30000"), Decimal("44.999"), Severity.HIGH, None),
            (Decimal("30000"), Decimal("45"), Severity.SEVERE, None),
            (Decimal("30000"), Decimal("54.999"), Severity.SEVERE, None),
            (Decimal("30000"), Decimal("55"), Severity.NO_TRAVEL, None),
            # Load == 30000.01 lb: overrides [45, 55) wind -> NO_TRAVEL
            (Decimal("30000.01"), Decimal("35"), Severity.HIGH, None),
            (Decimal("30000.01"), Decimal("44.999"), Severity.HIGH, None),
            (
                Decimal("30000.01"),
                Decimal("45"),
                Severity.NO_TRAVEL,
                "wind_45_54_load_over_30000_no_travel",
            ),
            (
                Decimal("30000.01"),
                Decimal("54.999"),
                Severity.NO_TRAVEL,
                "wind_45_54_load_over_30000_no_travel",
            ),
            (Decimal("30000.01"), Decimal("55"), Severity.NO_TRAVEL, None),
            # Load == 40000 lb: still > 30000, NOT > 40000
            (Decimal("40000"), Decimal("35"), Severity.HIGH, None),
            (Decimal("40000"), Decimal("44.999"), Severity.HIGH, None),
            (
                Decimal("40000"),
                Decimal("45"),
                Severity.NO_TRAVEL,
                "wind_45_54_load_over_30000_no_travel",
            ),
            (
                Decimal("40000"),
                Decimal("54.999"),
                Severity.NO_TRAVEL,
                "wind_45_54_load_over_30000_no_travel",
            ),
            (Decimal("40000"), Decimal("55"), Severity.NO_TRAVEL, None),
            # Load == 40000.01 lb: overrides [35, 45) -> SEVERE AND [45, 55) -> NO_TRAVEL
            (
                Decimal("40000.01"),
                Decimal("35"),
                Severity.SEVERE,
                "wind_35_44_load_over_40000_severe",
            ),
            (
                Decimal("40000.01"),
                Decimal("44.999"),
                Severity.SEVERE,
                "wind_35_44_load_over_40000_severe",
            ),
            (
                Decimal("40000.01"),
                Decimal("45"),
                Severity.NO_TRAVEL,
                "wind_45_54_load_over_30000_no_travel",
            ),
            (
                Decimal("40000.01"),
                Decimal("54.999"),
                Severity.NO_TRAVEL,
                "wind_45_54_load_over_30000_no_travel",
            ),
            (Decimal("40000.01"), Decimal("55"), Severity.NO_TRAVEL, None),
        ],
    )
    def test_load_override_matrix(
        self,
        load_lb: Decimal,
        wind_mph: Decimal,
        expected_severity: Severity,
        expected_override: str | None,
    ) -> None:
        res = classify_weather(_reading(wind=wind_mph), load_weight_lb=load_lb)
        assert res.wind_severity == expected_severity
        assert res.severity == expected_severity
        assert res.override_applied == expected_override
        if expected_override is not None:
            assert expected_override in res.reasons

    def test_wind_55_is_no_travel_even_with_zero_load(self) -> None:
        res = classify_weather(_reading(wind=Decimal("55")), load_weight_lb=Decimal("0"))
        assert res.severity == Severity.NO_TRAVEL
        assert res.status == "no_travel"
        assert res.override_applied is None

    def test_combined_severity_takes_max_and_preserves_all_contributing_reasons(self) -> None:
        res = classify_weather(
            _reading(wind=Decimal("36"), rain=Decimal("0.30"), snow=Decimal("2.5")),
            load_weight_lb=Decimal("45000"),
        )
        assert res.wind_severity == Severity.SEVERE
        assert res.rain_severity == Severity.HIGH
        assert res.snow_severity == Severity.SEVERE
        assert res.severity == Severity.SEVERE
        assert "wind_severe" in res.reasons
        assert "wind_35_44_load_over_40000_severe" in res.reasons
        assert "rain_high" in res.reasons
        assert "snow_severe" in res.reasons


class TestFailClosedUnknownHandling:
    """Missing, None, negative, NaN, Inf, or non-known statuses must classify as UNKNOWN."""

    @pytest.mark.parametrize(
        "bad_val",
        [None, Decimal("-0.01"), -5.0, float("nan"), float("inf"), float("-inf"), Decimal("NaN"), Decimal("Infinity")],
    )
    def test_invalid_or_missing_wind_fails_closed(self, bad_val: Any) -> None:
        res = classify_weather(_reading(wind=bad_val), load_weight_lb=Decimal("20000"))
        assert res.severity == Severity.UNKNOWN
        assert res.status == "unknown"
        assert res.wind_severity == Severity.UNKNOWN
        assert res.severity != Severity.LOW

    @pytest.mark.parametrize(
        "bad_val",
        [None, Decimal("-0.001"), float("nan"), float("inf"), float("-inf")],
    )
    def test_invalid_or_missing_rain_fails_closed(self, bad_val: Any) -> None:
        res = classify_weather(_reading(rain=bad_val), load_weight_lb=Decimal("20000"))
        assert res.severity == Severity.UNKNOWN
        assert res.status == "unknown"
        assert res.rain_severity == Severity.UNKNOWN

    @pytest.mark.parametrize(
        "bad_val",
        [None, Decimal("-1"), float("nan"), float("inf"), float("-inf")],
    )
    def test_invalid_or_missing_snow_fails_closed(self, bad_val: Any) -> None:
        res = classify_weather(_reading(snow=bad_val), load_weight_lb=Decimal("20000"))
        assert res.severity == Severity.UNKNOWN
        assert res.status == "unknown"
        assert res.snow_severity == Severity.UNKNOWN

    @pytest.mark.parametrize("bad_load", [-1, float("nan"), float("inf"), float("-inf")])
    def test_invalid_load_weight_fails_closed(self, bad_load: float) -> None:
        res = classify_weather(_reading(), load_weight_lb=bad_load)
        assert res.severity == Severity.UNKNOWN
        assert res.status == "unknown"
        assert "invalid_load_weight" in res.reasons

    @pytest.mark.parametrize("bad_status", ["missing", "out_of_range", "invalid", "corrupt"])
    def test_non_known_reading_status_fails_closed(self, bad_status: str) -> None:
        res = classify_weather(_reading(status=bad_status), load_weight_lb=Decimal("20000"))
        assert res.severity == Severity.UNKNOWN
        assert res.status == "unknown"


class TestUnitConversions:
    """Exact Decimal unit conversions and strict unit/value validation."""

    def test_wind_conversions(self) -> None:
        assert convert_wind_to_mph(Decimal("16.09344"), "km/h") == Decimal("10")
        assert convert_wind_to_mph(Decimal("88.51392"), "km/h") == Decimal("55")
        assert convert_wind_to_mph(Decimal("25"), "mph") == Decimal("25")
        mps_result = convert_wind_to_mph(Decimal("10"), "m/s")
        assert mps_result is not None
        assert float(mps_result) == pytest.approx(22.369362920544, rel=1e-9)
        knots_result = convert_wind_to_mph(Decimal("10"), "kn")
        assert knots_result is not None
        assert float(knots_result) == pytest.approx(11.507794480235, rel=1e-9)

    def test_rain_and_snow_conversions(self) -> None:
        assert convert_rain_to_in_per_hr(Decimal("25.4"), "mm") == Decimal("1")
        assert convert_rain_to_in_per_hr(Decimal("2.54"), "mm/hr") == Decimal("0.1")
        assert convert_snow_to_in_per_hr(Decimal("2.54"), "cm") == Decimal("1")
        assert convert_snow_to_in_per_hr(Decimal("7.62"), "cm/hr") == Decimal("3")
        assert convert_snow_to_in_per_hr(Decimal("25.4"), "mm") == Decimal("1")

    def test_none_preserved_while_validating_unit(self) -> None:
        assert convert_wind_to_mph(None, "km/h") is None
        assert convert_rain_to_in_per_hr(None, "mm") is None
        assert convert_snow_to_in_per_hr(None, "cm") is None

    @pytest.mark.parametrize("bad_unit", ["", "   ", "furlongs/fortnight", "feet/sec", "kelvin"])
    def test_unrecognized_unit_raises_unit_conversion_error(self, bad_unit: str) -> None:
        with pytest.raises(UnitConversionError):
            convert_wind_to_mph(10, bad_unit)
        with pytest.raises(UnitConversionError):
            convert_rain_to_in_per_hr(1, bad_unit)
        with pytest.raises(UnitConversionError):
            convert_snow_to_in_per_hr(1, bad_unit)

    def test_negative_and_nonfinite_raise_invalid_measurement_error(self) -> None:
        for bad in (-0.1, float("nan"), float("inf"), True):
            with pytest.raises(InvalidMeasurementError):
                convert_wind_to_mph(bad, "km/h")

    def test_distance_conversion_roundtrip(self) -> None:
        assert miles_to_meters(1) == pytest.approx(1609.344, abs=1e-9)
        assert meters_to_miles(1609.344) == pytest.approx(1.0, abs=1e-9)


class TestConservativeWindowAndPolicy:
    """Conservative hourly bracketing and policy specification checks."""

    def test_worst_adjacent_hourly_bin_wins(self) -> None:
        calm = _reading(wind=Decimal("10"), rain=Decimal("0"), snow=Decimal("0"), valid_at=_T0)
        storm = _reading(
            wind=Decimal("46"),
            rain=Decimal("0.30"),
            snow=Decimal("0"),
            valid_at=_T0 + timedelta(hours=1),
        )
        res = classify_conservative_window((calm, storm), load_weight_lb=Decimal("35000"))
        assert res.severity == Severity.NO_TRAVEL
        assert res.status == "no_travel"
        assert res.wind_severity == Severity.NO_TRAVEL
        assert res.rain_severity == Severity.HIGH
        assert res.override_applied == "wind_45_54_load_over_30000_no_travel"
        assert "all_conditions_low" not in res.reasons

    def test_any_missing_or_invalid_bin_forces_unknown(self) -> None:
        known_calm = _reading(wind=Decimal("10"), valid_at=_T0)
        missing_next = _reading(
            wind=None,
            rain=Decimal("0"),
            snow=Decimal("0"),
            valid_at=_T0 + timedelta(hours=1),
        )
        res = classify_conservative_window((known_calm, missing_next), load_weight_lb=Decimal("20000"))
        assert res.severity == Severity.UNKNOWN
        assert res.status == "unknown"

        known_severe = _reading(wind=Decimal("50"), valid_at=_T0)
        invalid_next = _reading(wind=Decimal("-3"), valid_at=_T0 + timedelta(hours=1))
        res2 = classify_conservative_window((known_severe, invalid_next), load_weight_lb=Decimal("20000"))
        assert res2.severity == Severity.UNKNOWN
        assert res2.status == "unknown"

    def test_empty_window_forces_unknown(self) -> None:
        res = classify_conservative_window((), load_weight_lb=Decimal("20000"))
        assert res.severity == Severity.UNKNOWN
        assert "missing_weather_window" in res.reasons

    def test_default_policy_version_and_validation(self) -> None:
        assert DEFAULT_RISK_POLICY.version == POLICY_VERSION == "risk-policy-v1"
        with pytest.raises(ValueError):
            RiskPolicy(wind_moderate_mph=Decimal("40"), wind_high_mph=Decimal("35"))
