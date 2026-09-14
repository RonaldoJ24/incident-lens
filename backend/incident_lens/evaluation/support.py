"""Claim support checks that never turn an absent citation into a fact."""

from __future__ import annotations

import re
from typing import Iterable, Mapping


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9][a-z0-9_-]*", text.lower()))


def evaluate_claim_support(claim: str, evidence: Iterable[Mapping[str, object]]) -> dict[str, object]:
    """Classify support using cited evidence and deterministic token overlap."""

    claim_tokens = _tokens(claim)
    cited = list(evidence)
    citations = [str(item.get("citation", "")) for item in cited if item.get("citation")]
    if not cited or not claim_tokens:
        return {"status": "unsupported", "method": "lexical-support-v1", "citations": citations, "overlap": 0.0}
    best = max(len(claim_tokens & _tokens(str(item.get("text", "")))) / len(claim_tokens) for item in cited)
    status = "supported" if best >= 0.35 else "uncertain"
    return {"status": status, "method": "lexical-support-v1", "citations": citations, "overlap": round(best, 6)}
