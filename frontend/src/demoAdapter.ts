export type DemoCase = {
  case_id: string;
  title: string;
  description: string;
  service: string;
  telemetry_origin: "controlled_runtime";
  fixture_kind: "authored_synthetic_controlled_fixture";
  source_interval: { start: string; end: string };
};

export const demoCases: DemoCase[] = [
  { case_id: "checkout-failure", title: "Checkout failure", description: "Checkout example with signals for a read-only local run.", service: "checkoutservice", telemetry_origin: "controlled_runtime", fixture_kind: "authored_synthetic_controlled_fixture", source_interval: { start: "2026-09-13T08:00:00Z", end: "2026-09-13T08:10:00Z" } },
  { case_id: "degraded-performance", title: "Degraded performance", description: "Latency example where a nearby release clue is not causal proof.", service: "checkoutservice", telemetry_origin: "controlled_runtime", fixture_kind: "authored_synthetic_controlled_fixture", source_interval: { start: "2026-09-13T09:00:00Z", end: "2026-09-13T09:10:00Z" } },
  { case_id: "insufficient-evidence", title: "Insufficient evidence", description: "Gap example with no metric or trace records in its interval.", service: "checkoutservice", telemetry_origin: "controlled_runtime", fixture_kind: "authored_synthetic_controlled_fixture", source_interval: { start: "2026-09-13T10:00:00Z", end: "2026-09-13T10:10:00Z" } },
];

function requestedMode(): string {
  if (typeof window === "undefined") return "";
  return new URLSearchParams(window.location.search).get("mode") ?? "";
}

// The Pages build remains the instant authored demo unless the user explicitly
// opts into live mode with ?mode=live. A live URL never routes through this adapter.
export const isLiveMode = requestedMode() === "live";
export const isDemoMode = !isLiveMode && import.meta.env.VITE_INCIDENT_LENS_DEMO === "1";
const configuredApiOrigin = String(import.meta.env.VITE_INCIDENT_LENS_API_ORIGIN ?? "").trim();

function apiInput(input: RequestInfo | URL): URL {
  const raw = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
  const base = typeof window === "undefined" ? "http://localhost" : window.location.origin;
  const requested = new URL(raw, base);
  const allowed = requested.pathname === "/v1" || requested.pathname.startsWith("/v1/") || requested.pathname === "/health" || requested.pathname.startsWith("/health/");
  if (!allowed) throw new Error("API path is outside the Incident Lens surface");
  if (requested.origin !== base) throw new Error("API requests must use a relative Incident Lens path");
  if (!isLiveMode) return requested;
  let origin: URL;
  try { origin = new URL(configuredApiOrigin); } catch { throw new Error("Live API origin is not configured"); }
  if (origin.protocol !== "https:" || (origin.pathname !== "/" && origin.pathname !== "")) throw new Error("Live API origin must be an absolute HTTPS origin");
  return new URL(`${requested.pathname}${requested.search}`, origin.origin);
}

export function apiHref(path: string): string {
  try { return apiInput(path).toString(); } catch { return "#"; }
}
const STORAGE_KEY = "incident-lens:public-demo:v2";
const DEMO_SOURCE = { source_id: "incident-lens-authored-fixture", version: "fixture-v1" };
const SAMPLE_JSONL = '{"event_id":"sample-log-1","timestamp":"2026-09-14T08:00:00Z","signal":"log","service":"checkoutservice","message":"request completed"}\n{"event_id":"sample-metric-1","timestamp":"2026-09-14T08:00:01Z","signal":"metric","service":"checkoutservice","value":42.0}\n{"event_id":"sample-trace-1","timestamp":"2026-09-14T08:00:02Z","signal":"trace","service":"checkoutservice","duration_ms":12.5}\n';
export const demoUploadSampleHref = `data:application/jsonl;charset=utf-8,${encodeURIComponent(SAMPLE_JSONL)}`;

type DemoRun = {
  run_id: string;
  session_id: string;
  case_id: string;
  status: "queued" | "running" | "partial" | "succeeded" | "failed" | "cancelled";
  attempt: number;
  provenance: { telemetry_origin: "controlled_runtime"; execution: "new_analysis"; run_version: "phase1-fixture-v1"; run_time: string; source_interval: { start: string; end: string } };
  withheld?: boolean;
};

