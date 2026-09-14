"""Typed run states shared by the future API and worker."""

from enum import Enum


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PARTIAL = "partial"
    SUCCEEDED = "succeeded"
    UNRESOLVED = "unresolved"
    FAILED = "failed"
    CANCELLED = "cancelled"
