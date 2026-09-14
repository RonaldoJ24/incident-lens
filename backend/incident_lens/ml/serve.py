"""Small serving boundary for unusual service/window ranking."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from .artifacts import ArtifactError, load_model
from .ranking import FEATURE_SCHEMA_VERSION, RANKING_SEMANTICS, rank_rows


class RankingService:
    """Load one verified artifact and expose safe ranking responses."""

    def __init__(self, artifact_path: Path) -> None:
        self.artifact, self.model = load_model(Path(artifact_path))

    def rank(self, rows: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
        ranking = rank_rows(rows, self.model)
        return {
            "ranking": ranking,
            "ranking_semantics": RANKING_SEMANTICS,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "feature_names": self.artifact.get("feature_names", []),
            "source": self.artifact.get("source", {}),
            "artifact_version": self.artifact["artifact_version"],
        }


def rank_unusual_windows(artifact_path: Path, rows: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    return RankingService(Path(artifact_path)).rank(rows)


__all__ = ["RankingService", "rank_unusual_windows"]
