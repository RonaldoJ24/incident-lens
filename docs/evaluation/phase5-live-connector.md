# Phase 5 live connector evidence

Status: bounded live access verified for one owned, maintained application
(2026-09-14).

The supplied live verification call was:

```text
GET https://api.github.com/repos/RonaldoJ24/cadencia-ai/actions/runs?per_page=5
```

The exact host allowlist entry was `api.github.com`. The configured source
metadata was `github-actions:RonaldoJ24/cadencia-ai` at
`github-actions-v3`, with access scope `connected_app`. The supplied access
time was `2026-09-14T07:26:24.531743Z`.

The response was `application/json`, 64,694 bytes, with `total_count: 17` and
five returned runs. The latest supplied run metadata was:

- run ID `34520907147`, name `CI`;
- status `completed`, conclusion `failure`;
- started `2026-09-10T19:31:31Z`;
- URL `https://github.com/RonaldoJ24/cadencia-ai/actions/runs/34520907147`.

No secret or token was needed for this bounded call. The connector enforces
HTTPS, an exact host allowlist, a configured fixed path, GET only, no redirects,
a timeout of at most 30 seconds, and a response limit of at most 10 MiB. The
API verifier returns source/access metadata, content type, byte size, bounded
top-level key metadata, and a response SHA-256 digest; it never returns the raw
response payload.

This evidence is CI/operational metadata from an owned maintained app. It is
not application incident telemetry, a model or provider result, or evidence of
a production deployment. The call does not establish a diagnosis, service
recovery, or broader telemetry coverage.
