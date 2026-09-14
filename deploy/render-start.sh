#!/bin/sh
set -eu

neon_env=/etc/secrets/neon.env
deepseek_env=/etc/secrets/deepseek.env
test -r "$neon_env" || { echo "missing Render secret file: $neon_env" >&2; exit 1; }
test -r "$deepseek_env" || { echo "missing Render secret file: $deepseek_env" >&2; exit 1; }

# Secret files contain shell assignments only. Values are never printed or put
# in command arguments; the migration runner reads the temporary environment.
set -a
. "$neon_env"
. "$deepseek_env"
set +a
test -n "${DATABASE_URL_UNPOOLED:-}" || { echo "missing unpooled database URL" >&2; exit 1; }
test -n "${DATABASE_URL:-}" || { echo "missing pooled database URL" >&2; exit 1; }
test -n "${INCIDENT_LENS_PROVIDER_API_KEY:-}" || { echo "missing provider API key" >&2; exit 1; }

INCIDENT_LENS_DATABASE_URL="$DATABASE_URL_UNPOOLED" uv run --project backend python -m incident_lens.migrations
export INCIDENT_LENS_DATABASE_URL="$DATABASE_URL"
exec uv run --project backend uvicorn incident_lens.api.app:app --host 0.0.0.0 --port "${PORT:-10000}"
