import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const app = await readFile(resolve(root, "src/App.tsx"), "utf8");
const css = await readFile(resolve(root, "src/styles.css"), "utf8");

for (const phrase of ["recorded benchmark", "new analysis", "Evidence drawer", "Execution timeline", "unusual service/window ranking", "Save / export"]) {
  assert.ok(app.includes(phrase), `UI contract missing: ${phrase}`);
}
for (const phrase of ["@media (max-width: 900px)", "@media (max-width: 560px)", "focus-visible"]) {
  assert.ok(css.includes(phrase), `responsive/accessibility contract missing: ${phrase}`);
}
console.log("frontend foundation checks passed");
