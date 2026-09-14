import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const app = await readFile(resolve(root, "src/App.tsx"), "utf8");
const css = await readFile(resolve(root, "src/styles.css"), "utf8");

for (const phrase of ["controlled_runtime", "new_analysis", "Evidence drawer", "Execution timeline", "unusual service/window ranking", "Save / export", "datetime-local", "Window start (UTC)", "+00:00", "window_start", "createObjectURL", "Withhold retrieved sources", "suggestions only"]) {
  assert.ok(app.includes(phrase), `UI contract missing: ${phrase}`);
}
assert.ok(!app.includes("State preview"), "debug state selector must not be exposed");
assert.ok(!app.includes("<button key={check}"), "suggested checks must not be inert buttons");
for (const phrase of ["@media (max-width: 900px)", "@media (max-width: 560px)", "focus-visible"]) {
  assert.ok(css.includes(phrase), `responsive/accessibility contract missing: ${phrase}`);
}
console.log("frontend foundation checks passed");
