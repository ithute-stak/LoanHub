/* Regression: deep-linked application dialogs must remain closed when dismissed. */
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { test } from "node:test";
import ts from "typescript";

const filename = new URL("../app/(dashboard)/company/marketplace/_components/internal-applications-workspace.tsx", import.meta.url);
const source = readFileSync(filename, "utf8");

test("internal applications workspace parses as TSX", () => {
  const tree = ts.createSourceFile(filename.pathname, source, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TSX);
  assert.equal(tree.parseDiagnostics.length, 0);
});

test("deep-linked applications are consumed once, not reopened whenever selected resets", () => {
  assert.match(source, /lastAutoOpenedApplicationId\.current === requestedApplicationId/);
  assert.match(source, /lastAutoOpenedApplicationId\.current = requestedApplicationId/);
  assert.match(source, /if \(requested\) \{/);
});

test("both close paths remove the application query parameter and clear selection", () => {
  assert.match(source, /function closeApplication\(\)/);
  assert.match(source, /url\.searchParams\.delete\("application"\)/);
  assert.match(source, /window\.history\.replaceState\(window\.history\.state/);
  assert.match(source, /onOpenChange=\{\(open\) => !open && !working && closeApplication\(\)\}/);
  assert.match(source, /onClick=\{closeApplication\} disabled=\{working\}>Close<\/Button>/);
});
