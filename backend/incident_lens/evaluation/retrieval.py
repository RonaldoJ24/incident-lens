"""Retrieval evaluation kept separate from claim-support evaluation."""

from __future__ import annotations

from typing import Iterable, Mapping

from incident_lens.retrieval import HybridRetriever


def evaluate_retrieval(retriever: HybridRetriever, queries: Iterable[Mapping[str, object]], *, limit: int = 3) -> dict[str, object]:
    rows = list(queries)
    reciprocal_ranks = []
    hits_at_k = 0
    hits_at_1 = 0
    details = []
    for row in rows:
        relevant = set(str(item) for item in row.get("relevant_source_ids", []))
        results = retriever.search(str(row["query"]), limit=limit)
        ranks = [item.rank for item in results if item.document.source_id in relevant]
        if ranks:
            hits_at_k += 1
            reciprocal_ranks.append(1.0 / min(ranks))
        else:
            reciprocal_ranks.append(0.0)
        top_source_id = results[0].document.source_id if results else None
        if top_source_id in relevant:
            hits_at_1 += 1
        details.append(
            {
                "query": str(row["query"]),
                "relevant_source_ids": sorted(relevant),
                "top_source_id": top_source_id,
                "retrieved_source_ids": [item.document.source_id for item in results],
                "relevant_rank": min(ranks) if ranks else None,
                "decoy_source_ids": [str(item) for item in row.get("decoy_source_ids", [])],
            }
        )
    count = len(rows)
    return {
        "status": "evaluated" if count else "not_measured",
        "method": "hybrid-lexical-tfidf-lsa-v1",
        "queries": count,
        "recall_at_1": round(hits_at_1 / count, 6) if count else None,
        "recall_at_k": round(hits_at_k / count, 6) if count else None,
        "mrr": round(sum(reciprocal_ranks) / count, 6) if count else None,
        "k": limit,
        "details": details,
        "limitations": ["TF-IDF/LSA is a deterministic local semantic fallback; no hosted provider was called."],
    }
