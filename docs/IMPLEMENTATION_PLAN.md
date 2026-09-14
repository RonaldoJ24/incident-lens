# Incident Lens implementation plan

**Overall status:** Phases 0–2 complete. Phase 3 is blocked at its semantic
audit gate, Phase 4 is in progress, Phase 5 has a verified bounded owned-app
connector but an unrun pilot, and Phases 6–7 are in progress.

This plan is the source of truth for phase status and acceptance evidence. A
phase may begin when its dependencies are met, but it is not complete until
the listed artifacts and checks exist. Commands below are targets to establish;
they must not be described as working until the repository contains and passes
them.

## Planning handoff

**Planning review:** complete on 2026-09-13. **Application delivery:** the
persistent API/source foundations are verified; the ranking and provider-backed
investigation gates remain incomplete. The product contract, eight-stage
sequence, dependencies, acceptance gates, and open decisions remain the source
of truth.

The cited RCAEval project and dataset pages were checked during this review and
support the planned 735-case total, the 90-case multi-source RE2-OB subset, and
per-case access. The OpenTelemetry Demo and feature-flag pages also remain
available as the planned separate controlled-runtime source. This is a source
sanity check only: Phase 0 must still pin exact revisions and record license,
attribution, redistribution, and derived-artifact terms before data is reused.

