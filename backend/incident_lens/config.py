"""Environment-only configuration with an explicit secret boundary."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Settings:
    environment: str = "local"
    api_origin: str = "http://localhost:8000"
    database_url: Optional[str] = None
    object_store_bucket: Optional[str] = None
    provider_api_key: Optional[str] = None


def load_settings() -> Settings:
    """Read names from the process environment; never read a credentials file."""

    return Settings(
        environment=os.getenv("INCIDENT_LENS_ENV", "local"),
        api_origin=os.getenv("INCIDENT_LENS_API_ORIGIN", "http://localhost:8000"),
        database_url=os.getenv("INCIDENT_LENS_DATABASE_URL") or None,
        object_store_bucket=os.getenv("INCIDENT_LENS_OBJECT_STORE_BUCKET") or None,
        provider_api_key=os.getenv("INCIDENT_LENS_PROVIDER_API_KEY") or None,
    )
