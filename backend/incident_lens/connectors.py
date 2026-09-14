"""Read-only connector boundary with explicit host and response bounds."""

import json
import hashlib
import os
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class ConnectorError(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ConnectorError("connector redirects are not permitted")


@dataclass(frozen=True)
class ConnectorResult:
    payload: Dict[str, Any]
    source_id: str
    source_version: str
    accessed_at: str
    access_scope: str
    endpoint: str
    content_type: str
    byte_size: int
    payload_sha256: str

    def as_metadata(self) -> Dict[str, Any]:
        """Return bounded verification metadata without returning the payload."""

        keys = sorted(self.payload)[:100]
        return {
            "status": "verified",
            "source_id": self.source_id,
            "source_version": self.source_version,
            "accessed_at": self.accessed_at,
            "access_scope": self.access_scope,
            "endpoint": self.endpoint,
            "content_type": self.content_type,
            "byte_size": self.byte_size,
            "top_level_keys": keys,
            "top_level_key_count": len(self.payload),
            "top_level_keys_truncated": len(keys) < len(self.payload),
            "payload_sha256": self.payload_sha256,
            "telemetry_origin": "connected_app",
        }


@dataclass(frozen=True)
class ConnectorStatus:
    status: str
    configured: bool
    reason: str
    allowed_hosts: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "configured": self.configured,
            "reason": self.reason,
            "allowed_hosts": list(self.allowed_hosts),
            "telemetry_origin": "connected_app",
        }


class ReadOnlyConnector:
    """A GET-only adapter; callers cannot issue mutations through this class."""

    def __init__(
        self,
        base_url: str,
        allowed_hosts: Iterable[str],
        *,
        source_id: str = "owned-maintained-app",
        source_version: str = "configured",
        access_scope: str = "connected_app",
        path: Optional[str] = None,
        timeout_seconds: float = 3.0,
        max_bytes: int = 2 * 1024 * 1024,
        require_https: bool = True,
    ) -> None:
        parsed = urlsplit(base_url)
        hosts = tuple(host.strip().lower() for host in allowed_hosts if host.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ConnectorError("connector base URL must be an http(s) URL without credentials")
        if parsed.hostname.lower() not in hosts:
            raise ConnectorError("connector host is not allowlisted")
        if require_https and parsed.scheme != "https":
            raise ConnectorError("connector requires HTTPS")
        if timeout_seconds <= 0 or timeout_seconds > 30:
            raise ConnectorError("connector timeout is outside the 0-30 second bound")
        if max_bytes <= 0 or max_bytes > 10 * 1024 * 1024:
            raise ConnectorError("connector response bound is outside the 10 MiB limit")
        self.base_url = base_url.rstrip("/") + "/"
        self._base = parsed
        self.allowed_hosts = hosts
        self.source_id = source_id
        self.source_version = source_version
        self.access_scope = access_scope
        self.path = path
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes
        self.require_https = require_https

    def _url(self, path: str) -> str:
        parsed_path = urlsplit(path)
        if not path or path.startswith("//") or "\\" in path or parsed_path.scheme or parsed_path.netloc:
            raise ConnectorError("connector path is invalid")
        target = urlsplit(urljoin(self.base_url, path))
        if target.scheme != self._base.scheme or target.hostname not in self.allowed_hosts:
            raise ConnectorError("connector target is not allowlisted")
        if target.port != self._base.port:
            raise ConnectorError("connector target port is not allowlisted")
        if self.require_https and target.scheme != "https":
            raise ConnectorError("connector requires HTTPS")
        return target.geturl()

    def get_json(self, path: Optional[str] = None) -> ConnectorResult:
        if self.path is not None:
            if path is not None and path != self.path:
                raise ConnectorError("connector path is fixed by configuration")
            path = self.path
        if path is None:
            raise ConnectorError("connector path is not configured")
        endpoint = self._url(path)
        request = Request(endpoint, method="GET", headers={"Accept": "application/json"})
        try:
            with build_opener(_NoRedirect()).open(request, timeout=self.timeout_seconds) as response:
                final = urlsplit(response.geturl())
                if final.hostname not in self.allowed_hosts or final.scheme != self._base.scheme:
                    raise ConnectorError("connector redirect target is not allowlisted")
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                if content_type and content_type != "application/json":
                    raise ConnectorError("connector response is not application/json")
                body = response.read(self.max_bytes + 1)
                if len(body) > self.max_bytes:
                    raise ConnectorError("connector response exceeds the configured bound")
        except (HTTPError, URLError, TimeoutError, socket.timeout) as exc:
            raise ConnectorError("read-only connector request failed") from exc
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConnectorError("connector response is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise ConnectorError("connector response must be a JSON object")
        return ConnectorResult(
            payload=payload,
            source_id=self.source_id,
            source_version=self.source_version,
            accessed_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            access_scope=self.access_scope,
            endpoint=endpoint,
            content_type=content_type or "application/json",
            byte_size=len(body),
            payload_sha256=hashlib.sha256(body).hexdigest(),
        )

    def verify(self) -> ConnectorResult:
        """Perform one bounded GET against the configured fixed path."""

        if self.path is None:
            raise ConnectorError("connector path is not configured")
        return self.get_json()


def connector_from_environment() -> Optional[ReadOnlyConnector]:
    base_url = os.getenv("INCIDENT_LENS_CONNECTOR_BASE_URL") or ""
    hosts = tuple(item for item in (os.getenv("INCIDENT_LENS_CONNECTOR_ALLOWED_HOSTS") or "").split(",") if item.strip())
    path = os.getenv("INCIDENT_LENS_CONNECTOR_PATH") or ""
    if not base_url or not hosts or not path:
        return None
    return ReadOnlyConnector(
        base_url,
        hosts,
        source_id=os.getenv("INCIDENT_LENS_CONNECTOR_SOURCE_ID", "owned-maintained-app"),
        source_version=os.getenv("INCIDENT_LENS_CONNECTOR_SOURCE_VERSION", "configured"),
        path=path,
        require_https=os.getenv("INCIDENT_LENS_CONNECTOR_ALLOW_HTTP", "") != "1",
    )


def connector_status() -> ConnectorStatus:
    base_url = os.getenv("INCIDENT_LENS_CONNECTOR_BASE_URL") or ""
    hosts = tuple(item.strip().lower() for item in (os.getenv("INCIDENT_LENS_CONNECTOR_ALLOWED_HOSTS") or "").split(",") if item.strip())
    path = os.getenv("INCIDENT_LENS_CONNECTOR_PATH") or ""
    if not base_url or not hosts or not path:
        return ConnectorStatus("blocked", False, "owned endpoint, fixed path, and host allowlist are not configured", hosts)
    try:
        connector_from_environment()
    except ConnectorError as exc:
        return ConnectorStatus("blocked", False, str(exc), hosts)
    return ConnectorStatus("blocked", True, "connector is configured but no live owned-app access has been verified", hosts)
