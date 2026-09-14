"""Versioned lexical plus local TF-IDF/LSA retrieval over verified summaries."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Set


TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]*")
EMBEDDING_VERSION = "tfidf-lsa-v1"


@dataclass(frozen=True)
class KnowledgeDocument:
    source_id: str
    source_version: str
    title: str
    url: str
    citation: str
    source_kind: str
    text: str


@dataclass(frozen=True)
class RetrievalHit:
    document: KnowledgeDocument
    lexical_score: float
    semantic_score: float
    combined_score: float
    rank: int

    def as_dict(self) -> Dict[str, object]:
        return {
            "source_id": self.document.source_id,
            "source_version": self.document.source_version,
            "title": self.document.title,
            "url": self.document.url,
            "citation": self.document.citation,
            "source_kind": self.document.source_kind,
            "text": self.document.text,
            "lexical_score": round(self.lexical_score, 6),
            "semantic_score": round(self.semantic_score, 6),
            "combined_score": round(self.combined_score, 6),
            "rank": self.rank,
            "embedding_version": EMBEDDING_VERSION,
        }


def _tokens(value: str) -> List[str]:
    return TOKEN_RE.findall(value.lower())


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return max(0.0, min(1.0, (numerator / (left_norm * right_norm) + 1.0) / 2.0))


class KnowledgeIndex:
    def __init__(self, documents: Iterable[KnowledgeDocument], manifest_id: str, embedding: Mapping[str, object]) -> None:
        self.documents = tuple(documents)
        self.manifest_id = manifest_id
        self.embedding = dict(embedding)
        if not self.documents:
            raise ValueError("knowledge index must contain at least one document")

    @classmethod
    def from_manifest(cls, path: Path) -> "KnowledgeIndex":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("index_version") != "incident-lens-knowledge-v1":
            raise ValueError("unsupported knowledge index version")
        documents = [KnowledgeDocument(**item) for item in payload.get("documents", [])]
        for document in documents:
            if not document.citation or not document.source_version or not document.source_id:
                raise ValueError("knowledge documents require source/version/citation metadata")
        return cls(documents, payload["manifest_id"], payload.get("embedding", {}))


class HybridRetriever:
    """Lexical overlap plus a frozen local TF-IDF/LSA semantic projection."""

    def __init__(self, index: KnowledgeIndex) -> None:
        self.index = index
        self.semantic_available = False
        self.semantic_version = EMBEDDING_VERSION
        texts = [document.title + " " + document.text for document in index.documents]
        try:
            from sklearn.decomposition import TruncatedSVD
            from sklearn.feature_extraction.text import TfidfVectorizer

            self._vectorizer = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), token_pattern=r"(?u)\b\w[\w-]+\b")
            matrix = self._vectorizer.fit_transform(texts)
            if matrix.shape[0] > 1 and matrix.shape[1] > 1:
                self._lsa = TruncatedSVD(n_components=min(2, matrix.shape[0] - 1, matrix.shape[1]), random_state=0)
                self._vectors = self._lsa.fit_transform(matrix)
                self.semantic_available = True
            else:
                self._vectors = matrix.toarray()
                self.semantic_version = "tfidf-v1"
        except ImportError:  # Honest lexical-only fallback when optional ML libs are absent.
            self._vectorizer = None
            self._lsa = None
            self._vectors = None

    def search(self, query: str, *, limit: int = 5, withheld_source_ids: Iterable[str] = ()) -> List[RetrievalHit]:
        if not query.strip():
            return []
        if limit < 1 or limit > 20:
            raise ValueError("retrieval limit must be between 1 and 20")
        withheld: Set[str] = set(withheld_source_ids)
        query_tokens = set(_tokens(query))
        if self.semantic_available:
            query_vector = self._lsa.transform(self._vectorizer.transform([query]))[0]
        elif self._vectorizer is not None:
            query_vector = self._vectorizer.transform([query]).toarray()[0]
        else:
            query_vector = []
        scored = []
        for document in self.index.documents:
            if document.source_id in withheld:
                continue
            document_tokens = set(_tokens(document.title + " " + document.text))
            lexical = len(query_tokens & document_tokens) / max(1, len(query_tokens))
            index = self.index.documents.index(document)
            semantic = _cosine(query_vector, self._vectors[index]) if self._vectors is not None else 0.0
            combined = 0.6 * lexical + 0.4 * semantic
            scored.append((combined, lexical, semantic, document))
        scored.sort(key=lambda item: (-item[0], item[3].source_id))
        return [RetrievalHit(item[3], item[1], item[2], item[0], rank) for rank, item in enumerate(scored[:limit], 1)]
