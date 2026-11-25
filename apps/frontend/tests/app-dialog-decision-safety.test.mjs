import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {test} from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("../lib/app-dialog-decisions.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
    compilerOptions: {module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022},
}).outputText;
const {
    cancelledDialogResult,
    canSubmitDialog,
    submittedDialogResult,
} = await import("data:text/javascript;base64," + Buffer.from(compiled).toString("base64"));

test("Cancel, Escape and outside click never approve a financial action", () => {
    assert.equal(cancelledDialogResult("confirm"), false);
    assert.equal(cancelledDialogResult("prompt"), null);
    assert.equal(cancelledDialogResult("message"), null);
    assert.notEqual(cancelledDialogResult("confirm"), true);
});

test("Only explicit confirmation returns true", () => {
    assert.equal(submittedDialogResult("confirm", "", {destructive: true}), true);
    assert.equal(submittedDialogResult("message", "", {}), null);
});

test("Required financial justification is enforced before submission", () => {
    const options = {minLength: 10, destructive: true};
    assert.equal(canSubmitDialog("prompt", "  short  ", options), false);
    assert.equal(submittedDialogResult("prompt", "  short  ", options), null);
    assert.equal(canSubmitDialog("prompt", "  documented reason  ", options), true);
    assert.equal(submittedDialogResult("prompt", "  documented reason  ", options), "  documented reason  ");
    assert.equal(canSubmitDialog("confirm", "", options), true);
});

test("Existing dialogs use the tested decision helpers for all dismissal paths", () => {
    const component = readFileSync(new URL("../lib/app-dialog.tsx", import.meta.url), "utf8");
    assert.match(component, /onOpenChange=\{\(open\) => \{ if \(!open\) resolve\(cancelledDialogResult\(kind\)\); \}\}/);
    assert.match(component, /onEscapeKeyDown=\{\(\) => resolve\(cancelledDialogResult\(kind\)\)\}/);
    assert.match(component, /onClick=\{\(\) => resolve\(cancelledDialogResult\(kind\)\)\}/);
    assert.match(component, /onClick=\{\(\) => resolve\(submittedDialogResult\(kind, value, options\)\)\}/);
    assert.match(component, /disabled=\{!allowed\}/);
});
