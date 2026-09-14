# Phase 6 browser visual review

**Review date:** 2026-09-14. **Evidence status:** manual interactive review
completed against both the browser-local authored preview and the published
live Render/Neon/DeepSeek path. Screenshots were captured and visually
inspected during the review but are **not checked into the repository**. This
is not evidence of production telemetry, connector access, or repair.

## Build and preview boundary

Normal and demo frontend lint, typecheck, test, and build checks passed. The
browser-local demo rendered after serving the preview with its correct base
path. The visible UI stated that the fixture was browser-local/authored and
that backend, provider, connector, and repair actions were not running.

## Responsive and layout evidence

DOM/layout checks at each CSS viewport found `document.scrollWidth` equal to the
viewport width, with no horizontal overflow:

| Viewport | Observed layout |
| ---: | --- |
| 1440 px | Normal wide workspace; screenshot captured and visually inspected |
| 1280 px | Two workspace columns; controls in five columns |
| 768 px | One workspace column; controls in two columns |
| 390 px | One workspace column; controls in one column; screenshot captured and visually inspected |

The demo banner was visible at every checked width.

## Interaction flows verified

- Successful checkout investigation run completed.
- Insufficient-evidence run displayed explicit missing metric and trace
  signals.
- Keyboard focus was visible: the focused **Download sample** control showed a
  3px solid `rgb(11,99,206)` focus ring.
- Source withholding removed the runbook evidence from the displayed context.
- Save and export reached the saved state.
- Valid JSONL upload accepted 3 records with zero missing, duplicate, or
  conflicting records.
- Malformed JSONL upload was rejected and displayed missing metric/trace
  signals.
- Local run and source-withholding state survived browser reload.

These flows exercised the browser-local authored preview. They do not claim a
live connector integration or a repair action.

## Published live-path review

Pages run
[`34869828671`](https://github.com/RonaldoJ24/incident-lens/actions/runs/34869828671)
published the exact Render origin. At 1280×800, the live page displayed backend
readiness, completed a fresh provider workflow, and rendered the provider/model
label, explicit uncertainty, `uncertain` support status, three cited source
IDs, three linked knowledge evidence IDs, authored signal evidence, and four
next checks. The stale “local API” wording was removed before this final run.

At 390×844 the context controls stacked into one column, the run button remained
full-width and usable, and the live finding preserved its hierarchy. DOM checks
at both widths found `document.documentElement.scrollWidth == window.innerWidth`
with no horizontal overflow. The default URL remained visibly labelled
“Public demo · authored fixture · browser-local” and did not show a provider
claim.

This verifies public UI wiring and layout only. It does not turn the authored
fixture into live application telemetry or establish representative claim
quality, hosted latency, cost, repair, or user impact.
