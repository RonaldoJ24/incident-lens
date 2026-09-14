# Incident Lens

Incident Lens is an evidence-first workspace for bounded, read-only incident
investigation. It helps an engineer inspect an authored incident example,
review the evidence and execution timeline, record a finding or uncertainty,
and save/export a report without claiming that a system was repaired.

## Public preview

**[Open the live preview](https://ronaldoj24.github.io/incident-lens/)**

This URL is a static GitHub Pages build of the authored-fixture browser demo.
It runs the demo adapter in the browser and makes the boundary visible: the
FastAPI/PostgreSQL backend, model provider, live connector, and repair actions
are not running at that URL.

The Pages build remains this instant demo by default. An explicitly selected
`?mode=live` URL uses the build-time `VITE_INCIDENT_LENS_API_ORIGIN` absolute
HTTPS backend origin, never the demo adapter, and shows whether the backend is
starting, ready, or unavailable. Render Free may sleep, so its first wake can
take about one minute; the checked-in Pages workflow keeps a non-secret origin
placeholder until the backend URL is externally verified.

Verified delivery evidence:

| Surface | Evidence |
| --- | --- |
| Public preview | [Final UI deploy run `34821311324`](https://github.com/RonaldoJ24/incident-lens/actions/runs/34821311324) passed; [live URL](https://ronaldoj24.github.io/incident-lens/) resolves to the browser-local preview |
| Release matrix | [Final run `34821311229`](https://github.com/RonaldoJ24/incident-lens/actions/runs/34821311229) passed the backend/PostgreSQL, frontend, and container jobs |
| PostgreSQL persistence | [Phase 1 run `34819200466`](https://github.com/RonaldoJ24/incident-lens/actions/runs/34819200466) passed the PostgreSQL integration path |
| Owned connector | The bounded metadata-only verification is recorded in [`docs/evaluation/phase5-live-connector.md`](docs/evaluation/phase5-live-connector.md) |

## What you can try

The preview offers three authored examples: checkout failure, degraded
performance, and insufficient evidence. A guest can:

- run a bounded check over the selected time window;
- inspect findings, linked evidence, and the actual read-only execution timeline;
- withhold retrieved knowledge, accept/correct/challenge a finding, cancel or
  rerun a check, and change the window;
- validate a bounded JSONL upload with missing, duplicate, conflicting, and
  prompt-like content reported as data; and
- save and export a report. Reports retain provenance and never assert repair.
- inspect the accessible **Evaluation** and **Engineering** sections; optional
  upload and technical details stay collapsed until requested.

The browser demo stores its state locally so a reload can replay the current
authored preview session. It is not a hosted incident service.

## Architecture

- **Frontend:** React and TypeScript, with a responsive investigation shell,
  explicit loading/partial/error/uncertainty states, evidence drawer, review
  actions, and export.
- **API and state:** FastAPI/Pydantic with guest-scoped sessions and report
  state. PostgreSQL is selected with `INCIDENT_LENS_DATABASE_URL`; SQLite is
  the zero-service local fallback. Ordered migrations cover state, artifact
  references, and workflow checkpoints.
- **Offline data path:** a pinned per-case RCAEval adapter, neutral IDs and
  leakage checks, portable normalization, and an optional PySpark parity path.
  Spark is an offline dependency, not an interactive request dependency.
- **Investigation workflow:** a compiled, typed LangGraph workflow with
  bounded read-only tools, retrieval citations, checkpoints, restart,
  cancellation/retry, source withholding, and idempotent report revisions.
- **Guest uploads and integration:** strict bounded JSONL validation and an
  exact-host/fixed-path connector that returns metadata and a digest, never the
  connected payload. The verified owned-app call is GitHub Actions metadata,
  not application incident telemetry.

The main contracts are in [`contracts/v1`](contracts/v1). The implementation
is split between [`frontend/`](frontend), [`backend/`](backend),
[`data/manifests/`](data/manifests), and [`docs/`](docs/).

## Local setup

Requirements: Python 3.9+, `uv`, Node.js with `pnpm`, and Docker only for the
PostgreSQL path.

```sh
make setup
```

### Local API and frontend

With no database URL, the API uses SQLite and the authored fixture:

```sh
uv run --project backend uvicorn incident_lens.api.app:app --host 127.0.0.1 --port 8000
pnpm --dir frontend dev
```

The Vite development server proxies `/v1` and `/health` to the API. The local
fixture is `fixture-v1` and is labeled `controlled_runtime`; it is not RCAEval,
production telemetry, or live connector data.

To run the browser-local adapter directly:

```sh
VITE_INCIDENT_LENS_DEMO=1 pnpm --dir frontend dev
```

### PostgreSQL and migrations

```sh
cp .env.example .env  # edit POSTGRES_PASSWORD in the ignored file
docker compose up --build
```

The API applies ordered migrations on startup. To run the migration runner
explicitly, set `INCIDENT_LENS_DATABASE_URL` outside Git:

```sh
INCIDENT_LENS_DATABASE_URL="$RELEASE_DATABASE_URL" \
  uv run --project backend python -m incident_lens.migrations
```

See [`docs/LOCAL_DEVELOPMENT.md`](docs/LOCAL_DEVELOPMENT.md) and
[`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) for the complete local and
secret-boundary contract.

## API

The versioned API contract is [`contracts/v1/api.openapi.json`](contracts/v1/api.openapi.json).
The smallest local flow is:

```sh
# Create an isolated guest session.
curl -sS -X POST http://127.0.0.1:8000/v1/sessions

# List authored cases.
curl -sS http://127.0.0.1:8000/v1/cases

# Start a bounded authored-fixture run (replace SESSION_ID).
curl -sS -X POST http://127.0.0.1:8000/v1/runs \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: SESSION_ID" \
  -d '{"session_id":"SESSION_ID","case_id":"checkout-failure","service":"checkoutservice"}'
```

Use the returned `run_id` with `GET /v1/runs/{run_id}`,
`GET /v1/runs/{run_id}/evidence`, `GET /v1/runs/{run_id}/findings`, and
`GET /v1/runs/{run_id}/timeline`. The workflow endpoint is
`POST /v1/runs/{run_id}/workflow`; reports are saved with `POST /v1/reports`
and exported with `POST /v1/reports/{report_id}/export`.

Uploads use `application/jsonl` and are guest-isolated. Download the sample
from `GET /v1/uploads/sample`, initiate a slot with
`POST /v1/uploads/initiate`, then stream it to
`PUT /v1/uploads/{upload_id}`. Connector verification is deliberately narrow:
`GET /v1/connectors/verify` uses only the configured fixed path and returns
source/access metadata, bounded structural metadata, and a SHA-256 digest.

## Evaluation and evidence

Run the reproducible local checks with:

```sh
make release-check PERF_SAMPLES=20
```

The release surface covers contracts, backend tests, leakage and injection
checks, reproducibility, provisional artifact verification, controlled local
workload measurement, frontend checks, container boundaries, and the static
preview build. PostgreSQL integration is included when
`INCIDENT_LENS_DATABASE_URL` is configured. The corresponding green CI matrix
is [final run `34821311229`](https://github.com/RonaldoJ24/incident-lens/actions/runs/34821311229).

The evidence trail is split by data boundary:

- [`docs/evaluation/phase2-source-boundary.md`](docs/evaluation/phase2-source-boundary.md)
  describes pinned per-case normalization and the portable/Spark boundary.
- [`docs/evaluation/phase4-workflow-evidence.md`](docs/evaluation/phase4-workflow-evidence.md)
  records compiled workflow, retrieval, checkpoints, recovery, and hostile-log
  handling.
- [`docs/evaluation/phase5-live-connector.md`](docs/evaluation/phase5-live-connector.md)
  records the owned `RonaldoJ24/cadencia-ai` GitHub Actions metadata call.
- [`docs/evaluation/phase6-performance.md`](docs/evaluation/phase6-performance.md)
  records the authored local workload and explicitly states what was not
  measured.
- [`docs/MODEL_DATA_CARD.md`](docs/MODEL_DATA_CARD.md) records provenance,
  safety boundaries, and the provisional model artifact status.

## Deployment

[`deploy/`](deploy) contains a provider-neutral release compose contract and
the migration, readiness, metrics, secret, and rollback runbook. It expects an
immutable API image and a managed PostgreSQL URL supplied by a deployment
secret manager. No backend deployment, provider, ingress, or public API URL is
claimed. The only verified public deployment is the static authored-fixture
Pages preview described above.

## Important limitations

> The public Pages URL is a browser-local authored-fixture preview. It is not
> the FastAPI/PostgreSQL application and does not connect to a model provider,
> the owned connector, or a repair system.

- **Phase 3 is blocked:** the semantic audit found unsupported latency naming
  and globally aggregated/non-operational metrics. The resulting comparison is
  provisional; no model or threshold selection is accepted, and the final
  held-out split remains sealed.
- **Phase 4 remains deliberately unverified live:** the repository now includes
  a bounded provider-neutral OpenAI-compatible runtime seam and a labelled
  deterministic no-key fallback. The reviewed local corpus has 14 concise
  summaries and 15 public-demo retrieval queries (Recall@1/Recall@3/MRR are
  local-corpus measurements only). No live provider call or production-quality
  generative investigation result is claimed.
- **Connector scope is metadata-only:** the owned verification proves one
  bounded GitHub Actions metadata call, not application telemetry, diagnosis,
  recovery, or broader coverage.
- **Pilot is unrun:** no participants were contacted and no user-impact claim
  is made.
- **No repair claims:** tools are read-only, findings can be uncertain or
  conflicting, and saved reports keep `repair_claim: false`.
- Local workload timings are regression measurements for the authored fixture,
  not hosted or operational latency claims. Provider cost, hosted latency,
  live-connector latency, and complete-investigation quality are not measured.

## Attribution and original contribution

The source audit in [`docs/evaluation/source-audit.md`](docs/evaluation/source-audit.md)
records attribution and license boundaries. RCAEval and its Hugging Face copy
are MIT-licensed sources attributed to Pham, Luan et al.; the audited revisions
are pinned in the manifests, raw telemetry stays outside Git, and neutral IDs
prevent hidden labels from entering prompts or retrieval. The OpenTelemetry
Demo and feature-flag documentation are Apache-2.0 sources attributed to the
OpenTelemetry Authors and remain a separate controlled-runtime boundary.

The original contribution in this repository is the Incident Lens product
slice: the v1 contracts, guest-isolated FastAPI/React workflow, provenance and
evidence model, deterministic offline adapters, typed checkpointed LangGraph
orchestration, bounded JSONL and connector policies, release/runbook checks,
and the browser-local authored-fixture presentation. These additions do not
turn upstream sources into a claimed production model or live incident feed.

For phase-by-phase decisions and acceptance gates, see
[`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md).
