SHELL := /bin/sh

PYTHON := uv run --project backend python
PERF_SAMPLES ?= 20

.PHONY: setup setup-backend setup-frontend contracts unit integration-postgres \
  leakage injection reproducibility evaluate performance frontend-check \
  container-check visual-review release-check

setup: setup-backend setup-frontend

setup-backend:
	uv sync --project backend --locked

setup-frontend:
	@if command -v corepack >/dev/null 2>&1; then corepack enable && corepack prepare pnpm@9.15.0 --activate; else echo "corepack unavailable; using the existing pnpm executable"; fi
	pnpm --dir frontend install --frozen-lockfile

contracts:
	$(PYTHON) -m incident_lens.validation.contracts contracts/v1/examples/representative.json
	$(PYTHON) -m incident_lens.validation.manifests data/manifests
	$(PYTHON) -m unittest backend.tests.test_contracts backend.tests.test_manifests -v

unit:
	$(PYTHON) -m unittest discover -s backend/tests -v

integration-postgres:
	@test -n "$${INCIDENT_LENS_DATABASE_URL:-}" || (echo "INCIDENT_LENS_DATABASE_URL is required for PostgreSQL integration" >&2; exit 1)
	$(PYTHON) -m incident_lens.migrations
	$(PYTHON) -m unittest backend/tests/test_postgres_integration.py -v > /tmp/incident-lens-postgres.log 2>&1; code=$$?; cat /tmp/incident-lens-postgres.log; test $$code -eq 0
	! grep -q "skipped" /tmp/incident-lens-postgres.log

leakage:
	$(PYTHON) -m incident_lens.pipeline.check_leakage data/manifests

injection:
	$(PYTHON) -m unittest backend.tests.test_phase4_workflow backend.tests.test_phase5_uploads backend.tests.test_phase5_connector -v

reproducibility:
	$(PYTHON) -m unittest \
		backend.tests.test_phase2_pipeline.Phase2NormalizationTests.test_normalization_is_deterministic_and_timezone_normalized \
		backend.tests.test_phase2_pipeline.Phase2IsolationTests.test_quality_generation_is_deterministic_and_cleans_only_requested_case \
		backend.tests.test_api.ApiFlowTests.test_three_authored_cases_have_distinct_deterministic_outcomes -v

evaluate:
	@echo "Phase 3 validation is provisional and blocked from release acceptance: audit found unsupported latency feature naming and globally aggregated/non-operational ranking metrics."
	$(PYTHON) -m incident_lens.ml.verify_artifact docs/evaluation/phase3-artifact-manifest.json
	$(PYTHON) -m incident_lens.ml.validate --manifest data/manifests/validation.json --train-manifest data/manifests/train.json --artifact docs/evaluation/phase3-artifact-manifest.json --report /tmp/incident-lens-phase6-validation.json
	@echo "Phase 3 output is mechanical/provisional only, not release acceptance; final held-out evaluation remains sealed and no held-out manifest was read."

performance:
	$(PYTHON) -m incident_lens.validation.performance --samples $(PERF_SAMPLES)

frontend-check:
	pnpm --dir frontend run lint
	pnpm --dir frontend run typecheck
	pnpm --dir frontend test
	pnpm --dir frontend run build

container-check:
	$(PYTHON) -m unittest backend.tests.test_phase6_release.Phase6ReleaseTests -v

visual-review:
	@echo "Visual review target rebuilds the frontend only; dated manual browser evidence is in docs/evaluation/phase6-visual-review.md and screenshots are not checked in."
	pnpm --dir frontend run build

release-check:
	$(MAKE) contracts
	$(MAKE) unit
	$(MAKE) leakage
	$(MAKE) injection
	$(MAKE) reproducibility
	$(MAKE) evaluate
	$(MAKE) performance
	$(MAKE) frontend-check
	$(MAKE) container-check
	$(MAKE) visual-review
	@if [ -n "$${INCIDENT_LENS_DATABASE_URL:-}" ]; then $(MAKE) integration-postgres; else echo "PostgreSQL integration not run: INCIDENT_LENS_DATABASE_URL is unset"; fi
