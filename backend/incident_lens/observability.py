"""Small dependency-free request metrics hook for local and release checks."""

from __future__ import annotations

import time
from collections import Counter
from threading import Lock
from typing import Any, Awaitable, Callable, Dict, List, MutableMapping


class RequestMetrics:
    """Bounded in-process counters; no request bodies or credentials are stored."""

    def __init__(self, max_samples: int = 2000) -> None:
        self.max_samples = max_samples
        self._lock = Lock()
        self._requests = 0
        self._errors = 0
        self._status = Counter()
        self._durations: List[float] = []

    def observe(self, path: str, status: int, duration_ms: float) -> None:
        del path  # Paths are deliberately not retained to avoid high-cardinality labels.
        with self._lock:
            self._requests += 1
            if status >= 500:
                self._errors += 1
            self._status[status] += 1
            self._durations.append(max(0.0, duration_ms))
            if len(self._durations) > self.max_samples:
                del self._durations[: len(self._durations) - self.max_samples]

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "requests_total": self._requests,
                "errors_total": self._errors,
                "status_counts": dict(self._status),
                "duration_samples": len(self._durations),
            }

    def prometheus(self) -> str:
        snapshot = self.snapshot()
        lines = [
            "# HELP incident_lens_http_requests_total HTTP requests observed by the process.",
            "# TYPE incident_lens_http_requests_total counter",
            "incident_lens_http_requests_total %d" % snapshot["requests_total"],
            "# HELP incident_lens_http_errors_total HTTP 5xx responses observed by the process.",
            "# TYPE incident_lens_http_errors_total counter",
            "incident_lens_http_errors_total %d" % snapshot["errors_total"],
            "# HELP incident_lens_http_response_status_total HTTP responses by status code.",
            "# TYPE incident_lens_http_response_status_total counter",
        ]
        for status, count in sorted(snapshot["status_counts"].items()):
            lines.append('incident_lens_http_response_status_total{status="%s"} %d' % (status, count))
        lines.extend([
            "# HELP incident_lens_http_duration_samples Number of bounded duration samples retained.",
            "# TYPE incident_lens_http_duration_samples gauge",
            "incident_lens_http_duration_samples %d" % snapshot["duration_samples"],
        ])
        return "\n".join(lines) + "\n"


class MetricsMiddleware:
    """ASGI middleware that records status and duration without logging content."""

    def __init__(self, app: Callable[..., Awaitable[Any]], metrics: RequestMetrics) -> None:
        self.app = app
        self.metrics = metrics

    async def __call__(self, scope: MutableMapping[str, Any], receive: Callable[..., Awaitable[Any]], send: Callable[..., Awaitable[Any]]) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status = 500

        async def capture(message: Dict[str, Any]) -> None:
            nonlocal status
            if message.get("type") == "http.response.start":
                status = int(message.get("status", 500))
            await send(message)

        try:
            await self.app(scope, receive, capture)
        finally:
            self.metrics.observe(str(scope.get("path", "")), status, (time.perf_counter() - started) * 1000.0)


__all__ = ["MetricsMiddleware", "RequestMetrics"]