type DemoEvidence = { evidence_id: string; source_type: "log" | "metric" | "trace" | "runbook"; source: typeof DEMO_SOURCE; source_event?: string; event_time: string; query_window: DemoRun["provenance"]["source_interval"]; content_or_summary: string; quality_flags: string[]; access_scope: "guest_session" | "public_knowledge" };
type DemoFinding = { finding_id: string; run_id: string; assessment: string; certainty: "uncertain" | "insufficient_evidence"; evidence_ids: string[]; next_checks: string[] };
type DemoTimeline = { event_id: string; run_id: string; step: string; state: "succeeded" | "partial" | "cancelled" | "failed"; scope: { operation: string; read_only: true; parameters: Record<string, unknown> }; evidence_ids: string[]; duration_ms: number };
type DemoReport = { report_id: string; session_id: string; run_id: string; revision: number; provenance: DemoRun["provenance"]; finding_ids: string[]; saved_at: string; repair_claim: false };
type DemoUpload = { session_id: string; bytes?: number; result?: Record<string, unknown> };
type DemoRecord = { session_id: string; next_run: number; last_run_id?: string; last_run_case_id?: string; runs: Record<string, DemoRun>; evidence: Record<string, DemoEvidence[]>; findings: Record<string, DemoFinding[]>; timeline: Record<string, DemoTimeline[]>; reports: Record<string, DemoReport>; reportKeys: Record<string, string>; uploads: Record<string, DemoUpload> };

function newRecord(): DemoRecord {
  return { session_id: "demo-session-browser-local", next_run: 1, runs: {}, evidence: {}, findings: {}, timeline: {}, reports: {}, reportKeys: {}, uploads: {} };
}

function loadRecord(): DemoRecord {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...newRecord(), ...JSON.parse(raw) } as DemoRecord;
  } catch {
    // Private browsing or blocked storage still gets an in-memory session.
  }
  return newRecord();
}

let record = newRecord();
if (isDemoMode && typeof window !== "undefined") record = loadRecord();

function persist(): void {
  try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(record)); } catch { /* storage is optional */ }
}

function json(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...headers } });
}

function text(body: string, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(body, { status, headers: { "Content-Type": "text/plain", ...headers } });
}

function requestSession(init?: RequestInit): string | undefined {
  const headers = new Headers(init?.headers);
  return headers.get("X-Session-ID") ?? headers.get("x-session-id") ?? undefined;
}

function owned(sessionId: string | undefined): boolean {
  return sessionId === record.session_id;
}

function notFound(): Response { return json({ detail: "Not found" }, 404); }

function runFor(path: string): DemoRun | undefined {
  const runId = path.split("/")[3];
  return record.runs[runId];
}

function bodyOf(init?: RequestInit): Record<string, unknown> {
  if (typeof init?.body !== "string") return {};
  try { return JSON.parse(init.body) as Record<string, unknown>; } catch { return {}; }
}

function evidenceFor(run: DemoRun, includeWithheld = false): DemoEvidence[] {
  const items = record.evidence[run.run_id] ?? [];
  return includeWithheld || !run.withheld ? items : items.filter((item) => item.source_type !== "runbook");
}

function evidenceDetails(caseId: string, signal: "log" | "metric" | "trace", interval: DemoRun["provenance"]["source_interval"], missing: string[]): { eventTime: string; summary: string; sourceEvent?: string } {
  if (caseId === "checkout-failure") {
    if (signal === "log") return { eventTime: "2026-09-13T08:04:30Z", summary: "ERROR checkout result: authored error event retained as untrusted content.", sourceEvent: "checkout_result" };
    if (signal === "metric") return { eventTime: "2026-09-13T08:04:00Z", summary: "2 metric values at 2026-09-13T08:04:00Z: request error rate 0.24 and request latency 820 ms.", sourceEvent: "request_error_rate, request_latency_ms" };
    return { eventTime: "2026-09-13T08:04:45Z", summary: "ERROR checkout request: duration 910 ms at 2026-09-13T08:04:45Z.", sourceEvent: "checkout_request" };
  }
  if (caseId === "degraded-performance") {
    if (signal === "metric") return { eventTime: "2026-09-13T09:05:00Z", summary: "2 metric values at 2026-09-13T09:05:00Z: request latency 640 ms and error rate 0.04.", sourceEvent: "request_latency_ms, request_error_rate" };
    if (signal === "log") return { eventTime: "2026-09-13T09:05:15Z", summary: "WARN checkout result: authored latency observation retained as untrusted content.", sourceEvent: "checkout_result" };
    return { eventTime: "2026-09-13T09:05:30Z", summary: "OK checkout trace: duration 640 ms at 2026-09-13T09:05:30Z.", sourceEvent: "checkout_request" };
  }
  if (caseId === "insufficient-evidence" && signal === "log") return { eventTime: "2026-09-13T10:05:00Z", summary: "INFO checkout result: only the authored log signal is available.", sourceEvent: "checkout_result" };
  if (missing.includes(signal)) return { eventTime: interval.start, summary: ({ log: `No log records returned at the selected interval start (${interval.start}).`, metric: `No metric records returned at the selected interval start (${interval.start}).`, trace: `No trace records returned at the selected interval start (${interval.start}).` }[signal]) };
  return { eventTime: interval.start, summary: `1 ${signal} event at ${interval.start}.`, sourceEvent: `${signal}_event` };
}