| Phase | Current evidence | Next gate | Known decision or blocker |
| --- | --- | --- | --- |
| 0 | Scaffold, v1 contracts, rendered wireframe, audited manifests, and focused validation pass | Complete | No current Phase 0 blocker |
| 1 | React/FastAPI slice, SQLite fallback, PostgreSQL store/migrations, API flow tests, and PostgreSQL 16 CI run `34819200466` | Complete | Local Docker is unavailable; the required PostgreSQL path is verified in CI |
| 2 | Pinned per-case adapter, portable/Spark normalization, isolation checks, reviewed real-case report, and Spark CI run `34813930327` | Complete | Raw telemetry and protected locators remain outside Git by design |
| 3 | Real grouped train/validation rows, rules/Isolation Forest comparison, artifact verification, and sealed final-test policy | Correct feature semantics and per-run operational metrics before model selection | Audit found unsupported latency naming and globally aggregated/non-operational metrics; current report is provisional and final held-out remains sealed |
| 4 | Local TF-IDF/LSA retrieval, citations, typed compiled LangGraph, durable checkpoints, review, recovery, hostile-input tests, bounded provider seam, and expanded reviewed corpus | Root-level live provider verification and grounded claim review over the configured model | Provider path has mocked tests only; no live provider or production claim is made |
| 5 | Bounded guest upload flow plus fixed-path, metadata-only live verification of the owned `cadencia-ai` GitHub Actions feed | Keep live connector scope explicit; pilot outreach requires authorization | Connector evidence is CI metadata, not application incident telemetry; pilot protocol is unrun |
| 6 | Reproducible release checks, container/CI contract, runbooks, threat/model cards, controlled workload, four-width browser-local visual review, and green release matrix run `34821311229` | Preserve the public preview boundary and verify any future full backend hosting; the static Pages preview is available at [ronaldoj24.github.io/incident-lens](https://ronaldoj24.github.io/incident-lens/) | Final held-out stays sealed; provider cost/hosted latency and full browser/API integration are not measured |
| 7 | Static authored-fixture preview and Pages workflow implemented; final UI deploy run `34821311324` verified at [ronaldoj24.github.io/incident-lens](https://ronaldoj24.github.io/incident-lens/) | Keep the README and preview explicit about browser-local authored-fixture behavior | Static preview is not the FastAPI/PostgreSQL/provider-backed application |

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

**Status:** Complete — local SQLite and PostgreSQL-backed paths, ordered
migrations, the React investigation shell, focused flow tests, and PostgreSQL
16 CI verification are recorded.

**Dependencies:** Phase 0 contracts and design decisions.

**Deliverables**

- React/TypeScript frontend Investigate route with the default checkout example,
  degraded-performance and insufficient-evidence examples, responsive shell,
  findings area, evidence drawer, timeline, keyboard behavior, and explicit
  empty/loading/partial/error states.
- FastAPI/Pydantic API plus background worker with PostgreSQL persistence and
  migrations for
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
- `backend/tests/test_postgres_integration.py` covers ordered migration records,
  API flow persistence across app reload, transaction rollback, and concurrent
  idempotent run writes when `INCIDENT_LENS_DATABASE_URL` is configured.

**Checks to establish**

- `docker compose up --build`
- `pnpm --dir frontend test`
- `uv run --project backend pytest -m integration`
- `pnpm --dir frontend e2e -- --width=1440`

Evidence record 2026-09-14
Status: complete
Changed paths: `backend/incident_lens/api/store.py`, `backend/incident_lens/api/app.py`, `backend/incident_lens/migrations.py`, `backend/migrations/`, `backend/tests/test_postgres_integration.py`, `backend/pyproject.toml`, `backend/uv.lock`, `backend/Dockerfile`, `compose.yml`, `.github/workflows/phase1-postgres.yml`, `.env.example`, `docs/CONFIGURATION.md`, `docs/LOCAL_DEVELOPMENT.md`, `README.md`
Acceptance evidence: local API flow in `backend/tests/test_api.py` covers session creation, three distinct case outcomes, UTC window preservation, evidence/findings/timeline retrieval, guest isolation, cancellation, retry, review history, reload from SQLite, idempotent report save, and downloadable JSON export; `PostgresStateStore` uses parameterized SQL, JSONB payloads, explicit transactions, foreign keys, and unique-key idempotency; `backend/tests/test_postgres_integration.py` covers migrations, persistence across reload, rollback, concurrent idempotency, and ownership against PostgreSQL 16
Checks: PostgreSQL CI workflow run `34819200466` — pass (3 live PostgreSQL integration tests and the complete then-current backend suite); `uv lock --project backend --check` — pass; local browser review — pass with screenshots inspected but not checked in
Fixture/source versions: authored synthetic controlled fixture `fixture-v1`; SQLite local fallback; PostgreSQL 16; migrations `001_initial.sql` through `003_workflow_checkpoints.sql`
Known limitations/blockers: Docker/PostgreSQL are unavailable on this host, so local container execution is deferred to CI; the fixture is authored controlled data, not RCAEval or live telemetry
Next gate: complete the later provider-backed retrieval and release gates without reopening Phase 1

## Phase 2 — Real source adapters and data isolation

**Status:** Complete — pinned per-case fetch, portable and Spark deterministic
normalization, leakage/isolation checks, separate controlled-runtime adapter,
artifact references, one reviewed quality report, and Spark CI parity are
implemented and verified.

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
Status: complete
Changed paths: `backend/incident_lens/adapters/rcaeval.py`, `backend/incident_lens/adapters/otel.py`, `backend/incident_lens/pipeline/`, `backend/tests/test_phase2_pipeline.py`, `backend/migrations/002_artifact_references.sql`, `data/manifests/development.json`, `docs/evaluation/phase2-source-boundary.md`, `docs/evaluation/rcaeval-re2ob-001-quality.json`, `.github/workflows/phase2-offline.yml`, `docs/LOCAL_DEVELOPMENT.md`, `README.md`
Acceptance evidence: pinned RCAEval/Hugging Face per-case adapter with protected locators and raw cleanup; one real RE2-OB case quality report regenerated by `incident_lens.pipeline.generate_quality` with neutral IDs, deterministic counts/hashes, sub-second timestamp handling, and injection metadata excluded; independent OpenTelemetry controlled-runtime result schema; object-storage key/reference design in `backend/incident_lens/pipeline/artifacts.py` and `backend/migrations/002_artifact_references.sql`
Checks: `PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/tests -v` — pass (28 tests before Phase 3 additions); `PYTHONPATH=backend backend/.venv/bin/python -m incident_lens.pipeline.check_leakage data/manifests` — pass; `PYTHONPATH=backend backend/.venv/bin/python -m incident_lens.validation.manifests data/manifests` — pass (5 manifests, including the Phase 3 train/validation manifests); `PYTHONPATH=backend backend/.venv/bin/python -m incident_lens.validation.local README.md docs backend contracts data .env.example frontend/src` — pass; `uv lock --project backend --check` — pass; `git diff --check` — pass; `.github/workflows/phase2-offline.yml` — pass on GitHub Actions run `34813930327` (Java 17, Spark/portable parity, sub-second fixture, leakage rejection)
Fixture/source versions: RCAEval `bb48c5aa9a24f1d5fcc716bdd479ea2d63145c90`; Hugging Face `afeacb11bcc94dadfd1c8f483ee4377b2b8b614e`; reviewed case `dev-re2ob-001`; normalization `incident-lens-normalization-v1`
Known limitations/blockers: eleven selected development cases retain unknown completeness and must be reviewed before a meaningful Phase 3 comparison; PostgreSQL runtime verification is tracked under the Phase 1 CI gate; raw telemetry and protected locators are not in Git
Next gate: produce leakage-safe, quality-reviewed training and validation inputs for Phase 3 without opening the sealed final test

## Phase 3 — ML train, evaluate, and serve

**Status:** Blocked — a real grouped rules/Isolation Forest comparison exists,
but its current feature names and aggregate metrics failed semantic review. The
checked-in report is provisional and cannot select a model or threshold.

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

Evidence record 2026-09-14
Status: blocked
Changed paths: `backend/incident_lens/ml/`, `backend/tests/test_phase3_ml.py`, `backend/pyproject.toml`, `backend/uv.lock`, `data/manifests/train.json`, `data/manifests/validation.json`, `docs/evaluation/phase3-artifact-manifest.json`, `docs/evaluation/phase3-validation-report.json`, `frontend/src/App.tsx`, `backend/incident_lens/worker/runner.py`
Acceptance evidence: public grouped train/validation manifests contain neutral IDs and aggregate rows; `docs/evaluation/phase3-artifact-manifest.json` verifies the artifact bytes; the report compares rules and Isolation Forest but is explicitly provisional; serving/UI language uses unusual service/window ranking rather than a causal probability
Checks: Phase 3 tests, manifest validation, leakage checks, artifact verification, and mechanical validation pass; semantic acceptance fails because source `latency-90` samples were labeled as mean/p95 features and MRR/false-alarm metrics were globally aggregated rather than computed per independent run at an operational alert policy
Fixture/source versions: RCAEval `bb48c5aa9a24f1d5fcc716bdd479ea2d63145c90`; Hugging Face `afeacb11bcc94dadfd1c8f483ee4377b2b8b614e`; normalization `incident-lens-normalization-v1`; artifact `incident-lens-ranking-v1`; feature schema `incident-lens-features-v1`
Known limitations/blockers: current model selection and thresholds are not accepted; complete-investigation quality is not measured; final held-out manifest remains sealed
Next gate: correct feature semantics and per-run ranking/false-alarm evaluation, freeze the resulting model/retrieval/provider decisions, and only then authorize final-held-out evaluation

## Phase 4 — RAG and persistent evidence workflow

**Status:** In progress — local deterministic retrieval, typed LangGraph
workflow, evidence support evaluation, hostile-log handling, source
withholding, checkpoint/restart/cancel/retry, idempotent reports, a bounded
provider-neutral OpenAI-compatible seam, and an expanded reviewed retrieval
corpus are implemented and locally tested. PostgreSQL runtime is verified in
CI, while live provider verification and claim-quality review remain pending.

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

Evidence record 2026-09-14
Status: in progress
Changed paths: `backend/incident_lens/provider/`, `backend/incident_lens/config.py`, `backend/incident_lens/workflow/graph.py`, `backend/incident_lens/api/app.py`, `backend/incident_lens/retrieval/`, `backend/incident_lens/evaluation/retrieval.py`, `backend/tests/test_phase4_provider.py`, `backend/tests/test_phase4_workflow.py`, `data/knowledge/verified-runbooks-v1.json`, `data/manifests/knowledge-sources.json`, `data/manifests/retrieval.json`, `.env.example`, `docs/CONFIGURATION.md`, `docs/evaluation/phase4-retrieval-report.json`, `docs/evaluation/phase4-workflow-evidence.md`, `README.md`
Acceptance evidence: the API injects a provider-neutral OpenAI-compatible generator when a key is configured and otherwise uses a clearly labelled deterministic non-provider fallback; prompts and outputs are bounded, retries/timeouts/call caps are explicit, structured claims require explicit uncertainty and retrieved source IDs, and provider failures never substitute an authored replay. Unknown citations, malformed/truncated JSON, timeout, provider-error, no-key, forbidden-tool, and secret-boundary paths have mocked tests. The reviewed index contains 14 concise paraphrased summaries and the manifest contains 15 queries with decoys; local retrieval reports Recall@1 1.0, Recall@3 1.0, and MRR 1.0. Existing compiled workflow checkpoint/recovery, withholding, cancellation, review, and hostile-input evidence remains covered.
Checks: `PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_phase4_provider backend.tests.test_phase4_workflow -v` — pass (16 tests); `PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/tests -v` — pass (77 tests, 3 PostgreSQL tests skipped because `INCIDENT_LENS_DATABASE_URL` is unset); `PYTHONPATH=backend backend/.venv/bin/python -m incident_lens.validation.manifests data/manifests` — pass; `PYTHONPATH=backend backend/.venv/bin/python -m compileall -q backend/incident_lens` — pass; `git diff --check` — pass
Known limitations/blockers: live provider verification, provider cost/latency, and claim-quality review remain unrun; the local retrieval metrics are not production or incident-diagnosis quality measures; browser evidence covers the authored static preview rather than the full API path
Next gate: root-level live provider test with an explicitly authorized key, then separate claim-support evaluation and review of safe provider failures before any Phase 4 completion decision

## Phase 5 — Guest testing, uploads, and owned live connector

**Status:** In progress — bounded guest upload validation, quota/policy helpers,
and a strict read-only connector are implemented. One live fixed-path HTTPS
verification against the owned `cadencia-ai` application is recorded.

**Dependencies:** Phase 4 evidence workflow and Phase 2 upload/source contracts.

**Deliverables**

- Bounded JSONL upload flow with downloadable sample, schema validation,
  missing-signal report, size/type/retention limits, cancellation, and isolated
  guest state.
- [Exploratory pilot protocol](evaluation/phase5-pilot-protocol.md) for 3–5
  willing engineers using matched tasks, a declared counterbalanced order,
  exact timing/correctness rules, consent/privacy handling, and structured
  feedback. Results remain exploratory; no unsupported significance or broad
  impact claim, and no outreach without explicit authorization.
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

Evidence record 2026-09-14
Status: in progress
Changed paths: `backend/incident_lens/uploads.py`, `backend/incident_lens/connectors.py`, `backend/incident_lens/provider_policy.py`, `backend/incident_lens/api/app.py`, `backend/tests/fixtures/uploads/`, `backend/tests/test_phase5_uploads.py`, `backend/tests/test_phase5_connector.py`, `contracts/v1/api.openapi.json`, `contracts/v1/domain.schema.json`, `.env.example`, `docs/CONFIGURATION.md`, `docs/evaluation/phase5-pilot-protocol.md`, `docs/evaluation/phase5-live-connector.md`
Acceptance evidence: streamed JSONL validation enforces 10 MiB/256 KiB/10,000-record bounds, strict event fields, retention cleanup, isolation, cancellation, duplicate/conflict/missing/untrusted counts, and per-session budgets; `GET /v1/connectors/verify` performs one GET to a configured fixed path and returns source/access metadata, bounded top-level keys, and a payload digest without returning raw data; the [live evidence note](evaluation/phase5-live-connector.md) records a successful bounded call to the owned maintained `cadencia-ai` GitHub Actions feed; the [pilot protocol](evaluation/phase5-pilot-protocol.md) is executable but explicitly unrun
Checks: connector/upload focused tests — pass; full local backend suite — 70 passed, 3 PostgreSQL skips; live connector — verified `application/json`, 64,694 bytes, five returned workflow runs at the recorded access time
Fixture/source versions: authored Phase 5 JSONL fixtures; controlled HTTP server fixture; `github-actions:RonaldoJ24/cadencia-ai` / `github-actions-v3`
Known limitations/blockers: the live connector evidence is CI/operational metadata, not application incident telemetry; its public default configuration remains empty; the pilot is unrun and no participants were contacted; uploads remain process-local
Next gate: retain the connector's narrow scope in the public presentation and run the pilot only with explicit outreach authorization

**Checks to establish**

- `uv run --project backend pytest -m uploads`
- `pnpm --dir frontend e2e -- --scenario guest-isolation`
- `python -m incident_lens.validation.injection_fixtures`
- `python -m incident_lens.validation.cost_budget --workload sample`

## Phase 6 — Hardened deployment, evaluation, and visual QA

**Status:** In progress — reproducible local release checks, provider-neutral
deployment contract, container hardening, readiness/metrics hooks, rollback
runbook, threat/access review, model/data card, controlled workload
measurement, and browser-local visual review are implemented. Release matrix
run `34821311229` is green across backend/PostgreSQL, frontend, and container;
the static authored-fixture Pages preview is verified separately by run
`34821311324` at <https://ronaldoj24.github.io/incident-lens/>. Full API/
PostgreSQL browser integration, a backend deployment, and final held-out
evaluation remain unverified/sealed.

**Dependencies:** Phases 1–5 complete or documented blockers with independent
work finished.

**Deliverables**

- Reproducible local/container setup, migrations, CI, observability, secret
  management, deployment contract, rollback, and runbook.
- A verified public deployment, required for intended delivery, plus frozen
  final/held-out evaluation and separate controlled telemetry results. The final
  test remains sealed until model, threshold, retrieval, and prompt decisions
  are fixed.
- Measurement of p50/p95 latency, completion, recovery, and supported upload
  workloads with sample sizes and versions. Provider cost remains explicitly
  not measured.
- Browser visual review with actual screenshots and interaction checks at all
  four target widths, including keyboard, focus, error, and mobile states.
- Final threat/access review and a concise model/data card.

**Acceptance evidence**

- `Makefile` exposes setup, unit/integration, contracts, leakage/injection,
  reproducibility, evaluation, performance, frontend, visual-review, and
  release-check targets without opening final-held-out data.
- CI workflow `phase6-release.yml` verifies contracts, unit/PostgreSQL
  integration, frontend build, leakage/injection, reproducibility, controlled
  performance, container rendering, and non-root image checks.
- `docs/OPERATIONS.md`, `docs/THREAT_MODEL.md`, and `deploy/` document
  migrations, rollback, health/metrics, secret boundaries, and a provider/
  URL-neutral release contract.
- `docs/evaluation/phase6-performance.md` records local controlled workload
  results with failures, limits, sample sizes, and versions. Provider cost,
  hosted latency, public deployment, and live connector performance remain not
  measured.
- [Browser visual review evidence](evaluation/phase6-visual-review.md) records
  the dated browser-local authored preview review, responsive layout checks,
  keyboard focus, upload, source-withholding, save/export, reload, and
  uncertainty flows. Screenshots were captured and inspected interactively but
  are not checked in. No full FastAPI/PostgreSQL, public deployment, provider,
  connector, or repair claim follows from this review.

**Checks to establish**

- `make setup`
- `make release-check`
- `docker compose config` with `POSTGRES_PASSWORD` supplied only through an
  ignored environment file
- `make evaluate`
- `make visual-review`
- Follow the rollback procedure in `docs/OPERATIONS.md` using a managed
  PostgreSQL snapshot and an immutable prior image; no destructive down
  migration is provided.

Evidence record 2026-09-14
Status: in progress
Changed paths: `Makefile`, `.github/workflows/phase6-release.yml`, `backend/Dockerfile`, `backend/incident_lens/observability.py`, `backend/incident_lens/validation/performance.py`, `backend/incident_lens/api/app.py`, `backend/incident_lens/api/store.py`, `backend/tests/test_phase6_release.py`, `contracts/v1/api.openapi.json`, `compose.yml`, `deploy/compose.release.yml`, `deploy/README.md`, `.env.example`, `README.md`, `docs/CONFIGURATION.md`, `docs/LOCAL_DEVELOPMENT.md`, `docs/OPERATIONS.md`, `docs/THREAT_MODEL.md`, `docs/MODEL_DATA_CARD.md`, `docs/evaluation/phase6-performance.md`, `docs/evaluation/phase6-visual-review.md`
Acceptance evidence: local release command surface, provider-neutral release compose contract, non-root/healthchecked API image, readiness and bounded metrics endpoints, migration/rollback runbook, threat/access review, model/data card, and controlled workload measurement report
Checks: release matrix run `34821311229` — pass (backend/PostgreSQL, frontend, and container jobs); final UI deploy run `34821311324` — pass (static authored-fixture preview at <https://ronaldoj24.github.io/incident-lens/>); `make release-check PERF_SAMPLES=20` — pass; full backend discovery ran 70 tests with 3 PostgreSQL skips because no `INCIDENT_LENS_DATABASE_URL` is configured; contracts, leakage, injection, reproducibility, artifact verification/validation, readiness/metrics/container boundary tests, and local controlled workload measurement passed; frontend lint/typecheck/test/build passed; `uv lock --project backend --check` — pass; `uv run --project backend python -m compileall -q backend/incident_lens` — pass; local link/privacy validator — pass; `git diff --check` — pass; compose files parsed with Ruby YAML because Docker is unavailable
Fixture/source versions: authored `fixture-v1`, Phase 5 upload sample `phase5-upload-v1`, Phase 3 artifact `incident-lens-ranking-v1`, workload `phase6-local-controlled-v1`
Known limitations/blockers: the verified public URL is only a browser-local authored static preview; no backend deployment/provider is configured; provider cost and hosted latency are not measured; the browser evidence covers only the static preview, not full FastAPI/PostgreSQL integration; screenshots are not checked in; final held-out data remains sealed
Next gate: if a full public application is pursued, verify its API/PostgreSQL browser path and preserve the connector's narrow metadata-only scope; do not treat the Pages preview or green release matrix as Phase 6 completion

## Phase 7 — Final public presentation

**Status:** In progress — the README and static authored-fixture Pages preview
are verified, while the full application presentation remains bounded by the
known provider, backend-hosting, Phase 3, Phase 4, and pilot limitations.

**Dependencies:** Phase 6 acceptance evidence and a verified public preview;
a full public backend deployment remains optional future work and is not
claimed here.

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

- `PYTHONPATH=backend python3 -m incident_lens.validation.local README.md docs`
- `git diff --check`
- `make release-check`

Evidence record 2026-09-14
Status: in progress
Changed paths: `README.md`, `docs/IMPLEMENTATION_PLAN.md`, `frontend/src/App.tsx`, `frontend/src/demoAdapter.ts`, `frontend/src/UploadPanel.tsx`, `frontend/src/styles.css`, `frontend/scripts/test.mjs`, `.github/workflows/public-demo-pages.yml`
Acceptance evidence: README links the verified static Pages preview at
<https://ronaldoj24.github.io/incident-lens/>, identifies it as a browser-local
authored-fixture demo, documents the exact local setup/API/evaluation/deployment
surfaces, and publishes Phase 3/4/5 limitations. The deployed UI exposes
accessible Evaluation and Engineering sections, a compact investigation
hierarchy (context, primary finding, evidence drawer, timeline, review actions),
and a collapsed optional upload. Primary status/finding copy is plain-language;
technical details and the backend/provider/connector boundary remain explicit
in disclosures. Canonical fixture values are concrete and reproducible:
`checkout-failure` on `checkoutservice` from `2026-09-13T08:00:00Z` to
`2026-09-13T08:10:00Z` includes error rate `0.24`, latency `820 ms`, and a
`910 ms` trace; `degraded-performance` runs from `2026-09-13T09:00:00Z` to
`2026-09-13T09:10:00Z` with `640 ms`
latency, `0.04` error rate, and a `640 ms` trace; `insufficient-evidence` runs
from `2026-09-13T10:00:00Z` to `2026-09-13T10:10:00Z` with metric and trace
records missing. Browser
acceptance at `1280x800` and `390x844` found no horizontal overflow; screenshots
were captured and inspected but are not checked in. Final UI deploy run
`34821311324` passed; release matrix run `34821311229` passed its
backend/PostgreSQL, frontend, and container jobs; PostgreSQL integration run
`34819200466` passed.
Checks: `PYTHONPATH=backend python3 -m incident_lens.validation.local README.md docs` — pass; `git diff --check` — pass; manual link/path/privacy-sensitive wording review — pass
Fixture/source versions: browser preview `VITE_INCIDENT_LENS_DEMO=1`, authored
fixture `fixture-v1`; connector evidence remains the metadata-only
`github-actions:RonaldoJ24/cadencia-ai` / `github-actions-v3` record
Known limitations/blockers: the Pages URL is not hosted FastAPI/PostgreSQL,
provider, or connector infrastructure; Phase 3 semantic audit remains
blocked, Phase 4 live provider verification and claim-quality review remain
pending despite the bounded provider seam and 14-document local corpus, the
pilot is unrun, and no repair claim is made
Next gate: keep the public presentation aligned with verified behavior; only
mark this phase complete after the README acceptance checks and review of the
remaining blockers, without marking the overall project complete

## Current blockers and decisions

There is no blocker to foundation documentation. The static authored-fixture
Pages preview is verified at
<https://ronaldoj24.github.io/incident-lens/>; it is a browser-local preview,
not hosted FastAPI/API/PostgreSQL/provider infrastructure. The owned-app
connector is also verified, but only as a bounded metadata-only GitHub Actions
call against `RonaldoJ24/cadencia-ai`, as recorded in
`docs/evaluation/phase5-live-connector.md`; it is not application incident
telemetry. Remaining blockers are the Phase 3 semantic metrics audit, live
verification and claim-quality review for the Phase 4 provider seam, public
backend/API/PostgreSQL hosting, and the unrun pilot. These blockers do not
mark the overall project complete and do not support a repair claim.
