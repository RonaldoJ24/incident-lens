"""FastAPI application for the local Phase 1 investigation slice."""

import atexit
import json
import os
import uuid
from datetime import datetime
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
)
from incident_lens.api.store import StateStore, iso, utc_now
from incident_lens.worker.runner import BoundedInvestigationRunner


def metadata() -> Dict[str, str]:
    return {"name": "Incident Lens API", "contract_version": CONTRACT_VERSION, "status": "phase_1_local_slice"}


def _case_payload(row: Any) -> Dict[str, Any]:
    return {
        "case_id": row["case_id"],
        "title": row["title"],
        "description": row["description"],
        "service": row["service"],
        "telemetry_origin": row["telemetry_origin"],
        "source_interval": json.loads(row["source_interval_json"]),
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
        provenance=json.loads(row["provenance_json"]),
    )


def _report_payload(row: Dict[str, Any]) -> Report:
    return Report(
        report_id=row["report_id"],
        session_id=row["session_id"],
        run_id=row["run_id"],
        revision=row["revision"],
        provenance=json.loads(row["provenance_json"]),
        finding_ids=json.loads(row["finding_ids_json"]),
        saved_at=row["saved_at"],
        repair_claim=bool(row["repair_claim"]),
    )


def create_app(db_path: Optional[str] = None) -> FastAPI:
    """Create an isolated app instance; tests pass a temporary SQLite path."""

    configured_path = db_path or os.getenv("INCIDENT_LENS_SQLITE_PATH", "/tmp/incident-lens-phase1.sqlite3")
    store = StateStore(configured_path)
    from incident_lens.fixtures.loader import load_cases

    store.seed_cases(load_cases())
    runner = BoundedInvestigationRunner(store)
    app = FastAPI(title="Incident Lens API", version=CONTRACT_VERSION)
    app.state.store = store
    app.state.runner = runner

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
        source_interval = json.loads(case["source_interval_json"])
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

    @app.get("/v1/runs/{run_id}/corrections", response_model=list[Correction])
    def get_corrections(run_id: str, x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID")) -> list[Correction]:
        owned_run(run_id, x_session_id)
        return [Correction(**item) for item in store.list_corrections(run_id)]

    @app.post("/v1/runs/{run_id}/review", response_model=Correction, status_code=202)
    def review_run(run_id: str, request: ReviewRequest, x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID")) -> Correction:
        owned_run(run_id, x_session_id)
        if request.action == "withhold_source":
            raise HTTPException(status_code=409, detail="Source withholding is planned for Phase 4; no source was withheld.")
        correction = {
            "correction_id": "correction-" + uuid.uuid4().hex[:12],
            "run_id": run_id,
            "action": request.action,
            "note": request.note,
            "created_at": iso(utc_now()),
            "context_preserved": True,
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
                "scope": {"operation": "record_review", "read_only": True},
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
            json.loads(run["provenance_json"]),
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
        return JSONResponse(
            content={
                "report": _report_payload(report).model_dump(mode="json"),
                "provenance": json.loads(report["provenance_json"]),
                "findings": store.list_findings(report["run_id"]),
                "evidence": store.list_evidence(report["run_id"]),
                "timeline": store.list_timeline(report["run_id"]),
            },
            headers={"Content-Disposition": 'attachment; filename="incident-lens-%s-r%d.json"' % (report_id, report["revision"])},
        )

    @app.post("/v1/uploads", response_model=UploadValidation)
    async def validate_upload(request: Request, x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID")) -> UploadValidation:
        if not x_session_id or not store.session_exists(x_session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        body = await request.body()
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        messages = []
        if content_type != "application/jsonl":
            messages.append("content-type must be application/jsonl")
        if len(body) > 10 * 1024 * 1024:
            messages.append("upload exceeds 10 MiB")
        try:
            lines = [line for line in body.decode("utf-8").splitlines() if line.strip()]
            for line in lines:
                if not isinstance(json.loads(line), dict):
                    messages.append("every JSONL line must be an object")
                    break
        except (UnicodeDecodeError, json.JSONDecodeError):
            messages.append("body must be valid JSONL")
        validation = "accepted" if not messages else "invalid"
        return UploadValidation(
            upload_id="upload-" + uuid.uuid4().hex[:12],
            session_id=x_session_id,
            content_type="application/jsonl",
            byte_size=len(body),
            validation=validation,
            telemetry_origin="guest_upload",
            messages=messages,
        )

    return app


app = create_app()
atexit.register(app.state.store.close)
