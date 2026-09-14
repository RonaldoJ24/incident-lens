"""Object-storage keys and PostgreSQL reference records.

Only references live in PostgreSQL.  Raw telemetry and large normalized files
remain private objects.  Keys contain a neutral case ID and never the upstream
case directory, which encodes the benchmark answer.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


class ArtifactAccessError(ValueError):
    """Raised when a raw/derived object is outside the caller's scope."""


_NEUTRAL_CASE = re.compile(r"^dev-re2ob-\d{3}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_KEY = re.compile(r"^[a-z0-9._/-]+$")


def _case(case_id: str) -> str:
    if not _NEUTRAL_CASE.fullmatch(case_id):
        raise ArtifactAccessError("artifact key requires a neutral case ID")
    return case_id


def raw_key(source_revision: str, case_id: str, filename: str) -> str:
    """Stable private raw key; callers must pass a filename, not a path."""

    if not re.fullmatch(r"[0-9a-f]{40}", source_revision):
        raise ArtifactAccessError("raw key requires a pinned source revision")
    if filename not in {"metrics.parquet", "logs.parquet", "traces.parquet", "inject_time.txt"}:
        raise ArtifactAccessError("unsupported raw artifact")
    return "raw/rcaeval/%s/%s/%s" % (source_revision, _case(case_id), filename)


def derived_key(kind: str, version: str, case_id: str, digest: str, extension: str = "json") -> str:
    if kind not in {"normalized", "quality", "manifest"}:
        raise ArtifactAccessError("unsupported derived artifact kind")
    if not re.fullmatch(r"v[0-9]+", version):
        raise ArtifactAccessError("derived key requires a version")
    if not _SHA256.fullmatch(digest):
        raise ArtifactAccessError("derived key requires a SHA-256 digest")
    if not re.fullmatch(r"[a-z0-9]+", extension):
        raise ArtifactAccessError("invalid artifact extension")
    return "derived/%s/%s/%s/%s.%s" % (kind, version, _case(case_id), digest, extension)


def validate_private_key(key: str, *, case_id: str, allow_raw: bool = True) -> None:
    """Reject traversal, foreign case keys, and public access to raw data."""

    if not isinstance(key, str) or not _KEY.fullmatch(key) or ".." in key.split("/"):
        raise ArtifactAccessError("invalid object key")
    neutral = _case(case_id)
    parts = key.split("/")
    if len(parts) < 4 or parts[0] not in {"raw", "derived"} or neutral not in parts:
        raise ArtifactAccessError("artifact is outside the case scope")
    if parts[0] == "raw" and not allow_raw:
        raise ArtifactAccessError("raw telemetry is private")
    if parts[0] == "raw" and "rcaeval" not in parts:
        raise ArtifactAccessError("unknown raw source")


@dataclass(frozen=True)
class ArtifactReference:
    """The row persisted in PostgreSQL, not the object bytes themselves."""

    artifact_id: str
    case_id: str
    artifact_kind: str
    bucket: str
    object_key: str
    sha256: str
    byte_size: int
    source_version: str
    manifest_hash: Optional[str]
    access_scope: str = "private"
    created_at: str = ""

    def __post_init__(self) -> None:
        _case(self.case_id)
        validate_private_key(self.object_key, case_id=self.case_id)
        if not _SHA256.fullmatch(self.sha256):
            raise ArtifactAccessError("artifact reference requires a SHA-256 digest")
        if self.byte_size < 0:
            raise ArtifactAccessError("artifact byte size cannot be negative")
        if self.access_scope not in {"private", "guest_session", "public_derived"}:
            raise ArtifactAccessError("unsupported artifact access scope")
        if self.created_at:
            try:
                datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ArtifactAccessError("artifact created_at must be ISO-8601") from exc

    @classmethod
    def new(
        cls,
        artifact_id: str,
        case_id: str,
        artifact_kind: str,
        bucket: str,
        object_key: str,
        content: bytes,
        source_version: str,
        manifest_hash: Optional[str] = None,
        access_scope: str = "private",
    ) -> "ArtifactReference":
        return cls(
            artifact_id=artifact_id,
            case_id=case_id,
            artifact_kind=artifact_kind,
            bucket=bucket,
            object_key=object_key,
            sha256=hashlib.sha256(content).hexdigest(),
            byte_size=len(content),
            source_version=source_version,
            manifest_hash=manifest_hash,
            access_scope=access_scope,
            created_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        )

    def as_postgres_record(self) -> dict:
        """Return columns for the artifact_references migration."""

        return {
            "artifact_id": self.artifact_id,
            "case_id": self.case_id,
            "artifact_kind": self.artifact_kind,
            "object_bucket": self.bucket,
            "object_key": self.object_key,
            "sha256": self.sha256,
            "byte_size": self.byte_size,
            "source_version": self.source_version,
            "manifest_hash": self.manifest_hash,
            "access_scope": self.access_scope,
            "created_at": self.created_at,
        }


__all__ = [
    "ArtifactAccessError",
    "ArtifactReference",
    "derived_key",
    "raw_key",
    "validate_private_key",
]
