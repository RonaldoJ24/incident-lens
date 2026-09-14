"""Typed Phase 4 workflow with compiled LangGraph execution and control path."""

from __future__ import annotations

import hashlib
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from typing import Any, Callable, Dict, List, Literal, Optional, TypedDict

from incident_lens.api.store import iso, parse_json, utc_now
from incident_lens.evaluation.support import evaluate_claim_support
from incident_lens.retrieval import HybridRetriever, KnowledgeIndex
from incident_lens.workflow.tools import ReadOnlyToolRegistry

try:  # Optional dependency: tests and local fallback do not need a provider.
    from langgraph.graph import END, START, StateGraph
    LANGGRAPH_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised on the minimal local install
    END = START = StateGraph = None
    LANGGRAPH_AVAILABLE = False


class InvestigationState(TypedDict, total=False):
    run_id: str
    session_id: str
    case_id: str
    query: str
    status: Literal["queued", "running", "paused", "completed", "cancelled", "failed"]
    node: str
    attempt: int
    tool_calls: int
    retrieval_hits: List[Dict[str, Any]]
    claims: List[Dict[str, Any]]
    evidence_ids: List[str]
    withheld_source_ids: List[str]
    error: Optional[str]
    report_id: Optional[str]
    budget_deadline_at: float


class WorkflowConfig:
    def __init__(self, *, max_tool_calls: int = 3, max_seconds: float = 5.0, max_retries: int = 1) -> None:
        self.max_tool_calls = max_tool_calls
        self.max_seconds = max_seconds
        self.max_retries = max_retries


class WorkflowBudgetExceeded(RuntimeError):
    """Raised before a node when the persisted workflow budget is exhausted."""


