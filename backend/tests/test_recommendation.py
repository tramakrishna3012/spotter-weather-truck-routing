"""Unit tests for distance-weighted route risk scoring and lexicographic recommendation ranking."""

from __future__ import annotations

import pytest

from domain.recommendation.ranker import (
    RouteRankingInput,
    RouteRiskScore,
    rank_and_recommend,
    score_route,
)
from domain.risk.classifier import ClassificationResult
from domain.risk.policy import Severity
from domain.risk.units import miles_to_meters
from domain.routing.sampling import sample_route_points, select_display_checkpoint_indices
from domain.routing.segments import RiskSegment, build_voronoi_risk_segments

pytestmark = pytest.mark.unit


def _segment(from_mi: float, to_mi: float, severity: Severity) -> RiskSegment:
    status = (
        "no_travel"
        if severity == Severity.NO_TRAVEL
        else ("unknown" if severity == Severity.UNKNOWN else "known")
    )
    return RiskSegment(
        from_distance_m=miles_to_meters(from_mi),
        to_distance_m=miles_to_meters(to_mi),
        severity=severity,
        status=status,
        reason_codes=(f"sev_{severity.value}",),
        coordinates=[[-105.0, 39.7], [-105.5, 39.8]],
    )


def _candidate(
    route_id: str,
    *,
    duration_seconds: float = 3600.0,
    distance_mi: float = 100.0,
    severe_miles: float = 0.0,
    high_miles: float = 0.0,
    moderate_miles: float = 0.0,
    low_miles: float = 100.0,
    no_travel_miles: float = 0.0,
    unknown_miles: float = 0.0,
    weighted_average_risk: float | None = 0.0,
    eligible: bool = True,
    coverage_fraction: float = 1.0,
) -> RouteRankingInput:
    reasons: list[str] = []
    if no_travel_miles > 0.0:
        reasons.append("contains_no_travel_segment")
    if unknown_miles > 0.0 or coverage_fraction < 1.0:
        reasons.append("incomplete_weather_coverage")
    return RouteRankingInput(
        route_id=route_id,
        duration_seconds=duration_seconds,
        distance_m=miles_to_meters(distance_mi),
        risk=RouteRiskScore(
            severe_miles=severe_miles,
            high_miles=high_miles,
            moderate_miles=moderate_miles,
            low_miles=low_miles,
            no_travel_miles=no_travel_miles,
            unknown_miles=unknown_miles,
            weighted_average_risk=weighted_average_risk,
            eligible=eligible,
            coverage_fraction=coverage_fraction,
            ineligibility_reasons=tuple(reasons),
        ),
    )


class TestLexicographicRanking:
    """Strict lexicographic ranking order: Severe -> High -> weighted_avg -> duration -> route_id."""

    def test_severe_miles_dominates_all_other_metrics(self) -> None:
        r_less_severe = _candidate(
            "route-b",
            severe_miles=5.0,
            high_miles=50.0,
            weighted_average_risk=2.2,
            duration_seconds=9000.0,
        )
        r_more_severe = _candidate(
            "route-a",
            severe_miles=5.1,
            high_miles=0.0,
            weighted_average_risk=0.2,
            duration_seconds=3000.0,
        )
        outcome = rank_and_recommend([r_more_severe, r_less_severe])
        assert outcome.recommendation_status == "recommended"
        assert outcome.recommended_route_id == "route-b"
        assert outcome.ordered_route_ids == ("route-b", "route-a")

    def test_high_miles_breaks_severe_tie(self) -> None:
        r_less_high = _candidate(
            "route-b",
            severe_miles=2.0,
            high_miles=10.0,
            weighted_average_risk=1.8,
            duration_seconds=7200.0,
        )
        r_more_high = _candidate(
            "route-a",
            severe_miles=2.0,
            high_miles=10.5,
            weighted_average_risk=0.5,
            duration_seconds=3600.0,
        )
        outcome = rank_and_recommend([r_more_high, r_less_high])
        assert outcome.recommended_route_id == "route-b"
        assert outcome.ordered_route_ids == ("route-b", "route-a")

    def test_weighted_average_risk_breaks_severe_and_high_tie(self) -> None:
        r_lower_avg = _candidate(
            "route-c",
            severe_miles=0.0,
            high_miles=10.0,
            weighted_average_risk=0.45,
            duration_seconds=8000.0,
        )
        r_higher_avg = _candidate(
            "route-a",
            severe_miles=0.0,
            high_miles=10.0,
            weighted_average_risk=0.55,
            duration_seconds=3600.0,
        )
        outcome = rank_and_recommend([r_higher_avg, r_lower_avg])
        assert outcome.recommended_route_id == "route-c"
        assert outcome.ordered_route_ids == ("route-c", "route-a")

    def test_duration_breaks_risk_ties(self) -> None:
        r_faster = _candidate(
            "route-b",
            severe_miles=0.0,
            high_miles=5.0,
            weighted_average_risk=0.3,
            duration_seconds=3599.0,
        )
        r_slower = _candidate(
            "route-a",
            severe_miles=0.0,
            high_miles=5.0,
            weighted_average_risk=0.3,
            duration_seconds=3600.0,
        )
        outcome = rank_and_recommend([r_slower, r_faster])
        assert outcome.recommended_route_id == "route-b"
        assert outcome.ordered_route_ids == ("route-b", "route-a")

    def test_deterministic_route_id_breaks_complete_tie(self) -> None:
        r_b = _candidate("route-b", severe_miles=0.0, high_miles=0.0, weighted_average_risk=0.0, duration_seconds=3600.0)
        r_a = _candidate("route-a", severe_miles=0.0, high_miles=0.0, weighted_average_risk=0.0, duration_seconds=3600.0)
        r_c = _candidate("route-c", severe_miles=0.0, high_miles=0.0, weighted_average_risk=0.0, duration_seconds=3600.0)
        outcome = rank_and_recommend([r_c, r_b, r_a])
        assert outcome.recommended_route_id == "route-a"
        assert outcome.ordered_route_ids == ("route-a", "route-b", "route-c")


