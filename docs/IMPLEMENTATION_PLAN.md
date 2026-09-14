# Incident Lens implementation plan

**Overall status:** Phase 0 complete; Phase 1 local slice and Phase 2 source
work are in progress. No application phase is complete.

This plan is the source of truth for phase status and acceptance evidence. A
phase may begin when its dependencies are met, but it is not complete until
the listed artifacts and checks exist. Commands below are targets to establish;
they must not be described as working until the repository contains and passes
them.

## Planning handoff

**Planning review:** complete on 2026-09-13. **Application delivery:** Phase 1
local slice and Phase 2 source work in progress. The product contract, eight-stage sequence,
dependencies, acceptance gates, and open decisions remain the source of truth.

The cited RCAEval project and dataset pages were checked during this review and
support the planned 735-case total, the 90-case multi-source RE2-OB subset, and
per-case access. The OpenTelemetry Demo and feature-flag pages also remain
available as the planned separate controlled-runtime source. This is a source
sanity check only: Phase 0 must still pin exact revisions and record license,
attribution, redistribution, and derived-artifact terms before data is reused.

| Phase | Current evidence | Next gate | Known decision or blocker |
| --- | --- | --- | --- |
| 0 | Scaffold, v1 contracts, rendered wireframe, audited manifests, and focused validation pass (evidence record below) | Phase 1 runnable vertical slice | No external blocker; per-case telemetry fetch and final development selection remain Phase 2 evidence-led work |
| 1 | Local SQLite API, authored fixture worker, React Investigate shell, migration, API flow tests, and four-width browser review (evidence record below) | PostgreSQL persistence implementation and runtime verification | Docker and PostgreSQL are unavailable on this host; neither the persistence implementation nor migration runtime is verified |
| 2 | Pinned per-case source adapter, portable deterministic normalization, separate controlled-runtime schema, artifact layout, and one reviewed quality report (evidence record below) | Spark CI parity/isolation run plus remaining case review | Spark/Java CI workflow has not run; PostgreSQL persistence implementation and runtime verification remain Phase 1 work |
| 3 | None | Quality-reviewed, leakage-safe train/validation manifests | Blocked by Phase 2; method and thresholds remain evidence-led decisions |
| 4 | None | Persistent workflow state, source metadata, and ranking output | Blocked by Phases 1–3; embedding/model provider remains unselected pending availability and evaluation |
| 5 | None | Evidence workflow and upload/source contracts | Blocked by Phases 2 and 4; owned-app target/access is an external decision, and pilot outreach requires explicit authorization |
| 6 | None | Prior phases complete, except explicitly documented external blockers after independent work finishes | Deployment target, budget, credentials, and domain access remain open; final test stays sealed until tuning decisions are fixed |
| 7 | None | Verified public deployment and Phase 6 evidence | Blocked by Phase 6; any unresolved owned-connector access must remain visible in the presentation |

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

## Phase evidence record

Keep the table above current. When work changes a phase, append one compact,
dated record under that phase before handoff. Use this form; remove fields that
do not apply rather than filling them with guesses:

```text
Evidence record YYYY-MM-DD
Status: not started | in progress | blocked | complete
Changed paths: <repository-relative paths>
Acceptance evidence: <artifact, screenshot, response, or report and where to inspect it>
Checks: <exact command> — <pass/fail and decisive result>
Fixture/source versions: <manifest, revision, model, provider, or not applicable>
Known limitations/blockers: <specific unresolved item and independent work that can continue>
Next gate: <single concrete acceptance gate>
```

`Complete` is valid only when every acceptance item in that phase has inspectable
evidence. A command listed under “Checks to establish” is not evidence until it
exists in the repository and its result is recorded.

## Phase 0 — Foundation, interfaces, design, and data audit

**Status:** Complete — scaffold, contracts, design artifacts, source audit, and
focused validation are checked in. Application behavior remains Phase 1 work.

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

Evidence record 2026-09-13
Status: complete
Changed paths: `frontend/`, `backend/`, `contracts/v1/`, `data/manifests/`, `docs/design/`, `docs/evaluation/`, `.env.example`, `docs/CONFIGURATION.md`
Acceptance evidence: v1 JSON Schema with entity/payload discriminator binding, OpenAPI retrieval/review/export operations, and representative fixture at `contracts/v1/`; rendered wireframe PNG/SVG and token/mapping notes at `docs/design/`; neutral RE2-OB, separate controlled-runtime, and knowledge ledgers at `data/manifests/`; leakage review at `docs/evaluation/leakage-review.md`
Checks: `pnpm --dir frontend run lint` — pass; `pnpm --dir frontend run typecheck` — pass; `pnpm --dir frontend test` — pass; `pnpm --dir frontend run build` — pass; `PYTHONPATH=backend python3 -m unittest discover -s backend/tests -v` — pass (10 tests); `PYTHONPATH=backend python3 -m incident_lens.validation.manifests data/manifests` — pass (3 manifests); `PYTHONPATH=backend python3 -m incident_lens.validation.contracts contracts/v1/examples/representative.json` — pass (9 documents); `PYTHONPATH=backend python3 -m incident_lens.validation.local README.md docs backend contracts data .env.example frontend/src` — pass; `rsvg-convert -w 1440 -h 1040 docs/design/investigation-wireframe.svg -o docs/design/investigation-wireframe.png` — pass; `git diff --check` — pass
Fixture/source versions: RCAEval `bb48c5aa9a24f1d5fcc716bdd479ea2d63145c90`; RCAEval Hugging Face `afeacb11bcc94dadfd1c8f483ee4377b2b8b614e`; OpenTelemetry Demo `9bfe486ff48ee8a6ea942be74171342cb71a9327`; domain contracts `v1`
Known limitations/blockers: no raw telemetry, live connector, provider, persistence, or completed workflow is claimed; RE2-OB cases remain neutral selection records with unknown completeness until the Phase 2 per-case adapter runs; browser review is recorded in the Phase 1 evidence below, but screenshots are not checked in
Next gate: Phase 1 runnable vertical slice with persistent state and actual browser review at 1440/1280/768/390

