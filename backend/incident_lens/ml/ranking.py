"""Feature schema and deterministic rule/model ranking primitives."""

from __future__ import annotations

import math
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


ARTIFACT_VERSION = "incident-lens-ranking-v1"
FEATURE_SCHEMA_VERSION = "incident-lens-features-v1"
RANKING_SEMANTICS = "unusual service/window ranking; not a root-cause probability"
ERROR_RATE_THRESHOLD = 0.05
LATENCY_THRESHOLD_MS = 500.0

# Keep this list ordered.  It is part of the serialized feature contract.
FEATURE_NAMES = (
    "error_rate",
    "latency_ms",
    "latency_p95_ms",
    "error_count",
    "request_count",
    "event_count",
    "log_count",
    "metric_count",
    "trace_count",
    "missing_logs",
    "missing_metrics",
    "missing_traces",
    "conflict_count",
)
_NUMERIC = set(FEATURE_NAMES)
_NEUTRAL_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_BAD_TEXT = re.compile(
    r"(?:root.?cause|ground.?truth|hidden.?label|fault.?type|inject(?:ion)?_?time|"
    r"source.?filename|file.?name|answer|solution|re[123](?:ob|ss|tt)_[a-z0-9_-]+)",
    re.IGNORECASE,
)


class RankingInputError(ValueError):
    """Raised when an input could cross the public ranking boundary."""


def _assert_safe_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise RankingInputError("%s must be a short non-empty identifier" % field)
    if not _NEUTRAL_ID.fullmatch(value) or _BAD_TEXT.search(value):
        raise RankingInputError("%s must be a neutral identifier" % field)
    return value


