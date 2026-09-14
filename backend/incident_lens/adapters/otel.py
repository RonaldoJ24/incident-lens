"""OpenTelemetry controlled-runtime adapter boundary.

The adapter deliberately does not implement a connector in Phase 0. Its
request and result types keep controlled failures separate from RCAEval data.
"""

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class ControlledFailureQuery:
    scenario_id: str
    service: str
    start: str
    end: str
    read_only: bool = True


@dataclass(frozen=True)
class ControlledFailureRecord:
    scenario_id: str
    source_version: str
    observed_at: str
    signals: tuple[str, ...]
    controlled: bool = True


class OpenTelemetryAdapter(Protocol):
    """Future read-only adapter; no RCAEval-shaped payload is assumed."""

    def inspect(self, query: ControlledFailureQuery) -> Sequence[ControlledFailureRecord]:
        ...
