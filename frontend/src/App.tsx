import { useEffect, useMemo, useRef, useState } from "react";

type PreviewState = "empty" | "loading" | "running" | "partial" | "successful" | "unresolved" | "failed" | "cached" | "upload-invalid" | "upload-accepted" | "saved" | "export-failed";
type CaseItem = {
  case_id: string;
  title: string;
  description: string;
  service: string;
  telemetry_origin: string;
  fixture_kind: string;
  source_interval: { start: string; end: string };
};
type RunItem = { run_id: string; status: string; attempt: number; provenance: { telemetry_origin: string; execution: string; run_version: string; run_time: string } };
type EvidenceItem = { evidence_id: string; source_type: string; content_or_summary: string; event_time: string; quality_flags: string[] };
type FindingItem = { finding_id: string; assessment: string; certainty: string; evidence_ids: string[]; next_checks: string[] };
type TimelineItem = { event_id: string; step: string; state: string; scope: { operation: string; read_only: boolean; parameters?: Record<string, unknown> }; evidence_ids: string[]; duration_ms: number };

const fallbackCases: CaseItem[] = [
  { case_id: "checkout-failure", title: "Checkout failure", description: "Authored checkout example with bounded local checks.", service: "checkoutservice", telemetry_origin: "controlled_runtime", fixture_kind: "authored_synthetic_controlled_fixture", source_interval: { start: "2026-09-13T08:00:00Z", end: "2026-09-13T08:10:00Z" } },
  { case_id: "degraded-performance", title: "Degraded performance", description: "Authored latency example where a release clue is not causal proof.", service: "checkoutservice", telemetry_origin: "controlled_runtime", fixture_kind: "authored_synthetic_controlled_fixture", source_interval: { start: "2026-09-13T09:00:00Z", end: "2026-09-13T09:10:00Z" } },
  { case_id: "insufficient-evidence", title: "Insufficient evidence", description: "Authored gap example with missing metrics and traces.", service: "checkoutservice", telemetry_origin: "controlled_runtime", fixture_kind: "authored_synthetic_controlled_fixture", source_interval: { start: "2026-09-13T10:00:00Z", end: "2026-09-13T10:10:00Z" } },
];

const stateCopy: Record<PreviewState, string> = {
  empty: "Select a case and run a bounded check to begin.", loading: "Loading the selected manifest.", running: "Running bounded read-only checks. You can cancel this run.", partial: "Some evidence returned; missing signals are called out below.", successful: "The authored fixture supports an unusual service/window ranking; causality remains unresolved.", unresolved: "Evidence conflicts or is insufficient. The next useful check stays visible.", failed: "The provider or tool failed safely. Retry the run or inspect the failure.", cached: "Previously completed example · replayed result, not a live run.", "upload-invalid": "Upload validation failed. Check JSONL type, size, and required signals.", "upload-accepted": "Upload accepted for this guest session; no shared state was changed.", saved: "Report revision saved. Saving does not mean the system was repaired.", "export-failed": "Export failed safely. The saved report remains available to retry.",
};

function localInput(value: string): string { return value.replace(/Z$/, "").slice(0, 16); }
function apiTimestamp(value: string): string { return `${value}:00+00:00`; }

function StatusMessage({ state }: { state: PreviewState }) {
  return <p className={`status-message status-${state}`} role="status" aria-live="polite"><span aria-hidden="true">●</span> {stateCopy[state]}</p>;
}

