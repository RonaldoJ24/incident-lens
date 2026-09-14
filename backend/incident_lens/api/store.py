"""SQLite and PostgreSQL state stores for the Phase 1 slice.

Both backends expose the same relational operations and JSON provenance
payloads; PostgreSQL stores those payloads as JSONB.
"""

import json
import os
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


def parse_json(value: Any) -> Any:
    """Read JSON stored as text (SQLite) or native JSONB (PostgreSQL)."""

    return json.loads(value) if isinstance(value, str) else value


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
                CREATE TABLE IF NOT EXISTS workflow_checkpoints (
                  run_id TEXT PRIMARY KEY REFERENCES runs(run_id),
                  checkpoint_id TEXT NOT NULL,
                  state_json TEXT NOT NULL,
                  status TEXT NOT NULL,
                  updated_at TEXT NOT NULL
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

    def list_withheld_source_ids(self, run_id: str) -> List[str]:
        withheld: List[str] = []
        for correction in self.list_corrections(run_id):
            if correction.get("action") == "withhold_source":
                withheld.extend(correction.get("source_ids", []))
        return sorted(set(withheld))

    def save_checkpoint(self, run_id: str, checkpoint_id: str, state: Dict[str, Any], status: str) -> Dict[str, Any]:
        updated_at = iso(utc_now())
        with self.lock:
            self.connection.execute(
                """INSERT INTO workflow_checkpoints(run_id,checkpoint_id,state_json,status,updated_at)
                VALUES (?,?,?,?,?)
                ON CONFLICT(run_id) DO UPDATE SET checkpoint_id=excluded.checkpoint_id,
                  state_json=excluded.state_json,status=excluded.status,updated_at=excluded.updated_at""",
                (run_id, checkpoint_id, json_text(state), status, updated_at),
            )
            self.connection.commit()
        return {"run_id": run_id, "checkpoint_id": checkpoint_id, "state": state, "status": status, "updated_at": updated_at}

    def get_checkpoint(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            row = self.connection.execute("SELECT * FROM workflow_checkpoints WHERE run_id = ?", (run_id,)).fetchone()
        if not row:
            return None
        return {"run_id": row["run_id"], "checkpoint_id": row["checkpoint_id"], "state": parse_json(row["state_json"]), "status": row["status"], "updated_at": row["updated_at"]}

    def save_report(self, session_id: str, run_id: str, provenance: Dict[str, Any], finding_ids: List[str], idempotency_key: Optional[str]) -> Dict[str, Any]:
        with self.lock:
            owner = self.connection.execute("SELECT session_id FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if not owner or owner["session_id"] != session_id:
                raise ValueError("Report session does not own run")
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


class PostgresStateStore:
    """PostgreSQL state store with the same API as :class:`StateStore`.

    psycopg is imported only when this backend is selected, keeping SQLite-only
    unit tests independent of a PostgreSQL client or service.
    """

    def __init__(self, database_url: str, migration_dir: Optional[str] = None) -> None:
        try:
            import psycopg
            from psycopg.rows import dict_row
            from psycopg.types.json import Jsonb
        except ImportError as exc:  # pragma: no cover - exercised in setup failures
            raise RuntimeError("PostgreSQL requires the psycopg package; install the backend dependencies") from exc
        self._psycopg = psycopg
        self._Jsonb = Jsonb
        self.migration_dir = migration_dir
        self.connection = psycopg.connect(database_url, row_factory=dict_row)
        self.lock = threading.RLock()
        from incident_lens.migrations import apply_migrations

        apply_migrations(self.connection, migration_dir=migration_dir)

    def close(self) -> None:
        with self.lock:
            self.connection.close()

    def create_schema(self) -> None:
        """Keep the SQLite-compatible store lifecycle for callers that expect it."""

        from incident_lens.migrations import apply_migrations

        with self.lock:
            apply_migrations(self.connection, migration_dir=self.migration_dir)

    @staticmethod
    def _row_value(row: Any, key: str) -> Any:
        return row[key]

    def seed_cases(self, cases: Iterable[FixtureCase]) -> None:
        with self.lock, self.connection.transaction():
            for case in cases:
                self.connection.execute(
                    """INSERT INTO cases
                    (case_id,title,description,service,fixture_key,telemetry_origin,source_interval_json,fixture_kind,public_example)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (case_id) DO NOTHING""",
                    (
                        case.case_id,
                        case.title,
                        case.description,
                        case.service,
                        case.case_id,
                        "controlled_runtime",
                        self._Jsonb(case.source_interval_payload),
                        case.fixture_kind,
                        True,
                    ),
                )

    def create_session(self) -> Dict[str, Any]:
        now = utc_now()
        session = {
            "session_id": "sess-" + uuid.uuid4().hex[:12],
            "created_at": iso(now),
            "expires_at": iso(now + timedelta(hours=1)),
            "isolation_scope": "guest",
        }
        with self.lock, self.connection.transaction():
            self.connection.execute(
                "INSERT INTO sessions(session_id,created_at,expires_at,isolation_scope) VALUES (%s,%s,%s,%s)",
                tuple(session.values()),
            )
        return session

    def session_exists(self, session_id: str) -> bool:
        with self.lock, self.connection.transaction():
            row = self.connection.execute("SELECT 1 FROM sessions WHERE session_id = %s", (session_id,)).fetchone()
        return row is not None

    def list_cases(self) -> List[Dict[str, Any]]:
        with self.lock, self.connection.transaction():
            return list(self.connection.execute("SELECT * FROM cases ORDER BY case_id").fetchall())

    def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        with self.lock, self.connection.transaction():
            return self.connection.execute("SELECT * FROM cases WHERE case_id = %s", (case_id,)).fetchone()

    def create_run(self, session_id: str, case_id: str, provenance: Dict[str, Any], idempotency_key: Optional[str]) -> Dict[str, Any]:
        now = utc_now()
        run_id = "run-" + uuid.uuid4().hex[:12]
        with self.lock, self.connection.transaction():
            row = None
            if idempotency_key:
                row = self.connection.execute(
                    "SELECT * FROM runs WHERE session_id = %s AND idempotency_key = %s",
                    (session_id, idempotency_key),
                ).fetchone()
            if row:
                return dict(row)
            row = self.connection.execute(
                """INSERT INTO runs(run_id,session_id,case_id,status,attempt,provenance_json,created_at,updated_at,idempotency_key)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (session_id, idempotency_key) DO NOTHING
                RETURNING *""",
                (run_id, session_id, case_id, "queued", 1, self._Jsonb(provenance), now, now, idempotency_key),
            ).fetchone()
            if row:
                return dict(row)
            # Another request won the idempotency race. The transaction is
            # still healthy because the conflict was handled by PostgreSQL.
            return dict(
                self.connection.execute(
                    "SELECT * FROM runs WHERE session_id = %s AND idempotency_key = %s",
                    (session_id, idempotency_key),
                ).fetchone()
            )

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self.lock, self.connection.transaction():
            return self.connection.execute("SELECT * FROM runs WHERE run_id = %s", (run_id,)).fetchone()

    def update_run(self, run_id: str, status: str, provenance: Optional[Dict[str, Any]] = None, increment_attempt: bool = False) -> Optional[Dict[str, Any]]:
        now = utc_now()
        with self.lock, self.connection.transaction():
            row = self.connection.execute("SELECT attempt, provenance_json FROM runs WHERE run_id = %s FOR UPDATE", (run_id,)).fetchone()
            if not row:
                return None
            attempt = row["attempt"] + (1 if increment_attempt else 0)
            updated = self.connection.execute(
                """UPDATE runs SET status = %s, attempt = %s, provenance_json = %s, updated_at = %s
                WHERE run_id = %s RETURNING *""",
                (status, attempt, self._Jsonb(provenance if provenance is not None else row["provenance_json"]), now, run_id),
            ).fetchone()
        return dict(updated) if updated else None

    def _next_sequence(self, table: str, run_id: str) -> int:
        if table not in {"timeline_events", "evidence", "corrections"}:
            raise ValueError("unsupported sequence table")
        self.connection.execute("SELECT run_id FROM runs WHERE run_id = %s FOR UPDATE", (run_id,)).fetchone()
        row = self.connection.execute("SELECT COALESCE(MAX(sequence), -1) + 1 AS next_sequence FROM %s WHERE run_id = %%s" % table, (run_id,)).fetchone()
        return int(row["next_sequence"])

    def insert_timeline(self, run_id: str, payload: Dict[str, Any]) -> None:
        with self.lock, self.connection.transaction():
            self.connection.execute(
                "INSERT INTO timeline_events(event_id,run_id,payload_json,sequence) VALUES (%s,%s,%s,%s)",
                (payload["event_id"], run_id, self._Jsonb(payload), self._next_sequence("timeline_events", run_id)),
            )

    def insert_evidence(self, run_id: str, payload: Dict[str, Any]) -> None:
        with self.lock, self.connection.transaction():
            self.connection.execute(
                "INSERT INTO evidence(evidence_id,run_id,payload_json,sequence) VALUES (%s,%s,%s,%s)",
                (payload["evidence_id"], run_id, self._Jsonb(payload), self._next_sequence("evidence", run_id)),
            )

    def insert_finding(self, run_id: str, payload: Dict[str, Any]) -> None:
        with self.lock, self.connection.transaction():
            self.connection.execute(
                "INSERT INTO findings(finding_id,run_id,payload_json) VALUES (%s,%s,%s)",
                (payload["finding_id"], run_id, self._Jsonb(payload)),
            )

    def insert_correction(self, run_id: str, payload: Dict[str, Any]) -> None:
        with self.lock, self.connection.transaction():
            self.connection.execute(
                "INSERT INTO corrections(correction_id,run_id,payload_json,sequence) VALUES (%s,%s,%s,%s)",
                (payload["correction_id"], run_id, self._Jsonb(payload), self._next_sequence("corrections", run_id)),
            )

    def _payloads(self, table: str, run_id: str) -> List[Dict[str, Any]]:
        if table not in {"evidence", "timeline_events", "corrections"}:
            raise ValueError("unsupported payload table")
        with self.lock, self.connection.transaction():
            rows = self.connection.execute("SELECT payload_json FROM %s WHERE run_id = %%s ORDER BY sequence" % table, (run_id,)).fetchall()
        return [parse_json(row["payload_json"]) for row in rows]

    def list_evidence(self, run_id: str) -> List[Dict[str, Any]]:
        return self._payloads("evidence", run_id)

    def list_findings(self, run_id: str) -> List[Dict[str, Any]]:
        with self.lock, self.connection.transaction():
            rows = self.connection.execute("SELECT payload_json FROM findings WHERE run_id = %s ORDER BY finding_id", (run_id,)).fetchall()
        return [parse_json(row["payload_json"]) for row in rows]

    def list_timeline(self, run_id: str) -> List[Dict[str, Any]]:
        return self._payloads("timeline_events", run_id)

    def list_corrections(self, run_id: str) -> List[Dict[str, Any]]:
        return self._payloads("corrections", run_id)

    def list_withheld_source_ids(self, run_id: str) -> List[str]:
        withheld: List[str] = []
        for correction in self.list_corrections(run_id):
            if correction.get("action") == "withhold_source":
                withheld.extend(correction.get("source_ids", []))
        return sorted(set(withheld))

    def save_checkpoint(self, run_id: str, checkpoint_id: str, state: Dict[str, Any], status: str) -> Dict[str, Any]:
        updated_at = utc_now()
        with self.lock, self.connection.transaction():
            self.connection.execute(
                """INSERT INTO workflow_checkpoints(run_id,checkpoint_id,state_json,status,updated_at)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (run_id) DO UPDATE SET checkpoint_id=EXCLUDED.checkpoint_id,
                  state_json=EXCLUDED.state_json,status=EXCLUDED.status,updated_at=EXCLUDED.updated_at""",
                (run_id, checkpoint_id, self._Jsonb(state), status, updated_at),
            )
        return {"run_id": run_id, "checkpoint_id": checkpoint_id, "state": state, "status": status, "updated_at": iso(updated_at)}

    def get_checkpoint(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self.lock, self.connection.transaction():
            row = self.connection.execute("SELECT * FROM workflow_checkpoints WHERE run_id = %s", (run_id,)).fetchone()
        if not row:
            return None
        return {"run_id": row["run_id"], "checkpoint_id": row["checkpoint_id"], "state": parse_json(row["state_json"]), "status": row["status"], "updated_at": iso(row["updated_at"])}

    def save_report(self, session_id: str, run_id: str, provenance: Dict[str, Any], finding_ids: List[str], idempotency_key: Optional[str]) -> Dict[str, Any]:
        report_id = "report-" + uuid.uuid4().hex[:12]
        with self.lock, self.connection.transaction():
            owner = self.connection.execute("SELECT session_id FROM runs WHERE run_id = %s FOR UPDATE", (run_id,)).fetchone()
            if not owner or owner["session_id"] != session_id:
                raise ValueError("Report session does not own run")
            if idempotency_key:
                existing = self.connection.execute(
                    "SELECT * FROM reports WHERE session_id = %s AND idempotency_key = %s",
                    (session_id, idempotency_key),
                ).fetchone()
                if existing:
                    return dict(existing)
            # The ownership query above also serializes revision allocation.
            revision_row = self.connection.execute("SELECT COALESCE(MAX(revision), 0) + 1 AS revision FROM reports WHERE run_id = %s", (run_id,)).fetchone()
            inserted = self.connection.execute(
                """INSERT INTO reports(report_id,session_id,run_id,revision,provenance_json,finding_ids_json,saved_at,repair_claim,idempotency_key)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (session_id, idempotency_key) DO NOTHING
                RETURNING *""",
                (report_id, session_id, run_id, int(revision_row["revision"]), self._Jsonb(provenance), self._Jsonb(finding_ids), utc_now(), False, idempotency_key),
            ).fetchone()
            if inserted:
                return dict(inserted)
            return dict(self.connection.execute("SELECT * FROM reports WHERE session_id = %s AND idempotency_key = %s", (session_id, idempotency_key)).fetchone())

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        with self.lock, self.connection.transaction():
            return self.connection.execute("SELECT * FROM reports WHERE report_id = %s", (report_id,)).fetchone()


def select_store(db_path: Optional[str] = None, database_url: Optional[str] = None) -> Any:
    """Select PostgreSQL when configured; otherwise retain the local SQLite path."""

    if db_path is not None:
        return StateStore(db_path)
    configured_url = database_url or os.getenv("INCIDENT_LENS_DATABASE_URL")
    if configured_url:
        return PostgresStateStore(configured_url)
    return StateStore(os.getenv("INCIDENT_LENS_SQLITE_PATH", "/tmp/incident-lens-phase1.sqlite3"))
