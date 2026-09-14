# Release and operations runbook

**Scope:** reproducible local and provider-neutral release operations for
Incident Lens. **Status:** no external deployment or public URL has been
verified.

## Pre-release gate

Run `make setup` once, then `make release-check`. In CI, the same checks run in
`.github/workflows/phase6-release.yml` with PostgreSQL 16. The release check
must include the PostgreSQL integration job; a local run without
`INCIDENT_LENS_DATABASE_URL` is explicitly incomplete. The final held-out
evaluation remains sealed and is never part of this gate.

The `make evaluate` target only mechanically verifies the current Phase 3
artifact and writes a provisional validation report. It is **blocked from
release acceptance**: audit found unsupported latency feature naming and
globally aggregated/non-operational ranking metrics. It must not be presented
as accepted Phase 3 evidence or a production model result.

The dated browser-local visual review is recorded in
[`docs/evaluation/phase6-visual-review.md`](evaluation/phase6-visual-review.md).
It covers the authored static preview only; its interactively inspected
screenshots are not checked in and it does not verify the full API/PostgreSQL,
public deployment, provider, or connector path.

The release image must pass the static container checks: UID/GID `10001`, no
credentials baked into the image, read-only filesystem where supported, no new
privileges, dropped Linux capabilities, and a passing `/health/ready` check.

## Startup and migrations

Local SQLite remains the zero-service fallback. A release process must set
`INCIDENT_LENS_DATABASE_URL`; otherwise it is not a PostgreSQL release.
Migrations are ordered by their three-digit filename and recorded in
`incident_lens_schema_migrations`:

```sh
INCIDENT_LENS_DATABASE_URL="$RELEASE_DATABASE_URL" \
  uv run --project backend python -m incident_lens.migrations
```

The migration command runs in one transaction and is idempotent for already
recorded versions. Inspect the applied versions with a privileged database
client; never place the URL or its output in Git or application logs.

After migration, start the image with the command in
`deploy/compose.release.yml`, wait for `/health/ready`, and perform one fresh
guest-session smoke flow: create a session, run the authored fixture, retrieve
evidence/findings/timeline, save a report, and export it. A successful smoke
flow demonstrates wiring only; it is not live telemetry or a repair claim.

## Health and observability

- `/health` is a liveness response and does not prove database readiness.
- `/health/ready` executes a bounded `SELECT 1` against the selected store and
  returns 503 when it is unavailable.
- `/metrics` exposes bounded in-process request counters and response-status
  counts. It deliberately retains no request bodies, credentials, or
  high-cardinality path labels. Forward it only through an authenticated
  internal observability path.
- Alert on readiness failures, sustained 5xx responses, migration errors, and
  upload quota rejection. The local metrics hook is not a durable monitoring
  system and is not a public endpoint.

## Rollout and rollback

1. Render `deploy/compose.release.yml` with the secret manager and inspect the
   result. The image reference must be immutable and separately verified.
2. Take a managed PostgreSQL snapshot before applying a new migration. Keep
   the snapshot outside the repository and record its provider-side identifier
   in the release system, not in application logs.
3. Apply migrations, start the new image, and require readiness plus the smoke
   flow before traffic admission.
4. If only application behavior is bad and the schema is backward compatible,
   stop admission and redeploy the previous verified image digest. Re-run the
   smoke flow.
5. If a migration is incompatible or data integrity is in question, stop the
   API, preserve logs/metrics, and restore the last known-good database snapshot
   using the managed PostgreSQL provider's documented restore procedure. Do not
   invent or run an unreviewed destructive `down` migration.
6. Re-run `incident_lens_schema_migrations` inspection and the smoke flow before
   reopening traffic. Record the failed image, migration versions, snapshot
   identifier, and recovery result in the external release log.

No deployment, rollback, provider, or public URL is claimed by this document.
