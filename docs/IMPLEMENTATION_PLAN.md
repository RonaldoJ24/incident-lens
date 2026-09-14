# Incident Lens implementation plan

**Overall status:** foundation/planning only. No application phase is complete.

This plan is the source of truth for phase status and acceptance evidence. A
phase may begin when its dependencies are met, but it is not complete until
the listed artifacts and checks exist. Commands below are targets to establish;
they must not be described as working until the repository contains and passes
them.

## Delivery rules

- Keep the public README aligned with finished behavior and verified evidence.
- Preserve independent source adapters and explicit run origins. Never hide
  missing credentials, unavailable providers, or failed live calls behind a
  cached result.
- Freeze manifests before tuning. Training fits on training data, validation
  selects models/thresholds/retrieval/prompts, and the final held-out test
  remains sealed until decisions are fixed. Keep development, public demo,
  controlled failure, and final held-out evaluation separate.
- Build the smallest useful slice that still has a real persistent Python API,
  real state transitions, honest loading/error behavior, and a reviewable UI.
- Record a short evidence note per phase: changed paths, command, result,
  fixture/version, and known limitation.

## Phase 0 — Foundation, interfaces, design, and data audit

**Status:** In progress — documentation foundation only.

**Dependencies:** none.

**Deliverables**

- A simple layout with one TypeScript frontend and one Python package: a
  frontend directory, a Python package containing `api`, `worker`, `pipeline`,
  and `ml` modules, plus `docs`, `data/manifests`, and focused tests. Do not
  create speculative separate services, contract packages, or a script forest.
- Versioned API/domain contracts for sessions, cases, evidence, runs, findings,
  timeline events, corrections, reports, uploads, and independent provenance:
  telemetry origin, execution, source interval, run version, and run time.
- A small visual design system and rendered investigation wireframe covering
  findings, evidence drawer, timeline, all required states, and the four target
  widths in the product spec.
- RCAEval source/license audit, 10–20 RE2-OB development case manifest,
  neutral IDs, signal completeness notes, and leakage review. No raw dataset in
  Git.
- OpenTelemetry Demo adapter boundary and separate controlled-failure manifest.
- Knowledge-source ledger that identifies public documentation/runbooks and
  excludes held-out solutions.
- Local configuration and secret boundary documented without real credentials.

**Acceptance evidence**

- Contract files validate a representative case, run, evidence item, and report
  with origin and version metadata.
- A reviewer can trace every planned screen state to a product requirement;
  unresolved visual decisions are recorded rather than silently improvised.
- Manifests contain neutral IDs, explicit splits, source versions, timestamps,
  and license/attribution fields. A negative test demonstrates that filename or
  hidden-label leakage is rejected.

**Checks to establish**

Record the actual frontend lint/typecheck, Python package tests, manifest
validation, and compose configuration commands after the scaffold exists. Do
not mark these checks complete from speculative paths or commands.

## Phase 1 — Runnable vertical slice

**Status:** Not started.

**Dependencies:** Phase 0 contracts and design decisions.

**Deliverables**

- React/TypeScript frontend Investigate route with the default checkout example,
  degraded-performance and insufficient-evidence examples, responsive shell,
  findings area, evidence drawer, timeline, keyboard behavior, and explicit
  empty/loading/partial/error states.
- FastAPI/Pydantic API plus background worker with PostgreSQL migrations for
  isolated guest session, case selection, run lifecycle, evidence, findings,
  timeline, report revisions, and export metadata.
- Recorded telemetry fixture adapter that performs real bounded inference over
  versioned fixtures; no fabricated metrics or fake “live” badge.
- Progress events, cancellation, timeout, retry, and idempotent report write.

**Acceptance evidence**

- A clean local environment can create a session, run the fixture, inspect
  findings/evidence/timeline, reload state, and export a report using documented
  commands.
- Browser review at 1440/1280/768/390 shows a readable investigation task,
  intentional loading/error/empty states, focus behavior, and no horizontal
  overflow. Screenshots are stored only after they are real.
- API tests cover run transitions, cancellation, retry, session isolation, and
  duplicate report requests.

**Checks to establish**

- `docker compose up --build`
- `pnpm --dir frontend test`
- `uv run --project backend pytest -m integration`
- `pnpm --dir frontend e2e -- --width=1440`

## Phase 2 — Real source adapters and data isolation

**Status:** Not started.

**Dependencies:** Phase 1 persistent state and Phase 0 manifests.

