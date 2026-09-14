"""Retrieval evaluation kept separate from claim-support evaluation."""

from __future__ import annotations

from typing import Iterable, Mapping

from incident_lens.retrieval import HybridRetriever


def evaluate_retrieval(retriever: HybridRetriever, queries: Iterable[Mapping[str, object]], *, limit: int = 3) -> dict[str, object]:
    rows = list(queries)
    reciprocal_ranks = []
    hits = 0
    for row in rows:
        relevant = set(str(item) for item in row.get("relevant_source_ids", []))
        results = retriever.search(str(row["query"]), limit=limit)
        ranks = [item.rank for item in results if item.document.source_id in relevant]
        if ranks:
            hits += 1
            reciprocal_ranks.append(1.0 / min(ranks))
        else:
            reciprocal_ranks.append(0.0)
    count = len(rows)
    return {
        "status": "evaluated" if count else "not_measured",
        "method": "hybrid-lexical-tfidf-lsa-v1",
        "queries": count,
        "recall_at_k": round(hits / count, 6) if count else None,
        "mrr": round(sum(reciprocal_ranks) / count, 6) if count else None,
        "k": limit,
        "limitations": ["TF-IDF/LSA is a deterministic local semantic fallback; no hosted provider was called."],
    }
