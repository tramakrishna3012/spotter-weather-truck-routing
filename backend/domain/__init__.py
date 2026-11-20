"""Pure Python domain package for Spotter weather-aware truck routing.

This package intentionally contains zero Django, DRF, HTTP, or provider SDK imports.
"""

from domain.recommendation.ranker import (
    RecommendationOutcome,
    RouteRankingInput,
    RouteRiskScore,
    rank_and_recommend,
    score_route,
)
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

__all__ = [
    "ClassificationResult",
    "DEFAULT_RISK_POLICY",
    "POLICY_VERSION",
    "RISK_WEIGHT",
    "RecommendationOutcome",
    "RiskPolicy",
    "RouteRankingInput",
    "RouteRiskScore",
    "SEVERITY_RANK",
    "Severity",
    "WeatherReading",
    "classify_conservative_window",
    "classify_weather",
    "rank_and_recommend",
    "score_route",
]