function App() {
  const [cases, setCases] = useState<CaseItem[]>(fallbackCases);
  const [selectedCaseId, setSelectedCaseId] = useState("checkout-failure");
  const [state, setState] = useState<PreviewState>("empty");
  const [evidenceOpen, setEvidenceOpen] = useState(true);
  const [sessionId, setSessionId] = useState<string>();
  const [run, setRun] = useState<RunItem>();
  const [finding, setFinding] = useState<FindingItem>();
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [apiStatus, setApiStatus] = useState<"loading" | "ready" | "unavailable">("loading");
  const [windowStart, setWindowStart] = useState(localInput(fallbackCases[0].source_interval.start));
  const [windowEnd, setWindowEnd] = useState(localInput(fallbackCases[0].source_interval.end));
  const windowStartRef = useRef<HTMLInputElement>(null);
  const selectedCase = useMemo(() => cases.find((item) => item.case_id === selectedCaseId) ?? fallbackCases[0], [cases, selectedCaseId]);
  const canRun = apiStatus === "ready" && Boolean(sessionId) && state !== "running";
  const canReview = apiStatus === "ready" && Boolean(sessionId && run) && state !== "running";
  const canSave = apiStatus === "ready" && Boolean(sessionId && run) && state !== "running";

  useEffect(() => {
    setWindowStart(localInput(selectedCase.source_interval.start));
    setWindowEnd(localInput(selectedCase.source_interval.end));
  }, [selectedCaseId, selectedCase.source_interval.start, selectedCase.source_interval.end]);

  useEffect(() => {
    let active = true;
    const boot = async () => {
      try {
        const [sessionResponse, casesResponse] = await Promise.all([fetch("/v1/sessions", { method: "POST" }), fetch("/v1/cases")]);
        if (!sessionResponse.ok || !casesResponse.ok) throw new Error("API unavailable");
        const session = await sessionResponse.json() as { session_id: string };
        const result = await casesResponse.json() as { cases: CaseItem[] };
        if (active) { setSessionId(session.session_id); setCases(result.cases); setApiStatus("ready"); setState("empty"); }
      } catch { if (active) { setApiStatus("unavailable"); setState("failed"); } }
    };
    void boot();
    return () => { active = false; };
  }, []);

  const headers: Record<string, string> = sessionId ? { "X-Session-ID": sessionId } : {};

  const refreshRun = async (runId: string) => {
    if (!sessionId) return;
    const [runResponse, evidenceResponse, findingResponse, timelineResponse] = await Promise.all([
      fetch(`/v1/runs/${runId}`, { headers }), fetch(`/v1/runs/${runId}/evidence`, { headers }), fetch(`/v1/runs/${runId}/findings`, { headers }), fetch(`/v1/runs/${runId}/timeline`, { headers }),
    ]);
    if (!runResponse.ok || !evidenceResponse.ok || !findingResponse.ok || !timelineResponse.ok) throw new Error("Run could not be loaded");
    const nextRun = await runResponse.json() as RunItem;
    setRun(nextRun); setEvidence((await evidenceResponse.json() as { evidence: EvidenceItem[] }).evidence); setFinding((await findingResponse.json() as { findings: FindingItem[] }).findings[0]); setTimeline((await timelineResponse.json() as { events: TimelineItem[] }).events);
    setState(nextRun.status === "partial" ? "partial" : nextRun.status === "succeeded" ? "successful" : nextRun.status === "cancelled" ? "failed" : "running");
  };

  const runCheck = async () => {
    if (!canRun || !sessionId || !windowStart || !windowEnd) return;
    setState("running");
    try {
      const response = await fetch("/v1/runs", { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": `ui-${selectedCaseId}-${Date.now()}` }, body: JSON.stringify({ session_id: sessionId, case_id: selectedCaseId, service: selectedCase.service, window_start: apiTimestamp(windowStart), window_end: apiTimestamp(windowEnd) }) });
      if (!response.ok) throw new Error("Run failed");
      await refreshRun((await response.json() as { run_id: string }).run_id);
    } catch { setState("failed"); }
  };

  const cancelRun = async () => {
    if (!sessionId || !run) return;
    try {
      const response = await fetch(`/v1/runs/${run.run_id}`, { method: "DELETE", headers });
      if (!response.ok) throw new Error("Cancel failed");
      setRun(await response.json() as RunItem); setState("failed");
    } catch { setState("failed"); }
  };

  const review = async (action: "accept" | "correct" | "challenge") => {
    if (!canReview || !sessionId || !run) return;
    try { const response = await fetch(`/v1/runs/${run.run_id}/review`, { method: "POST", headers: { ...headers, "Content-Type": "application/json" }, body: JSON.stringify({ action, note: "Review recorded in the current run context." }) }); if (!response.ok) throw new Error("Review failed"); await refreshRun(run.run_id); } catch { setState("failed"); }
  };

  const saveExport = async () => {
    if (!canSave || !sessionId || !run) return;
    try {
      const reportResponse = await fetch("/v1/reports", { method: "POST", headers: { ...headers, "Content-Type": "application/json", "Idempotency-Key": `ui-report-${run.run_id}` }, body: JSON.stringify({ session_id: sessionId, run_id: run.run_id }) });
      if (!reportResponse.ok) throw new Error("Save failed");
      const report = await reportResponse.json() as { report_id: string };
      const exportResponse = await fetch(`/v1/reports/${report.report_id}/export`, { method: "POST", headers });
      if (!exportResponse.ok) throw new Error("Export failed");
      const download = document.createElement("a");
      const downloadUrl = URL.createObjectURL(await exportResponse.blob());
      download.href = downloadUrl;
      download.download = exportResponse.headers.get("content-disposition")?.match(/filename="([^"]+)"/)?.[1] ?? `incident-lens-${report.report_id}.json`;
      download.click();
      window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 0);
      setState("saved");
    } catch { setState("export-failed"); }
  };

  const selectCase = (caseId: string) => {
    const nextCase = cases.find((item) => item.case_id === caseId);
    setSelectedCaseId(caseId); setRun(undefined); setFinding(undefined); setEvidence([]); setTimeline([]); setState("empty");
    if (nextCase) { setWindowStart(localInput(nextCase.source_interval.start)); setWindowEnd(localInput(nextCase.source_interval.end)); }
  };
  const findingHeading = finding ? (finding.certainty === "insufficient_evidence" ? "Evidence gap" : selectedCaseId === "degraded-performance" ? "Latency signal ranking" : "Error signal ranking") : "Ready to inspect";

  return <div className="app-shell">
    <header className="site-header"><a className="brand" href="#investigate" aria-label="Incident Lens home">Incident Lens</a><nav aria-label="Primary navigation"><a className="active" href="#investigate">Investigate</a><a href="#evaluation">Evaluation</a><a href="#engineering">Engineering</a></nav></header>
    <main id="investigate">
      <section className="context-bar" aria-labelledby="context-heading"><div><p className="eyebrow">Context</p><h1 id="context-heading">{selectedCase.title} <span>· authored fixture</span></h1><div className="provenance" aria-label="Independent run provenance"><span>Origin · {selectedCase.telemetry_origin}</span><span>Execution · {run?.provenance.execution ?? "new_analysis"}</span><span>{run ? `Run ${run.provenance.run_version} · ${run.provenance.run_time}` : "No run yet"}</span></div></div><div className="context-controls"><label>Example<select value={selectedCaseId} onChange={(event) => selectCase(event.target.value)} aria-label="Choose incident example">{cases.map((item) => <option key={item.case_id} value={item.case_id}>{item.title}</option>)}</select></label><label>Service<select value={selectedCase.service} disabled aria-label="Selected service"><option>{selectedCase.service}</option></select></label><div className="time-window-fields"><label htmlFor="window-start">Window start (UTC)</label><input ref={windowStartRef} id="window-start" type="datetime-local" value={windowStart} onChange={(event) => setWindowStart(event.target.value)} /></div><div className="time-window-fields"><label htmlFor="window-end">Window end (UTC)</label><input id="window-end" type="datetime-local" value={windowEnd} onChange={(event) => setWindowEnd(event.target.value)} /></div><button className="primary" type="button" disabled={state === "running" ? !run : !canRun} onClick={() => void (state === "running" ? cancelRun() : runCheck())}>{state === "running" ? "Cancel run" : "Run check"}</button></div></section>
      <div className="connection-row"><StatusMessage state={state} /><span className={`connection-note connection-${apiStatus}`} role={apiStatus === "unavailable" ? "alert" : "status"}>{apiStatus === "loading" ? "Connecting to local API…" : apiStatus === "ready" ? `Local API ready · ${run ? `run ${run.status}` : "no run has been executed"}` : "API unavailable · run, review, and export controls are disabled"}</span></div>
      <div className="workspace-grid"><section className="findings-panel" aria-labelledby="finding-heading"><div className="panel-heading"><p className="eyebrow">Finding</p><span className="certainty uncertain">{finding?.certainty ?? "Awaiting run"}</span></div><h2 id="finding-heading">{findingHeading}</h2><p className="finding-copy">{finding?.assessment ?? selectedCase.description}</p>{finding && <p className="small-copy">This finding is linked to evidence returned by the bounded local worker. It does not prove causality.</p>}<div className="checks"><p className="eyebrow">Next useful checks <span className="small-copy">· suggestions only</span></p><ul className="suggested-checks">{(finding?.next_checks ?? ["Inspect trace interval for downstream errors", "Compare the adjacent baseline window"]).map((check) => <li key={check}>{check}</li>)}</ul></div><p className="quiet-note">Finding IDs stay linked to their evidence, even when the diagnosis is unresolved.</p></section>
        <aside className={`evidence-panel ${evidenceOpen ? "open" : "closed"}`} aria-labelledby="evidence-heading"><div className="panel-heading"><p className="eyebrow">Evidence drawer</p><button className="icon-button" type="button" aria-expanded={evidenceOpen} onClick={() => setEvidenceOpen(!evidenceOpen)}>{evidenceOpen ? "Hide" : "Show"}</button></div>{evidenceOpen && <div><h2 id="evidence-heading">What supports this?</h2>{evidence.length ? evidence.map((item) => <div className="evidence-item" key={item.evidence_id}><p className="eyebrow">{item.source_type} · authored fixture</p><code>{item.evidence_id} · {item.event_time}</code><p className="small-copy">{item.content_or_summary} {item.quality_flags.length ? `(${item.quality_flags.join(", ")})` : ""}</p></div>) : <><p className="eyebrow">Awaiting a run</p><p className="small-copy">Evidence appears here only after the bounded worker returns it. No supporting passage retrieved yet.</p></>}</div>}</aside></div>
      <details className="timeline"><summary><span><span className="eyebrow">Execution timeline</span> {timeline.length ? `${timeline.length} actual event(s)` : "No run executed"}</span><span className="timeline-meta">{timeline.length ? "read-only · inspect details" : "collapsed"}</span></summary>{timeline.length ? timeline.map((event) => <div className="timeline-detail" key={event.event_id}><code>{event.scope.operation}</code><span>{event.state}</span><span>{event.duration_ms} ms</span><span>{event.scope.read_only ? "read-only" : "scope unknown"}</span><span>{event.evidence_ids.length} evidence</span><code>params: {JSON.stringify(event.scope.parameters ?? {})}</code></div>) : <div className="timeline-detail">Run a case to record actual tool calls, parameters, evidence, retries, and failures.</div>}</details>
      <section className="review-bar" aria-label="Review actions"><button type="button" disabled={!canReview} onClick={() => void review("accept")}>Accept finding</button><button type="button" disabled={!canReview} onClick={() => void review("correct")}>Correct</button><button type="button" disabled={!canReview} onClick={() => void review("challenge")}>Challenge</button><button type="button" disabled title="Unavailable until the Phase 4 source-withholding workflow is implemented">Withhold source · unavailable (Phase 4)</button><button type="button" onClick={() => windowStartRef.current?.focus()}>Change window</button><button type="button" disabled={!canRun} onClick={() => void runCheck()}>Re-run</button><button className="primary" type="button" disabled={!canSave} onClick={() => void saveExport()}>Save / export</button></section>
    </main><footer><span>Phase 1 local slice · authored fixture · contracts v1</span><span>Responsive review widths: 1440 · 1280 · 768 · 390 CSS px</span></footer>
  </div>;
}

export default App;
