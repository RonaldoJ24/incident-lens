"""Dependency-free validation for the small, versioned v1 contract fixture.

The JSON Schema remains the normative interchange artifact. This validator is
intentionally focused on the cross-field invariants that matter in Phase 0 and
keeps checks runnable without installing a schema library.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable


class ContractError(ValueError):
    """Raised when a v1 contract document violates a required invariant."""


_ENTITIES = {
    "session": ("session_id", "created_at", "expires_at", "isolation_scope"),
    "case": ("case_id", "title", "telemetry_origin", "source_interval", "public_example"),
    "evidence": ("evidence_id", "source_type", "source", "event_time", "query_window", "content_or_summary", "quality_flags", "access_scope"),
    "run": ("run_id", "session_id", "case_id", "status", "provenance"),
    "finding": ("finding_id", "run_id", "assessment", "certainty", "evidence_ids", "next_checks"),
    "timeline_event": ("event_id", "run_id", "step", "state", "started_at", "ended_at", "scope", "evidence_ids"),
    "correction": ("correction_id", "run_id", "action", "created_at", "context_preserved"),
    "report": ("report_id", "session_id", "run_id", "revision", "provenance", "finding_ids", "saved_at", "repair_claim"),
    "upload": ("upload_id", "session_id", "content_type", "byte_size", "validation", "telemetry_origin"),
}
_ORIGINS = {"recorded_benchmark", "controlled_runtime", "guest_upload", "connected_app"}
_EXECUTIONS = {"new_analysis", "stored_result"}
_COMPLETENESS = {"available", "missing", "partial", "unknown"}
_ID_RE = re.compile(r"^[a-z0-9-]+$")


def _required(mapping: Dict[str, Any], fields: Iterable[str], label: str) -> None:
    missing = [field for field in fields if field not in mapping]
    if missing:
        raise ContractError("%s missing required fields: %s" % (label, ", ".join(missing)))


def _timestamp(value: Any, label: str) -> None:
    if not isinstance(value, str):
        raise ContractError("%s must be an ISO-8601 timestamp" % label)
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("%s must be an ISO-8601 timestamp" % label) from exc


def _source_interval(value: Any, label: str = "source_interval") -> None:
    if not isinstance(value, dict):
        raise ContractError("%s must be an object" % label)
    _required(value, ("start", "end", "case_or_upload_id", "source_version", "signal_completeness"), label)
    _timestamp(value["start"], "%s.start" % label)
    _timestamp(value["end"], "%s.end" % label)
    completeness = value["signal_completeness"]
    if not isinstance(completeness, dict):
        raise ContractError("%s.signal_completeness must be an object" % label)
    _required(completeness, ("logs", "metrics", "traces"), "%s.signal_completeness" % label)
    if any(item not in _COMPLETENESS for item in completeness.values()):
        raise ContractError("%s has invalid signal completeness" % label)


def _provenance(value: Any) -> None:
    if not isinstance(value, dict):
        raise ContractError("provenance must be an object")
    _required(value, ("telemetry_origin", "execution", "source_interval", "run_version", "run_time", "workflow_revision"), "provenance")
    if value["telemetry_origin"] not in _ORIGINS:
        raise ContractError("invalid telemetry_origin")
    if value["execution"] not in _EXECUTIONS:
        raise ContractError("invalid execution")
    _source_interval(value["source_interval"], "provenance.source_interval")
    _timestamp(value["run_time"], "provenance.run_time")
    if value["execution"] == "stored_result" and not value.get("prior_run_id"):
        raise ContractError("stored_result requires prior_run_id")


def validate_document(document: Dict[str, Any]) -> Dict[str, Any]:
    """Validate one envelope and return it for convenient pipeline use."""

    if not isinstance(document, dict):
        raise ContractError("contract document must be an object")
    _required(document, ("contract_version", "entity", "payload"), "document")
    if document["contract_version"] != "v1":
        raise ContractError("unsupported contract_version")
    entity = document["entity"]
    if entity not in _ENTITIES:
        raise ContractError("unsupported entity: %s" % entity)
    payload = document["payload"]
    if not isinstance(payload, dict):
        raise ContractError("payload must be an object")
    _required(payload, _ENTITIES[entity], entity)

    if entity == "session":
        if not re.match(r"^sess-[a-z0-9-]+$", payload["session_id"]):
            raise ContractError("invalid session_id")
        if payload["isolation_scope"] != "guest":
            raise ContractError("session isolation_scope must be guest")
        _timestamp(payload["created_at"], "created_at")
        _timestamp(payload["expires_at"], "expires_at")
    elif entity == "case":
        if not _ID_RE.match(payload["case_id"]):
            raise ContractError("invalid case_id")
        if payload["telemetry_origin"] not in _ORIGINS:
            raise ContractError("invalid case telemetry_origin")
        _source_interval(payload["source_interval"])
    elif entity == "evidence":
        if not re.match(r"^evidence-[a-z0-9-]+$", payload["evidence_id"]):
            raise ContractError("invalid evidence_id")
        _timestamp(payload["event_time"], "event_time")
        _source_interval(payload["query_window"], "query_window")
        if not isinstance(payload["quality_flags"], list):
            raise ContractError("quality_flags must be a list")
    elif entity == "run":
        if not re.match(r"^run-[a-z0-9-]+$", payload["run_id"]):
            raise ContractError("invalid run_id")
        _provenance(payload["provenance"])
    elif entity == "finding":
        if payload["certainty"] not in {"supported", "uncertain", "conflicting", "insufficient_evidence"}:
            raise ContractError("invalid finding certainty")
    elif entity == "timeline_event":
        _timestamp(payload["started_at"], "started_at")
        if payload["ended_at"] is not None:
            _timestamp(payload["ended_at"], "ended_at")
        if payload["scope"].get("read_only") is not True:
            raise ContractError("timeline scope must be read_only")
    elif entity == "correction":
        _timestamp(payload["created_at"], "created_at")
        if payload["context_preserved"] is not True:
            raise ContractError("correction must preserve context")
    elif entity == "report":
        if payload["revision"] < 1:
            raise ContractError("report revision must be positive")
        _provenance(payload["provenance"])
        _timestamp(payload["saved_at"], "saved_at")
        if payload["repair_claim"] is not False:
            raise ContractError("reports cannot claim repair")
    elif entity == "upload":
        if payload["content_type"] != "application/jsonl":
            raise ContractError("uploads must be JSONL")
        if not 0 <= payload["byte_size"] <= 10 * 1024 * 1024:
            raise ContractError("upload exceeds 10 MiB bound")
        if payload["telemetry_origin"] != "guest_upload":
            raise ContractError("upload origin must be guest_upload")
    return document


def validate_fixture(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    documents = data.get("documents") if isinstance(data, dict) else None
    if not isinstance(documents, list) or not documents:
        raise ContractError("representative fixture must contain documents")
    for document in documents:
        validate_document(document)
    return len(documents)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate a representative v1 contract fixture")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    print("validated %d contract documents" % validate_fixture(args.path))