## Phase 1 — Runnable vertical slice

**Status:** In progress — local SQLite API, authored fixture worker, React
shell, migration, focused flow tests, and browser review are implemented.
The PostgreSQL persistence implementation and PostgreSQL runtime/migration
verification remain pending.

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

Evidence record 2026-09-13
Status: in progress
Changed paths: `backend/incident_lens/api/`, `backend/incident_lens/worker/`, `backend/incident_lens/fixtures/`, `backend/migrations/`, `backend/tests/test_api.py`, `frontend/src/`, `frontend/vite.config.mjs`, `docs/LOCAL_DEVELOPMENT.md`, `README.md`
Acceptance evidence: local API flow in `backend/tests/test_api.py` covers session creation, three distinct case outcomes, UTC window preservation, evidence/findings/single-event timeline retrieval, guest isolation, cancellation, retry attempt, review history, reload from SQLite, idempotent report save, and downloadable JSON export; migration at `backend/migrations/001_initial.sql`; authored fixture and source boundary at `backend/incident_lens/fixtures/cases.json`; local run instructions at `docs/LOCAL_DEVELOPMENT.md`; local browser review exercised all three cases at 1440/1280/768/390 CSS pixels with no horizontal overflow, visible 3 px keyboard focus, explicit no-run state, and truthful unavailable actions
Checks: `uv run --project backend python -m unittest discover -s backend/tests -v` — pass (14 tests); `pnpm --dir frontend run lint` — pass; `pnpm --dir frontend run typecheck` — pass; `pnpm --dir frontend test` — pass; `pnpm --dir frontend run build` — pass; `uv run --project backend python -m incident_lens.validation.local README.md docs backend contracts data .env.example frontend/src` — pass; `git diff --check` — pass
Fixture/source versions: authored synthetic controlled fixture `fixture-v1`; FastAPI `0.141.1`; Pydantic `2.13.5`; SQLite local store; PostgreSQL migration `001_initial.sql`
Known limitations/blockers: PostgreSQL persistence implementation is not present and Docker/PostgreSQL are unavailable on this host, so migration/runtime verification is also pending; browser review was interactive and no screenshots are checked in yet; request-triggered FastAPI BackgroundTasks are bounded but durable queue/restart behavior remains Phase 4 work; fixture is not RCAEval or live telemetry
Next gate: implement PostgreSQL persistence, then verify the PostgreSQL runtime/migration path; Phase 2 source-adapter work can proceed independently against the persistent local contract

## Phase 2 — Real source adapters and data isolation

**Status:** In progress — pinned per-case fetch, portable deterministic
normalization, leakage/isolation checks, separate controlled-runtime adapter,
artifact references, and one reviewed quality report are implemented. Spark CI
parity and the remaining case review are not yet complete.

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

Evidence record 2026-09-14
Status: in progress
Changed paths: `backend/incident_lens/adapters/rcaeval.py`, `backend/incident_lens/adapters/otel.py`, `backend/incident_lens/pipeline/`, `backend/tests/test_phase2_pipeline.py`, `backend/migrations/002_artifact_references.sql`, `data/manifests/development.json`, `docs/evaluation/phase2-source-boundary.md`, `docs/evaluation/rcaeval-re2ob-001-quality.json`, `.github/workflows/phase2-offline.yml`, `docs/LOCAL_DEVELOPMENT.md`, `README.md`
Acceptance evidence: pinned RCAEval/Hugging Face per-case adapter with protected locators and raw cleanup; one real RE2-OB case quality report regenerated by `incident_lens.pipeline.generate_quality` with neutral IDs, deterministic counts/hashes, sub-second timestamp handling, and injection metadata excluded; independent OpenTelemetry controlled-runtime result schema; object-storage key/reference design in `backend/incident_lens/pipeline/artifacts.py` and `backend/migrations/002_artifact_references.sql`
Checks: `PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/tests -v` — pass (28 tests); `PYTHONPATH=backend backend/.venv/bin/python -m incident_lens.pipeline.check_leakage data/manifests` — pass; `PYTHONPATH=backend backend/.venv/bin/python -m incident_lens.validation.manifests data/manifests` — pass (3 manifests); `PYTHONPATH=backend backend/.venv/bin/python -m incident_lens.validation.local README.md docs backend contracts data .env.example frontend/src` — pass; `uv lock --project backend --check` — pass; `git diff --check` — pass; `.github/workflows/phase2-offline.yml` — parity/leakage workflow added, not run
Fixture/source versions: RCAEval `bb48c5aa9a24f1d5fcc716bdd479ea2d63145c90`; Hugging Face `afeacb11bcc94dadfd1c8f483ee4377b2b8b614e`; reviewed case `dev-re2ob-001`; normalization `incident-lens-normalization-v1`
Known limitations/blockers: Spark/Java CI workflow has not run, so Phase 2 remains in progress; PostgreSQL persistence implementation and PostgreSQL migration/runtime verification remain pending for Phase 1; raw telemetry and protected locators are not in Git
Next gate: run `.github/workflows/phase2-offline.yml` and inspect Spark/portable parity and leakage results

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
