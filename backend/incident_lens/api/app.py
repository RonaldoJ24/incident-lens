"""FastAPI application for the local Phase 1 investigation slice."""

import atexit
import uuid
from datetime import datetime
from pathlib import Path
from threading import Event
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from incident_lens import CONTRACT_VERSION
from incident_lens.api.models import (
    CaseList,
    CaseSummary,
    Correction,
    Evidence,
    EvidenceList,
    Finding,
    FindingList,
    Report,
    ReportCreate,
    ReviewRequest,
    Run,
    RunCreate,
    Session,
    TimelineEvent,
    TimelineList,
    UploadValidation,
    WorkflowRequest,
    WorkflowResponse,
)
from incident_lens.connectors import ConnectorError, connector_from_environment, connector_status
from incident_lens.api.store import iso, parse_json, select_store, utc_now
from incident_lens.observability import MetricsMiddleware, RequestMetrics
from incident_lens.retrieval import HybridRetriever, KnowledgeIndex
from incident_lens.uploads import SAMPLE_JSONL, UploadManager
from incident_lens.worker.runner import BoundedInvestigationRunner
from incident_lens.workflow import InvestigationWorkflow


def metadata() -> Dict[str, str]:
    return {"name": "Incident Lens API", "contract_version": CONTRACT_VERSION, "status": "phase_1_local_slice"}


def _case_payload(row: Any) -> Dict[str, Any]:
    return {
        "case_id": row["case_id"],
        "title": row["title"],
        "description": row["description"],
        "service": row["service"],
        "telemetry_origin": row["telemetry_origin"],
        "source_interval": parse_json(row["source_interval_json"]),
        "fixture_kind": row["fixture_kind"],
        "public_example": bool(row["public_example"]),
    }


def _run_payload(row: Dict[str, Any]) -> Run:
    return Run(
        run_id=row["run_id"],
        session_id=row["session_id"],
        case_id=row["case_id"],
        status=row["status"],
        attempt=row["attempt"],
        provenance=parse_json(row["provenance_json"]),
    )


def _report_payload(row: Dict[str, Any]) -> Report:
    return Report(
        report_id=row["report_id"],
        session_id=row["session_id"],
        run_id=row["run_id"],
        revision=row["revision"],
        provenance=parse_json(row["provenance_json"]),
        finding_ids=parse_json(row["finding_ids_json"]),
        saved_at=row["saved_at"],
        repair_claim=bool(row["repair_claim"]),
    )


