import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const app = await readFile(resolve(root, "src/App.tsx"), "utf8");
const demo = await readFile(resolve(root, "src/demoAdapter.ts"), "utf8");
const css = await readFile(resolve(root, "src/styles.css"), "utf8");
const ui = `${app}\n${demo}`;

for (const phrase of ["controlled_runtime", "new_analysis", "Evidence drawer", "Execution timeline", "signal ranking", "Save / export", "datetime-local", "Window start (UTC)", "+00:00", "window_start", "createObjectURL", "Withhold retrieved sources", "suggestions only", "Technical details", "Application log", "Technical record", "source_event", "0.24", "820 ms", "08:04:00Z", "08:04:30Z", "08:04:45Z", "09:05:00Z", "09:05:15Z", "09:05:30Z", "10:05:00Z", "No metric records returned"]) {
  assert.ok(ui.includes(phrase), `UI contract missing: ${phrase}`);
}
for (const phrase of ["VITE_INCIDENT_LENS_DEMO", "Public demo · authored fixture · browser-local", "FastAPI/PostgreSQL backend, live provider/connector, and repair actions are not running.", "localStorage", "incident-lens:public-demo:v2", "fixture-v1", "validateUpload", "reportKeys"]) {
  assert.ok(ui.includes(phrase), `demo contract missing: ${phrase}`);
}
assert.ok(app.includes("apiFetch"), "UI must route through the API/demo adapter");
assert.ok(app.includes("Browser-local preview ready"), "demo connection status must be explicit");
assert.ok(app.includes("FastAPI/PostgreSQL backend, live provider/connector, and repair actions are not running."), "demo notice must disclose unavailable services");
for (const phrase of ["id=\"investigate\"", "id=\"evaluation\"", "id=\"engineering\"", "Investigate", "Evaluation", "Engineering", "aria-current={activeSection === id ? \"location\"", "href={`#${id}`}"]) {
  assert.ok(app.includes(phrase), `navigation/section contract missing: ${phrase}`);
}
assert.ok(!ui.includes("unusual service/window ranking"), "internal ranking wording must not be product copy");
assert.ok(!ui.includes("bounded"), "internal scope wording must not be product copy");
assert.ok(!demo.includes("Authored fixture returned"), "generic evidence summaries must not be used");
assert.ok(demo.includes("ERROR checkout result"), "checkout evidence must include the authored error value");
assert.ok(demo.includes("request error rate 0.24") && demo.includes("request latency 820 ms"), "checkout evidence must include both authored metric values");
assert.ok(demo.includes("duration 910 ms"), "checkout trace evidence must include the authored duration");
assert.ok(demo.includes("request latency 640 ms") && demo.includes("error rate 0.04"), "degraded evidence must include both authored metric values");
assert.ok(demo.includes("WARN checkout result") && demo.includes("OK checkout trace"), "degraded evidence must include authored log and trace states");
assert.ok(demo.includes('sourceEvent: "checkout_result"') && demo.includes('sourceEvent: "checkout_request"'), "technical details must use canonical authored event names");
assert.ok(demo.includes("No metric records returned"), "missing evidence must remain explicit");
assert.ok(!demo.includes("1 metric record"), "checkout evidence must not collapse two metric events to one");
assert.ok(!app.includes("<span>· authored fixture</span>"), "case heading should not repeat fixture label");
assert.ok(!app.includes("} · Authored fixture</p>"), "evidence eyebrows should not repeat fixture label");
assert.ok(app.includes("UploadPanel sessionId"), "upload panel should remain available");
assert.ok(app.includes("upload-details"), "guest upload should be a secondary collapsible panel");
assert.ok(!app.includes('apiStatus === "ready" ? `Local API ready'), "demo mode must not claim the local API is ready");
assert.ok(demo.includes("Window start must precede window end"), "demo run adapter must reject invalid windows");
assert.ok(!app.includes("State preview"), "debug state selector must not be exposed");
assert.ok(!app.includes("<button key={check}"), "suggested checks must not be inert buttons");
for (const phrase of ["@media (max-width: 900px)", "@media (max-width: 560px)", "focus-visible"]) {
  assert.ok(css.includes(phrase), `responsive/accessibility contract missing: ${phrase}`);
}
console.log("frontend foundation checks passed");