def _number(value: Any, field: str, *, minimum: float = 0.0, maximum: Optional[float] = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RankingInputError("%s must be numeric" % field)
    number = float(value)
    if not math.isfinite(number) or number < minimum or (maximum is not None and number > maximum):
        raise RankingInputError("%s is outside its allowed range" % field)
    return number


def validate_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate and return one neutral feature row.

    Rows intentionally have no target/answer field.  Evaluation labels, when
    they eventually exist, must be supplied through a private review process
    and must never be serialized into a public training or validation manifest.
    """

    if not isinstance(row, Mapping):
        raise RankingInputError("ranking row must be an object")
    required = ("sample_id", "run_group", "service_id", "window_id", "features")
    missing = [key for key in required if key not in row]
    if missing:
        raise RankingInputError("ranking row is missing %s" % ", ".join(missing))
    unknown_fields = set(row) - set(required) - {"case_id"}
    if unknown_fields:
        raise RankingInputError("unsupported ranking field(s): %s" % ", ".join(sorted(map(str, unknown_fields))))
    output = {
        key: _assert_safe_text(row[key], key)
        for key in ("sample_id", "run_group", "service_id", "window_id")
    }
    features = row["features"]
    if not isinstance(features, Mapping):
        raise RankingInputError("features must be an object")
    unknown = set(features) - _NUMERIC
    if unknown:
        raise RankingInputError("unknown feature(s): %s" % ", ".join(sorted(map(str, unknown))))
    clean: Dict[str, Optional[float]] = {}
    for name in FEATURE_NAMES:
        value = features.get(name)
        if value is None:
            clean[name] = None
            continue
        maximum = 1.0 if name == "error_rate" else None
        clean[name] = _number(value, "features.%s" % name, maximum=maximum)
    output["features"] = clean
    if "case_id" in row:
        case_id = _assert_safe_text(row["case_id"], "case_id")
        if not re.fullmatch(r"dev-re2ob-\d{3}", case_id):
            raise RankingInputError("case_id must be neutral")
        output["case_id"] = case_id
    return output


def feature_vector(row: Mapping[str, Any]) -> List[float]:
    """Return a deterministic numeric vector with explicit missingness flags."""

    checked = validate_row(row)
    vector: List[float] = []
    for name in FEATURE_NAMES:
        value = checked["features"][name]
        vector.append(0.0 if value is None else float(value))
        vector.append(1.0 if value is None else 0.0)
    return vector


def _bounded(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def rule_scores(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Compute explicit error-rate and latency baseline scores.

    Thresholds are intentionally simple and versioned.  Missing inputs are not
    imputed as healthy: they produce a zero score plus an explicit limitation.
    """

    checked = validate_row(row)
    features = checked["features"]
    reasons: List[str] = []
    candidates: List[float] = []
    error_rate_score = 0.0
    latency_score = 0.0
    error_rate = features["error_rate"]
    latency = features["latency_ms"]
    latency_p95 = features["latency_p95_ms"]
    if error_rate is not None:
        error_rate_score = _bounded(error_rate / ERROR_RATE_THRESHOLD)
        candidates.append(error_rate_score)
        if error_rate > ERROR_RATE_THRESHOLD:
            reasons.append("error-rate-rule")
    else:
        reasons.append("missing-error-rate")
    latency_value = latency_p95 if latency_p95 is not None else latency
    if latency_value is not None:
        latency_score = _bounded(latency_value / LATENCY_THRESHOLD_MS)
        candidates.append(latency_score)
        if latency_value > LATENCY_THRESHOLD_MS:
            reasons.append("latency-rule")
    else:
        reasons.append("missing-latency")
    missing = [
        name
        for name in ("logs", "metrics", "traces")
        if features["missing_" + name] is not None and features["missing_" + name] >= 1.0
    ]
    if missing:
        reasons.append("missing-signals:" + ",".join(missing))
    if features["conflict_count"] is not None and features["conflict_count"] > 0:
        reasons.append("conflicting-signals")
    score = max(candidates) if candidates else 0.0
    return {
        "score": round(_bounded(score), 12),
        "error_rate_score": round(error_rate_score, 12),
        "latency_score": round(latency_score, 12),
        "method": "error-rate-latency-rules-v1",
        "reasons": reasons,
        "ranking_semantics": RANKING_SEMANTICS,
    }


def rank_rows(rows: Iterable[Mapping[str, Any]], model: Any = None) -> List[Dict[str, Any]]:
    """Rank rows with an optional fitted model, returning safe public fields."""

    checked = [validate_row(row) for row in rows]
    model_scores: Optional[Sequence[float]] = None
    if model is not None:
        try:
            model_scores = list(model.score_samples([feature_vector(row) for row in checked]))
        except Exception as exc:  # pragma: no cover - protects serving boundary
            raise RankingInputError("ranking model could not score rows") from exc
    ranked: List[Dict[str, Any]] = []
    for index, row in enumerate(checked):
        baseline = rule_scores(row)
        if model_scores is None:
            score = float(baseline["score"])
            method = baseline["method"]
        else:
            # IsolationForest score_samples is higher for normal points.  Flip
            # and squash to make larger values mean more unusual.
            score = _bounded(0.5 - float(model_scores[index]))
            method = ARTIFACT_VERSION
        missing_signals = [
            name
            for name in ("logs", "metrics", "traces")
            if row["features"]["missing_" + name] is not None
            and row["features"]["missing_" + name] >= 1.0
        ]
        ranked.append(
            {
                "sample_id": row["sample_id"],
                "service_id": row["service_id"],
                "window_id": row["window_id"],
                "unusual_score": round(score, 12),
                "method": method,
                "ranking_semantics": RANKING_SEMANTICS,
                "missing_signals": missing_signals,
                "feature_schema_version": FEATURE_SCHEMA_VERSION,
            }
        )
    ranked.sort(key=lambda item: (-item["unusual_score"], item["service_id"], item["window_id"], item["sample_id"]))
    return ranked


__all__ = [
    "ARTIFACT_VERSION",
    "FEATURE_NAMES",
    "FEATURE_SCHEMA_VERSION",
    "ERROR_RATE_THRESHOLD",
    "LATENCY_THRESHOLD_MS",
    "RANKING_SEMANTICS",
    "RankingInputError",
    "feature_vector",
    "rank_rows",
    "rule_scores",
    "validate_row",
]
