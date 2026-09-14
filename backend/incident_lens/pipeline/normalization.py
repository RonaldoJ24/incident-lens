"""Deterministic, source-neutral telemetry normalization.

This module is deliberately usable without PySpark.  The request path can use
the safe manifest and derived objects; the optional Spark job calls the same
canonicalization rules offline when processing larger collections.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


NORMALIZATION_VERSION = "incident-lens-normalization-v1"
_LEAK_KEY = re.compile(
    r"(?:root.?cause|ground.?truth|hidden.?label|fault.?type|inject(?:ion)?_?time|source.?case|source.?filename|file.?name|answer|solution)",
    re.IGNORECASE,
)
_LEAK_TEXT = re.compile(
    r"(?:root.?cause|ground.?truth|hidden.?label|fault.?type|inject(?:ion)?_?time|/root_cause\.txt|"
    r"re[123](?:ob|ss|tt)_[a-z0-9-]+_(?:cpu|mem|disk|delay|loss|socket|f[1-5])_\d+|"
    r"(?:^|/)(?:metrics|logs|traces)\.(?:csv|json|parquet)(?:$|/))",
    re.IGNORECASE,
)
# RCAEval traces include a display-only ``time`` column alongside a numeric
# start time. Prefer the machine timestamp before that display column.
_ISO_TIMESTAMP_KEYS = ("timestamp", "event_time", "observed_at", "startTimeMillis", "startTime", "start_time", "time")
_SIGNALS = ("logs", "metrics", "traces")
_NEUTRAL_CASE = re.compile(r"^dev-re2ob-\d{3}$")
_ISO_FRACTION = re.compile(r"[T ]\d{2}:\d{2}:\d{2}(?:\.(\d+))?")


class NormalizationError(ValueError):
    """Raised when telemetry cannot safely enter a derived artifact."""


class LeakageError(NormalizationError):
    """Raised when a hidden answer, source filename, or cause leaks."""


class DuplicateEventError(NormalizationError):
    """Raised in strict mode when duplicate telemetry is found."""


class TimestampError(NormalizationError):
    """Raised for malformed or timezone-ambiguous timestamps."""


class SplitError(NormalizationError):
    """Raised when a selected case is outside the allowed split."""


def canonical_json(value: Any) -> str:
    """Stable JSON encoding used for event, file, and manifest hashes."""

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)


def _walk_for_leakage(value: Any, path: str = "record") -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if _LEAK_KEY.search(str(key)):
                yield "%s.%s" % (path, key)
            yield from _walk_for_leakage(child, "%s.%s" % (path, key))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            yield from _walk_for_leakage(child, "%s[%d]" % (path, index))
    elif isinstance(value, str) and _LEAK_TEXT.search(value):
        yield path


def assert_no_leakage(value: Any) -> None:
    paths = list(_walk_for_leakage(value))
    if paths:
        raise LeakageError("hidden-label or filename leakage at %s" % ", ".join(paths))


def _timestamp_parts(value: Any) -> Tuple[datetime, int]:
    """Return UTC datetime (microsecond precision) plus remaining nanoseconds."""

    if isinstance(value, bool):
        raise TimestampError("boolean is not a timestamp")
    if isinstance(value, (int, float, Decimal)):
        try:
            numeric = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise TimestampError("timestamp must be finite") from exc
        if not numeric.is_finite():
            raise TimestampError("timestamp must be finite")
        magnitude = abs(numeric)
        # RCAEval uses Unix seconds for metrics/logs, milliseconds for spans;
        # the explicit ranges keep microsecond and nanosecond epochs distinct.
        if magnitude >= Decimal("1e17"):
            scale = Decimal("1e9")
        elif magnitude >= Decimal("1e14"):
            scale = Decimal("1e6")
        elif magnitude >= Decimal("1e11"):
            scale = Decimal("1e3")
        else:
            scale = Decimal("1")
        seconds = numeric / scale
        whole = seconds.to_integral_value(rounding=ROUND_FLOOR)
        fraction = seconds - whole
        nanos = int((fraction * Decimal("1e9")).to_integral_value(rounding=ROUND_FLOOR))
        try:
            base = datetime.fromtimestamp(int(whole), tz=timezone.utc)
            return base + timedelta(microseconds=nanos // 1000), nanos % 1000
        except (OverflowError, OSError, ValueError) as exc:
            raise TimestampError("timestamp is outside the supported range") from exc
    if not isinstance(value, str) or not value.strip():
        raise TimestampError("timestamp must be an aware ISO-8601 value or Unix epoch")
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TimestampError("malformed timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TimestampError("timestamp must include a timezone")
    match = _ISO_FRACTION.search(text)
    fraction_text = (match.group(1) if match else "") or ""
    if len(fraction_text) > 9:
        raise TimestampError("timestamp has more than nanosecond precision")
    nanos = int(fraction_text.ljust(9, "0")) if fraction_text else 0
    base = parsed.replace(microsecond=0).astimezone(timezone.utc)
    return base + timedelta(microseconds=nanos // 1000), nanos % 1000


def parse_timestamp(value: Any) -> datetime:
    """Parse seconds, milliseconds, microseconds, nanoseconds, or aware ISO."""

    return _timestamp_parts(value)[0]


def canonical_timestamp(value: Any) -> str:
    """Render UTC with enough fractional digits to avoid sub-second collisions."""

    parsed, remainder = _timestamp_parts(value)
    if parsed.microsecond == 0 and remainder == 0:
        return parsed.isoformat().replace("+00:00", "Z")
    whole = parsed.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    fraction = "%09d" % (parsed.microsecond * 1000 + remainder)
    return whole[:-1] + "." + fraction + "Z"


def _event_sort_key(value: str) -> Tuple[datetime, str]:
    # The compact whole-second form sorts after a fractional form in ASCII;
    # parse first, then retain the canonical string to distinguish nanoseconds.
    return parse_timestamp(value), value


def _timestamp_value(record: Mapping[str, Any]) -> Any:
    for key in _ISO_TIMESTAMP_KEYS:
        if key in record:
            return record[key]
    raise TimestampError("record has no timestamp field")


def _clean_value(value: Any) -> Any:
    """Make parquet/numpy-like scalar values JSON-safe without a dependency."""

    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, (list, tuple)):
        return [_clean_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _clean_value(child) for key, child in value.items()}
    # numpy scalar values expose item() but importing numpy is unnecessary.
    item = getattr(value, "item", None)
    if callable(item):
        return _clean_value(item())
    return str(value)


@dataclass(frozen=True)
class NormalizedEvent:
    event_id: str
    signal: str
    timestamp: str
    attributes: Mapping[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {"event_id": self.event_id, "signal": self.signal, "timestamp": self.timestamp, "attributes": dict(self.attributes)}


@dataclass(frozen=True)
class SignalQuality:
    signal: str
    input_count: int
    output_count: int
    duplicate_count: int
    malformed_count: int
    first_event_time: Optional[str]
    last_event_time: Optional[str]
    sha256: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "signal": self.signal,
            "input_count": self.input_count,
            "output_count": self.output_count,
            "duplicate_count": self.duplicate_count,
            "malformed_count": self.malformed_count,
            "first_event_time": self.first_event_time,
            "last_event_time": self.last_event_time,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class NormalizedCase:
    case_id: str
    split: str
    source_version: str
    dataset_revision: str
    events: Tuple[NormalizedEvent, ...]
    signals: Tuple[SignalQuality, ...]
    window_start: Optional[str]
    window_end: Optional[str]
    generated_at: str
    manifest_hash: str

    def manifest(self) -> Dict[str, Any]:
        # This is safe to publish: no locator, upstream path, labels, or raw
        # object key appears here.
        return {
            "manifest_version": "2.0.0",
            "manifest_id": "incident-lens-derived-%s" % self.case_id,
            "generated_at": self.generated_at,
            "source": {
                "source_id": "rcaeval",
                "dataset": "RCAEval",
                "subset": "RE2-OB",
                "source_version": self.source_version,
                "dataset_revision": self.dataset_revision,
            },
            "split": self.split,
            "case_id": self.case_id,
            "normalization_version": NORMALIZATION_VERSION,
            "window": {"start": self.window_start, "end": self.window_end, "event_count": len(self.events)},
            "signals": [item.as_dict() for item in self.signals],
            "manifest_hash": self.manifest_hash,
            "license": {"name": "MIT", "url": "https://github.com/phamquiluan/RCAEval/blob/bb48c5aa9a24f1d5fcc716bdd479ea2d63145c90/LICENSE", "redistribution": "raw telemetry remains outside Git"},
            "attribution": "Pham, Luan et al. RCAEval (2025). Derived quality summary generated from a pinned case.",
            "raw_data_in_repo": False,
            "leakage_review": {"neutral_ids": True, "hidden_labels_removed": True, "source_filenames_removed": True, "review_status": "passed"},
        }


def _event_from_record(signal: str, record: Mapping[str, Any]) -> NormalizedEvent:
    assert_no_leakage(record)
    timestamp = canonical_timestamp(_timestamp_value(record))
    attributes = {str(key): _clean_value(value) for key, value in record.items() if str(key) not in _ISO_TIMESTAMP_KEYS}
    assert_no_leakage(attributes)
    identity = {"signal": signal, "timestamp": timestamp, "attributes": attributes}
    digest = hashlib.sha256(canonical_json(identity).encode("utf-8")).hexdigest()
    return NormalizedEvent(event_id="evt-" + digest[:24], signal=signal, timestamp=timestamp, attributes=attributes)


def normalize_events(
    signal: str,
    records: Iterable[Mapping[str, Any]],
    *,
    strict: bool = True,
) -> Tuple[Tuple[NormalizedEvent, ...], SignalQuality]:
    """Normalize one signal and return stable events plus a quality summary."""

    if signal not in _SIGNALS:
        raise NormalizationError("unsupported signal")
    materialized = list(records)
    events: List[NormalizedEvent] = []
    malformed = 0
    seen = set()
    duplicate_count = 0
    for record in materialized:
        if not isinstance(record, Mapping):
            raise NormalizationError("every telemetry record must be an object")
        try:
            event = _event_from_record(signal, record)
        except TimestampError:
            malformed += 1
            if strict:
                raise
            continue
        if event.event_id in seen:
            duplicate_count += 1
            continue
        seen.add(event.event_id)
        events.append(event)
    if strict and duplicate_count:
        raise DuplicateEventError("duplicate %s event(s)" % duplicate_count)
    events.sort(key=lambda item: (_event_sort_key(item.timestamp), item.event_id))
    encoded = (canonical_json(item.as_dict()) + "\n" for item in events)
    digest = hashlib.sha256("".join(encoded).encode("utf-8")).hexdigest()
    quality = SignalQuality(
        signal=signal,
        input_count=len(materialized),
        output_count=len(events),
        duplicate_count=duplicate_count,
        malformed_count=malformed,
        first_event_time=events[0].timestamp if events else None,
        last_event_time=events[-1].timestamp if events else None,
        sha256=digest,
    )
    return tuple(events), quality


def _manifest_hash(document: Mapping[str, Any]) -> str:
    without_hash = dict(document)
    without_hash.pop("manifest_hash", None)
    # Execution time is truthful provenance, not part of deterministic content
    # identity. Reprocessing identical telemetry therefore keeps the same hash.
    without_hash.pop("generated_at", None)
    return hashlib.sha256(canonical_json(without_hash).encode("utf-8")).hexdigest()


def normalize_case(
    case_id: str,
    split: str,
    source_version: str,
    dataset_revision: str,
    records_by_signal: Mapping[str, Iterable[Mapping[str, Any]]],
    *,
    allowed_split: str = "development",
    strict: bool = True,
    generated_at: Optional[str] = None,
) -> NormalizedCase:
    """Normalize a case into a deterministic, leakage-safe derived object."""

    if not _NEUTRAL_CASE.fullmatch(case_id):
        raise NormalizationError("case ID must be neutral")
    if split != allowed_split:
        raise SplitError("case is outside the permitted split")
    assert_no_leakage(records_by_signal)
    unknown = set(records_by_signal) - set(_SIGNALS)
    if unknown:
        raise NormalizationError("unsupported signals: %s" % ", ".join(sorted(unknown)))
    all_events: List[NormalizedEvent] = []
    quality: List[SignalQuality] = []
    for signal in _SIGNALS:
        events, summary = normalize_events(signal, records_by_signal.get(signal, ()), strict=strict)
        all_events.extend(events)
        quality.append(summary)
    all_events.sort(key=lambda item: (_event_sort_key(item.timestamp), item.signal, item.event_id))
    times = [item.timestamp for item in all_events]
    run_generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    # Validate an explicitly supplied execution timestamp through the same
    # timezone-safe parser used for telemetry.
    run_generated_at = canonical_timestamp(run_generated_at)
    document = {
        "manifest_version": "2.0.0",
        "manifest_id": "incident-lens-derived-%s" % case_id,
        "generated_at": run_generated_at,
        "source": {"source_id": "rcaeval", "dataset": "RCAEval", "subset": "RE2-OB", "source_version": source_version, "dataset_revision": dataset_revision},
        "split": split,
        "case_id": case_id,
        "normalization_version": NORMALIZATION_VERSION,
        "window": {"start": times[0] if times else None, "end": times[-1] if times else None, "event_count": len(all_events)},
        "signals": [item.as_dict() for item in quality],
        "license": {"name": "MIT", "url": "https://github.com/phamquiluan/RCAEval/blob/bb48c5aa9a24f1d5fcc716bdd479ea2d63145c90/LICENSE", "redistribution": "raw telemetry remains outside Git"},
        "attribution": "Pham, Luan et al. RCAEval (2025). Derived quality summary generated from a pinned case.",
        "raw_data_in_repo": False,
        "leakage_review": {"neutral_ids": True, "hidden_labels_removed": True, "source_filenames_removed": True, "review_status": "passed"},
    }
    manifest_hash = _manifest_hash(document)
    document["manifest_hash"] = manifest_hash
    return NormalizedCase(
        case_id=case_id,
        split=split,
        source_version=source_version,
        dataset_revision=dataset_revision,
        events=tuple(all_events),
        signals=tuple(quality),
        window_start=times[0] if times else None,
        window_end=times[-1] if times else None,
        generated_at=run_generated_at,
        manifest_hash=manifest_hash,
    )


def write_manifest(case: NormalizedCase, destination: Path) -> str:
    """Write only the safe manifest and return its digest."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = (canonical_json(case.manifest()) + "\n").encode("utf-8")
    destination.write_bytes(encoded)
    return hashlib.sha256(encoded).hexdigest()


def read_parquet_records(path: Path) -> List[Dict[str, Any]]:
    """Read a parquet file only in offline tooling (pyarrow is optional)."""

    try:
        import pyarrow.parquet as parquet  # type: ignore
    except ImportError:
        try:
            import polars as pl  # type: ignore
        except ImportError as exc:
            raise NormalizationError("a parquet reader is required; install the data extra") from exc
        return [dict(row) for row in pl.read_parquet(path).to_dicts()]
    table = parquet.read_table(path)
    return [dict(row) for row in table.to_pylist()]


__all__ = [
    "DuplicateEventError",
    "LeakageError",
    "NORMALIZATION_VERSION",
    "NormalizedCase",
    "NormalizedEvent",
    "NormalizationError",
    "SignalQuality",
    "SplitError",
    "TimestampError",
    "assert_no_leakage",
    "canonical_json",
    "canonical_timestamp",
    "normalize_case",
    "normalize_events",
    "parse_timestamp",
    "read_parquet_records",
    "write_manifest",
]
