"""Bounded, guest-isolated JSONL upload validation."""

import asyncio
import hashlib
import json
import math
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterable, Callable, Dict, Iterable, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_UPLOAD_RECORDS = 10_000
MAX_LINE_BYTES = 256 * 1024
UPLOAD_RETENTION_SECONDS = 60 * 60
EXPECTED_SIGNALS = ("log", "metric", "trace")
_INJECTION_RE = re.compile(r"(?:ignore\s+(?:all|any|the|previous)|system\s+message|execute\s+(?:a\s+)?command|you\s+are\s+now)", re.I)


class UploadEvent(BaseModel):
    """The deliberately small strict schema accepted by the guest boundary."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=128)
    timestamp: datetime
    signal: Literal["log", "metric", "trace"]
    service: str = Field(min_length=1, max_length=128)
    message: Optional[str] = Field(default=None, max_length=100_000)
    value: Optional[float] = None
    duration_ms: Optional[float] = Field(default=None, ge=0)
    severity: Optional[str] = Field(default=None, max_length=32)
    status: Optional[str] = Field(default=None, max_length=32)


def _strict_input(record: Dict[str, Any]) -> None:
    required_strings = ("event_id", "signal", "service")
    for field_name in required_strings:
        if not isinstance(record.get(field_name), str):
            raise ValueError("%s must be a string" % field_name)
    if "timestamp" not in record or not isinstance(record["timestamp"], str):
        raise ValueError("timestamp must be an ISO-8601 string")
    for field_name in ("message", "severity", "status"):
        if field_name in record and record[field_name] is not None and not isinstance(record[field_name], str):
            raise ValueError("%s must be a string" % field_name)
    for field_name in ("value", "duration_ms"):
        if field_name in record and record[field_name] is not None and (isinstance(record[field_name], bool) or not isinstance(record[field_name], (int, float))):
            raise ValueError("%s must be numeric" % field_name)


def parse_event(record: Any) -> UploadEvent:
    if not isinstance(record, dict):
        raise ValueError("every JSONL line must be an object")
    _strict_input(record)
    event = UploadEvent.model_validate(record)
    if event.signal not in EXPECTED_SIGNALS:
        raise ValueError("signal must be one of: %s" % ", ".join(EXPECTED_SIGNALS))
    if event.signal == "log" and not event.message:
        raise ValueError("log records require message")
    if event.signal == "metric" and event.value is None:
        raise ValueError("metric records require value")
    if event.signal == "trace" and event.duration_ms is None:
        raise ValueError("trace records require duration_ms")
    if event.timestamp.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return event


def _event_fingerprint(event: UploadEvent) -> str:
    payload = event.model_dump(mode="json")
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass
class UploadResult:
    upload_id: str
    session_id: str
    content_type: str
    byte_size: int
    validation: str
    messages: List[str] = field(default_factory=list)
    record_count: int = 0
    duplicate_count: int = 0
    conflict_count: int = 0
    missing_signals: List[str] = field(default_factory=list)
    untrusted_record_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None

    def response(self) -> Dict[str, Any]:
        return {
            "upload_id": self.upload_id,
            "session_id": self.session_id,
            "content_type": "application/jsonl",
            "byte_size": self.byte_size,
            "validation": self.validation,
            "telemetry_origin": "guest_upload",
            "messages": self.messages,
            "record_count": self.record_count,
            "duplicate_count": self.duplicate_count,
            "conflict_count": self.conflict_count,
            "missing_signals": self.missing_signals,
            "missing_signal_count": len(self.missing_signals),
            "untrusted_record_count": self.untrusted_record_count,
            "expires_at": self.expires_at,
        }


class QuotaExceeded(ValueError):
    pass


class CostQuota:
    """In-process guest budget; no upload can consume another guest's quota."""

    def __init__(self, max_bytes: int = 50 * MAX_UPLOAD_BYTES, max_records: int = 50_000, max_cost_units: int = 60_000) -> None:
        self.max_bytes = max_bytes
        self.max_records = max_records
        self.max_cost_units = max_cost_units
        self._used: Dict[str, List[int]] = {}
        self._lock = threading.RLock()

    def charge(self, session_id: str, byte_size: int, records: int) -> None:
        cost_units = records + int(math.ceil(byte_size / (1024 * 1024)))
        with self._lock:
            used_bytes, used_records, used_cost = self._used.get(session_id, [0, 0, 0])
            if used_bytes + byte_size > self.max_bytes or used_records + records > self.max_records or used_cost + cost_units > self.max_cost_units:
                raise QuotaExceeded("guest upload budget exceeded")
            self._used[session_id] = [used_bytes + byte_size, used_records + records, used_cost + cost_units]

    def usage(self, session_id: str) -> Dict[str, int]:
        with self._lock:
            used_bytes, used_records, used_cost = self._used.get(session_id, [0, 0, 0])
        return {"bytes": used_bytes, "records": used_records, "cost_units": used_cost}