**Deliverables**

- Per-case RCAEval fetch/normalization adapter with source/version/license
  ledger, quality report, neutral IDs, and split enforcement.
- Offline PySpark jobs for normalization, deduplication, timestamp checks,
  signal completeness, windows, and versioned manifests. Request handling does
  not depend on a Spark cluster.
- Separate OpenTelemetry Demo/feature-flag adapter and controlled-failure
  result format; no schema reuse by assumption.
- Object-storage layout for raw/derived artifacts and PostgreSQL references.

**Acceptance evidence**

- Re-running one selected case produces the same manifest and quality summary
  under a pinned source version.
- Tests reject hidden labels, filename cause leakage, out-of-split cases,
  malformed timestamps, duplicate events, and unauthorized artifact access.
- UI displays missing logs/metrics/traces and source origin clearly.

**Checks to establish**

- `uv run --project backend pytest -m pipeline`
- `python -m incident_lens.pipeline.normalize --manifest data/manifests/dev.json`
- `python -m incident_lens.pipeline.check_leakage data/manifests`
- `uv run --project backend pytest -m isolation`

## Phase 3 — ML train, evaluate, and serve

**Status:** Not started.

**Dependencies:** Phase 2 quality-reviewed manifests and enough development
cases to make comparisons meaningful.

**Deliverables**

- Reproducible training/validation/final-test pipeline with grouped
  independent-run splits and frozen manifests before tuning. Training fits
  artifacts; validation selects models, thresholds, retrieval settings, and
  prompts; the final-test manifest remains sealed until those decisions are
  fixed.
- Scikit-learn anomaly ranking baseline (for example, Isolation Forest) and
  error-rate/latency rule baselines, with versioned artifacts and features.
- Serving path that reports unusual service/window ranking and feature/source
  metadata without calling the score a root-cause probability.
- Error analysis for false alarms, missing signals, conflicting signals,
  unseen services, and insufficient evidence.

**Acceptance evidence**

- Evaluation reports separate model/anomaly metrics (event detection, false
  alarms, and ranking) from complete investigation quality (failing-service
  identification, useful checks, evidence support, uncertainty, and completion)
  with split, case count, workload, versions, and known failures. “Not measured”
  remains explicit where appropriate.
- An ablation or baseline comparison explains why the selected method is kept;
  a simpler rule remains the choice if evidence favors it.
- API response and UI language consistently say “unusual ranking” rather than
  “probability of root cause.”
- Phase 3 may inspect training and validation results only. The final-test
  manifest remains sealed until Phase 6; its labels and results are not used for
  model, threshold, retrieval, or prompt decisions here.

**Checks to establish**

- `uv run --project backend pytest -m ml`
- `python -m incident_lens.ml.train --manifest data/manifests/train.json`
- `python -m incident_lens.ml.validate --manifest data/manifests/validation.json`
- `python -m incident_lens.ml.verify_artifact artifacts/model-manifest.json`

## Phase 4 — RAG and persistent evidence workflow

**Status:** Not started.

**Dependencies:** Phase 1 workflow state and Phase 2 source/version metadata;
Phase 3 ranking output for a complete comparison.

**Deliverables**

- Versioned lexical plus semantic knowledge index over verified runbooks and
  prior knowledge, with source/version citations and retrieval metadata.
- LangGraph workflow with typed state, explicit read-only diagnostic tools,
  bounded calls/time/cost, checkpoints, restart, cancellation, retries, and
  idempotent report revisions.
- Separate retrieval evaluation and claim-support evaluation, including
  injection/untrusted-log fixtures and source withholding.
- Human review actions for accepting/correcting/challenging a finding.

**Acceptance evidence**

- Timeline shows actual tool calls, parameters/scope, outputs, retries, and
  failure state; no arbitrary model-generated shell or SQL is executable.
- Restart from a checkpoint and duplicate delivery produce one consistent
  report revision. Cancellation stops or marks work clearly.
- Every material claim in a sample report links to evidence or is labeled
  unsupported/uncertain. Withholding a source changes the recorded context.

**Checks to establish**

- `uv run --project backend pytest -m workflow`
- `python -m incident_lens.ml.evaluate_retrieval --manifest data/manifests/retrieval.json`
- `uv run --project backend pytest -m recovery`
- `pnpm --dir frontend e2e -- --scenario evidence-review`

## Phase 5 — Guest testing, uploads, and owned live connector

**Status:** Not started.

