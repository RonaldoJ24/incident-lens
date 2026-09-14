# Incident Lens

### AI incident investigation for software teams

**Understand what failed, see the evidence, and continue the investigation.**

> **Status: Phase 1 local slice in progress; Phase 2 source work complete.** The
> repository contains a runnable React/TypeScript and FastAPI/Pydantic slice
> over a small authored SQLite fixture, plus a pinned, leakage-safe RCAEval
> per-case adapter and deterministic offline normalization. PostgreSQL
> persistence implementation and runtime verification remain pending; the
> migration is a contract artifact only. Spark parity/isolation is verified in
> CI; deployment, live connectors, and benchmark evaluation remain unverified.

Incident Lens is a focused investigation workspace for the period after a
checkout failure. An engineer selects a service and time window, reviews logs,
metrics, and traces, retrieves relevant runbooks and prior knowledge, tests
hypotheses with permitted read-only tools, and saves or exports a report. The
system can show a supported conclusion, uncertainty, conflicting evidence, or
an unresolved diagnosis. Saving a report does not claim that the system was
fixed.

The first public experience is designed for a reviewer to understand quickly:

- **Investigate** opens a default checkout incident, with additional examples
  for degraded performance and insufficient evidence.
- One readable findings area explains the current assessment and its evidence;
  an evidence drawer keeps detail available without turning the task into a
  dashboard of charts.
- An expandable execution timeline shows what was actually run. Loading,
  progress, partial evidence, provider/quota failure, and retry states are
  explicit.
- A guest can run fresh inference over recorded telemetry, ask a follow-up or
  challenge a finding, change the window, withhold a source, rerun, accept or
  correct the result, and export a report. A previously completed example is
  offered only with an explicit label when a live run cannot proceed.

Runs keep telemetry origin, execution type, source interval, run version, and
run time as separate provenance fields so a new analysis and a stored replay
cannot be confused.

The product is planned as one React and TypeScript frontend plus one Python
package organized into API, worker, offline pipeline, and ML modules. PostgreSQL
will hold state and pgvector will support knowledge retrieval. Raw telemetry
and Parquet artifacts will use object storage. PySpark belongs to offline
normalization, deduplication, quality checks, window features, and versioned
manifests; it is not an interactive request dependency. A scikit-learn anomaly
ranking model will be compared with error and latency rules, with honest error
analysis. A LangGraph workflow will provide persistent, typed, bounded
orchestration with checkpoint and restart behavior. The final provider choice is
an evidence-led decision based on actual availability, not a claim made by this
foundation.

A verified public deployment is an intended delivery requirement. The read-only
connector to an owned maintained application is also a real integration target;
a stub will not satisfy that requirement. If credentials or external access are
unavailable, the exact blocker will be reported and independent work will
continue. Neither is represented as available in this foundation.

The source and evaluation plan starts with [RCAEval](https://github.com/phamquiluan/RCAEval)
and its [Hugging Face dataset](https://huggingface.co/datasets/phamquiluan/RCAEval):
735 benchmark cases in total, with 10–20 development cases initially selected
from the 90-case RE2-OB subset. Cases are fetched individually by the Phase 2
adapter, assigned neutral IDs, and kept out of the repository as raw data. One
reviewed RE2-OB quality report is checked in at
[`docs/evaluation/rcaeval-re2ob-001-quality.json`](docs/evaluation/rcaeval-re2ob-001-quality.json);
it contains real counts and hashes but no source locator, injection metadata,
or hidden label. Hidden cause labels, filenames, and indexes must not leak into
prompts or retrieval. The [OpenTelemetry
Demo](https://opentelemetry.io/docs/demo/) and its [feature flag
scenario](https://opentelemetry.io/docs/demo/feature-flags/) are planned as a
separate controlled-failure adapter, not as a schema assumption about RCAEval.
License and attribution terms will be verified when source material is reused.

Read the working contract in [`docs/PRODUCT_SPEC.md`](docs/PRODUCT_SPEC.md) and
the delivery sequence in [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md).

Phase 0 artifacts are in [`contracts/v1`](contracts/v1),
[`data/manifests`](data/manifests), [`docs/design`](docs/design), and
[`docs/evaluation`](docs/evaluation). Local configuration and secret handling
are documented in [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md). The exact
foundation checks and their results are recorded in the Phase 0 evidence record
in the implementation plan.

The local Phase 1 commands, authored-fixture boundary, API flow, and pending
PostgreSQL implementation and runtime/migration checks are documented in
[`docs/LOCAL_DEVELOPMENT.md`](docs/LOCAL_DEVELOPMENT.md).

There is no working demo URL, public screenshot set, measured result,
deployment, or live connector to report yet. The local API quickstart is for
the authored fixture only. Public deployment and the owned connector are
completion requirements in the plan, not promises represented as existing
features.