class TestEligibilityGatesAndTerminalStates:
    """Safety fail-closed eligibility gates for No-Travel and Unknown coverage."""

    def test_shortest_route_with_no_travel_excluded_and_safer_longer_recommended(self) -> None:
        short_blocked_score = score_route(
            [_segment(0, 49, Severity.LOW), _segment(49, 50, Severity.NO_TRAVEL)],
            total_distance_m=miles_to_meters(50),
        )
        assert short_blocked_score.eligible is False
        assert short_blocked_score.no_travel_miles == pytest.approx(1.0, abs=1e-6)
        assert "contains_no_travel_segment" in short_blocked_score.ineligibility_reasons

        longer_safe_score = score_route(
            [_segment(0, 60, Severity.MODERATE), _segment(60, 80, Severity.HIGH)],
            total_distance_m=miles_to_meters(80),
        )
        assert longer_safe_score.eligible is True
        # Distance-weighted avg = (60*1 + 20*2) / 80 = 1.25
        assert longer_safe_score.weighted_average_risk == pytest.approx(1.25, abs=1e-6)

        outcome = rank_and_recommend(
            [
                RouteRankingInput("route-short", 2700.0, miles_to_meters(50), short_blocked_score),
                RouteRankingInput("route-long", 5400.0, miles_to_meters(80), longer_safe_score),
            ]
        )
        assert outcome.recommendation_status == "recommended"
        assert outcome.recommended_route_id == "route-long"
        assert outcome.ordered_route_ids == ("route-long", "route-short")

    def test_route_with_any_unknown_miles_excluded_fail_closed(self) -> None:
        partial_score = score_route(
            [_segment(0, 99.5, Severity.LOW), _segment(99.5, 100.0, Severity.UNKNOWN)],
            total_distance_m=miles_to_meters(100),
        )
        assert partial_score.eligible is False
        assert partial_score.unknown_miles == pytest.approx(0.5, abs=1e-6)
        assert partial_score.coverage_fraction == pytest.approx(0.995, abs=1e-6)
        assert "incomplete_weather_coverage" in partial_score.ineligibility_reasons

        # Uncovered distance gap is also counted as UNKNOWN fail-closed
        gap_score = score_route(
            [_segment(0, 80, Severity.LOW)],
            total_distance_m=miles_to_meters(100),
        )
        assert gap_score.eligible is False
        assert gap_score.unknown_miles == pytest.approx(20.0, abs=1e-6)
        assert gap_score.coverage_fraction == pytest.approx(0.8, abs=1e-6)

    def test_all_routes_no_travel_returns_no_eligible_route(self) -> None:
        s1 = score_route([_segment(0, 50, Severity.NO_TRAVEL)], miles_to_meters(50))
        s2 = score_route(
            [_segment(0, 40, Severity.LOW), _segment(40, 50, Severity.NO_TRAVEL)],
            miles_to_meters(50),
        )
        outcome = rank_and_recommend(
            [
                RouteRankingInput("route-a", 3000.0, miles_to_meters(50), s1),
                RouteRankingInput("route-b", 3200.0, miles_to_meters(50), s2),
            ]
        )
        assert outcome.recommendation_status == "no_eligible_route"
        assert outcome.recommended_route_id is None
        assert outcome.ordered_route_ids == ("route-b", "route-a")

    def test_all_routes_incomplete_weather_returns_insufficient_weather_data(self) -> None:
        s1 = score_route(
            [_segment(0, 40, Severity.LOW), _segment(40, 50, Severity.UNKNOWN)],
            miles_to_meters(50),
        )
        s2 = score_route([_segment(0, 50, Severity.UNKNOWN)], miles_to_meters(50))
        outcome = rank_and_recommend(
            [
                RouteRankingInput("route-a", 3000.0, miles_to_meters(50), s1),
                RouteRankingInput("route-b", 3100.0, miles_to_meters(50), s2),
            ]
        )
        assert outcome.recommendation_status == "insufficient_weather_data"
        assert outcome.recommended_route_id is None
        assert outcome.ordered_route_ids == ("route-a", "route-b")

    def test_zero_routes_returns_no_routes(self) -> None:
        outcome = rank_and_recommend([])
        assert outcome.recommendation_status == "no_routes"
        assert outcome.recommended_route_id is None
        assert outcome.ordered_route_ids == ()


