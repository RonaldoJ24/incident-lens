import { useState } from "react";

type PreviewState =
  | "empty"
  | "loading"
  | "running"
  | "partial"
  | "successful"
  | "unresolved"
  | "failed"
  | "cached"
  | "upload-invalid"
  | "upload-accepted"
  | "saved"
  | "export-failed";

const states: Array<{ value: PreviewState; label: string }> = [
  { value: "successful", label: "Successful findings" },
  { value: "empty", label: "Empty" },
  { value: "loading", label: "Initial loading" },
  { value: "running", label: "Running" },
  { value: "partial", label: "Partial evidence" },
  { value: "unresolved", label: "Unresolved / conflicting" },
  { value: "failed", label: "Provider failure / retry" },
  { value: "cached", label: "Replayed example" },
  { value: "upload-invalid", label: "Upload validation failure" },
  { value: "upload-accepted", label: "Upload accepted" },
  { value: "saved", label: "Saved report" },
  { value: "export-failed", label: "Export failure" },
];

const stateCopy: Record<PreviewState, string> = {
  empty: "Choose an incident example to begin an investigation.",
  loading: "Loading the selected manifest. No evidence is shown until it returns.",
  running: "Running bounded read-only checks. You can cancel this run.",
  partial: "Some evidence returned; missing signals are called out below.",
  successful: "Evidence supports an unusual service/window ranking; causality remains unresolved.",
  unresolved: "Evidence conflicts or is insufficient. The next useful check stays visible.",
  failed: "The provider or tool failed safely. Retry the run or inspect the failure.",
  cached: "Previously completed example · replayed result, not a live run.",
  "upload-invalid": "Upload validation failed. Check JSONL type, size, and required signals.",
  "upload-accepted": "Upload accepted for this guest session; no shared state was changed.",
  saved: "Report revision saved. Saving does not mean the system was repaired.",
  "export-failed": "Export failed safely. The saved report remains available to retry.",
};

function StatusMessage({ state }: { state: PreviewState }) {
  return (
    <p className={`status-message status-${state}`} role="status" aria-live="polite">
      <span aria-hidden="true">●</span> {stateCopy[state]}
    </p>
  );
}

function App() {
  const [state, setState] = useState<PreviewState>("successful");
  const [evidenceOpen, setEvidenceOpen] = useState(true);

  return (
    <div className="app-shell">
      <header className="site-header">
        <a className="brand" href="#investigate" aria-label="Incident Lens home">Incident Lens</a>
        <nav aria-label="Primary navigation">
          <a className="active" href="#investigate">Investigate</a>
          <a href="#evaluation">Evaluation</a>
          <a href="#engineering">Engineering</a>
        </nav>
      </header>

      <main id="investigate">
        <section className="context-bar" aria-labelledby="context-heading">
          <div>
            <p className="eyebrow">Context</p>
            <h1 id="context-heading">Checkout failure <span>· recorded sample</span></h1>
            <div className="provenance" aria-label="Independent run provenance">
              <span>Origin · recorded benchmark</span>
              <span>Execution · new analysis</span>
              <span>Run v0.1 · 2026-09-13</span>
            </div>
          </div>
          <div className="context-controls">
            <label>Service<select defaultValue="checkoutservice"><option>checkoutservice</option><option>cartservice</option></select></label>
            <label>Time window<select defaultValue="ten-minutes"><option value="ten-minutes">12:00–12:10 UTC</option><option value="thirty-minutes">11:45–12:15 UTC</option></select></label>
            <button className="primary" type="button" onClick={() => setState("running")}>Run check</button>
          </div>
        </section>

        <div className="state-preview" aria-label="Foundation state preview">
          <span className="eyebrow">State preview</span>
          <select aria-label="Preview a required interface state" value={state} onChange={(event) => setState(event.target.value as PreviewState)}>
            {states.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
          <StatusMessage state={state} />
        </div>

        <div className="workspace-grid">
          <section className="findings-panel" aria-labelledby="finding-heading">
            <div className="panel-heading"><p className="eyebrow">Finding</p><span className="certainty uncertain">Uncertain</span></div>
            <h2 id="finding-heading">An unusual service/window ranking</h2>
            <p className="finding-copy">The recorded fixture shows a change around the selected window. Current evidence ranks unusual behavior; it does not prove causality. A competing explanation remains open.</p>
            <div className="checks">
              <p className="eyebrow">Next useful checks</p>
              <button type="button">Inspect trace interval for downstream errors <span>→</span></button>
              <button type="button">Compare the adjacent baseline window <span>→</span></button>
            </div>
            <p className="quiet-note">Finding IDs stay linked to their evidence, even when the diagnosis is unresolved.</p>
          </section>

          <aside className={`evidence-panel ${evidenceOpen ? "open" : "closed"}`} aria-labelledby="evidence-heading">
            <div className="panel-heading"><p className="eyebrow">Evidence drawer</p><button className="icon-button" type="button" aria-expanded={evidenceOpen} onClick={() => setEvidenceOpen(!evidenceOpen)}>{evidenceOpen ? "Hide" : "Show"}</button></div>
            {evidenceOpen && <div>
              <h2 id="evidence-heading">What supports this?</h2>
              <p className="eyebrow">Metric · recorded telemetry</p>
              <code>evidence-001 · 2023-05-01T12:05Z</code>
              <p className="small-copy">Fixture summary · source version fixture-v1</p>
              <div className="evidence-snippet"><code>window: 12:00 → 12:10</code><code>access: guest session · recorded</code></div>
              <p className="eyebrow">Knowledge</p><p className="small-copy">No supporting passage retrieved yet. Source/version citation appears here when available.</p>
            </div>}
          </aside>
        </div>

        <details className="timeline">
          <summary><span><span className="eyebrow">Execution timeline</span> Inspect signal completeness</span><span className="timeline-meta">1.2s · read-only · 1 evidence item</span></summary>
          <div className="timeline-detail"><code>read_recorded_manifest</code><span>queued → succeeded</span><span>Bounded parameters · no writes</span></div>
        </details>

        <section className="review-bar" aria-label="Review actions">
          <button type="button">Accept finding</button><button type="button">Correct</button><button type="button">Challenge</button><button type="button">Withhold source</button><button type="button">Change window</button><button type="button" onClick={() => setState("running")}>Re-run</button><button className="primary" type="button" onClick={() => setState("saved")}>Save / export</button>
        </section>
      </main>
      <footer><span>Foundation scaffold · contracts v1</span><span>Responsive review widths: 1440 · 1280 · 768 · 390 CSS px</span></footer>
    </div>
  );
}

export default App;