function executeWorkflow(run: DemoRun): void {
  const started = performance.now();
  const selected = demoCases.find((item) => item.case_id === run.case_id) ?? demoCases[0];
  const interval = run.provenance.source_interval;
  const missing = run.case_id === "insufficient-evidence" ? ["metric", "trace"] : [];
  const evidence: DemoEvidence[] = (["log", "metric", "trace"] as const).map((signal) => {
    const details = evidenceDetails(run.case_id, signal, interval, missing);
    return { evidence_id: `demo-evidence-${run.run_id}-${signal}`, source_type: signal, source: DEMO_SOURCE, source_event: details.sourceEvent, event_time: details.eventTime, query_window: interval, content_or_summary: details.summary, quality_flags: missing.includes(signal) ? ["missing"] : [], access_scope: "guest_session" };
  });
  if (!run.withheld) evidence.push({ evidence_id: `demo-evidence-${run.run_id}-runbook`, source_type: "runbook", source: DEMO_SOURCE, event_time: interval.start, query_window: interval, content_or_summary: "Reference guidance: compare the adjacent baseline before making a causal claim.", quality_flags: [], access_scope: "public_knowledge" });
  const available = evidence.filter((item) => item.source_type !== "runbook" && !item.quality_flags.includes("missing"));
  const finding: DemoFinding = {
    finding_id: `demo-finding-${run.run_id}`,
    run_id: run.run_id,
    assessment: missing.length ? "The log event is present at 10:05 UTC, but metric and trace records are missing from the selected interval. No causal conclusion is supported." : run.case_id === "degraded-performance" ? "The selected records include 640 ms latency, 0.04 error rate, a warning log, and an OK trace lasting 640 ms; the nearby release clue does not prove causality." : "The selected records include one checkout error, two metric values (error rate 0.24 and latency 820 ms), and one checkout request trace lasting 910 ms; this does not establish causality.",
    certainty: missing.length ? "insufficient_evidence" : "uncertain",
    evidence_ids: evidence.map((item) => item.evidence_id),
    next_checks: ["Inspect the trace interval", "Compare the adjacent baseline window"],
  };
  const status = missing.length ? "partial" : "succeeded";
  record.evidence[run.run_id] = evidence;
  record.findings[run.run_id] = [finding];
  record.timeline[run.run_id] = [{ event_id: `demo-timeline-${run.run_id}`, run_id: run.run_id, step: "inspect_authored_fixture", state: status, scope: { operation: "read_authored_fixture", read_only: true, parameters: { case_id: selected.case_id, window_start: interval.start, window_end: interval.end, max_events: 100 } }, evidence_ids: available.map((item) => item.evidence_id), duration_ms: Math.max(1, Math.round(performance.now() - started)) }];
  run.status = status;
  persist();
}

