"""SQLite state store for the local Phase 1 slice.

The schema is intentionally relational and portable. A future PostgreSQL
migration can retain the same tables and JSON provenance payloads.
"""

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from incident_lens.fixtures.loader import FixtureCase


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def json_text(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


class StateStore:
    """Thread-safe SQLite store with guest-session ownership on every record."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or ":memory:"
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.create_schema()

    def close(self) -> None:
        with self.lock:
            self.connection.close()

    def create_schema(self) -> None:
        with self.lock:
            self.connection.executescript(
                """
                PRAGMA foreign_keys = ON;
                CREATE TABLE IF NOT EXISTS sessions (
                  session_id TEXT PRIMARY KEY,
                  created_at TEXT NOT NULL,
                  expires_at TEXT NOT NULL,
                  isolation_scope TEXT NOT NULL CHECK (isolation_scope = 'guest')
                );
                CREATE TABLE IF NOT EXISTS cases (
                  case_id TEXT PRIMARY KEY,
                  title TEXT NOT NULL,
                  description TEXT NOT NULL,
                  service TEXT NOT NULL,
                  fixture_key TEXT NOT NULL,
                  telemetry_origin TEXT NOT NULL,
                  source_interval_json TEXT NOT NULL,
                  fixture_kind TEXT NOT NULL,
                  public_example INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                  run_id TEXT PRIMARY KEY,
                  session_id TEXT NOT NULL REFERENCES sessions(session_id),
                  case_id TEXT NOT NULL REFERENCES cases(case_id),
                  status TEXT NOT NULL,
                  attempt INTEGER NOT NULL,
                  provenance_json TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  idempotency_key TEXT,
                  UNIQUE(session_id, idempotency_key)
                );
                CREATE TABLE IF NOT EXISTS evidence (
                  evidence_id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL REFERENCES runs(run_id),
                  payload_json TEXT NOT NULL,
                  sequence INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS findings (
                  finding_id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL REFERENCES runs(run_id),
                  payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS timeline_events (
                  event_id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL REFERENCES runs(run_id),
                  payload_json TEXT NOT NULL,
                  sequence INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS corrections (
                  correction_id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL REFERENCES runs(run_id),
                  payload_json TEXT NOT NULL,
                  sequence INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reports (
                  report_id TEXT PRIMARY KEY,
                  session_id TEXT NOT NULL REFERENCES sessions(session_id),
                  run_id TEXT NOT NULL REFERENCES runs(run_id),
                  revision INTEGER NOT NULL,
                  provenance_json TEXT NOT NULL,
                  finding_ids_json TEXT NOT NULL,
                  saved_at TEXT NOT NULL,
                  repair_claim INTEGER NOT NULL CHECK (repair_claim = 0),
                  idempotency_key TEXT,
                  UNIQUE(session_id, idempotency_key)
                );
                """
            )
            self.connection.commit()

    def seed_cases(self, cases: Iterable[FixtureCase]) -> None:
        with self.lock:
            for case in cases:
                self.connection.execute(
                    """INSERT OR IGNORE INTO cases
                    (case_id,title,description,service,fixture_key,telemetry_origin,source_interval_json,fixture_kind,public_example)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        case.case_id,
                        case.title,
                        case.description,
                        case.service,
                        case.case_id,
                        "controlled_runtime",
                        json_text(case.source_interval_payload),
                        case.fixture_kind,
                        1,
                    ),
                )
            self.connection.commit()

    def create_session(self) -> Dict[str, Any]:
        now = utc_now()
        session = {
            "session_id": "sess-" + uuid.uuid4().hex[:12],
            "created_at": iso(now),
            "expires_at": iso(now + timedelta(hours=1)),
            "isolation_scope": "guest",
        }
        with self.lock:
            self.connection.execute(
                "INSERT INTO sessions(session_id,created_at,expires_at,isolation_scope) VALUES (?,?,?,?)",
                tuple(session.values()),
            )
            self.connection.commit()
        return session

    def session_exists(self, session_id: str) -> bool:
        with self.lock:
            row = self.connection.execute("SELECT 1 FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        return row is not None

    def list_cases(self) -> List[sqlite3.Row]:
        with self.lock:
            return list(self.connection.execute("SELECT * FROM cases ORDER BY case_id"))

    def get_case(self, case_id: str) -> Optional[sqlite3.Row]:
        with self.lock:
            return self.connection.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()

    def create_run(self, session_id: str, case_id: str, provenance: Dict[str, Any], idempotency_key: Optional[str]) -> Dict[str, Any]:
        now = iso(utc_now())
        with self.lock:
            if idempotency_key:
                existing = self.connection.execute(
                    "SELECT * FROM runs WHERE session_id = ? AND idempotency_key = ?",
                    (session_id, idempotency_key),
                ).fetchone()
                if existing:
                    return dict(existing)
            run_id = "run-" + uuid.uuid4().hex[:12]
            try:
                self.connection.execute(
                    """INSERT INTO runs(run_id,session_id,case_id,status,attempt,provenance_json,created_at,updated_at,idempotency_key)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (run_id, session_id, case_id, "queued", 1, json_text(provenance), now, now, idempotency_key),
                )
                self.connection.commit()
            except sqlite3.IntegrityError:
                existing = self.connection.execute(
                    "SELECT * FROM runs WHERE session_id = ? AND idempotency_key = ?",
                    (session_id, idempotency_key),
                ).fetchone()
                if existing:
                    return dict(existing)
                raise
            return self.get_run(run_id)  # type: ignore[return-value]

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            row = self.connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return dict(row) if row else None

    def update_run(self, run_id: str, status: str, provenance: Optional[Dict[str, Any]] = None, increment_attempt: bool = False) -> Optional[Dict[str, Any]]:
        now = iso(utc_now())
        with self.lock:
            row = self.connection.execute("SELECT attempt, provenance_json FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if not row:
                return None
            attempt = row["attempt"] + (1 if increment_attempt else 0)
            self.connection.execute(
                "UPDATE runs SET status = ?, attempt = ?, provenance_json = ?, updated_at = ? WHERE run_id = ?",
                (status, attempt, json_text(provenance) if provenance is not None else row["provenance_json"], now, run_id),
            )
            self.connection.commit()
        return self.get_run(run_id)

    def _next_sequence(self, table: str, run_id: str) -> int:
        row = self.connection.execute("SELECT COALESCE(MAX(sequence), -1) + 1 FROM %s WHERE run_id = ?" % table, (run_id,)).fetchone()
        return int(row[0])

    def insert_timeline(self, run_id: str, payload: Dict[str, Any]) -> None:
        with self.lock:
            self.connection.execute(
                "INSERT INTO timeline_events(event_id,run_id,payload_json,sequence) VALUES (?,?,?,?)",
                (payload["event_id"], run_id, json_text(payload), self._next_sequence("timeline_events", run_id)),
            )
            self.connection.commit()

    def insert_evidence(self, run_id: str, payload: Dict[str, Any]) -> None:
        with self.lock:
            self.connection.execute(
                "INSERT INTO evidence(evidence_id,run_id,payload_json,sequence) VALUES (?,?,?,?)",
                (payload["evidence_id"], run_id, json_text(payload), self._next_sequence("evidence", run_id)),
            )
            self.connection.commit()

    def insert_finding(self, run_id: str, payload: Dict[str, Any]) -> None:
        with self.lock:
            self.connection.execute(
                "INSERT INTO findings(finding_id,run_id,payload_json) VALUES (?,?,?)",
                (payload["finding_id"], run_id, json_text(payload)),
            )
            self.connection.commit()

    def insert_correction(self, run_id: str, payload: Dict[str, Any]) -> None:
        with self.lock:
            self.connection.execute(
                "INSERT INTO corrections(correction_id,run_id,payload_json,sequence) VALUES (?,?,?,?)",
                (payload["correction_id"], run_id, json_text(payload), self._next_sequence("corrections", run_id)),
            )
            self.connection.commit()

    def _payloads(self, table: str, run_id: str) -> List[Dict[str, Any]]:
        with self.lock:
            rows = self.connection.execute("SELECT payload_json FROM %s WHERE run_id = ? ORDER BY sequence" % table, (run_id,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def list_evidence(self, run_id: str) -> List[Dict[str, Any]]:
        return self._payloads("evidence", run_id)

    def list_findings(self, run_id: str) -> List[Dict[str, Any]]:
        with self.lock:
            rows = self.connection.execute("SELECT payload_json FROM findings WHERE run_id = ? ORDER BY finding_id", (run_id,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def list_timeline(self, run_id: str) -> List[Dict[str, Any]]:
        return self._payloads("timeline_events", run_id)

    def list_corrections(self, run_id: str) -> List[Dict[str, Any]]:
        return self._payloads("corrections", run_id)

    def save_report(self, session_id: str, run_id: str, provenance: Dict[str, Any], finding_ids: List[str], idempotency_key: Optional[str]) -> Dict[str, Any]:
        with self.lock:
            if idempotency_key:
                existing = self.connection.execute(
                    "SELECT * FROM reports WHERE session_id = ? AND idempotency_key = ?",
                    (session_id, idempotency_key),
                ).fetchone()
                if existing:
                    return dict(existing)
            report_id = "report-" + uuid.uuid4().hex[:12]
            row = self.connection.execute("SELECT COALESCE(MAX(revision), 0) + 1 FROM reports WHERE run_id = ?", (run_id,)).fetchone()
            revision = int(row[0])
            saved_at = iso(utc_now())
            self.connection.execute(
                """INSERT INTO reports(report_id,session_id,run_id,revision,provenance_json,finding_ids_json,saved_at,repair_claim,idempotency_key)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (report_id, session_id, run_id, revision, json_text(provenance), json_text(finding_ids), saved_at, 0, idempotency_key),
            )
            self.connection.commit()
            return dict(self.connection.execute("SELECT * FROM reports WHERE report_id = ?", (report_id,)).fetchone())

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            row = self.connection.execute("SELECT * FROM reports WHERE report_id = ?", (report_id,)).fetchone()
        return dict(row) if row else None
