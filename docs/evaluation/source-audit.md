# Phase 0 source and license audit

Audit date: **2026-09-13**. This record is a source sanity check and selection
manifest, not a claim that benchmark telemetry has been downloaded or run.

| Source | Pinned revision | License / attribution | Use boundary |
| --- | --- | --- | --- |
| [RCAEval repository](https://github.com/phamquiluan/RCAEval) | `bb48c5aa9a24f1d5fcc716bdd479ea2d63145c90` (`main` at audit) | MIT; Pham, Luan et al., *RCAEval: A Benchmark for Root Cause Analysis of Microservice Systems with Telemetry Data* (2025) | Audit-only in Phase 0; selected RE2-OB IDs are neutral and raw files stay outside Git |
| [RCAEval Hugging Face dataset](https://huggingface.co/datasets/phamquiluan/RCAEval) | `afeacb11bcc94dadfd1c8f483ee4377b2b8b614e` (`main` at audit) | MIT per dataset card; same authorship and citation | Individual case fetch is a Phase 2 adapter concern; index fields that reveal hidden labels are never copied into prompts or manifests |
| [OpenTelemetry Demo](https://github.com/open-telemetry/opentelemetry-demo) and [feature-flag docs](https://opentelemetry.io/docs/demo/feature-flags/) | `9bfe486ff48ee8a6ea942be74171342cb71a9327` (`main` at audit) | Apache-2.0; OpenTelemetry Authors | Separate controlled-runtime adapter boundary; no RCAEval schema reuse and no runtime result in this repository |

The current manifests record source URLs, revisions, license fields,
attribution, audit timestamps, split, and raw-data status. Redistribution and
derived-index terms are deliberately marked as not exercised where no source
artifact has been copied. Any future runbook or prior-incident document gets a
separate ledger row and license review; held-out answers do not enter the
knowledge index.

Inspect the machine-readable records in [`data/manifests/`](../../data/manifests/):
`development.json`, `controlled-runtime.json`, and `knowledge-sources.json`.