function validateUpload(bytes: ArrayBuffer, uploadId: string, sessionId: string): Record<string, unknown> {
  const messages: string[] = [];
  const textBody = new TextDecoder().decode(bytes);
  const lines = textBody.split(/\r?\n/).filter((line) => line.trim());
  let recordCount = 0;
  let untrusted = 0;
  let duplicateCount = 0;
  let conflictCount = 0;
  const seen = new Map<string, string>();
  const signals = new Set<string>();
  if (bytes.byteLength > 10 * 1024 * 1024) messages.push("upload exceeds 10 MiB");
  if (lines.length > 10000) messages.push("upload exceeds 10,000 records");
  lines.slice(0, 10000).forEach((line, index) => {
    try {
      const item = JSON.parse(line) as Record<string, unknown>;
      if (line.length > 256 * 1024 || typeof item.event_id !== "string" || typeof item.timestamp !== "string" || typeof item.signal !== "string" || typeof item.service !== "string" || !["log", "metric", "trace"].includes(item.signal)) throw new Error("invalid event fields");
      if (item.signal === "log" && typeof item.message !== "string") throw new Error("log records require message");
      if (item.signal === "metric" && typeof item.value !== "number") throw new Error("metric records require value");
      if (item.signal === "trace" && typeof item.duration_ms !== "number") throw new Error("trace records require duration_ms");
      recordCount += 1; signals.add(item.signal);
      const fingerprint = JSON.stringify(item, Object.keys(item).sort());
      const prior = seen.get(item.event_id);
      if (prior === undefined) seen.set(item.event_id, fingerprint);
      else if (prior === fingerprint) duplicateCount += 1;
      else conflictCount += 1;
      if (typeof item.message === "string") {
        untrusted += 1;
        if (/ignore\s+(?:all|any|the|previous)|system\s+message|execute\s+(?:a\s+)?command|you\s+are\s+now/i.test(item.message)) messages.push("prompt-like text retained as untrusted data; no instructions were executed");
      }
    } catch (error) { if (messages.length < 20) messages.push(`invalid record ${index + 1}: ${error instanceof Error ? error.message : "invalid JSON"}`); }
  });
  const missing = (["log", "metric", "trace"] as const).filter((signal) => !signals.has(signal));
  if (missing.length) messages.push(`missing signals: ${missing.join(", ")}`);
  if (conflictCount) messages.push("conflicting duplicate event IDs detected");
  if (duplicateCount) messages.push("duplicate records were ignored");
  const validation = messages.some((message) => message.startsWith("invalid") || message.includes("exceeds")) ? "invalid" : conflictCount ? "conflicting" : duplicateCount ? "duplicate" : missing.length ? "incomplete" : "accepted";
  const result = { upload_id: uploadId, session_id: sessionId, content_type: "application/jsonl", byte_size: bytes.byteLength, validation, telemetry_origin: "guest_upload", messages: [...new Set(messages)], record_count: recordCount, duplicate_count: duplicateCount, conflict_count: conflictCount, missing_signals: missing, missing_signal_count: missing.length, untrusted_record_count: untrusted };
  record.uploads[uploadId] = { session_id: sessionId, bytes: bytes.byteLength, result };
  persist();
  return result;
}

