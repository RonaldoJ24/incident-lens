# Phase 6 live deployment evidence

Status: in progress. The free-tier application path is deployed and verified;
Phase 3 and final held-out acceptance remain blocked and sealed.

## Deployment

- Frontend: GitHub Pages at <https://ronaldoj24.github.io/incident-lens/>.
  The default is the instant browser-local authored preview. The explicit
  <https://ronaldoj24.github.io/incident-lens/?mode=live> path calls the API.
- API: Render Free service `incident-lens-api` in Ohio at
  <https://incident-lens-api.onrender.com>. Deployment
  `dep-dak1vfeq1p3s73cajbdg` for commit `c189203` reached `live` on
  2026-09-14.
- State: Neon Free project `incident-lens` in AWS Ohio (`aws-us-east-2`). The
  pooled URL is used at runtime and the direct URL only for startup migrations.
- Provider: bounded OpenAI-compatible runtime configured for DeepSeek model
  `deepseek-flash`. Thinking is explicitly disabled for the structured call so
  the output cap is reserved for the required JSON answer.

All provider and database credentials are held in external files with mode
`0600`, transferred to Render as secret files, and absent from Git, the Pages
bundle, command arguments, and recorded output. The pre-existing unrelated
Neon project was not modified.

## Acceptance on 2026-09-14

- `/health/ready` returned HTTP 200 and `PostgresStateStore`.
- CORS preflight allowed exactly `https://ronaldoj24.github.io`; an unrelated
  origin received HTTP 400 and no `access-control-allow-origin` header.
- A fresh hosted flow returned: session HTTP 201, three cases, run HTTP 202,
  workflow HTTP 202 with `completed`, one provider claim from
  `deepseek-flash`, three cited source IDs, explicit uncertainty, four next
  checks, and no failed timeline event.
- The claim-support evaluator returned `uncertain` with lexical overlap
  `0.295455`. This conservative result is retained; it is not rewritten as a
  supported diagnosis.
- Fetching the persisted report and exporting the workflow both returned HTTP
  200, demonstrating Neon-backed state across the complete request flow.
- A local forced provider-transport failure returned a sanitized failure with
  zero claims and no fallback replay or credential leakage.
- `make release-check PERF_SAMPLES=20` exited 0. A separate real-Neon
  integration run passed all three PostgreSQL tests. Frontend lint, tests, and
  build passed, and the Render blueprint validated.

## Limits

This is deployment and wiring evidence for an authored controlled fixture. It
does not establish production incident quality, representative provider or
hosted latency, provider cost, live application telemetry, repair, or user
impact. Render Free may cold-start after inactivity. The model/provider seam is
replaceable, but no replacement provider has been verified. Phase 3 remains
blocked and the final held-out split was not opened.
