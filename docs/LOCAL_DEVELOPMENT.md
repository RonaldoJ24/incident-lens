# Local Phase 1 slice

The local vertical slice uses SQLite so its API flow can be exercised without
Docker or PostgreSQL. It loads the explicitly authored fixture at
`backend/incident_lens/fixtures/cases.json`; these values are not RCAEval,
production, or live-connector telemetry. The API labels the origin
`controlled_runtime` and the fixture kind in every case response.

From the repository root:

```sh
uv run --project backend uvicorn incident_lens.api.app:app --host 127.0.0.1 --port 8000
pnpm --dir frontend dev
```

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

The PostgreSQL migration is [`backend/migrations/001_initial.sql`](../backend/migrations/001_initial.sql),
but PostgreSQL/container runtime verification is still pending. No public
deployment, live connector, provider, or benchmark result is implied.