async def inspect_jsonl(
    chunks: AsyncIterable[bytes],
    *,
    upload_id: str,
    session_id: str,
    content_type: str,
    cancelled: Optional[Callable[[], bool]] = None,
) -> UploadResult:
    """Parse bounded chunks without buffering the complete request body."""

    result = UploadResult(upload_id, session_id, content_type, 0, "accepted")
    seen: Dict[str, str] = {}
    signals = set()
    buffer = bytearray()
    fatal = content_type != "application/jsonl"
    if fatal:
        result.messages.append("content-type must be application/jsonl")
    async for chunk in chunks:
        if cancelled and cancelled():
            result.validation = "incomplete"
            result.messages.append("upload cancelled before validation completed")
            return result
        if not isinstance(chunk, (bytes, bytearray)):
            result.validation = "invalid"
            result.messages.append("upload stream yielded non-byte data")
            return result
        result.byte_size += len(chunk)
        if result.byte_size > MAX_UPLOAD_BYTES:
            result.validation = "invalid"
            result.messages.append("upload exceeds 10 MiB")
            return result
        buffer.extend(chunk)
        if len(buffer) > MAX_LINE_BYTES and b"\n" not in buffer:
            result.validation = "invalid"
            result.messages.append("JSONL record exceeds 256 KiB")
            return result
        while b"\n" in buffer:
            line, _, remainder = buffer.partition(b"\n")
            buffer = bytearray(remainder)
            if not line.strip():
                continue
            if len(line) > MAX_LINE_BYTES:
                fatal = True
                result.messages.append("JSONL record exceeds 256 KiB")
                continue
            if result.record_count >= MAX_UPLOAD_RECORDS:
                fatal = True
                result.messages.append("upload exceeds 10,000 records")
                continue
            try:
                event = parse_event(json.loads(line.decode("utf-8")))
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, ValidationError) as exc:
                fatal = True
                if len(result.messages) < 20:
                    result.messages.append("invalid record %d: %s" % (result.record_count + 1, str(exc)))
                continue
            result.record_count += 1
            signals.add(event.signal)
            fingerprint = _event_fingerprint(event)
            previous = seen.get(event.event_id)
            if previous is not None:
                if previous == fingerprint:
                    result.duplicate_count += 1
                else:
                    result.conflict_count += 1
            else:
                seen[event.event_id] = fingerprint
            if event.message is not None:
                result.untrusted_record_count += 1
                if _INJECTION_RE.search(event.message) and "prompt-like text retained as untrusted data" not in result.messages:
                    result.messages.append("prompt-like text retained as untrusted data; no instructions were executed")
    if buffer.strip():
        if len(buffer) > MAX_LINE_BYTES:
            fatal = True
            result.messages.append("JSONL record exceeds 256 KiB")
            buffer.clear()
        elif result.record_count >= MAX_UPLOAD_RECORDS:
            fatal = True
            result.messages.append("upload exceeds 10,000 records")
        else:
            try:
                event = parse_event(json.loads(bytes(buffer).decode("utf-8")))
                result.record_count += 1
                signals.add(event.signal)
                fingerprint = _event_fingerprint(event)
                previous = seen.get(event.event_id)
                if previous is not None:
                    if previous == fingerprint:
                        result.duplicate_count += 1
                    else:
                        result.conflict_count += 1
                else:
                    seen[event.event_id] = fingerprint
                if event.message is not None:
                    result.untrusted_record_count += 1
                    if _INJECTION_RE.search(event.message) and "prompt-like text retained as untrusted data" not in result.messages:
                        result.messages.append("prompt-like text retained as untrusted data; no instructions were executed")
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, ValidationError) as exc:
                fatal = True
                result.messages.append("invalid final record: %s" % str(exc))
    result.missing_signals = [signal for signal in EXPECTED_SIGNALS if signal not in signals]
    if result.missing_signals:
        result.messages.append("missing signals: %s" % ", ".join(result.missing_signals))
    if result.conflict_count:
        result.validation = "conflicting"
        result.messages.append("conflicting duplicate event IDs detected")
    elif fatal:
        result.validation = "invalid"
    elif result.duplicate_count:
        result.validation = "duplicate"
        result.messages.append("duplicate records were ignored")
    elif result.missing_signals:
        result.validation = "incomplete"
    return result


