# Threat and access review

**Review status:** final local release-surface review completed 2026-09-14.
This is a design review, not proof of a deployed security boundary.

## Assets and trust boundaries

| Asset | Boundary | Required control |
| --- | --- | --- |
| Guest uploads and reports | Browser/API to process memory and store | Strict schema and byte/record bounds, session ownership, retention, quota, no shared fault controls |
| PostgreSQL state | API process to database | Parameterized SQL, foreign keys, transaction rollback, migration records, secret-injected URL |
| Fixture and knowledge content | Filesystem/retrieval workflow to prompt-facing output | Treat content as untrusted, bounded read-only tools, citations and uncertainty |
| Owned-app connector | API to external host | Exact HTTPS host allowlist, GET-only boundary, redirect rejection, response-size limit, source/access metadata |
| Credentials | Secret manager/process environment | Never commit or bake into image; no credential values in logs or metrics |
| Release image | Build system to runtime | Non-root UID/GID, read-only filesystem where supported, dropped capabilities, healthcheck |

## Abuse cases and mitigations

- **Prompt injection in logs or uploads:** records remain data; content is
  bounded, marked untrusted, and never executed as instructions. Shell and SQL
  are not model-generated operations.
- **Cross-guest access or report forgery:** every run, report, correction, and
  upload lookup checks the owning session; report ownership is also enforced at
  the store transaction boundary.
- **SQL injection or partial writes:** SQL uses parameters and explicit
  transactions. Foreign keys and unique idempotency keys protect relationships
  and retries.
- **Upload denial of service:** streaming parsing, 10 MiB total/256 KiB line/
  10,000 record limits, retention cleanup, cancellation, and per-session byte,
  record, and cost budgets bound work. The current upload state is process-local
  until the persistent workflow phase.
- **Connector SSRF or mutation:** only exact allowlisted hosts and bounded GET
  requests are permitted; redirects and arbitrary methods are rejected. No live
  owned endpoint is configured, so connector status remains `blocked`.
- **Secret exposure:** checked-in examples contain names/placeholders only;
  compose requires `POSTGRES_PASSWORD` from an ignored environment file, and
  release compose requires deployment-injected values.
- **Container escape or accidental privileged writes:** the release contract
  uses non-root execution, `read_only`, `cap_drop: ALL`, and
  `no-new-privileges`.
- **Migration failure or unsafe rollback:** ordered migrations are recorded and
  transactional; rollback is image rollback for compatible schemas or managed
  snapshot restore for incompatible changes. No destructive down migration is
  supplied.

## Access review checklist

- [x] Guest state and report ownership are enforced at API and store boundaries.
- [x] Read-only diagnostic tools reject unknown operations and arbitrary shell
      commands.
- [x] Uploads cannot mutate shared live fault controls.
- [x] Connector access is allowlisted and remains explicitly blocked without an
      authorized owned endpoint.
- [x] Secrets are environment/secret-manager inputs, not repository values.
- [x] CI uses read-only repository permissions and an ephemeral PostgreSQL
      service.
- [ ] Authentication, durable rate limiting, external audit storage, provider
      selection, and public ingress remain deployment decisions, not verified
      capabilities of this foundation.

Residual risk is therefore concentrated in the unauthenticated guest
capability-token model, process-local quotas, and unverified deployment
controls. These are release blockers, not silently accepted production claims.
