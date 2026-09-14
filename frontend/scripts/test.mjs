import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const app = await readFile(resolve(root, "src/App.tsx"), "utf8");
const demo = await readFile(resolve(root, "src/demoAdapter.ts"), "utf8");
const css = await readFile(resolve(root, "src/styles.css"), "utf8");
const ui = `${app}\n${demo}`;

for (const phrase of ["controlled_runtime", "new_analysis", "Evidence drawer", "Execution timeline", "unusual service/window ranking", "Save / export", "datetime-local", "Window start (UTC)", "+00:00", "window_start", "createObjectURL", "Withhold retrieved sources", "suggestions only"]) {
  assert.ok(ui.includes(phrase), `UI contract missing: ${phrase}`);
}
for (const phrase of ["VITE_INCIDENT_LENS_DEMO", "Public demo · authored fixture · browser-local", "FastAPI/PostgreSQL backend, live provider/connector, and repair actions are not running.", "localStorage", "fixture-v1", "validateUpload", "reportKeys"]) {
  assert.ok(ui.includes(phrase), `demo contract missing: ${phrase}`);
}
assert.ok(app.includes("apiFetch"), "UI must route through the API/demo adapter");
assert.ok(app.includes("Browser-local preview ready"), "demo connection status must be explicit");
assert.ok(app.includes("browser-local static preview · FastAPI/PostgreSQL/provider/connector not running"), "demo footer must disclose unavailable services");
assert.ok(!app.includes('apiStatus === "ready" ? `Local API ready'), "demo mode must not claim the local API is ready");
assert.ok(demo.includes("Window start must precede window end"), "demo run adapter must reject invalid windows");
assert.ok(!app.includes("State preview"), "debug state selector must not be exposed");
assert.ok(!app.includes("<button key={check}"), "suggested checks must not be inert buttons");
for (const phrase of ["@media (max-width: 900px)", "@media (max-width: 560px)", "focus-visible"]) {
  assert.ok(css.includes(phrase), `responsive/accessibility contract missing: ${phrase}`);
}
console.log("frontend foundation checks passed");
