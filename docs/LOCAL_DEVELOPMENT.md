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
