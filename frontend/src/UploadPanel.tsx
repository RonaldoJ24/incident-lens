import { useState } from "react";
import { apiFetch, apiHref, demoUploadSampleHref, isDemoMode } from "./demoAdapter";

type UploadPanelProps = {
  sessionId?: string;
  onState: (state: "upload-invalid" | "upload-accepted") => void;
};

type UploadResult = {
  upload_id?: string;
  validation: string;
  record_count: number;
  duplicate_count: number;
  conflict_count: number;
  missing_signal_count: number;
  untrusted_record_count: number;
  messages: string[];
};

export default function UploadPanel({ sessionId, onState }: UploadPanelProps) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<UploadResult>();

  const upload = async (file: File) => {
    if (!sessionId) return;
    setBusy(true);
    try {
      const initiatedResponse = await apiFetch("/v1/uploads/initiate", { method: "POST", headers: { "X-Session-ID": sessionId } });
      if (!initiatedResponse.ok) throw new Error("Upload could not be initiated");
      const initiated = await initiatedResponse.json() as { upload_id: string };
      const response = await apiFetch(`/v1/uploads/${initiated.upload_id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/jsonl", "X-Session-ID": sessionId },
        body: await file.arrayBuffer(),
      });
      const next = await response.json() as UploadResult;
      setResult(next);
      onState(response.ok && next.validation === "accepted" ? "upload-accepted" : "upload-invalid");
    } catch {
      setResult({ validation: "invalid", record_count: 0, duplicate_count: 0, conflict_count: 0, missing_signal_count: 0, untrusted_record_count: 0, messages: ["Upload request failed safely."] });
      onState("upload-invalid");
    } finally {
      setBusy(false);
    }
  };

  return <section className="upload-panel" aria-labelledby="upload-heading">
    <div><p className="eyebrow">Guest upload</p><h2 id="upload-heading">Bring a JSONL sample</h2><p className="small-copy">Only this guest session sees the validation result. Text is retained as untrusted data.</p></div>
    <div className="upload-actions"><a className="upload-sample" href={isDemoMode ? demoUploadSampleHref : apiHref("/v1/uploads/sample")} download>Download sample</a><label className="upload-input">Choose JSONL<input type="file" accept=".jsonl,application/jsonl" disabled={!sessionId || busy} onChange={(event) => { const file = event.target.files?.[0]; if (file) void upload(file); event.currentTarget.value = ""; }} /></label></div>
    {busy && <p className="small-copy" role="status">Validating upload…</p>}
    {result && <p className="small-copy" role="status">{result.validation} · {result.record_count} record(s) · {result.duplicate_count} duplicate(s) · {result.conflict_count} conflict(s) · {result.missing_signal_count} missing signal(s) · {result.untrusted_record_count} untrusted text record(s). {result.messages.join(" ")}</p>}
  </section>;
}
