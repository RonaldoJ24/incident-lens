"""Bounded deterministic investigation runner over the reviewed local fixture."""

import json
import time
from datetime import datetime
from typing import Dict, List
import uuid

from incident_lens.fixtures.loader import FixtureCase, load_cases
from incident_lens.api.store import StateStore, iso, utc_now


class BoundedInvestigationRunner:
    """Perform fixed read-only checks; no model-generated shell or SQL exists."""

    MAX_EVENTS = 100

    def __init__(self, store: StateStore) -> None:
        self.store = store
        self.fixtures: Dict[str, FixtureCase] = {case.case_id: case for case in load_cases()}

    def execute(self, run_id: str) -> None:
        run = self.store.get_run(run_id)
        if not run or run["status"] == "cancelled":
            return
        case = self.fixtures.get(run["case_id"])
        if not case:
            self.store.update_run(run_id, "failed")
            return
        self.store.update_run(run_id, "running")
        started = utc_now()
        started_clock = time.perf_counter()
        run_interval = json.loads(run["provenance_json"])["source_interval"]
        start = datetime.fromisoformat(run_interval["start"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(run_interval["end"].replace("Z", "+00:00"))
        events = [
            event
            for event in case.events
            if start <= datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00")) <= end
        ][: self.MAX_EVENTS]
        evidence_ids: List[str] = []
        for signal in ("log", "metric", "trace"):
            signal_events = [event for event in events if event.get("signal") == signal]
            evidence_id = "evidence-" + uuid.uuid4().hex[:12]
            evidence_ids.append(evidence_id)
            if signal_events:
                event_time = signal_events[0]["timestamp"]
                summary = "%d authored %s record(s) returned for the selected interval." % (len(signal_events), signal)
                flags: List[str] = []
            else:
                event_time = run_interval["start"]
                summary = "No %s records returned for the selected interval." % signal
                flags = ["missing"]
            self.store.insert_evidence(
                run_id,
                {
                    "evidence_id": evidence_id,
                    "source_type": signal,
                    "source": {"source_id": "incident-lens-authored-fixture", "version": "fixture-v1"},
                    "event_time": event_time,
                    "query_window": run_interval,
                    "content_or_summary": summary,
                    "quality_flags": flags,
                    "access_scope": "guest_session",
                },
            )

        missing = [signal for signal in ("log", "metric", "trace") if not any(event.get("signal") == signal for event in events)]
        error_events = sum(1 for event in events if event.get("severity") == "error" or event.get("status") == "error")
        latency_values = [event.get("value", event.get("duration_ms")) for event in events if event.get("value", event.get("duration_ms")) is not None]
        max_latency = max(latency_values) if latency_values else None
        if missing:
            status = "partial"
            certainty = "insufficient_evidence"
            assessment = "Evidence is incomplete: %s signal(s) are missing. No causal conclusion is supported." % ", ".join(missing)
        elif case.case_id == "degraded-performance":
            status = "succeeded"
            certainty = "uncertain"
            assessment = "The authored fixture contains an unusual latency sample (%sms); a nearby release clue would not prove causality." % max_latency
        else:
            status = "succeeded"
            certainty = "uncertain"
            assessment = "The authored fixture returned %d bounded records, including %d error record(s); this ranks unusual behavior but does not prove causality." % (len(events), error_events)
        self.store.insert_finding(
            run_id,
            {
                "finding_id": "finding-" + uuid.uuid4().hex[:12],
                "run_id": run_id,
                "assessment": assessment,
                "certainty": certainty,
                "evidence_ids": evidence_ids,
                "next_checks": ["Inspect the trace interval", "Compare the adjacent baseline window"],
            },
        )
        finished = utc_now()
        self.store.insert_timeline(
            run_id,
            {
                "event_id": "timeline-" + uuid.uuid4().hex[:12],
                "run_id": run_id,
                "step": "inspect_authored_fixture",
                "state": status,
                "started_at": iso(started),
                "ended_at": iso(finished),
                "scope": {
                    "operation": "read_authored_fixture",
                    "read_only": True,
                    "parameters": {
                        "case_id": case.case_id,
                        "window_start": run_interval["start"],
                        "window_end": run_interval["end"],
                        "max_events": self.MAX_EVENTS,
                    },
                },
                "evidence_ids": evidence_ids,
                "duration_ms": max(1, int(round((time.perf_counter() - started_clock) * 1000))),
                "error_code": None,
            },
        )
        self.store.update_run(run_id, status)
