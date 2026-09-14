# Local Phase 1 slice

The local vertical slice uses SQLite when no database URL is configured, so its
API flow can be exercised without Docker or PostgreSQL. Set
`INCIDENT_LENS_DATABASE_URL` to select the PostgreSQL store. Both backends load
the explicitly authored fixture at
`backend/incident_lens/fixtures/cases.json`; these values are not RCAEval,
production, or live-connector telemetry. The API labels the origin
`controlled_runtime` and the fixture kind in every case response.

From the repository root:

```sh
uv run --project backend uvicorn incident_lens.api.app:app --host 127.0.0.1 --port 8000
pnpm --dir frontend dev
```

For the PostgreSQL path, start the API and database together:

```sh
cp .env.example .env  # edit POSTGRES_PASSWORD in this ignored file
docker compose up --build
```

The API container applies `backend/migrations/001_initial.sql` and
`002_artifact_references.sql` through the ordered migration runner before
starting. The same runner can be invoked directly with
`INCIDENT_LENS_DATABASE_URL=... uv run --project backend python -m incident_lens.migrations`.

Vite proxies `/v1` and `/health` to the local API. The browser opens with the
checkout example, and the selector includes degraded performance and
insufficient evidence. Run, cancel, retry, review, save, and export actions
are bounded and read-only; the timeline records the actual fixture checks.

The Pages build defaults to the instant browser-local demo. Adding `?mode=live`
selects the build-time `VITE_INCIDENT_LENS_API_ORIGIN` absolute HTTPS origin;
that path never uses the demo adapter and reports starting, ready, or
unavailable connection state.

The guest upload boundary accepts only strict JSONL records with `log`,
`metric`, and `trace` signals. Download the authored sample from
`GET /v1/uploads/sample`, initiate a slot with
`POST /v1/uploads/initiate`, then stream the body to
`PUT /v1/uploads/{upload_id}` with `X-Session-ID` and
`Content-Type: application/jsonl`. The one-step `POST /v1/uploads` remains a
compatibility path. Validation reports record, duplicate, conflict,
missing-signal, and untrusted-content counts; `GET`/`DELETE
/v1/uploads/{upload_id}` remain isolated to the owning session, and DELETE can
cancel an active streaming validation.
The read-only connector status is available at `GET /v1/connectors/status` and
stays `blocked` until an owned endpoint, exact host allowlist, and fixed path
are configured. An explicit `GET /v1/connectors/verify` performs one bounded
GET to that configured path and returns source/access metadata, content type,
byte size, top-level keys, and a payload SHA-256 without returning the payload.
The request has no path or verb selector, and verification is not persisted;
the successful `verified` result is limited to that response and configuration
changes require a new explicit verification.

Focused validation:

```sh
uv run --project backend python -m unittest discover -s backend/tests -v
pnpm --dir frontend run lint
pnpm --dir frontend run typecheck
pnpm --dir frontend test
pnpm --dir frontend run build
```

The PostgreSQL adapter is covered by
`backend/tests/test_postgres_integration.py`; the test class skips only when no
database URL is configured. The required GitHub Actions workflow at
`.github/workflows/phase1-postgres.yml` provisions PostgreSQL 16, applies both
migrations, and runs those tests, but has not yet been run from this checkout.
No public deployment, live connector, provider, or benchmark result is implied.
