"""Pydantic request/response models for the v1 vertical slice."""

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class StrictModel(BaseModel):
    class Config:
        extra = "forbid"


TelemetryOrigin = Literal["recorded_benchmark", "controlled_runtime", "guest_upload", "connected_app"]
Execution = Literal["new_analysis", "stored_result"]


class SignalCompleteness(StrictModel):
    logs: Literal["available", "missing", "partial", "unknown"]
    metrics: Literal["available", "missing", "partial", "unknown"]
    traces: Literal["available", "missing", "partial", "unknown"]


class SourceInterval(StrictModel):
    start: datetime
    end: datetime
    case_or_upload_id: str
    source_version: str
    signal_completeness: SignalCompleteness


class Provenance(StrictModel):
    telemetry_origin: TelemetryOrigin
    execution: Execution
    source_interval: SourceInterval
    run_version: str
    run_time: datetime
    workflow_revision: str
    prior_run_id: Optional[str] = None


class Session(StrictModel):
    session_id: str
    created_at: datetime
    expires_at: datetime
    isolation_scope: Literal["guest"]


class CaseSummary(StrictModel):
    case_id: str
    title: str
    description: str
    service: str
    telemetry_origin: TelemetryOrigin
    source_interval: SourceInterval
    fixture_kind: str
    public_example: bool = True


class CaseList(StrictModel):
    cases: List[CaseSummary]


class RunCreate(StrictModel):
    session_id: str
    case_id: str
    service: str
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    defer: bool = False


class Run(StrictModel):
    run_id: str
    session_id: str
    case_id: str
    status: Literal["queued", "running", "partial", "succeeded", "unresolved", "failed", "cancelled"]
    attempt: int
    provenance: Provenance


class EvidenceSource(StrictModel):
    source_id: str
    version: str


class Evidence(StrictModel):
    evidence_id: str
    source_type: Literal["log", "metric", "trace", "runbook", "prior_knowledge", "metadata"]
    source: EvidenceSource
    event_time: datetime
    query_window: SourceInterval
    content_or_summary: str
    quality_flags: List[str]
    access_scope: Literal["guest_session", "public_knowledge", "internal_connector"]


class EvidenceList(StrictModel):
    evidence: List[Evidence]


class Finding(StrictModel):
    finding_id: str
    run_id: str
    assessment: str
    certainty: Literal["supported", "uncertain", "conflicting", "insufficient_evidence"]
    evidence_ids: List[str]
    next_checks: List[str]


class FindingList(StrictModel):
    findings: List[Finding]


class TimelineEvent(StrictModel):
    event_id: str
    run_id: str
    step: str
    state: Literal["queued", "running", "succeeded", "partial", "failed", "cancelled"]
    started_at: datetime
    ended_at: Optional[datetime] = None
    scope: Dict[str, object]
    evidence_ids: List[str]
    duration_ms: int = Field(ge=0)
    error_code: Optional[str] = None


class TimelineList(StrictModel):
    events: List[TimelineEvent]


class ReviewRequest(StrictModel):
    action: Literal["accept", "correct", "challenge", "withhold_source"]
    note: str = Field(default="", max_length=1000)


class Correction(StrictModel):
    correction_id: str
    run_id: str
    action: Literal["accept", "correct", "challenge", "withhold_source"]
    note: str
    created_at: datetime
    context_preserved: Literal[True]
    follow_up_run_id: Optional[str] = None


class ReportCreate(StrictModel):
    session_id: str
    run_id: str


class Report(StrictModel):
    report_id: str
    session_id: str
    run_id: str
    revision: int
    provenance: Provenance
    finding_ids: List[str]
    saved_at: datetime
    repair_claim: Literal[False]


class ExportMetadata(StrictModel):
    report_id: str
    revision: int
    format: Literal["json"]
    exported_at: datetime
    provenance: Provenance
    download_name: str


class UploadValidation(StrictModel):
    upload_id: str
    session_id: str
    content_type: Literal["application/jsonl"]
    byte_size: int
    validation: Literal["accepted", "invalid", "incomplete", "duplicate", "conflicting"]
    telemetry_origin: Literal["guest_upload"]
    messages: List[str]