async function demoFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const url = new URL(input.toString(), window.location.origin);
  const path = url.pathname;
  const method = (init?.method ?? "GET").toUpperCase();
  const requestBody = bodyOf(init);
  const sessionId = requestSession(init) ?? (method === "POST" && path === "/v1/runs" && typeof requestBody.session_id === "string" ? requestBody.session_id : undefined);
  if (method === "POST" && path === "/v1/sessions") return json({ session_id: record.session_id, last_run_id: record.last_run_id, last_run_case_id: record.last_run_case_id }, 201);
  if (method === "GET" && path === "/v1/cases") return json({ cases: demoCases });
  if (method === "GET" && path === "/v1/uploads/sample") return text(SAMPLE_JSONL, 200, { "Content-Type": "application/jsonl", "Content-Disposition": 'attachment; filename="incident-lens-sample.jsonl"' });
  if (!owned(sessionId)) return notFound();
  if (method === "POST" && path === "/v1/runs") {
    const payload = requestBody;
    const selected = demoCases.find((item) => item.case_id === payload.case_id);
    if (!selected) return json({ detail: "Case not found" }, 404);
    if (typeof payload.window_start !== "string" || typeof payload.window_end !== "string") return json({ detail: "Window start and end are required" }, 400);
    const startMs = Date.parse(payload.window_start);
    const endMs = Date.parse(payload.window_end);
    if (!Number.isFinite(startMs) || !Number.isFinite(endMs) || startMs >= endMs) return json({ detail: "Window start must precede window end" }, 400);
    const sourceInterval = { ...selected.source_interval, ...(typeof payload.window_start === "string" ? { start: payload.window_start.replace(/:00\+00:00$/, "Z") } : {}), ...(typeof payload.window_end === "string" ? { end: payload.window_end.replace(/:00\+00:00$/, "Z") } : {}) };
    const runId = `demo-run-${selected.case_id}-${record.next_run++}`;
    const run: DemoRun = { run_id: runId, session_id: record.session_id, case_id: selected.case_id, status: "queued", attempt: 1, provenance: { telemetry_origin: "controlled_runtime", execution: "new_analysis", run_version: "phase1-fixture-v1", run_time: new Date().toISOString(), source_interval: sourceInterval } };
    record.runs[runId] = run; record.last_run_id = runId; record.last_run_case_id = selected.case_id; persist();
    return json(run, 202);
  }
  const run = runFor(path);
  if (run && path.endsWith("/workflow") && method === "POST") { run.status = "running"; executeWorkflow(run); return json({ run_id: run.run_id, status: run.status, checkpoint_id: `demo-checkpoint-${run.run_id}`, retrieval_hits: [], claims: [], evidence_ids: (record.findings[run.run_id]?.[0]?.evidence_ids ?? []), report_id: null }, 202); }
  if (run && path.endsWith("/review") && method === "POST") { const payload = requestBody; if (payload.action === "withhold_source") run.withheld = true; persist(); return json({ correction_id: `demo-correction-${run.run_id}-${Date.now()}`, run_id: run.run_id, action: payload.action, note: payload.note ?? "", created_at: new Date().toISOString(), context_preserved: true, source_ids: payload.action === "withhold_source" ? [`${DEMO_SOURCE.source_id}`] : [] }, 201); }
  if (run && method === "DELETE") { run.status = "cancelled"; persist(); return json(run, 202); }
  if (run && method === "GET" && path.endsWith("/evidence")) return json({ evidence: evidenceFor(run) });
  if (run && method === "GET" && path.endsWith("/findings")) return json({ findings: record.findings[run.run_id] ?? [] });
  if (run && method === "GET" && path.endsWith("/timeline")) return json({ events: record.timeline[run.run_id] ?? [] });
  if (run && method === "GET") return json(run);
  if (method === "POST" && path === "/v1/reports") {
    const payload = requestBody; const runToSave = record.runs[String(payload.run_id)]; if (!runToSave) return notFound();
    const idempotency = new Headers(init?.headers).get("Idempotency-Key") ?? `demo-report-${runToSave.run_id}`;
    const existing = record.reportKeys[idempotency]; if (existing) return json(record.reports[existing], 201);
    const reportId = `demo-report-${runToSave.run_id}`; const report: DemoReport = { report_id: reportId, session_id: record.session_id, run_id: runToSave.run_id, revision: 1, provenance: runToSave.provenance, finding_ids: (record.findings[runToSave.run_id] ?? []).map((item) => item.finding_id), saved_at: new Date().toISOString(), repair_claim: false };
    record.reports[reportId] = report; record.reportKeys[idempotency] = reportId; persist(); return json(report, 201);
  }
  const reportId = path.split("/")[3];
  if (reportId && method === "POST" && path.endsWith("/export")) { const report = record.reports[reportId]; if (!report) return notFound(); const exportBody = { report, provenance: report.provenance, findings: record.findings[report.run_id] ?? [], evidence: evidenceFor(record.runs[report.run_id]), timeline: record.timeline[report.run_id] ?? [], workflow: { mode: "public_demo", authored_fixture: true } }; return json(exportBody, 200, { "Content-Disposition": `attachment; filename="incident-lens-${reportId}-r1.json"` }); }
  if (method === "POST" && path === "/v1/uploads/initiate") { const uploadId = `demo-upload-${Date.now()}`; record.uploads[uploadId] = { session_id: record.session_id }; persist(); return json({ upload_id: uploadId, session_id: record.session_id, content_type: "application/jsonl", byte_size: 0, validation: "incomplete", messages: ["upload initiated"] }, 201); }
  if (method === "PUT" && path.startsWith("/v1/uploads/")) { const uploadId = path.split("/")[3]; const body = init?.body; const bytes = body instanceof ArrayBuffer ? body : body instanceof Blob ? await body.arrayBuffer() : new ArrayBuffer(0); return json(validateUpload(bytes, uploadId, record.session_id)); }
  return notFound();
}

export function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  if (isDemoMode) return demoFetch(input, init);
  const target = apiInput(input);
  return fetch(target, { ...init, redirect: "error" });
}
