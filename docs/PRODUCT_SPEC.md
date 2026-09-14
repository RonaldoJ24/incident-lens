# Incident Lens product specification

**Status:** foundation specification; implementation has not started.

This document is the product and interaction contract for Incident Lens. It is
intentionally specific about investigation behavior, evidence, and uncertainty
so a later implementation does not collapse into a generic chat screen or a
decorative observability dashboard.

## 1. Product intent

Incident Lens helps a software engineer investigate a failed checkout without
pretending that a model has proved a root cause. The product combines bounded
analysis of recorded or connected telemetry with cited operational knowledge.
Every conclusion should make it possible to answer three questions:

1. What is the current finding?
2. Which evidence supports, weakens, or contradicts it?
3. What can the engineer inspect or ask next?

The promise is: **Understand what failed, see the evidence, and continue the
investigation.** The product may return “insufficient evidence” or “unresolved.”
It never performs remediation, changes live fault controls, or treats report
export as service recovery.

### 1.1 Product truths

- A release or deployment near the incident is a useful investigation clue,
  never proof of causality by timestamp alone.
- Scores rank unusual service/window behavior. They are not root-cause
  probabilities and must be described accordingly.
- Retrieved runbooks and prior incidents are supporting sources. They do not
  replace telemetry and must be cited at claim level.
- Missing, delayed, conflicting, or withheld evidence changes confidence and is
  visible to the engineer.
- Telemetry origin and execution are independent fields shown in the UI and
  report metadata. “Fresh inference,” “recorded replay,” and “previously
  completed example” are combinations of those fields, not competing origins.
- A completed workflow can still have an unresolved diagnosis. A saved report
  records the investigation state; it does not mean the system was fixed.

### 1.2 Non-goals

Incident Lens does not provide autonomous remediation, write access to
production systems, a general-purpose chat assistant, an unbounded SQL or shell
executor, a fake live dashboard, an employment or compliance claim, or a
benchmark score presented without its split, versions, workload, and sample
size.

## 2. Audience and interview path

The primary audience is a software engineer or on-call engineer reviewing a
service incident. The first use should require no signup, API key, local
installation, or uploaded data when using the recorded samples.

The primary CTA opens the default checkout incident. The navigation contains
three destinations:

- **Investigate** is the task workspace. It contains the service and time
  window controls, findings, evidence, timeline, follow-up actions, and report
  export.
- **Evaluation** explains the current data split, baselines, model/retrieval
  checks, uncertainty tests, supported upload fixtures, and known failures.
  It must show “not yet measured” where an artifact does not exist.
- **Engineering** explains the architecture, typed boundaries, state recovery,
  safety controls, and reproducible local/deployment workflow.

The three examples are deliberately different:

1. **Checkout failure:** enough signals for a ranked investigation with
   competing explanations.
2. **Degraded performance:** latency and saturation clues where the release
   timestamp is suggestive but not conclusive.
3. **Insufficient evidence:** missing metrics or traces that should produce a
   clear gap report and a request for the next useful check.

An engineer should reach one useful evidence-backed interaction within the
first minute. This is a design target to validate with browser timing; it is
not a measured performance claim.

## 3. Investigation workspace

### 3.1 Layout and hierarchy

The main workspace has a stable reading order:

1. **Context bar:** incident title, explicit telemetry-origin and execution
   labels, service selector, time-window control, and run/re-run action.
2. **Findings column:** one readable findings area with a short assessment,
   confidence/uncertainty language, key checks, and next suggested checks.
3. **Evidence drawer:** on-demand logs, metrics, traces, and knowledge sources
   with claim-level citations. It opens beside the findings on wide screens and
   as a full-height drawer on narrow screens.
4. **Execution timeline:** collapsed by default after the first run; expanding
   it shows actual tool calls, start/end state, bounded parameters, duration,
   evidence returned, retries, and failures.
5. **Review bar:** accept or correct a finding, challenge it with a question,
   withhold an evidence source, change the window, rerun, and save/export.

The page should feel like an investigation notebook with a clear evidence trail,
not a grid of metric cards. Charts appear only when they answer a stated check;
the interface must not invent a metric, health badge, or “resolved” status.

### 3.2 Responsive behavior

The implementation must be reviewed at 1440, 1280, 768, and 390 CSS pixels.

- At 1440 and 1280, findings remain the visual anchor and the evidence drawer
  can be opened beside them without pushing the task below the fold.
- At 768, the drawer becomes a deliberate overlay or stacked panel while the
  context controls remain usable without horizontal scrolling.
- At 390, the findings appear first, evidence and timeline open as sheets or
  accordions, and primary actions remain reachable with one hand. No dense
  multi-column table is required to understand the conclusion.

