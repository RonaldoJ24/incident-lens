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
