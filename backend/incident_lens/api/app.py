"""Small API metadata surface used until the Phase 1 HTTP server exists."""

from incident_lens import CONTRACT_VERSION


def metadata() -> dict[str, str]:
    """Return truthful API metadata without implying an available endpoint."""

    return {
        "name": "Incident Lens API",
        "contract_version": CONTRACT_VERSION,
        "status": "foundation_scaffold",
    }
