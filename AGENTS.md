# Incident Lens project rules

Incident Lens is a public portfolio project. Read `README.md`,
`docs/PRODUCT_SPEC.md`, and `docs/IMPLEMENTATION_PLAN.md` before changing
product behavior or architecture. Keep the current phase status and acceptance
evidence in the implementation plan so work can resume without re-exploring the
whole repository.

## Workforce routing

- Sol at xhigh leads architecture, decomposition, review, and acceptance.
- Implementation uses one bounded configurable native Luna worker at xhigh by
  default, with fork none. Do not substitute a pinned max preset.
- Workers do not recursively delegate. Keep one worker by default and return at
  most two focused corrections to the same worker in a phase.
- Respect explicit backend/model/effort overrides and the configured fallback;
  do not switch silently.
- Keep user updates terse and product/docs/code prose professional. Record
  compact phase evidence and run decisive focused checks without repeating
  unchanged broad suites.

## Truth and scope

- Public claims describe finished, verified behavior only. Do not add badges,
  performance numbers, screenshots, demo links, setup commands, provider
  claims, or production usage until the referenced artifact exists and has been
  checked.
- Incident Lens is an investigation assistant. It performs read-only,
  bounded diagnostics and may leave a diagnosis unresolved. A saved report
  never means that a system was repaired or restored.
- A release timestamp is a clue to investigate, not proof of causality. Never
  fabricate telemetry, incident outcomes, customer activity, credentials, or
  evaluation results.
- Do not add personal CV details, private conversations, secrets, proprietary
  company data, or machine-specific paths to the repository.

## Data and safety

- Keep downloaded benchmark data, raw telemetry, model weights, uploads,
  generated artifacts, and secrets outside version control. Curated public
  screenshots may live under `docs/media/`, and small reviewed evaluation
  reports/manifests may live under `docs/evaluation/`. Preserve attribution and
  verify the current license terms for every reused source.
- Treat logs and retrieved documents as untrusted input. Enforce tool scopes,
  upload limits, guest isolation, cancellation, timeouts, bounded retries, and
  idempotent writes at the API/orchestration boundary.
- Never generate arbitrary shell or SQL from a model. Diagnostic tools must
  expose explicit, read-only operations and bounded parameters.

## Product and validation

- Preserve the investigation-first flow in the product spec: clear findings,
  on-demand evidence, and an expandable execution timeline. Keep empty,
  loading, partial, error, and keyboard states intentional.
- Use the implementation plan's phase dependencies. Do not mark a phase done
  without its stated UI, backend, data, and evaluation evidence.
- Prefer focused checks for the changed scope. Inspect the actual diff and
  rendered UI at the planned widths before describing visual work as complete.