Use a consistent spacing scale, readable line length, and intentional type
hierarchy. The visual system should reserve the strongest accent for the
current investigation action and use semantic colors only with text/icon
labels: supported, uncertain, conflicting, missing, and failed. Body text and
focus indicators must meet accessible contrast expectations.

The visual baseline is a warm light reading canvas, strong dark typography,
restrained slate/blue accents, semantic amber/error colors, and monospace only
for telemetry. It should feel crisp and calm with purposeful charts based on
actual data, with source detail available on demand. Do not use a neon or
gradient hero, oversized marketing block, or generic card wall.

### 3.3 Required states

Every data-bearing component needs explicit states for:

- empty/no incident selected;
- initial loading with a human-readable progress message;
- running with current step and cancellation affordance;
- partial evidence with what is missing and why;
- successful findings with source citations;
- unresolved or conflicting evidence;
- provider, quota, timeout, or tool failure with a safe retry path;
- previously completed example, clearly labeled as replayed/cached and never
  described as a live result;
- upload validation failure and accepted upload summary;
- saved report confirmation and export failure.

Skeletons must not imply that evidence exists before it is returned. A failed
live run may offer an explicitly labeled completed example, but the UI must not
silently substitute it.

### 3.4 Interaction and accessibility

All actions must work with keyboard navigation, visible focus, logical tab
order, semantic headings, labels tied to controls, and screen-reader text for
status changes. Drawer and dialog focus must be managed and return to the
trigger. Do not rely on color alone. Long log lines wrap or scroll without
breaking the page. Copyable evidence includes its source, event time, and
whether it was recorded, uploaded, or retrieved knowledge.

Follow-up questions and challenges should preserve the current run context and
create a new bounded workflow step. They should not erase the prior finding.
When an engineer withholds a source, the resulting run and report must record
that omission so a comparison is honest.

## 4. Data, evidence, and origins

### 4.1 Evidence object

The backend should represent each evidence item with a stable ID, source type
(`log`, `metric`, `trace`, `runbook`, `prior_knowledge`, or `metadata`), source
and version, event or document time, query/window, content or summary, quality
flags, and access scope. Findings reference evidence IDs rather than copying an
uncited paragraph into a response.

Evidence quality flags include missing, delayed, sampled, duplicate, malformed,
conflicting, withheld, and synthetic/controlled. The UI should explain these
flags in plain language.

### 4.2 Independent provenance fields

Every run and report carries independent provenance fields rather than one
mutually exclusive label:

- **Telemetry origin:** `recorded_benchmark`, `controlled_runtime`,
  `guest_upload`, or `connected_app`.
- **Execution:** `new_analysis` or `stored_result`. A new analysis over a
  recorded case and a stored replay therefore share telemetry origin while
  remaining distinguishable by execution.
- **Source interval:** the start/end time window, case or upload identifier,
  source version, and signal completeness metadata.
- **Run metadata:** run version, execution time, workflow revision, and a link
  to the prior run when `execution` is `stored_result`. The UI may explain that
  stored result as a pinned replay or previously completed example, but that
  display text is not a competing telemetry origin.

The connected-app value is valid only for a real read-only connector to an
owned maintained application after credentials and external access are
available. A connector stub does not satisfy the integration target. Reports
must never omit provenance or make an old result appear current.

### 4.3 Planned public sources

