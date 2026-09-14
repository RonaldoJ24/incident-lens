# Neutral-ID and leakage review

The development manifest contains twelve IDs of the form `dev-re2ob-NNN`.
They are assigned before any per-case fetch and carry no upstream filename,
fault, service, hidden label, answer, or source case identifier. Signal
completeness is `unknown` and intervals are marked
`pending_per_case_fetch` until the Phase 2 adapter produces observed metadata.
This preserves honesty: the manifest is a selection plan, not an evaluation
result.

`incident_lens.validation.manifests` rejects suspicious keys and text in case
records (including filenames and hidden-label fields), requires the development
selection to contain 10–20 unique neutral IDs, and requires explicit split,
source version, timestamp, license, attribution, and raw-data status. Focused
tests mutate a valid case with a filename and a hidden-label field; both must
fail validation.

The controlled-runtime manifest has a separate scenario identifier and adapter
contract. It is not included in the RCAEval development split.