def create_app(db_path: Optional[str] = None, database_url: Optional[str] = None) -> FastAPI:
    """Create an isolated app, selecting PostgreSQL when a URL is configured."""

    store = select_store(db_path=db_path, database_url=database_url)
    from incident_lens.fixtures.loader import load_cases

    store.seed_cases(load_cases())
    runner = BoundedInvestigationRunner(store)
    upload_manager = UploadManager()
    app = FastAPI(title="Incident Lens API", version=CONTRACT_VERSION)
    metrics = RequestMetrics()
    app.add_middleware(MetricsMiddleware, metrics=metrics)
    app.state.store = store
    app.state.runner = runner
    app.state.uploads = upload_manager
    app.state.metrics = metrics

    def owned_run(run_id: str, session_id: Optional[str]) -> Dict[str, Any]:
        run = store.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        if session_id is None or run["session_id"] != session_id:
            raise HTTPException(status_code=404, detail="Run not found")
        return run

    @app.get("/health")
    def health() -> Dict[str, str]:
        return metadata()

    @app.get("/health/ready")
    def readiness() -> Dict[str, str]:
        try:
            store.healthcheck()
        except Exception as exc:
            raise HTTPException(status_code=503, detail="state store is unavailable") from exc
        return {**metadata(), "status": "ready", "database_backend": type(store).__name__}

    @app.get("/metrics", response_class=Response)
    def metrics_endpoint() -> Response:
        return Response(content=metrics.prometheus(), media_type="text/plain; version=0.0.4")

    @app.post("/v1/sessions", response_model=Session, status_code=201)
    def create_session() -> Session:
        return Session(**store.create_session())

    @app.get("/v1/cases", response_model=CaseList)
    def list_cases() -> CaseList:
        return CaseList(cases=[CaseSummary(**_case_payload(row)) for row in store.list_cases()])

    @app.get("/v1/cases/{case_id}", response_model=CaseSummary)
    def get_case(case_id: str) -> CaseSummary:
        row = store.get_case(case_id)
        if not row:
            raise HTTPException(status_code=404, detail="Case not found")
        return CaseSummary(**_case_payload(row))

    @app.post("/v1/runs", response_model=Run, status_code=202)
    def start_run(
        request: RunCreate,
        background_tasks: BackgroundTasks,
        idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    ) -> Run:
        if not store.session_exists(request.session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        case = store.get_case(request.case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        if request.service != case["service"]:
            raise HTTPException(status_code=400, detail="Service is not available for this case")
        source_interval = parse_json(case["source_interval_json"])
        if request.window_start:
            source_interval["start"] = iso(request.window_start)
        if request.window_end:
            source_interval["end"] = iso(request.window_end)
        try:
            start = datetime.fromisoformat(source_interval["start"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(source_interval["end"].replace("Z", "+00:00"))
            if start >= end:
                raise ValueError
        except ValueError:
            raise HTTPException(status_code=400, detail="Window start must precede end")
        provenance = {
            "telemetry_origin": "controlled_runtime",
            "execution": "new_analysis",
            "source_interval": source_interval,
            "run_version": "phase1-fixture-v1",
            "run_time": iso(utc_now()),
            "workflow_revision": "bounded-worker-v1",
            "prior_run_id": None,
        }
        row = store.create_run(request.session_id, request.case_id, provenance, idempotency_key)
        if not request.defer and row["status"] == "queued":
            background_tasks.add_task(runner.execute, row["run_id"])
        return _run_payload(row)

    @app.get("/v1/runs/{run_id}", response_model=Run)
    def get_run(run_id: str, x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID")) -> Run:
        return _run_payload(owned_run(run_id, x_session_id))

    @app.delete("/v1/runs/{run_id}", response_model=Run, status_code=202)
    def cancel_run(run_id: str, x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID")) -> Run:
        run = owned_run(run_id, x_session_id)
        if run["status"] in {"queued", "running"}:
            updated = store.update_run(run_id, "cancelled")
            return _run_payload(updated or run)
        return _run_payload(run)

    @app.post("/v1/runs/{run_id}/retry", response_model=Run, status_code=202)
    def retry_run(run_id: str, background_tasks: BackgroundTasks, x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID")) -> Run:
        run = owned_run(run_id, x_session_id)
        if run["status"] not in {"failed", "cancelled", "partial", "unresolved"}:
            raise HTTPException(status_code=409, detail="Only failed, cancelled, partial, or unresolved runs can be retried")
        updated = store.update_run(run_id, "queued", increment_attempt=True)
        if not updated:
            raise HTTPException(status_code=404, detail="Run not found")
        background_tasks.add_task(runner.execute, run_id)
        return _run_payload(updated)

    @app.get("/v1/runs/{run_id}/evidence", response_model=EvidenceList)
    def get_evidence(run_id: str, x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID")) -> EvidenceList:
        owned_run(run_id, x_session_id)
        return EvidenceList(evidence=[Evidence(**item) for item in store.list_evidence(run_id)])

    @app.get("/v1/runs/{run_id}/findings", response_model=FindingList)
    def get_findings(run_id: str, x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID")) -> FindingList:
        owned_run(run_id, x_session_id)
        return FindingList(findings=[Finding(**item) for item in store.list_findings(run_id)])

    @app.get("/v1/runs/{run_id}/timeline", response_model=TimelineList)
    def get_timeline(run_id: str, x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID")) -> TimelineList:
        owned_run(run_id, x_session_id)
        return TimelineList(events=[TimelineEvent(**item) for item in store.list_timeline(run_id)])

    @app.post("/v1/runs/{run_id}/workflow", response_model=WorkflowResponse, status_code=202)
    def run_workflow(run_id: str, request: WorkflowRequest, x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID")) -> WorkflowResponse:
        owned_run(run_id, x_session_id)
        index_path = Path(__file__).resolve().parents[3] / "data" / "knowledge" / "verified-runbooks-v1.json"
        workflow = InvestigationWorkflow(store, HybridRetriever(KnowledgeIndex.from_manifest(index_path)))
        cancel_event = Event()
        if request.cancel:
            cancel_event.set()
        state = workflow.run(run_id, x_session_id or "", request.query, resume=request.resume, cancel_event=cancel_event)
        checkpoint = store.get_checkpoint(run_id)
        return WorkflowResponse(run_id=run_id, status=state["status"], checkpoint_id=checkpoint["checkpoint_id"] if checkpoint else workflow.REVISION, retrieval_hits=state.get("retrieval_hits", []), claims=state.get("claims", []), evidence_ids=state.get("evidence_ids", []), report_id=state.get("report_id"), error=state.get("error"))

    @app.get("/v1/runs/{run_id}/corrections", response_model=list[Correction])
    def get_corrections(run_id: str, x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID")) -> list[Correction]:
        owned_run(run_id, x_session_id)
        return [Correction(**item) for item in store.list_corrections(run_id)]

    @app.post("/v1/runs/{run_id}/review", response_model=Correction, status_code=202)
    def review_run(run_id: str, request: ReviewRequest, x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID")) -> Correction:
        owned_run(run_id, x_session_id)
        source_ids = list(request.source_ids)
        if request.action == "withhold_source" and not source_ids:
            source_ids = [item["source"]["source_id"] for item in store.list_evidence(run_id) if item.get("source_type") in {"runbook", "prior_knowledge"}]
            if not source_ids:
                raise HTTPException(status_code=409, detail="No retrieved knowledge source is available to withhold")
        if request.action == "withhold_source":
            knowledge = [item for item in store.list_evidence(run_id) if item.get("source_type") in {"runbook", "prior_knowledge"}]
            available = {item["evidence_id"] for item in knowledge} | {item["source"]["source_id"] for item in knowledge}
            if not set(source_ids) <= available:
                raise HTTPException(status_code=404, detail="Requested source is not present in this run")
            source_ids = [item["source"]["source_id"] if item["evidence_id"] in source_ids else item["source"]["source_id"] for item in knowledge if item["evidence_id"] in source_ids or item["source"]["source_id"] in source_ids]
        correction = {
            "correction_id": "correction-" + uuid.uuid4().hex[:12],
            "run_id": run_id,
            "action": request.action,
            "note": request.note,
            "created_at": iso(utc_now()),
            "context_preserved": True,
            "source_ids": source_ids,
        }
        store.insert_correction(run_id, correction)
        store.insert_timeline(
            run_id,
            {
                "event_id": "timeline-" + uuid.uuid4().hex[:12],
                "run_id": run_id,
                "step": "human_review",
                "state": "succeeded",
                "started_at": correction["created_at"],
                "ended_at": correction["created_at"],
                "scope": {"operation": "record_review", "read_only": True, "parameters": {"action": request.action, "source_ids": source_ids}},
                "evidence_ids": [],
                "duration_ms": 0,
                "error_code": None,
            },
        )
        return Correction(**correction)

    @app.post("/v1/reports", response_model=Report, status_code=201)
    def save_report(
        request: ReportCreate,
        x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID"),
        idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    ) -> Report:
        if x_session_id != request.session_id:
            raise HTTPException(status_code=404, detail="Session not found")
        run = owned_run(request.run_id, x_session_id)
        report = store.save_report(
            request.session_id,
            request.run_id,
            parse_json(run["provenance_json"]),
            [item["finding_id"] for item in store.list_findings(request.run_id)],
            idempotency_key,
        )
        return _report_payload(report)

    @app.get("/v1/reports/{report_id}", response_model=Report)
    def get_report(report_id: str, x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID")) -> Report:
        report = store.get_report(report_id)
        if not report or report["session_id"] != x_session_id:
            raise HTTPException(status_code=404, detail="Report not found")
        return _report_payload(report)

    @app.post("/v1/reports/{report_id}/export", response_class=Response)
    def export_report(report_id: str, x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID")) -> Response:
        report = store.get_report(report_id)
        if not report or report["session_id"] != x_session_id:
            raise HTTPException(status_code=404, detail="Report not found")
        checkpoint = store.get_checkpoint(report["run_id"])
        return JSONResponse(
            content={
                "report": _report_payload(report).model_dump(mode="json"),
                "provenance": parse_json(report["provenance_json"]),
                "findings": store.list_findings(report["run_id"]),
                "evidence": store.list_evidence(report["run_id"]),
                "timeline": store.list_timeline(report["run_id"]),
                "workflow": checkpoint.get("state") if checkpoint else None,
            },
            headers={"Content-Disposition": 'attachment; filename="incident-lens-%s-r%d.json"' % (report_id, report["revision"])},
        )

    @app.get("/v1/uploads/sample", response_class=Response)
    def download_upload_sample() -> Response:
        return Response(
            content=SAMPLE_JSONL,
            media_type="application/jsonl",
            headers={"Content-Disposition": 'attachment; filename="incident-lens-sample.jsonl"'},
        )

    @app.post("/v1/uploads/initiate", response_model=UploadValidation, status_code=201)
    def initiate_upload(x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID")) -> UploadValidation:
        if not x_session_id or not store.session_exists(x_session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        upload_id = upload_manager.begin(x_session_id)
        result = upload_manager.get(x_session_id, upload_id)
        return UploadValidation(**(result.response() if result else {
            "upload_id": upload_id,
            "session_id": x_session_id,
            "content_type": "application/jsonl",
            "byte_size": 0,
            "validation": "incomplete",
            "telemetry_origin": "guest_upload",
            "messages": ["upload initiated"],
        }))

    @app.post("/v1/uploads", response_model=UploadValidation)
    async def validate_upload(request: Request, x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID")) -> UploadValidation:
        if not x_session_id or not store.session_exists(x_session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        upload_id = upload_manager.begin(x_session_id)
        result = await upload_manager.validate(x_session_id, upload_id, content_type, request.stream())
        return UploadValidation(**result.response())

    @app.put("/v1/uploads/{upload_id}", response_model=UploadValidation)
    async def stream_upload(upload_id: str, request: Request, x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID")) -> UploadValidation:
        if not x_session_id:
            raise HTTPException(status_code=404, detail="Upload not found")
        if not upload_manager.get(x_session_id, upload_id):
            raise HTTPException(status_code=404, detail="Upload not found")
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        try:
            result = await upload_manager.validate(x_session_id, upload_id, content_type, request.stream())
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Upload not found") from exc
        return UploadValidation(**result.response())

    @app.get("/v1/uploads/{upload_id}", response_model=UploadValidation)
    def get_upload(upload_id: str, x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID")) -> UploadValidation:
        if not x_session_id:
            raise HTTPException(status_code=404, detail="Upload not found")
        result = upload_manager.get(x_session_id, upload_id)
        if not result:
            raise HTTPException(status_code=404, detail="Upload not found")
        return UploadValidation(**result.response())

    @app.delete("/v1/uploads/{upload_id}", response_model=UploadValidation)
    def cancel_upload(upload_id: str, x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID")) -> UploadValidation:
        if not x_session_id or not upload_manager.cancel(x_session_id, upload_id):
            raise HTTPException(status_code=404, detail="Upload not found")
        result = upload_manager.get(x_session_id, upload_id)
        return UploadValidation(**(result.response() if result else {
            "upload_id": upload_id,
            "session_id": x_session_id,
            "content_type": "application/jsonl",
            "byte_size": 0,
            "validation": "incomplete",
            "telemetry_origin": "guest_upload",
            "messages": ["upload cancelled"],
        }))

    @app.get("/v1/connectors/status")
    def get_connector_status() -> Dict[str, Any]:
        return connector_status().as_dict()

    @app.get("/v1/connectors/verify")
    def verify_connector() -> Dict[str, Any]:
        try:
            connector = connector_from_environment()
        except ConnectorError as exc:
            raise HTTPException(status_code=409, detail="owned connector configuration is invalid") from exc
        if connector is None:
            raise HTTPException(status_code=409, detail="owned connector is not configured")
        try:
            return connector.verify().as_metadata()
        except ConnectorError as exc:
            raise HTTPException(status_code=502, detail="owned connector verification failed") from exc

    return app


app = create_app()
atexit.register(app.state.store.close)
