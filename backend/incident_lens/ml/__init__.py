"""Leakage-safe, deterministic unusual-service/window ranking.

The package deliberately calls outputs *rankings*.  A score is an ordering
signal for an unusual service/window and is never a causal or root-cause
probability.
"""

from .ranking import (
    ARTIFACT_VERSION,
    ERROR_RATE_THRESHOLD,
    FEATURE_SCHEMA_VERSION,
    FEATURE_NAMES,
    LATENCY_THRESHOLD_MS,
    RANKING_SEMANTICS,
    RankingInputError,
    rank_rows,
    rule_scores,
)

__all__ = [
    "ARTIFACT_VERSION",
    "ERROR_RATE_THRESHOLD",
    "FEATURE_SCHEMA_VERSION",
    "FEATURE_NAMES",
    "LATENCY_THRESHOLD_MS",
    "RANKING_SEMANTICS",
    "RankingInputError",
    "rank_rows",
    "rule_scores",
]
