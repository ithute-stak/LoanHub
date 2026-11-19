/* Static safety regression checks on the actual frontend source. No network. */
import { readFileSync } from "node:fs";
import { test } from "node:test";
import assert from "node:assert/strict";
import ts from "typescript";

const componentPath = new URL("../components/clients/disabled-registration-field.tsx", import.meta.url);
const pagePath = new URL("../app/(dashboard)/company/clients/registration-preview/page.tsx", import.meta.url);
const apiPath = new URL("../api/batlokoaRegistration.ts", import.meta.url);

function source(url) {
  return readFileSync(url, "utf8");
}

function jsxTags(file) {
  const result = [];
  const sourceFile = ts.createSourceFile(file.pathname, source(file), ts.ScriptTarget.ES2022, true, ts.ScriptKind.TSX);
  assert.equal(sourceFile.parseDiagnostics.length, 0, "Component must parse as TSX");
  function visit(node) {
    if (ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node)) {
      result.push({
        name: node.tagName.getText(sourceFile),
        properties: node.attributes.properties.map((attribute) =>
          ts.isJsxAttribute(attribute) ? attribute.name.getText(sourceFile) : "...spread"),
      });
    }
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
  return result;
}

test("prototype has no writable input, consent control, or implicit field values", () => {
  const tags = jsxTags(componentPath);
  const controls = tags.filter((tag) => tag.name === "Input" || tag.name === "Checkbox");
  assert.ok(controls.length >= 2);
  for (const control of controls) {
    assert.ok(control.properties.includes("disabled"), control.name + " must be disabled");
    assert.ok(!control.properties.includes("onChange"));
    assert.ok(!control.properties.includes("defaultValue"));
    assert.ok(!control.properties.includes("value"));
    assert.ok(!control.properties.includes("...spread"));
  }
  const entire = source(componentPath);
  assert.ok(!/localStorage|sessionStorage|onSubmit|fetch\s*\(/.test(entire));
});

test("preview page and registration client do not contain write-capable calls", () => {
  const page = source(pagePath);
  const api = source(apiPath);
  assert.ok(!/api\.post\s*\(|api\.patch\s*\(|api\.put\s*\(|api\.delete\s*\(/.test(page + api));
  assert.ok(!/localStorage|sessionStorage|onSubmit|<form\b/i.test(page + api));
  assert.ok(api.includes('"/batlokoa/registration/availability"'));
  assert.ok(api.includes('"/batlokoa/registration/form-requirements"'));
  assert.ok(page.includes("validateBatlokoaPreviewContract(status, form)"));
});
