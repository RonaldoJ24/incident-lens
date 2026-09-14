# Release deployment contract

**Status: deployed on the selected free-tier path.** The public API readiness
endpoint is <https://incident-lens-api.onrender.com/health/ready>. The
`compose.release.yml` file remains a provider-neutral container contract that
requires an immutable image reference and a managed PostgreSQL URL supplied
outside Git.

Before using the contract:

1. Build and scan an immutable image. Confirm that the image runs as UID/GID
   `10001`, has the `/health/ready` check, and contains no credentials.
2. Supply `INCIDENT_LENS_IMAGE` and `INCIDENT_LENS_DATABASE_URL` through the
   deployment secret manager. Do not add them to this file or a tracked env
   file. Run `docker compose -f deploy/compose.release.yml config` with those
   values to inspect the rendered configuration.
3. Apply migrations as part of the release transaction, then wait for
   `/health/ready` before admitting traffic. The application exposes
   `/metrics` for bounded in-process request counters; forward it only through
   an authenticated internal observability path.
4. Perform the smoke flow in `docs/OPERATIONS.md` using a fresh guest session.

This generic contract is not evidence for a compose-based deployment. The
verified Render/Neon/DeepSeek path is recorded separately in
[`../docs/evaluation/phase6-live-deployment.md`](../docs/evaluation/phase6-live-deployment.md).

## Verified Render Free path

[`../render.yaml`](../render.yaml) is the checked-in, provider-specific start
contract for the Render Free Python service. It uses the repository root,
installs/syncs the backend with `uv`, runs migrations from
[`render-start.sh`](render-start.sh), listens on `$PORT`, and exposes
`/health/ready` in the Ohio region on the free plan. Render secret files must
provide `/etc/secrets/neon.env` with Neon’s existing `DATABASE_URL_UNPOOLED`
(direct) and `DATABASE_URL` (pooled) assignments, plus
`/etc/secrets/deepseek.env` with `INCIDENT_LENS_PROVIDER_API_KEY`. The start
script sources those files without printing or putting values in command-line
arguments, runs migrations with the direct URL, then starts the API with the
pooled URL.

Render Free has no paid pre-deploy hook, so migration is intentionally a
startup step. Its disk is ephemeral and the service is limited to 512 MB and
0.1 CPU; no durable uploads or local database files are part of this contract.
The service `incident-lens-api` is deployed in Ohio on Render Free and uses the
exact Pages origin for CORS. A live readiness request and a fresh
session/case/run/workflow/report/export flow passed on 2026-09-14 against Neon
PostgreSQL and DeepSeek. The deployed telemetry remains the authored
controlled fixture; it is not a live production feed.
