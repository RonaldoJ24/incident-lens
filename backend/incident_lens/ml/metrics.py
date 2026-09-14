"""Targeted development ranking metrics with no public label output."""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, Mapping, Set


def ranking_metrics(ranked: Iterable[Mapping[str, Any]], positive_sample_ids: Set[str]) -> Dict[str, Any]:
    """Compute aggregate binary event/ranking metrics at target-count k.

    The target IDs are private reviewer inputs and are never returned.  A
    metric is ``not measured`` when no reviewed positive is represented in the
    evaluated rows.
    """

    rows = list(ranked)
    positives = {str(item["sample_id"]) for item in rows if str(item["sample_id"]) in positive_sample_ids}
    if not rows or not positives:
        return {
            "status": "not measured",
            "event_detection": "not measured",
            "false_alarm_rate": "not measured",
            "ranking": {"event_window_mrr": "not measured", "event_window_ndcg_at_5": "not measured"},
        }
    k = len(positives)
    selected = rows[:k]
    selected_ids = {str(item["sample_id"]) for item in selected}
    true_positive = len(selected_ids & positives)
    false_positive = k - true_positive
    negative_count = len(rows) - len(positives)
    false_negative = len(positives) - true_positive
    true_negative = max(0, negative_count - false_positive)
    precision = true_positive / k
    recall = true_positive / len(positives)
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    false_alarm_rate = false_positive / negative_count if negative_count else 0.0
    first_positive_rank = next((index + 1 for index, item in enumerate(rows) if str(item["sample_id"]) in positives), None)
    mrr = 1.0 / first_positive_rank if first_positive_rank else 0.0
    cutoff = min(5, len(rows))
    gains = sum(1.0 / math.log2(index + 2) for index, item in enumerate(rows[:cutoff]) if str(item["sample_id"]) in positives)
    ideal = sum(1.0 / math.log2(index + 2) for index in range(min(len(positives), cutoff)))
    ndcg = gains / ideal if ideal else 0.0
    return {
        "status": "measured",
        "event_detection": {
            "precision_at_k": round(precision, 6),
            "recall_at_k": round(recall, 6),
            "f1_at_k": round(f1, 6),
            "k": k,
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
        },
        "false_alarm_rate": round(false_alarm_rate, 6),
        "ranking": {"event_window_mrr": round(mrr, 6), "event_window_ndcg_at_5": round(ndcg, 6)},
    }


def better_model(model: Mapping[str, Any], baseline: Mapping[str, Any]) -> bool:
    """Return true only for a strict, target-supported ranking improvement."""

    if model.get("status") != "measured" or baseline.get("status") != "measured":
        return False
    model_score = float(model["ranking"]["event_window_ndcg_at_5"])
    baseline_score = float(baseline["ranking"]["event_window_ndcg_at_5"])
    if model_score != baseline_score:
        return model_score > baseline_score
    return float(model["event_detection"]["f1_at_k"]) > float(baseline["event_detection"]["f1_at_k"])


__all__ = ["better_model", "ranking_metrics"]