async def inspect_bytes(body: bytes, *, upload_id: str = "upload-test", session_id: str = "sess-test", content_type: str = "application/jsonl") -> UploadResult:
    async def one_chunk() -> AsyncIterable[bytes]:
        yield body

    return await inspect_jsonl(one_chunk(), upload_id=upload_id, session_id=session_id, content_type=content_type)


SAMPLE_JSONL = """{"event_id":"sample-log-1","timestamp":"2026-09-14T08:00:00Z","signal":"log","service":"checkoutservice","message":"request completed"}
{"event_id":"sample-metric-1","timestamp":"2026-09-14T08:00:01Z","signal":"metric","service":"checkoutservice","value":42.0}
{"event_id":"sample-trace-1","timestamp":"2026-09-14T08:00:02Z","signal":"trace","service":"checkoutservice","duration_ms":12.5}
"""


@dataclass
class _UploadState:
    session_id: str
    upload_id: str
    created_at: datetime
    cancelled: threading.Event = field(default_factory=threading.Event)
    result: Optional[UploadResult] = None
    active: bool = True


class UploadManager:
    def __init__(self, retention_seconds: int = UPLOAD_RETENTION_SECONDS, quota: Optional[CostQuota] = None) -> None:
        self.retention_seconds = retention_seconds
        self.quota = quota or CostQuota()
        self._states: Dict[str, _UploadState] = {}
        self._lock = threading.RLock()

    def _cleanup(self) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self.retention_seconds)
        self._states = {key: state for key, state in self._states.items() if state.created_at >= cutoff}

    def begin(self, session_id: str) -> str:
        with self._lock:
            self._cleanup()
            upload_id = "upload-" + uuid.uuid4().hex[:12]
            self._states[upload_id] = _UploadState(
                session_id,
                upload_id,
                datetime.now(timezone.utc),
                result=UploadResult(upload_id, session_id, "application/jsonl", 0, "incomplete", ["upload initiated"]),
            )
            return upload_id

    def cancel(self, session_id: str, upload_id: str) -> bool:
        with self._lock:
            self._cleanup()
            state = self._states.get(upload_id)
            if not state or state.session_id != session_id:
                return False
            if state.active:
                state.cancelled.set()
                state.result = UploadResult(upload_id, session_id, "application/jsonl", 0, "incomplete", ["upload cancelled"])
            return True

    async def validate(self, session_id: str, upload_id: str, content_type: str, chunks: AsyncIterable[bytes]) -> UploadResult:
        with self._lock:
            self._cleanup()
            state = self._states.get(upload_id)
            if not state or state.session_id != session_id:
                raise KeyError("upload not found")
        result = await inspect_jsonl(chunks, upload_id=upload_id, session_id=session_id, content_type=content_type, cancelled=state.cancelled.is_set)
        state.active = False
        if not state.cancelled.is_set():
            try:
                self.quota.charge(session_id, result.byte_size, result.record_count)
            except QuotaExceeded as exc:
                result.validation = "invalid"
                result.messages.append(str(exc))
        result.expires_at = result.created_at + timedelta(seconds=self.retention_seconds)
        with self._lock:
            state.result = result
        return result

    def get(self, session_id: str, upload_id: str) -> Optional[UploadResult]:
        with self._lock:
            self._cleanup()
            state = self._states.get(upload_id)
            if not state or state.session_id != session_id:
                return None
            return state.result


def run(coro):
    """Small synchronous bridge for callers that validate in a worker/test."""

    return asyncio.run(coro)
