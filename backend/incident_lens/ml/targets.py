"""Private development reviewer targets for Phase 3 metric calculation.

Targets are intentionally kept outside Git under ``data/cache``.  They are
positive sample IDs only; no upstream case names, service names, causes, or
injection timestamps are serialized into public artifacts or reports.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Set


class ReviewTargetError(ValueError):
    """Raised when private reviewer targets are unsafe or unavailable."""


_SAMPLE = re.compile(r"^sample-[a-z0-9-]{1,120}$")


def load_review_targets(path: Optional[Path] = None) -> Optional[Set[str]]:
    """Load private positive sample IDs, or ``None`` when not available."""

    target_path = Path(path or "data/cache/rcaeval/phase3-review-targets.json")
    if not target_path.exists():
        return None
    # A final/held-out target file is never a Phase 3 input.
    if re.search(r"(?:final|held.?out|test)", target_path.name, re.IGNORECASE):
        raise ReviewTargetError("final held-out targets are sealed")
    try:
        document = json.loads(target_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewTargetError("cannot read private review targets") from exc
    if not isinstance(document, Mapping) or document.get("version") != "phase3-review-v1":
        raise ReviewTargetError("unsupported reviewer target version")
    if document.get("target_semantics") != "reviewed event-window target; not a failing-service or root-cause label":
        raise ReviewTargetError("review targets must be event-window targets")
    values = document.get("positive_sample_ids")
    if not isinstance(values, list) or any(not isinstance(item, str) or not _SAMPLE.fullmatch(item) for item in values):
        raise ReviewTargetError("review targets must contain neutral sample IDs")
    targets = set(values)
    if len(targets) != len(values):
        raise ReviewTargetError("review target sample IDs must be unique")
    return targets


__all__ = ["ReviewTargetError", "load_review_targets"]
