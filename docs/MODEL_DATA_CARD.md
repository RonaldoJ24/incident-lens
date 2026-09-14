# Model and data card

**Card status:** provisional local artifact summary; **not accepted for release
or production use**. Audit found unsupported latency feature naming and globally
aggregated/non-operational ranking metrics. The held-out split remains sealed.

## Intended use

Incident Lens ranks unusual service/window signals and presents bounded evidence
for human investigation. The ranking is not a root-cause probability and a
saved report never claims that a system was repaired. The local API may use the
authored controlled fixture; live provider and connector access remain
unverified.

## Data and provenance

- Public development and validation artifacts use neutral IDs and keep raw
  telemetry outside Git. The current Phase 3 artifact references RCAEval
  revision `bb48c5aa9a24f1d5fcc716bdd479ea2d63145c90` and dataset revision
  `afeacb11bcc94dadfd1c8f483ee4377b2b8b614e`.
- The checked-in Phase 3 artifact uses feature schema
  `incident-lens-features-v1`, artifact version
  `incident-lens-ranking-v1`, and the deterministic
  `error-rate-latency-rules-v1` baseline/selected method.
- The current comparison artifact records 505 training rows and 254 validation
  rows across independent groups. It measures event-window ranking targets;
  those targets do not identify a failing service or root cause.
- The application fixture is separate (`fixture-v1`,
  `controlled_runtime`) and must not be presented as RCAEval, production, or
  live telemetry.

## Current evidence

The checked-in validation report records provisional event-window metrics and explicitly
marks complete-investigation quality, failing-service identification,
uncertainty quality, useful-next-check quality, provider cost, and final-held-out
performance as not measured. The Phase 3 comparison is still subject to its
frozen-evidence gate and is blocked from release acceptance by the audit findings
above; no new held-out data was opened for this card. The deterministic local
retrieval/provider path is also not a production-quality claim: retrieval uses
a local fallback, no hosted provider was selected, and complete investigation
quality remains unmeasured.

## Limitations and safety

- Missing or conflicting signals are surfaced rather than imputed into a causal
  claim.
- Prompt-like content is untrusted data and is not executable.
- The model has no authorization to mutate systems; diagnostic operations are
  bounded and read-only.
- Metrics are not transferable to live incidents, new environments, or user
  populations without a separately reviewed evaluation.
- Hosted providers, provider costs, public deployment, and the owned connector
  are not selected or verified. Their performance and cost are **not measured**.