**Dependencies:** Phase 4 evidence workflow and Phase 2 upload/source contracts.

**Deliverables**

- Bounded JSONL upload flow with downloadable sample, schema validation,
  missing-signal report, size/type/retention limits, cancellation, and isolated
  guest state.
- Exploratory pilot protocol for 3–5 willing engineers using matched tasks,
  declared task order balance, sample size, task time, correctness, and
  structured feedback. Results remain exploratory; no unsupported significance
  or broad impact claim, and no outreach without explicit authorization.
- A real read-only connector to an owned maintained app. A stub does not satisfy
  this integration target. If credentials or external access are unavailable,
  record that specific blocker and continue independent work.
- Cost/quota guardrails and clear provider failure/replay choice.

**Acceptance evidence**

- Upload fixtures cover valid, malformed, incomplete, oversized, duplicate,
  conflicting, and prompt-injection content. No upload can mutate shared live
  fault controls or another guest's state.
- The UI and report expose independent telemetry origin, execution, source
  interval, run version, and run time; fresh analysis and stored replay are not
  represented as competing origins.
- Any connected-app result includes access time and source metadata; absent
  access remains an explicit outstanding blocker, not a completed integration.

**Checks to establish**

- `uv run --project backend pytest -m uploads`
- `pnpm --dir frontend e2e -- --scenario guest-isolation`
- `python -m incident_lens.validation.injection_fixtures`
- `python -m incident_lens.validation.cost_budget --workload sample`

## Phase 6 — Hardened deployment, evaluation, and visual QA

**Status:** Not started.

**Dependencies:** Phases 1–5 complete or documented blockers with independent
work finished.

**Deliverables**

- Reproducible local/container setup, migrations, CI, observability, secret
  management, deployment, rollback, and runbook.
- A verified public deployment, required for intended delivery, plus frozen
  final/held-out evaluation and separate controlled telemetry results. The final
  test remains sealed until model, threshold, retrieval, and prompt decisions
  are fixed.
- Measurement of p50/p95 latency, cost, completion, recovery, and supported
  upload workloads with sample sizes and versions.
- Browser visual review with actual screenshots and interaction checks at all
  four target widths, including keyboard, focus, error, and mobile states.
- Final threat/access review and a concise model/data card.

**Acceptance evidence**

- A fresh checkout follows the exact documented setup, migration, demo, test,
  and rollback commands. Every command in the README has been run against the
  verified public deployment.
- CI verifies contracts, unit/integration/e2e checks, leakage/injection tests,
  and reproducibility checks.
- Published results include failures, limits, workload, sample size, and
  artifact versions. Model/anomaly metrics are separate from complete
  investigation quality. No unmeasured badge or scale claim is added.
- Rendered browser review confirms the findings/evidence/timeline hierarchy at
  1440, 1280, 768, and 390 CSS pixels.

**Checks to establish**

- `docker compose up --build`
- `docker compose run --rm api alembic upgrade head`
- `make test`
- `make evaluate`
- `make visual-review`
- `make rollback VERSION=<verified-version>`

## Phase 7 — Final public presentation

**Status:** Not started.

**Dependencies:** Phase 6 acceptance evidence and a verified public deployment.

**Deliverables**

- README rewritten around the implemented behavior, with a working demo URL
  only if verified, real screenshots/short walkthrough, architecture, exact
  setup/env/migration/demo commands, attribution, model/data/evaluation notes,
  API examples, deployment/runbook, and original contribution.
- Final review for truthful wording, accessible links, no private data or
  credentials, and no references to unfinished features. Missing external
  access or connector credentials remain named blockers rather than being
  replaced with a stub or omitted.

**Acceptance evidence**

- A reviewer can reproduce the documented path or see the precise external
  blocker. Screenshots and links resolve to the current implementation.
- The presentation distinguishes public demo, development, held-out,
  controlled, pilot, and live data. Published limitations are easy to find.

**Checks to establish**

- `python -m incident_lens.validation.verify_public_docs`
- `python -m incident_lens.validation.check_links README.md docs/`
- `make release-check`

## Current blockers and decisions

There is no blocker to foundation documentation. Application implementation,
provider selection, deployment target, live connector access, exact command
names, and measured evaluation numbers remain intentionally undecided until the
relevant phase produces evidence. Public deployment and the owned-app
connector are required intended deliverables; missing access is a specific
outstanding blocker and does not stop independent work. A provider or connector
must not be named as available merely because it appears in a plan.