class InvestigationWorkflow:
    REVISION = "phase4-workflow-v1"

    def __init__(self, store: Any, retriever: HybridRetriever, *, config: Optional[WorkflowConfig] = None, tools: Optional[ReadOnlyToolRegistry] = None, clock: Optional[Callable[[], float]] = None) -> None:
        self.store = store
        self.retriever = retriever
        self.config = config or WorkflowConfig()
        self.tools = tools or ReadOnlyToolRegistry()
        self.clock = clock or time.time

    def build_langgraph(self) -> Any:
        """Compile the typed nodes used by fresh runs and checkpoint resumes."""
        if not LANGGRAPH_AVAILABLE:
            return None
        graph = StateGraph(InvestigationState)
        graph.add_node("inspect", self._inspect_node)
        graph.add_node("retrieve", self._retrieve_node)
        graph.add_node("support", self._support_node)
        graph.add_conditional_edges(
            START,
            self._entry_node,
            {"inspect": "inspect", "retrieve": "retrieve", "support": "support", "done": END},
        )
        graph.add_edge("inspect", "retrieve")
        graph.add_edge("retrieve", "support")
        graph.add_edge("support", END)
        return graph.compile()

    @staticmethod
    def _entry_node(state: InvestigationState) -> str:
        """Resume compiled execution at the next durable node when available."""
        node = state.get("node", "inspect")
        return node if node in {"inspect", "retrieve", "support"} else "done"

    def run(self, run_id: str, session_id: str, query: str, *, resume: bool = True, cancel_event: Optional[Event] = None, stop_after: Optional[str] = None) -> InvestigationState:
        run = self.store.get_run(run_id)
        if not run or run["session_id"] != session_id:
            raise ValueError("workflow run is not owned by session")
        checkpoint = self.store.get_checkpoint(run_id) if resume else None
        if checkpoint:
            state = dict(checkpoint["state"])
            if checkpoint["status"] == "completed":
                return state  # duplicate delivery is idempotent
        else:
            state = InvestigationState(run_id=run_id, session_id=session_id, case_id=run["case_id"], query=query, status="queued", node="inspect", attempt=1, tool_calls=0, retrieval_hits=[], claims=[], evidence_ids=[], withheld_source_ids=self.store.list_withheld_source_ids(run_id), error=None, report_id=None, budget_deadline_at=self.clock() + self.config.max_seconds)
        try:
            # Check persisted deadlines before dispatching a fresh or resumed
            # graph. A synchronous tool already in flight cannot be forcibly
            # killed here; no further node is started after the deadline.
            self._ensure_budget(state, state.get("node", "inspect"))
            if LANGGRAPH_AVAILABLE and cancel_event is None and stop_after is None:
                # Fresh runs and restarts use the same compiled graph. Its
                # conditional entry resumes from the next durable node.
                state = self.build_langgraph().invoke(state)
            else:
                nodes = (("inspect", self._inspect_node), ("retrieve", self._retrieve_node), ("support", self._support_node))
                node_names = [name for name, _ in nodes]
                start_index = node_names.index(state.get("node", "inspect")) if state.get("node", "inspect") in node_names else 0
                for index, (node_name, node) in enumerate(nodes[start_index:], start_index):
                    self._ensure_budget(state, node_name)
                    if cancel_event and cancel_event.is_set():
                        state["status"] = "cancelled"
                        self._timeline(state, "workflow_cancelled", {"node": state.get("node", "inspect")}, {"reason": "cancelled"}, utc_now(), "cancelled")
                        self._checkpoint(state, "cancelled")
                        return state
                    state["status"] = "running"
                    state["node"] = node_name
                    state = node(state)
                    state["node"] = node_names[index + 1] if index + 1 < len(node_names) else "done"
                    self._checkpoint(state, "paused" if stop_after == node_name else "running")
                    if stop_after == node_name:
                        state["status"] = "paused"
                        self._checkpoint(state, "paused")
                        return state
            state["status"] = "completed"
            state["node"] = "done"
            run = self.store.get_run(run_id)
            if run:
                report = self.store.save_report(session_id, run_id, parse_json(run["provenance_json"]), [item["finding_id"] for item in self.store.list_findings(run_id)], "phase4-%s" % run_id)
                state["report_id"] = report["report_id"]
            self._checkpoint(state, "completed")
            return state
        except WorkflowBudgetExceeded as exc:
            state = self._latest_running_state(run_id, state)
            state["status"] = "failed"
            state["error"] = str(exc)
            self._timeline(state, "workflow_failed", {"node": state.get("node", "unknown")}, {"error": str(exc)}, utc_now(), "failed", error_code="time_budget_exceeded")
            self._checkpoint(state, "failed")
            return state
        except Exception as exc:
            state = self._latest_running_state(run_id, state)
            state["status"] = "failed"
            state["error"] = str(exc)
            self._timeline(state, "workflow_failed", {"node": state.get("node", "unknown")}, {"error": str(exc)}, utc_now(), "failed", error_code="workflow_error")
            self._checkpoint(state, "failed")
            return state

    def _inspect_node(self, state: InvestigationState) -> InvestigationState:
        self._ensure_budget(state, "inspect")
        if state.get("tool_calls", 0) >= self.config.max_tool_calls:
            raise RuntimeError("workflow tool-call bound exceeded")
        params = {"case_id": state["case_id"], "max_events": self.tools.max_events}
        retry_index = 0
        while True:
            started = utc_now()
            started_clock = time.perf_counter()
            try:
                output = self.tools.call("inspect_fixture", params)
                state["tool_calls"] = state.get("tool_calls", 0) + 1
                self._timeline(state, "inspect_fixture", params, output, started, "succeeded", retry_index=retry_index, started_clock=started_clock)
                state["status"] = "running"
                state["node"] = "retrieve"
                self._checkpoint(state, "running")
                return state
            except Exception as exc:
                self._timeline(state, "inspect_fixture", params, {"error": str(exc)}, started, "failed", error_code="tool_error", retry_index=retry_index, started_clock=started_clock)
                if retry_index >= self.config.max_retries:
                    raise
                retry_index += 1
                state["attempt"] = state.get("attempt", 1) + 1

    def _retrieve_node(self, state: InvestigationState) -> InvestigationState:
        self._ensure_budget(state, "retrieve")
        started = utc_now()
        started_clock = time.perf_counter()
        hits = self.retriever.search(state["query"], limit=3, withheld_source_ids=state.get("withheld_source_ids", []))
        state["retrieval_hits"] = [hit.as_dict() for hit in hits]
        run = self.store.get_run(state["run_id"])
        interval = parse_json(run["provenance_json"])["source_interval"] if run else {}
        for hit in hits:
            evidence_id = "knowledge-" + hashlib.sha256((state["run_id"] + hit.document.source_id + hit.document.source_version).encode("utf-8")).hexdigest()[:12]
            state.setdefault("evidence_ids", []).append(evidence_id)
            if evidence_id not in {item["evidence_id"] for item in self.store.list_evidence(state["run_id"])}:
                self.store.insert_evidence(state["run_id"], {"evidence_id": evidence_id, "source_type": "runbook", "source": {"source_id": hit.document.source_id, "version": hit.document.source_version}, "event_time": interval.get("start", iso(utc_now())), "query_window": interval, "content_or_summary": hit.document.text, "quality_flags": [], "access_scope": "guest_session"})
        self._timeline(state, "retrieve_knowledge", {"query": state["query"], "limit": 3, "withheld_source_ids": state.get("withheld_source_ids", [])}, {"hit_count": len(hits), "citations": [hit.document.citation for hit in hits]}, started, started_clock=started_clock)
        state["status"] = "running"
        state["node"] = "support"
        self._checkpoint(state, "running")
        return state

    def _support_node(self, state: InvestigationState) -> InvestigationState:
        self._ensure_budget(state, "support")
        started = utc_now()
        started_clock = time.perf_counter()
        claim = "The selected case has evidence that warrants bounded follow-up, not a causal conclusion."
        evidence = [{"text": hit["text"], "citation": hit["citation"]} for hit in state.get("retrieval_hits", [])]
        state["claims"] = [{"claim_id": "claim-" + hashlib.sha256(claim.encode("utf-8")).hexdigest()[:12], "text": claim, "evidence_ids": state.get("evidence_ids", []), "support": evaluate_claim_support(claim, evidence)}]
        self._timeline(state, "evaluate_claim_support", {"claim_id": state["claims"][0]["claim_id"]}, {"status": state["claims"][0]["support"]["status"], "citations": state["claims"][0]["support"]["citations"]}, started, started_clock=started_clock)
        state["status"] = "running"
        state["node"] = "done"
        self._checkpoint(state, "running")
        return state

    def _timeline(self, state: InvestigationState, operation: str, params: Dict[str, Any], output: Dict[str, Any], started: datetime, status: str = "succeeded", *, error_code: Optional[str] = None, retry_index: int = 0, started_clock: Optional[float] = None) -> None:
        duration_ms = max(1, int(round((time.perf_counter() - started_clock) * 1000))) if started_clock is not None else 1
        self.store.insert_timeline(state["run_id"], {"event_id": "timeline-" + uuid.uuid4().hex[:12], "run_id": state["run_id"], "step": operation, "state": status, "started_at": iso(started), "ended_at": iso(utc_now()), "scope": {"operation": operation, "read_only": True, "parameters": params, "output": output, "retry_index": retry_index}, "evidence_ids": state.get("evidence_ids", []), "duration_ms": duration_ms, "error_code": error_code})

    def _checkpoint(self, state: InvestigationState, status: str) -> None:
        self.store.save_checkpoint(state["run_id"], self.REVISION, dict(state), status)

    def _latest_running_state(self, run_id: str, state: InvestigationState) -> InvestigationState:
        """Keep the last node checkpoint when LangGraph raises before returning state."""
        checkpoint = self.store.get_checkpoint(run_id)
        if checkpoint and checkpoint["status"] == "running":
            return dict(checkpoint["state"])
        return state

    def _ensure_budget(self, state: InvestigationState, node: str) -> None:
        deadline = state.get("budget_deadline_at")
        if deadline is None:
            deadline = self.clock() + self.config.max_seconds
            state["budget_deadline_at"] = deadline
        state["node"] = node
        if self.clock() >= float(deadline):
            raise WorkflowBudgetExceeded("time budget exhausted before node %s" % node)
