"""Distance-weighted route risk scoring and lexicographic route recommendation.

Implements docs/06_RISK_AND_RECOMMENDATION.md:
- Any No-Travel segment or incomplete/unknown weather coverage makes a route ineligible.
- Never recommends an ineligible route.
- Eligible routes are ranked lexicographically by:
  (severe_miles, high_miles, weighted_average_risk, duration_seconds, route_id).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from domain.risk.policy import RISK_WEIGHT, Severity
from domain.risk.units import METERS_PER_MILE
from domain.routing.segments import RiskSegment


@dataclass(frozen=True)
class RouteRiskScore:
    """Distance-weighted mileage breakdown and eligibility summary for a route."""

    severe_miles: float
    high_miles: float
    moderate_miles: float
    low_miles: float
    no_travel_miles: float
    unknown_miles: float
    weighted_average_risk: float | None
    eligible: bool
    coverage_fraction: float
    ineligibility_reasons: tuple[str, ...]


@dataclass(frozen=True)
class RouteRankingInput:
    """Inputs required to rank candidate routes deterministically."""

    route_id: str
    duration_seconds: float
    distance_m: float
    risk: RouteRiskScore


@dataclass(frozen=True)
class RecommendationOutcome:
    """Explainable recommendation decision and deterministic route ordering."""

    recommendation_status: str
    recommended_route_id: str | None
    recommendation_reason: str
    ordered_route_ids: tuple[str, ...]


def score_route(segments: Sequence[RiskSegment], total_distance_m: float) -> RouteRiskScore:
    """Compute distance-weighted risk mileage, coverage, and eligibility from Voronoi segments."""
    if not math.isfinite(total_distance_m) or total_distance_m <= 0.0:
        raise ValueError(
            f"total_distance_m must be finite and positive, got {total_distance_m!r}."
        )

    total_m = Decimal(str(total_distance_m))
    meters_by_sev: dict[Severity, Decimal] = {sev: Decimal("0") for sev in Severity}
    accounted_m = Decimal("0")

    for seg in segments:
        seg_len_f = seg.to_distance_m - seg.from_distance_m
        if not math.isfinite(seg_len_f) or seg_len_f < 0.0:
            raise ValueError(
                f"Invalid segment distance bounds: [{seg.from_distance_m}, {seg.to_distance_m}]."
            )
        seg_m = Decimal(str(seg_len_f))
        meters_by_sev[seg.severity] += seg_m
        accounted_m += seg_m

    # Fail closed if segments do not cover the full route distance.
    uncovered_gap_m = total_m - accounted_m
    if uncovered_gap_m > Decimal("1e-3"):
        meters_by_sev[Severity.UNKNOWN] += uncovered_gap_m

    denom_m = max(total_m, accounted_m)
    unknown_m = meters_by_sev[Severity.UNKNOWN]
    no_travel_m = meters_by_sev[Severity.NO_TRAVEL]
    known_m = max(Decimal("0"), denom_m - unknown_m)
    coverage_fraction = max(0.0, min(1.0, float(known_m / denom_m)))

    severe_m = meters_by_sev[Severity.SEVERE]
    high_m = meters_by_sev[Severity.HIGH]
    moderate_m = meters_by_sev[Severity.MODERATE]
    low_m = meters_by_sev[Severity.LOW]

    scored_m = low_m + moderate_m + high_m + severe_m
    weighted_average_risk: float | None
    if scored_m > Decimal("0"):
        weighted_sum = (
            low_m * Decimal(RISK_WEIGHT[Severity.LOW])
            + moderate_m * Decimal(RISK_WEIGHT[Severity.MODERATE])
            + high_m * Decimal(RISK_WEIGHT[Severity.HIGH])
            + severe_m * Decimal(RISK_WEIGHT[Severity.SEVERE])
        )
        weighted_average_risk = float(weighted_sum / scored_m)
    else:
        weighted_average_risk = None

    severe_miles = float(severe_m / METERS_PER_MILE)
    high_miles = float(high_m / METERS_PER_MILE)
    moderate_miles = float(moderate_m / METERS_PER_MILE)
    low_miles = float(low_m / METERS_PER_MILE)
    no_travel_miles = float(no_travel_m / METERS_PER_MILE)
    unknown_miles = float(unknown_m / METERS_PER_MILE)

    ineligibility_reasons: list[str] = []
    if not segments:
        ineligibility_reasons.append("no_risk_segments")
    if no_travel_m > Decimal("0"):
        ineligibility_reasons.append("contains_no_travel_segment")
    if unknown_m > Decimal("0") or coverage_fraction < 1.0:
        ineligibility_reasons.append("incomplete_weather_coverage")

    eligible = (
        len(ineligibility_reasons) == 0
        and no_travel_m == Decimal("0")
        and unknown_m == Decimal("0")
        and coverage_fraction >= 1.0
        and total_m > Decimal("0")
    )

    return RouteRiskScore(
        severe_miles=severe_miles,
        high_miles=high_miles,
        moderate_miles=moderate_miles,
        low_miles=low_miles,
        no_travel_miles=no_travel_miles,
        unknown_miles=unknown_miles,
        weighted_average_risk=weighted_average_risk,
        eligible=eligible,
        coverage_fraction=coverage_fraction,
        ineligibility_reasons=tuple(ineligibility_reasons),
    )


def _eligible_sort_key(item: RouteRankingInput) -> tuple[float, float, float, float, str]:
    avg_risk = item.risk.weighted_average_risk if item.risk.weighted_average_risk is not None else 0.0
    return (
        round(item.risk.severe_miles, 6),
        round(item.risk.high_miles, 6),
        round(avg_risk, 6),
        round(item.duration_seconds, 3),
        item.route_id,
    )


def _ineligible_sort_key(
    item: RouteRankingInput,
) -> tuple[float, float, float, float, float, str]:
    return (
        round(item.risk.no_travel_miles, 6),
        round(item.risk.unknown_miles, 6),
        round(item.risk.severe_miles, 6),
        round(item.risk.high_miles, 6),
        round(item.duration_seconds, 3),
        item.route_id,
    )


def _explain_recommendation(
    best: RouteRankingInput,
    runner_up: RouteRankingInput | None,
    has_ineligible: bool,
) -> str:
    if runner_up is None:
        if has_ineligible:
            return "Only eligible route with complete forecast coverage and no No-Travel segments"
        return "Only eligible route with complete forecast coverage"

    if round(best.risk.severe_miles, 6) < round(runner_up.risk.severe_miles, 6):
        return "Lowest Severe miles among covered eligible routes"
    if round(best.risk.high_miles, 6) < round(runner_up.risk.high_miles, 6):
        return "Lowest High miles among tied Severe-mile routes"
    best_avg = round(best.risk.weighted_average_risk or 0.0, 6)
    runner_avg = round(runner_up.risk.weighted_average_risk or 0.0, 6)
    if best_avg < runner_avg:
        return "Lowest weighted average risk among eligible routes"
    if round(best.duration_seconds, 3) < round(runner_up.duration_seconds, 3):
        return "Shortest travel time among tied lowest-risk routes"
    return "Selected deterministically among identically scored eligible routes"


def rank_and_recommend(candidates: Sequence[RouteRankingInput]) -> RecommendationOutcome:
    """Order candidate routes and select the safest eligible recommendation.

    Never recommends an ineligible route. Returns explicit `no_routes`,
    `insufficient_weather_data`, or `no_eligible_route` statuses when no route qualifies.
    """
    if not candidates:
        return RecommendationOutcome(
            recommendation_status="no_routes",
            recommended_route_id=None,
            recommendation_reason="No valid truck routes were returned for this trip.",
            ordered_route_ids=(),
        )

    eligible = sorted((c for c in candidates if c.risk.eligible), key=_eligible_sort_key)
    ineligible = sorted((c for c in candidates if not c.risk.eligible), key=_ineligible_sort_key)

    ordered_ids = tuple(c.route_id for c in eligible) + tuple(c.route_id for c in ineligible)

    if eligible:
        best = eligible[0]
        runner_up = eligible[1] if len(eligible) > 1 else None
        reason = _explain_recommendation(best, runner_up, has_ineligible=bool(ineligible))
        return RecommendationOutcome(
            recommendation_status="recommended",
            recommended_route_id=best.route_id,
            recommendation_reason=reason,
            ordered_route_ids=ordered_ids,
        )

    has_unknown = any(c.risk.unknown_miles > 0.0 for c in ineligible)
    has_no_travel = any(c.risk.no_travel_miles > 0.0 for c in ineligible)

    if has_unknown and not has_no_travel:
        return RecommendationOutcome(
            recommendation_status="insufficient_weather_data",
            recommended_route_id=None,
            recommendation_reason=(
                "Weather forecast coverage is incomplete for all candidate routes; "
                "no route can be recommended safely."
            ),
            ordered_route_ids=ordered_ids,
        )

    if has_no_travel and not has_unknown:
        return RecommendationOutcome(
            recommendation_status="no_eligible_route",
            recommended_route_id=None,
            recommendation_reason=(
                "All candidate routes contain No-Travel weather hazard segments."
            ),
            ordered_route_ids=ordered_ids,
        )

    return RecommendationOutcome(
        recommendation_status="no_eligible_route",
        recommended_route_id=None,
        recommendation_reason=(
            "No candidate route is eligible due to No-Travel hazards or incomplete weather coverage."
        ),
        ordered_route_ids=ordered_ids,
    )
