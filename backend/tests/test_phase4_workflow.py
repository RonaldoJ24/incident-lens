import json
import sys
import tempfile
import unittest
from threading import Event
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from incident_lens.api.store import StateStore, iso, utc_now
from incident_lens.evaluation.retrieval import evaluate_retrieval
from incident_lens.evaluation.support import evaluate_claim_support
from incident_lens.retrieval import HybridRetriever, KnowledgeIndex
from incident_lens.workflow.graph import InvestigationWorkflow, WorkflowConfig
from incident_lens.workflow.tools import ReadOnlyToolRegistry, ToolError, hostile_fixture_event


ROOT = Path(__file__).parents[2]


class Phase4RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.index = KnowledgeIndex.from_manifest(ROOT / "data/knowledge/verified-runbooks-v1.json")
        self.retriever = HybridRetriever(self.index)

    def test_hybrid_retrieval_has_citations_and_local_semantic_metadata(self):
        self.assertTrue(self.retriever.semantic_available)
        hits = self.retriever.search("feature flag telemetry evaluation", limit=2)
        self.assertEqual(hits[0].document.source_id, "otel-feature-flags-docs")
        self.assertEqual(hits[0].document.source_version, "docs@2026-09-13")
        self.assertTrue(hits[0].document.citation)
        self.assertEqual(hits[0].as_dict()["embedding_version"], "tfidf-lsa-v1")
        self.assertEqual(self.retriever.search("feature flag", withheld_source_ids={"otel-feature-flags-docs"})[0].document.source_id, "otel-demo-docs")

    def test_retrieval_and_claim_support_evaluations_are_separate_and_honest(self):
        manifest = json.loads((ROOT / "data/manifests/retrieval.json").read_text())
        report = evaluate_retrieval(self.retriever, manifest["queries"])
        self.assertEqual(report["status"], "evaluated")
        self.assertEqual(report["queries"], 3)
        supported = evaluate_claim_support("feature flag scenario demonstrates evaluating a flag", [self.retriever.search("feature flag", limit=1)[0].as_dict()])
        unsupported = evaluate_claim_support("this release caused the incident", [])
        self.assertEqual(supported["status"], "supported")
        self.assertEqual(unsupported["status"], "unsupported")


