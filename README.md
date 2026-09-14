# Incident Lens

### AI incident investigation for software teams

**Understand what failed, see the evidence, and continue the investigation.**

> **Status: foundation and planning.** The application is not implemented yet.
> This repository currently contains the product contract and phased delivery
> plan. Future README claims must be updated only after the corresponding
> behavior, evidence, and checks exist.

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
from the 90-case RE2-OB subset. Cases will be fetched individually, assigned
neutral IDs, and kept out of the repository as raw data. Hidden cause labels,
filenames, and indexes must not leak into prompts or retrieval. The [OpenTelemetry
Demo](https://opentelemetry.io/docs/demo/) and its [feature flag
scenario](https://opentelemetry.io/docs/demo/feature-flags/) are planned as a
separate controlled-failure adapter, not as a schema assumption about RCAEval.
License and attribution terms will be verified when source material is reused.

Read the working contract in [`docs/PRODUCT_SPEC.md`](docs/PRODUCT_SPEC.md) and
the delivery sequence in [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md).

There is no working demo URL, screenshot set, API quickstart, measured result,
deployment, or live connector to report yet. Public deployment and the owned
connector are completion requirements in the plan, not promises represented as
existing features.
