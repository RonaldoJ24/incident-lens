# Local configuration and secret boundary

The checked-in [`.env.example`](../.env.example) contains names only. Copy it
to an untracked `.env` for local overrides; `.env`, secret directories, raw
telemetry, uploads, derived artifacts, and model artifacts are ignored by Git.
When `INCIDENT_LENS_DATABASE_URL` is set, the API selects its PostgreSQL store.
When it is blank, `INCIDENT_LENS_SQLITE_PATH` (or its documented default) keeps
zero-service local development available.

Configuration is read at process startup and is scoped to the local process:

| Variable | Purpose | Secret? | Phase 0 default |
| --- | --- | --- | --- |
| `INCIDENT_LENS_ENV` | Runtime environment label | No | `local` |
| `INCIDENT_LENS_API_ORIGIN` | Browser API origin | No | `http://localhost:8000` |
| `INCIDENT_LENS_DATABASE_URL` | PostgreSQL connection; selects the PostgreSQL store when set | Yes | unset (SQLite fallback) |
| `INCIDENT_LENS_SQLITE_PATH` | SQLite path used when no PostgreSQL URL is set | No | `/tmp/incident-lens-phase1.sqlite3` |
| `INCIDENT_LENS_OBJECT_STORE_BUCKET` | Future raw/derived artifact location | No | unset |
| `INCIDENT_LENS_PROVIDER_API_KEY` | Future model provider credential | Yes | unset |
| `INCIDENT_LENS_CONNECTOR_BASE_URL` | Optional read-only owned-app endpoint | No | unset (blocked) |
| `INCIDENT_LENS_CONNECTOR_ALLOWED_HOSTS` | Comma-separated exact host allowlist | No | unset (blocked) |
| `INCIDENT_LENS_CONNECTOR_PATH` | Fixed relative GET path (including any query) | No | unset (blocked) |
| `INCIDENT_LENS_CONNECTOR_SOURCE_ID` | Connector source identifier | No | `owned-maintained-app` |
| `INCIDENT_LENS_CONNECTOR_SOURCE_VERSION` | Connector source/version label | No | `configured` |
| `INCIDENT_LENS_CONNECTOR_ALLOW_HTTP` | Test-only local HTTP opt-in (`1`) | No | unset (HTTPS required) |
| `POSTGRES_DB` | Compose-only local database name | No | `incident_lens` |
| `POSTGRES_USER` | Compose-only local database user | No | `incident_lens` |
| `POSTGRES_PASSWORD` | Compose-only local database password | Yes | unset; required by `compose.yml` |

Real credentials must be injected by a local secret manager or deployment
secret store, never placed in source, fixtures, manifests, prompts, logs, or
the frontend bundle. Optional integrations remain unconfigured by default.
The owned-app connector can verify a public endpoint without a secret; any
integration that does require a secret must fail clearly when it is absent and
must not substitute a stored result silently.

When all three connector fields are set, `GET /v1/connectors/status` reports
`blocked` until an explicit `GET /v1/connectors/verify` performs one bounded
request. The verifier always uses the configured fixed path; callers cannot
choose a path or HTTP verb. A successful verifier response says `verified` and
returns source/access and bounded structural metadata (including a SHA-256
digest), never the response payload. Verification is request-scoped and is not
retained after configuration changes.