The initial benchmark audit uses [RCAEval](https://github.com/phamquiluan/RCAEval)
and the [Hugging Face copy](https://huggingface.co/datasets/phamquiluan/RCAEval).
The source describes 735 cases overall; development begins with 10–20 cases
from RE2-OB, whose 90 cases include logs, metrics, and traces. Other subsets
may have different formats and must be adapted separately. Cases are fetched
per case; raw downloads and hidden labels stay outside Git. Filenames and
indexes that reveal causes are neutralized before model prompts, retrieval, or
evaluation.

The [OpenTelemetry Demo](https://opentelemetry.io/docs/demo/) and [feature flag
scenario](https://opentelemetry.io/docs/demo/feature-flags/) provide a separate
controlled-failure source. Its adapters and results remain separate from
RCAEval. Runbooks are written and verified from public app documentation and
development incidents; held-out solutions do not enter the knowledge index.
Attribution and the current license terms are recorded before distributing
derived artifacts.

## 5. Analysis and retrieval behavior

### 5.1 Offline normalization and anomaly ranking

PySpark is an offline pipeline for schema normalization, deduplication, quality
checks, timestamp/window features, and versioned manifests. It is not a live
request dependency. Anomaly ranking begins with a scikit-learn method such as
Isolation Forest and is compared with error-rate and latency rules. The chosen
method must be based on held-out evidence, not on the appeal of a model name.

Splits are by grouped independent runs with no nearby-window leakage. Training
fits artifacts on the training manifest. Validation selects models, thresholds,
retrieval settings, and prompts. The final test manifest is frozen and sealed
until those decisions are fixed; it is never used for tuning. The evaluation
reports event detection, false alarms, and ranking metrics separately from
complete investigation quality such as failing-service identification, useful
checks, evidence support, and uncertainty under missing/conflicting evidence.
Scores rank unusual service/windows; they are not causal probabilities.

### 5.2 Retrieval

Runtime retrieval combines lexical and semantic search over versioned runbooks
and prior knowledge. Each returned passage carries a stable source/version
citation. Retrieval quality is evaluated separately from whether a generated
claim is supported. The system should expose the retrieved source and let an
engineer see when no source supports a claim.

### 5.3 Investigation workflow

The workflow uses persistent LangGraph orchestration with typed state, explicit
read-only tools, bounded call count/time/cost, checkpoint/restart, cancellation,
and idempotent report writes. A conceptual run is:

1. validate session, telemetry origin, execution, service, time window, and
   source permissions;
2. load the pinned manifest and inspect signal completeness;
3. run bounded telemetry checks and record actual outputs;
4. rank unusual service/windows and retrieve relevant knowledge;
5. form findings with evidence IDs, uncertainty, and competing explanations;
6. evaluate claim support and unsafe/untrusted content;
7. present for human review, accept/correct/challenge, and optionally rerun;
8. persist an immutable report revision and export it with all provenance
   fields.

The workflow must be restartable from a checkpoint and safe to retry. A model
may propose the next permitted check, but the tool layer validates scope,
parameters, and read-only behavior before execution.

## 6. Backend contract and boundaries

The planned backend is one Python package with FastAPI/Pydantic API, worker,
offline pipeline, and ML modules, plus PostgreSQL state. Exact paths and schemas
will be versioned during Phase 0; the following capabilities are required, not
implemented endpoints:

- create/read an isolated guest session;
- list incident examples and retrieve a case manifest;
- start, cancel, retry, and inspect an investigation run;
- submit bounded JSONL upload, validate it, and report missing signals;
- retrieve findings, evidence, timeline events, and independent provenance;
- accept/correct/challenge a finding and start a bounded follow-up;
- save immutable report revisions and export a report;
- expose evaluation/engineering metadata without exposing hidden labels.

The API should expose the independent telemetry-origin, execution, source
interval, and run-version/time fields on run and report responses.

PostgreSQL stores session, run, evidence reference, workflow checkpoint, and
report state. pgvector is limited to versioned knowledge retrieval. Raw
telemetry and large derived artifacts use object storage. Background work must
surface progress and cancellation rather than blocking an HTTP request.

Each guest session has isolated state, bounded upload size/retention, and no
ability to mutate shared live fault controls. Secrets are supplied through the
deployment secret manager. Logs are treated as untrusted content and are
redacted or constrained before entering prompts or citations.

## 7. Evaluation and release evidence

Evaluation keeps these sets and activities distinct:

- public demo examples;
- development cases used for iteration;
- frozen final/held-out cases;
- controlled OpenTelemetry failures;
- exploratory pilot tasks with 3–5 willing engineers;
- any live customer activity, only if it actually becomes available.

The evaluation record includes versions, manifests, workloads, sample sizes,
metrics, failure cases, and known limits. It covers event detection and false
alarms, failing-service identification, useful next checks, retrieval/citation
support, uncertainty with missing/conflicting evidence, model/rule and
retrieval baselines/ablations, upload support, prompt-injection resilience,
access boundaries, restart/cancel/retry/idempotency, and p50/p95 latency/cost.
No number is published before it is measured and reproducible.

The exploratory pilot may record task time, correctness against a reviewed
answer key, and structured feedback for matched tasks with a declared task
order balance and sample size. It remains exploratory: do not claim statistical
significance, broad impact, or production usage, and do not contact participants
without explicit authorization.

## 8. Completion bar for the product

Incident Lens is ready for a public presentation only when the implementation
plan's phases have evidence for the working UI, persistent API, real adapters,
data isolation, honest model/retrieval comparisons, workflow recovery, guest
controls, browser visual review, a verified public deployment, a real owned-app
read-only connector, and measured limitations. Missing credentials or external
access are specific outstanding blockers and cannot be hidden by a stub or
counted as completion.
The final README can then describe the implemented behavior, tested setup and
commands, real demo URL, screenshots/walkthrough, architecture, attribution,
model/data/evaluation notes, API examples, runbook, and original contribution.
