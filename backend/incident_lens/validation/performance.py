"""Measure the bounded local API workload without external services."""

from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List

from fastapi.testclient import TestClient

from incident_lens.api.app import create_app
from incident_lens.uploads import MAX_UPLOAD_BYTES, MAX_UPLOAD_RECORDS, SAMPLE_JSONL


WORKLOAD_VERSION = "phase6-local-controlled-v1"
CASE_FIXTURE_VERSION = "fixture-v1"
UPLOAD_SAMPLE_VERSION = "phase5-upload-v1"


def percentile(values: Iterable[float], fraction: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("percentile requires at least one value")
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("fraction must be between 0 and 1")
    if len(ordered) == 1:
        return round(ordered[0], 3)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    value = ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
    return round(value, 3)


def _latency_summary(values: List[float]) -> Dict[str, Any]:
    return {
        "samples": len(values),
        "p50_ms": percentile(values, 0.50),
        "p95_ms": percentile(values, 0.95),
        "min_ms": round(min(values), 3),
        "max_ms": round(max(values), 3),
    }


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def measure(samples: int = 20) -> Dict[str, Any]:
    """Run a fixed authored fixture, recovery, and upload workload."""

    if not 1 <= samples <= 100:
        raise ValueError("samples must be between 1 and 100")
    run_latencies: List[float] = []
    upload_latencies: List[float] = []
    completed = 0
    recovered = 0
    uploads_accepted = 0
    upload_records = 0
    body = SAMPLE_JSONL.encode("utf-8")

    with tempfile.NamedTemporaryFile(suffix=".sqlite3") as database:
        app = create_app(database.name)
        client = TestClient(app)
        try:
            session_response = client.post("/v1/sessions")
            session_response.raise_for_status()
            session_id = session_response.json()["session_id"]
            headers = {"X-Session-ID": session_id}

            for index in range(samples):
                started = time.perf_counter()
                response = client.post(
                    "/v1/runs",
                    headers={**headers, "Idempotency-Key": "phase6-run-%d" % index},
                    json={"session_id": session_id, "case_id": "checkout-failure", "service": "checkoutservice"},
                )
                response.raise_for_status()
                run_id = response.json()["run_id"]
                final = client.get("/v1/runs/%s" % run_id, headers=headers)
                final.raise_for_status()
                run_latencies.append((time.perf_counter() - started) * 1000.0)
                if final.json()["status"] == "succeeded":
                    completed += 1

                recovery = client.post(
                    "/v1/runs",
                    headers=headers,
                    json={"session_id": session_id, "case_id": "checkout-failure", "service": "checkoutservice", "defer": True},
                )
                recovery.raise_for_status()
                recovery_id = recovery.json()["run_id"]
                client.delete("/v1/runs/%s" % recovery_id, headers=headers).raise_for_status()
                retried = client.post("/v1/runs/%s/retry" % recovery_id, headers=headers)
                retried.raise_for_status()
                final_recovery = client.get("/v1/runs/%s" % recovery_id, headers=headers)
                final_recovery.raise_for_status()
                if final_recovery.json()["status"] == "succeeded":
                    recovered += 1

                upload_started = time.perf_counter()
                upload = client.post("/v1/uploads", headers={**headers, "Content-Type": "application/jsonl"}, content=body)
                upload.raise_for_status()
                upload_payload = upload.json()
                upload_latencies.append((time.perf_counter() - upload_started) * 1000.0)
                if upload_payload["validation"] == "accepted":
                    uploads_accepted += 1
                upload_records += int(upload_payload["record_count"])
        finally:
            client.close()
            app.state.store.close()

    return {
        "status": "measured",
        "measurement_version": WORKLOAD_VERSION,
        "workload": {
            "samples": samples,
            "case_id": "checkout-failure",
            "case_fixture_version": CASE_FIXTURE_VERSION,
            "run_workload": "create-and-complete-authored-fixture-run",
            "recovery_workload": "cancel-deferred-run-then-retry",
            "upload_sample_version": UPLOAD_SAMPLE_VERSION,
            "upload_content_type": "application/jsonl",
            "upload_body_bytes": len(body),
            "upload_records_per_request": 3,
            "upload_max_bytes": MAX_UPLOAD_BYTES,
            "upload_max_records": MAX_UPLOAD_RECORDS,
        },
        "latency_ms": {
            "run_create_to_complete": _latency_summary(run_latencies),
            "upload_validation": _latency_summary(upload_latencies),
        },
        "completion": {
            "attempted": samples,
            "completed": completed,
            "completion_rate": _rate(completed, samples),
        },
        "recovery": {
            "attempted": samples,
            "recovered_after_cancel_and_retry": recovered,
            "recovery_rate": _rate(recovered, samples),
        },
        "upload": {
            "attempted": samples,
            "accepted": uploads_accepted,
            "accepted_rate": _rate(uploads_accepted, samples),
            "records_processed": upload_records,
        },
        "not_measured": ["provider cost", "hosted provider latency", "live connector latency", "public deployment latency"],
        "held_out_evaluation": "sealed and not opened",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure the bounded local Incident Lens workload")
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = measure(args.samples)
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()


__all__ = ["measure", "percentile"]
