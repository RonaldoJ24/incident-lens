# Phase 4 workflow evidence

Status: in progress. This record covers the local deterministic evidence
workflow only; it does not claim a hosted retrieval provider, production
telemetry, or benchmark performance.

The verified knowledge index is `data/knowledge/verified-runbooks-v1.json`.
Every hit carries a source ID, source version, title, citation, and source
kind. The index now contains 14 concise reviewed summaries: 13 official
OpenTelemetry documentation/specification entries and one explicitly
project-authored Incident Lens guidance entry. The local semantic path is
`tfidf-lsa-v1`, a frozen TF-IDF/truncated-SVD projection over this small
index. If scikit-learn is not available, retrieval reports semantic support as
unavailable rather than calling a provider.

`data/manifests/retrieval.json` records 15 public-demo queries with decoy
candidates. The local check reports Recall@1 1.0, Recall@3 1.0, and MRR 1.0
for this deliberately small corpus; these are retrieval-only measurements,
not incident-diagnosis quality or production performance.

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
When `INCIDENT_LENS_PROVIDER_API_KEY` is set, the workflow can call the
bounded provider-neutral OpenAI-compatible runtime using the configured
model/base URL. Its structured answer can cite only retrieved source IDs and
must include explicit uncertainty. Timeouts, malformed answers, provider
errors, and unknown citations fail safely. With no key, the workflow uses
`deterministic_non_provider_fallback`, which is clearly labelled and is not
represented as fresh AI inference.

Known limitations: the checked-in provider path has only mocked tests here;
root-level live provider verification, provider cost/latency measurement,
PostgreSQL runtime, and browser/e2e review remain pending. Retrieval metrics
cover the reviewed public-demo corpus only, and no hosted model or external
retrieval provider was called for this evidence.
