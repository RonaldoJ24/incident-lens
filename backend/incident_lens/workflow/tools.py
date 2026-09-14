"""Explicit read-only diagnostic tool registry; no shell or SQL tool exists."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping

from incident_lens.fixtures.loader import load_cases


class ToolError(ValueError):
    pass


class ReadOnlyToolRegistry:
    ALLOWED = frozenset({"inspect_fixture"})

    def __init__(self, max_events: int = 100) -> None:
        self.max_events = max_events
        self.cases = {case.case_id: case for case in load_cases()}

    def call(self, name: str, params: Mapping[str, Any]) -> Dict[str, Any]:
        if name not in self.ALLOWED:
            raise ToolError("tool is not allowlisted: %s" % name)
        if name == "inspect_fixture":
            return self._inspect_fixture(params)
        raise ToolError("unsupported tool")

    def _inspect_fixture(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        case_id = str(params.get("case_id", ""))
        case = self.cases.get(case_id)
        if not case:
            raise ToolError("unknown case")
        limit = int(params.get("max_events", self.max_events))
        if limit < 1 or limit > self.max_events:
            raise ToolError("max_events exceeds read-only bound")
        events = list(case.events[:limit])
        # Fixture messages are untrusted content and are returned as data only.
        signals = {signal: sum(1 for event in events if event.get("signal") == signal) for signal in ("log", "metric", "trace")}
        return {"case_id": case_id, "event_count": len(events), "signal_counts": signals, "untrusted_content": True, "fixture_version": "fixture-v1"}


def hostile_fixture_event() -> Dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "fixtures" / "hostile_logs.json"
    return json.loads(path.read_text(encoding="utf-8"))["events"][0]
