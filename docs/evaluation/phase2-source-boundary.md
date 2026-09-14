# Phase 2 source and artifact boundary

The RCAEval adapter fetches one case at a time from the pinned Hugging Face
revision recorded in [`development.json`](../../data/manifests/development.json).
The neutral `dev-re2ob-NNN` ID is the only case identifier that reaches a
derived manifest, prompt, report, or UI. The mapping to the upstream directory
(which encodes the benchmark answer) is a protected locator loaded from
`INCIDENT_LENS_SOURCE_LOCATOR_FILE`. The default location is
`data/raw/rcaeval/source-locators.json`, which is ignored by Git; deployments
may point it at a secret-mounted file outside the repository.

Raw objects are private and use this deterministic key layout:

```text
raw/rcaeval/<pinned-source-revision>/<neutral-case-id>/<signal>.parquet
derived/<kind>/<version>/<neutral-case-id>/<sha256>.<extension>
```

`kind` is `normalized`, `quality`, or `manifest`. PostgreSQL stores only an
`artifact_references` row (bucket, key, byte size, SHA-256, source version,
manifest hash, scope, and timestamps); it never stores telemetry bytes. The
migration is [`002_artifact_references.sql`](../../backend/migrations/002_artifact_references.sql).

Normalization is deterministic and rejects hidden-label/filename text,
timezone-naive or malformed timestamps, duplicate events in strict mode, and
cases outside the requested split. Epoch seconds, milliseconds, microseconds,
and nanoseconds are distinguished; canonical timestamps retain nanoseconds so
sub-second events cannot be falsely deduplicated. The optional Spark job uses
the same canonical event function and emits the same quality summary, including
for an existing zero-row signal file. `generated_at` records the actual run
time and is excluded from the deterministic content hash; identical telemetry
still produces the same content identity and quality report. The API does not
import Spark or require Java.

The reviewed one-case quality record is
[`rcaeval-re2ob-001-quality.json`](rcaeval-re2ob-001-quality.json). It reports
real counts and hashes from the pinned RE2-OB case while excluding injection
metadata, hidden labels, upstream paths, and raw data.

To regenerate it, provide a protected locator file (the upstream directory
name belongs only in that file) and run:

```sh
INCIDENT_LENS_SOURCE_LOCATOR_FILE=/secure/incident-lens/rcaeval-locators.json \
  uv run --project backend --extra data python -m incident_lens.pipeline.generate_quality \
  --manifest data/manifests/development.json \
  --case-id dev-re2ob-001 \
  --output docs/evaluation/rcaeval-re2ob-001-quality.json
```

The generator fetches the pinned telemetry, reads only the three signal
Parquet files, writes the deterministic report, and removes exactly
`data/raw/rcaeval/dev-re2ob-001` in a `finally` block. Use `--keep-raw` only for
an explicitly private inspection; raw data and the locator file remain ignored.

Local checks that do not require Java, Docker, or PostgreSQL:

```sh
PYTHONPATH=backend python3 -m unittest discover -s backend/tests -v
PYTHONPATH=backend python3 -m incident_lens.pipeline.check_leakage data/manifests
git diff --check
```

The PySpark runtime path is CI-only on hosts without Java: install the backend
`data` and `spark` extras in a runner, then invoke
`incident_lens.pipeline.spark_normalize.run_spark_normalization` with a private
neutral-ID raw directory. `.github/workflows/phase2-offline.yml` compares its
summary and content hash with portable normalization on sub-second and empty
authored signals and asserts leakage rejection. GitHub Actions run
`34813930327` passed these checks at commit `72c3434`.

The exact Spark signal hash uses one `collect_list` aggregation over a single
case. That is verified for this bounded per-case workload, not evidence of an
unbounded or distributed-scale hashing design. PostgreSQL artifact migration
execution and Phase 1 PostgreSQL persistence verification are tracked
separately.
