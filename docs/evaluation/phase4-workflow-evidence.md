# Phase 4 workflow evidence

Status: in progress. This record covers the local deterministic evidence
workflow only; it does not claim a hosted retrieval provider, production
telemetry, or benchmark performance.

The verified knowledge index is `data/knowledge/verified-runbooks-v1.json`.
Every hit carries a source ID, source version, title, citation, and source
kind. Public OpenTelemetry entries are short reviewed summaries tied to the
existing knowledge ledger; the Incident Lens guidance entry is explicitly
project-authored. The local semantic path is `tfidf-lsa-v1`, a frozen
TF-IDF/truncated-SVD projection over this small index. If scikit-learn is not
available, retrieval reports semantic support as unavailable rather than
calling a provider.

`InvestigationWorkflow` uses a typed state and a compiled LangGraph graph for
fresh runs and checkpoint resumes. The same node functions are used by the
small manual control path only when cancellation or an explicit partial-stop
test is requested. Each successful graph node writes the next node and running
state to SQLite or PostgreSQL migration 003 before the graph advances. Only
`inspect_fixture` is allowlisted; it is bounded, read-only, and returns
untrusted fixture content as data. Timeline events include tool parameters,
outputs, retry/error state, read-only scope, and measured duration.

The persisted time budget is checked before dispatching every graph node and
when resuming from a checkpoint. On exhaustion the workflow records a bounded
failure and refuses to start another node; Python cannot forcibly stop a
synchronous read-only tool that is already running.

The hostile log fixture is authored synthetic content. It is never interpreted
as instructions. Source withholding records source IDs in review history and
excludes them from the next retrieval context. Exported workflow claims carry
evidence IDs plus `supported`, `uncertain`, or `unsupported` support status.

Known limitations: retrieval uses three local summaries and three evaluation
queries; no live connector or external model was called; PostgreSQL runtime
and browser/e2e review remain pending.