class TestDisplaySpacingInvariance:
    """Changing display spacing (10/25/50 mi) never alters internal scoring or recommendation."""

    def test_ranking_invariant_across_10_25_50_display_spacing(self) -> None:
        coords_a = [(40.0 + i * 0.05, -105.0 - i * 0.1) for i in range(25)]
        coords_b = [(40.0 + i * 0.04, -105.0 - i * 0.11) for i in range(25)]
        total_m = miles_to_meters(120.0)

        pts_a = sample_route_points(coords_a, spacing_miles=10.0, total_distance_m=total_m)
        pts_b = sample_route_points(coords_b, spacing_miles=10.0, total_distance_m=total_m)

        # Hidden 10-mile severe storm pocket at checkpoint index 3 (30 mi) on route A
        # that a 50-mile display spacing does NOT display as a marker!
        def _cls(sev: Severity) -> ClassificationResult:
            return ClassificationResult(
                severity=sev,
                status="known",
                reasons=(sev.value,),
                wind_severity=sev,
                rain_severity=Severity.LOW,
                snow_severity=Severity.LOW,
            )

        cls_a = [_cls(Severity.SEVERE if i == 3 else Severity.LOW) for i in range(len(pts_a))]
        cls_b = [_cls(Severity.MODERATE if i in (2, 4) else Severity.LOW) for i in range(len(pts_b))]

        results_by_display: dict[int, tuple[str | None, float, float, int]] = {}
        for display_mi in (10, 25, 50):
            display_indices_a = select_display_checkpoint_indices(pts_a, display_mi, total_m)
            # Scoring always uses full internal points, independent of display_indices
            seg_a = build_voronoi_risk_segments(coords_a, pts_a, cls_a, total_m)
            seg_b = build_voronoi_risk_segments(coords_b, pts_b, cls_b, total_m)
            score_a = score_route(seg_a, total_m)
            score_b = score_route(seg_b, total_m)
            outcome = rank_and_recommend(
                [
                    RouteRankingInput("route-a", 7200.0, total_m, score_a),
                    RouteRankingInput("route-b", 7600.0, total_m, score_b),
                ]
            )
            results_by_display[display_mi] = (
                outcome.recommended_route_id,
                score_a.severe_miles,
                score_b.weighted_average_risk or 0.0,
                len(display_indices_a),
            )

        # Route B wins under all display spacings; severe_miles on route A never hidden
        for display_mi in (10, 25, 50):
            rec_id, sev_a, avg_b, _ = results_by_display[display_mi]
            assert rec_id == "route-b"
            assert sev_a == pytest.approx(10.0, abs=1e-6)
            assert avg_b == results_by_display[10][2]

        # Display counts strictly decrease as spacing coarsens
        assert results_by_display[10][3] > results_by_display[25][3] > results_by_display[50][3]
