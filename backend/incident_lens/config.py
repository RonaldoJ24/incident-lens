"""Environment-only configuration with an explicit secret boundary."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Settings:
    environment: str = "local"
    api_origin: str = "http://localhost:8000"
    cors_allowed_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "https://ronaldoj24.github.io",
    )
    database_url: Optional[str] = None
    object_store_bucket: Optional[str] = None
    provider_api_key: Optional[str] = None
    # OpenAI-compatible defaults point at the verified DeepSeek API shape,
    # while every value remains environment-overridable for another provider.
    provider_base_url: str = "https://api.deepseek.com"
    provider_model: str = "deepseek-flash"
    provider_timeout_seconds: float = 8.0
    provider_max_input_tokens: int = 1400
    provider_max_context_tokens: int = 1000
    provider_max_output_tokens: int = 320
    provider_max_retries: int = 1
    provider_max_calls_per_process: int = 32
    provider_disable_thinking: bool = True


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_origins(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if value is None:
        return default
    return tuple(dict.fromkeys(item.strip().rstrip("/") for item in value.split(",") if item.strip()))


def load_settings() -> Settings:
    """Read names from the process environment; never read a credentials file."""

    return Settings(
        environment=os.getenv("INCIDENT_LENS_ENV", "local"),
        api_origin=os.getenv("INCIDENT_LENS_API_ORIGIN", "http://localhost:8000"),
        cors_allowed_origins=_env_origins(
            "INCIDENT_LENS_CORS_ALLOWED_ORIGINS",
            Settings.cors_allowed_origins,
        ),
        database_url=os.getenv("INCIDENT_LENS_DATABASE_URL") or None,
        object_store_bucket=os.getenv("INCIDENT_LENS_OBJECT_STORE_BUCKET") or None,
        provider_api_key=os.getenv("INCIDENT_LENS_PROVIDER_API_KEY") or None,
        provider_base_url=os.getenv("INCIDENT_LENS_PROVIDER_BASE_URL", "https://api.deepseek.com").rstrip("/"),
        provider_model=os.getenv("INCIDENT_LENS_PROVIDER_MODEL", "deepseek-flash"),
        provider_timeout_seconds=float(os.getenv("INCIDENT_LENS_PROVIDER_TIMEOUT_SECONDS", "8")),
        provider_max_input_tokens=int(os.getenv("INCIDENT_LENS_PROVIDER_MAX_INPUT_TOKENS", "1400")),
        provider_max_context_tokens=int(os.getenv("INCIDENT_LENS_PROVIDER_MAX_CONTEXT_TOKENS", "1000")),
        provider_max_output_tokens=int(os.getenv("INCIDENT_LENS_PROVIDER_MAX_OUTPUT_TOKENS", "320")),
        provider_max_retries=int(os.getenv("INCIDENT_LENS_PROVIDER_MAX_RETRIES", "1")),
        provider_max_calls_per_process=int(os.getenv("INCIDENT_LENS_PROVIDER_MAX_CALLS_PER_PROCESS", "32")),
        provider_disable_thinking=_env_bool("INCIDENT_LENS_PROVIDER_DISABLE_THINKING", True),
    )
