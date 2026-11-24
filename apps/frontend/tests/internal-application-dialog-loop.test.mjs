/* Behavioral regression: deep-linked dialogs open once and stay closed. */
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { test } from "node:test";
import ts from "typescript";

const filename = new URL("../app/(dashboard)/company/marketplace/_components/internal-applications-workspace.tsx", import.meta.url);
const helperFile = new URL("../app/(dashboard)/company/marketplace/_components/internal-application-deeplink.ts", import.meta.url);
const source = readFileSync(filename, "utf8");
const helperSource = readFileSync(helperFile, "utf8");
const compiled = ts.transpileModule(helperSource, {
    compilerOptions: {module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022},
}).outputText;
const {applicationToAutoOpen, urlAfterClosingApplication} = await import(
    "data:text/javascript;base64," + Buffer.from(compiled).toString("base64")
);

test("internal applications workspace parses as TSX", () => {
    const tree = ts.createSourceFile(filename.pathname, source, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TSX);
    assert.equal(tree.parseDiagnostics.length, 0);
});

test("new deep link opens just once and stays closed after dismissal and list refresh", () => {
    const ids = ["loan-a", "loan-b"];
    const requested = "loan-a";
    assert.equal(applicationToAutoOpen(requested, null, null, ids), "loan-a");
    assert.equal(applicationToAutoOpen(requested, "loan-a", null, ids), null);
    assert.equal(applicationToAutoOpen(requested, "loan-a", null, [...ids]), null);
    assert.equal(applicationToAutoOpen(requested, null, "loan-b", ids), null);
    assert.equal(applicationToAutoOpen("missing", null, null, ids), null);
    assert.equal(applicationToAutoOpen(null, null, null, ids), null);
    assert.equal(applicationToAutoOpen("loan-b", "loan-a", null, ids), "loan-b");
});

test("closing removes only the application parameter, preserving other filters and hash", () => {
    assert.equal(
        urlAfterClosingApplication("https://loanhub.co.ls/company/marketplace?application=loan-a&filter=pending#list"),
        "/company/marketplace?filter=pending#list",
    );
    assert.equal(urlAfterClosingApplication("https://loanhub.co.ls/company/marketplace?filter=pending"), null);
    assert.equal(
        urlAfterClosingApplication("https://loanhub.co.ls/company/marketplace?application=loan-a&application=loan-b"),
        "/company/marketplace",
    );
});

test("workspace consumes and clears deep links on both close paths", () => {
    assert.match(source, /applicationToAutoOpen\(/);
    assert.match(source, /lastAutoOpenedApplicationId\.current = requestedApplicationId/);
    assert.match(source, /urlAfterClosingApplication\(window\.location\.href\)/);
    assert.match(source, /window\.history\.replaceState\(window\.history\.state/);
    assert.match(source, /onOpenChange=\{\(open\) => !open && !working && closeApplication\(\)\}/);
    assert.match(source, /onClick=\{closeApplication\} disabled=\{working\}>Close<\/Button>/);
});
