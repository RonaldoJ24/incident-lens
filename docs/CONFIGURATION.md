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
| `INCIDENT_LENS_CORS_ALLOWED_ORIGINS` | Comma-separated exact browser origins allowed to call the API; no credentials | No | local Vite/preview origins plus `https://ronaldoj24.github.io` |
| `INCIDENT_LENS_DATABASE_URL` | PostgreSQL connection; selects the PostgreSQL store when set | Yes | unset (SQLite fallback) |
| `INCIDENT_LENS_SQLITE_PATH` | SQLite path used when no PostgreSQL URL is set | No | `/tmp/incident-lens-phase1.sqlite3` |
| `INCIDENT_LENS_OBJECT_STORE_BUCKET` | Future raw/derived artifact location | No | unset |
| `INCIDENT_LENS_PROVIDER_API_KEY` | OpenAI-compatible model credential; absence selects the labelled deterministic fallback | Yes | unset |
| `INCIDENT_LENS_PROVIDER_BASE_URL` | OpenAI-compatible `/chat/completions` base URL | No | `https://api.deepseek.com` |
| `INCIDENT_LENS_PROVIDER_MODEL` | Provider model identifier | No | `deepseek-flash` |
| `INCIDENT_LENS_PROVIDER_TIMEOUT_SECONDS` | Per-request timeout bound | No | `8` |
| `INCIDENT_LENS_PROVIDER_MAX_INPUT_TOKENS` | Maximum estimated prompt tokens | No | `1400` |
| `INCIDENT_LENS_PROVIDER_MAX_CONTEXT_TOKENS` | Maximum estimated retrieved-context tokens | No | `1000` |
| `INCIDENT_LENS_PROVIDER_MAX_OUTPUT_TOKENS` | Maximum requested completion tokens | No | `320` |
| `INCIDENT_LENS_PROVIDER_MAX_RETRIES` | Maximum bounded retry count for transient failures | No | `1` |
| `INCIDENT_LENS_PROVIDER_MAX_CALLS_PER_PROCESS` | Conservative process-global provider HTTP-call cap (including retries) | No | `32` |
| `INCIDENT_LENS_PROVIDER_DISABLE_THINKING` | Send DeepSeek's bounded `thinking: disabled` option; set false to omit it for another compatible provider | No | `true` |
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

The provider path sends only a bounded, structured prompt to an
OpenAI-compatible `/chat/completions` endpoint. The answer schema contains a
claim, explicit uncertainty, next checks, and source IDs drawn from the
retrieved passages. Unknown citations, malformed or truncated JSON, timeouts,
and provider errors fail the workflow safely; they do not replay an authored
fixture as fresh AI. With no API key, the workflow uses a deterministic local
fallback labelled `deterministic_non_provider_fallback` and makes no provider
claim. Credentials are never written to prompts, timeline output, manifests,
or error messages.

When all three connector fields are set, `GET /v1/connectors/status` reports
`blocked` until an explicit `GET /v1/connectors/verify` performs one bounded
request. The verifier always uses the configured fixed path; callers cannot
choose a path or HTTP verb. A successful verifier response says `verified` and
returns source/access and bounded structural metadata (including a SHA-256
digest), never the response payload. Verification is request-scoped and is not
retained after configuration changes.
