"""Independent OpenTelemetry Demo controlled-runtime adapter.

The controlled source has its own query and result schema.  In particular, it
does not accept RCAEval case IDs, filenames, labels, or tabular assumptions.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping, Protocol, Sequence, Tuple


@dataclass(frozen=True)
class ControlledFailureQuery:
    scenario_id: str
    service: str
    start: str
    end: str
    read_only: bool = True

    def validate(self) -> None:
        if not self.scenario_id or not self.service:
            raise ControlledFailureError("scenario and service are required")
        if not self.read_only:
            raise ControlledFailureError("controlled-runtime inspection is read-only")
        start = _timestamp(self.start)
        end = _timestamp(self.end)
        if start >= end:
            raise ControlledFailureError("query start must precede end")
        if (end - start).total_seconds() > 3600:
            raise ControlledFailureError("query window is limited to one hour")


@dataclass(frozen=True)
class ControlledFailureRecord:
    scenario_id: str
    source_version: str
    observed_at: str
    signals: tuple[str, ...]
    controlled: bool = True


@dataclass(frozen=True)
class ControlledFailureResult:
    """Safe result shape for a controlled scenario inspection."""

    scenario_id: str
    service: str
    source_version: str
    start: str
    end: str
    observed_at: str
    signals: Tuple[str, ...]
    signal_completeness: Mapping[str, str]
    controlled: bool = True


class ControlledFailureError(ValueError):
    """Raised when a controlled-runtime request or result is unsafe."""


def _timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ControlledFailureError("timestamps must be ISO-8601 strings")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ControlledFailureError("malformed controlled-runtime timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ControlledFailureError("controlled-runtime timestamp must include timezone")
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def result_from_records(query: ControlledFailureQuery, records: Sequence[ControlledFailureRecord]) -> ControlledFailureResult:
    """Build a controlled result without interpreting RCAEval fields."""

    query.validate()
    if any(not item.controlled or item.scenario_id != query.scenario_id for item in records):
        raise ControlledFailureError("result does not belong to the requested controlled scenario")
    signals = tuple(sorted({signal for item in records for signal in item.signals if signal in {"logs", "metrics", "traces"}}))
    completeness = {signal: ("available" if signal in signals else "missing") for signal in ("logs", "metrics", "traces")}
    observed = max((_timestamp(item.observed_at) for item in records), default=_timestamp(query.start))
    source_versions = {item.source_version for item in records}
    if len(source_versions) > 1:
        raise ControlledFailureError("controlled-runtime records disagree on source version")
    return ControlledFailureResult(
        scenario_id=query.scenario_id,
        service=query.service,
        source_version=next(iter(source_versions), "unknown"),
        start=_timestamp(query.start).isoformat().replace("+00:00", "Z"),
        end=_timestamp(query.end).isoformat().replace("+00:00", "Z"),
        observed_at=observed.isoformat().replace("+00:00", "Z"),
        signals=signals,
        signal_completeness=completeness,
    )


class OpenTelemetryAdapter(Protocol):
    """Read-only controlled-runtime adapter; no RCAEval payload is assumed."""

    def inspect(self, query: ControlledFailureQuery) -> Sequence[ControlledFailureRecord]:
        ...


class RecordedOpenTelemetryAdapter:
    """Small deterministic adapter for controlled-runtime review fixtures."""

    def __init__(self, records: Sequence[ControlledFailureRecord]) -> None:
        self._records = tuple(records)

    def inspect(self, query: ControlledFailureQuery) -> Sequence[ControlledFailureRecord]:
        query.validate()
        return tuple(item for item in self._records if item.scenario_id == query.scenario_id)


__all__ = [
    "ControlledFailureError",
    "ControlledFailureQuery",
    "ControlledFailureRecord",
    "ControlledFailureResult",
    "OpenTelemetryAdapter",
    "RecordedOpenTelemetryAdapter",
    "result_from_records",
]
