# Release deployment contract

**Status: not deployed.** No provider, public URL, ingress, domain, or
provider credential is selected or verified in this repository. The
`compose.release.yml` file is a provider-neutral container contract that
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

This is not a deployment claim. Public deployment and the owned read-only
connector remain explicit external blockers in the implementation plan.

## Optional Render Free contract

[`../render.yaml`](../render.yaml) is a checked-in, provider-specific start
contract for a later Render Free Python service. It uses the repository root,
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
The Render service and API URL remain unverified until an external deployment
is actually run.