class Phase4WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.database = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        self.database.close()
        self.store = StateStore(self.database.name)
        from incident_lens.fixtures.loader import load_cases

        self.store.seed_cases(load_cases())
        self.session_id = self.store.create_session()["session_id"]
        provenance = {"source_interval": {"start": "2026-09-13T08:00:00Z", "end": "2026-09-13T08:10:00Z"}}
        self.run = self.store.create_run(self.session_id, "checkout-failure", provenance, "phase4-workflow")
        index = KnowledgeIndex.from_manifest(ROOT / "data/knowledge/verified-runbooks-v1.json")
        self.workflow = InvestigationWorkflow(self.store, HybridRetriever(index))

    def tearDown(self):
        self.store.close()
        Path(self.database.name).unlink(missing_ok=True)

    def test_checkpoint_restart_and_duplicate_delivery_are_idempotent(self):
        paused = self.workflow.run(self.run["run_id"], self.session_id, "feature flag telemetry", resume=False, stop_after="inspect")
        self.assertEqual(paused["status"], "paused")
        completed = self.workflow.run(self.run["run_id"], self.session_id, "feature flag telemetry", resume=True)
        duplicate = self.workflow.run(self.run["run_id"], self.session_id, "different query", resume=True)
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(duplicate["report_id"], completed["report_id"])
        self.assertEqual(self.store.get_checkpoint(self.run["run_id"])["status"], "completed")
        self.assertEqual(len(self.store.list_evidence(self.run["run_id"])), 3)
        operations = [event["scope"]["operation"] for event in self.store.list_timeline(self.run["run_id"])]
        self.assertEqual(operations, ["inspect_fixture", "retrieve_knowledge", "evaluate_claim_support"])
        self.assertTrue(all(event["scope"]["read_only"] for event in self.store.list_timeline(self.run["run_id"])))
        self.assertNotIn("shell", json.dumps(self.store.list_timeline(self.run["run_id"])))

    def test_compiled_langgraph_invocation_and_completed_checkpoint_session_isolation(self):
        graph = self.workflow.build_langgraph()
        self.assertIsNotNone(graph)
        completed = self.workflow.run(self.run["run_id"], self.session_id, "feature flag telemetry", resume=False)
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(self.store.get_checkpoint(self.run["run_id"])["status"], "completed")

        other_session = self.store.create_session()["session_id"]
        with self.assertRaisesRegex(ValueError, "not owned"):
            self.workflow.run(self.run["run_id"], other_session, "feature flag telemetry", resume=True)

    def test_compiled_graph_checkpoint_resumes_after_controlled_interruption(self):
        class InterruptingWorkflow(InvestigationWorkflow):
            def _retrieve_node(self, state):
                raise RuntimeError("controlled graph interruption")

        interrupted = InterruptingWorkflow(self.store, self.workflow.retriever)
        initial = {
            "run_id": self.run["run_id"],
            "session_id": self.session_id,
            "case_id": "checkout-failure",
            "query": "feature flag telemetry",
            "status": "queued",
            "node": "inspect",
            "attempt": 1,
            "tool_calls": 0,
            "retrieval_hits": [],
            "claims": [],
            "evidence_ids": [],
            "withheld_source_ids": [],
            "error": None,
            "report_id": None,
        }
        with self.assertRaisesRegex(RuntimeError, "controlled graph interruption"):
            interrupted.build_langgraph().invoke(initial)
        checkpoint = self.store.get_checkpoint(self.run["run_id"])
        self.assertEqual(checkpoint["status"], "running")
        self.assertEqual(checkpoint["state"]["node"], "retrieve")

        completed = self.workflow.run(self.run["run_id"], self.session_id, "feature flag telemetry", resume=True)
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(self.store.get_checkpoint(self.run["run_id"])["status"], "completed")

        support_run = self.store.create_run(
            self.session_id,
            "checkout-failure",
            {"source_interval": {"start": "2026-09-13T08:00:00Z", "end": "2026-09-13T08:10:00Z"}},
            "phase4-support-checkpoint",
        )

        class SupportInterruptingWorkflow(InvestigationWorkflow):
            def _support_node(self, state):
                raise RuntimeError("controlled support interruption")

        support_interrupted = SupportInterruptingWorkflow(self.store, self.workflow.retriever)
        support_initial = dict(initial, run_id=support_run["run_id"])
        with self.assertRaisesRegex(RuntimeError, "controlled support interruption"):
            support_interrupted.build_langgraph().invoke(support_initial)
        support_checkpoint = self.store.get_checkpoint(support_run["run_id"])
        self.assertEqual(support_checkpoint["status"], "running")
        self.assertEqual(support_checkpoint["state"]["node"], "support")

    def test_compiled_graph_refuses_next_node_after_persisted_time_budget(self):
        class FakeClock:
            def __init__(self):
                self.value = 100.0

            def __call__(self):
                return self.value

            def advance(self, seconds):
                self.value += seconds

        clock = FakeClock()

        class SlowInspectWorkflow(InvestigationWorkflow):
            def _inspect_node(self, state):
                state = super()._inspect_node(state)
                clock.advance(3.0)
                return state

        bounded = SlowInspectWorkflow(self.store, self.workflow.retriever, config=WorkflowConfig(max_seconds=2), clock=clock)
        result = bounded.run(self.run["run_id"], self.session_id, "feature flag telemetry", resume=False)
        self.assertEqual(result["status"], "failed")
        self.assertIn("time budget exhausted", result["error"])
        checkpoint = self.store.get_checkpoint(self.run["run_id"])
        self.assertEqual(checkpoint["status"], "failed")
        self.assertEqual(checkpoint["state"]["node"], "retrieve")
        timeline = self.store.list_timeline(self.run["run_id"])
        self.assertEqual(timeline[-1]["error_code"], "time_budget_exceeded")
        self.assertNotIn("retrieve_knowledge", [event["scope"]["operation"] for event in timeline])

    def test_source_withholding_changes_retrieval_context(self):
        self.store.insert_correction(self.run["run_id"], {"correction_id": "correction-withhold", "run_id": self.run["run_id"], "action": "withhold_source", "source_ids": ["otel-feature-flags-docs"], "note": "Do not use this source.", "created_at": iso(utc_now()), "context_preserved": True})
        result = self.workflow.run(self.run["run_id"], self.session_id, "feature flag telemetry", resume=False)
        self.assertNotIn("otel-feature-flags-docs", {hit["source_id"] for hit in result["retrieval_hits"]})

    def test_untrusted_log_is_data_and_unknown_tools_are_rejected(self):
        event = hostile_fixture_event()
        self.assertTrue("IGNORE" in event["message"])
        self.assertTrue(ReadOnlyToolRegistry().call("inspect_fixture", {"case_id": "checkout-failure"})["untrusted_content"])
        with self.assertRaisesRegex(ToolError, "allowlisted"):
            ReadOnlyToolRegistry().call("shell", {"command": "cat secrets"})

    def test_cancellation_and_bounded_retry_are_recorded(self):
        cancelled = Event()
        cancelled.set()
        result = self.workflow.run(self.run["run_id"], self.session_id, "feature flag telemetry", resume=False, cancel_event=cancelled)
        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(self.store.list_timeline(self.run["run_id"])[0]["state"], "cancelled")

        class FlakyTools(ReadOnlyToolRegistry):
            def __init__(self):
                super().__init__()
                self.calls = 0

            def call(self, name, params):
                self.calls += 1
                if self.calls == 1:
                    raise ToolError("temporary tool failure")
                return super().call(name, params)

        retry_store = self.store
        retry_run = retry_store.create_run(self.session_id, "checkout-failure", {"source_interval": {"start": "2026-09-13T08:00:00Z", "end": "2026-09-13T08:10:00Z"}}, "phase4-retry")
        retry_workflow = InvestigationWorkflow(retry_store, self.workflow.retriever, config=WorkflowConfig(max_retries=1), tools=FlakyTools())
        retry_workflow.run(retry_run["run_id"], self.session_id, "feature flag telemetry", resume=False)
        states = [item["state"] for item in retry_store.list_timeline(retry_run["run_id"])]
        self.assertEqual(states[:2], ["failed", "succeeded"])


if __name__ == "__main__":
    unittest.main()
