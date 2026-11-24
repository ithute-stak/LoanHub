import { readFileSync, existsSync } from "node:fs";
import { test } from "node:test";
import assert from "node:assert/strict";

const read = (path) => readFileSync(new URL("../" + path, import.meta.url), "utf8");

test("shared modal surfaces render the LoanHub branding", () => {
  assert.ok(existsSync(new URL("../public/loanhub-horizontal-logo.png", import.meta.url)));
  const dialog = read("components/ui/dialog.tsx");
  assert.match(dialog, /<Image src="\/loanhub-horizontal-logo\.png" alt="LoanHub"/);
  assert.match(dialog, /<DialogBrand\s*\/>/);
  assert.doesNotMatch(dialog, /brandSrc|brandAlt/);
  for (const name of ["alert-dialog", "sheet", "drawer"]) {
    assert.match(read("components/ui/" + name + ".tsx"), /<DialogBrand\s*\/>/, name);
  }
});

test("solid custom headers retain branding and separate the title", () => {
  const custom = read("components/ui/custom-dialog.tsx");
  assert.doesNotMatch(custom, /brandSrc|brandAlt|banner\s*=/);
  assert.match(custom, /<DialogContent\b/);
  assert.doesNotMatch(custom, /!solidHeader\s*\?/);
  assert.doesNotMatch(custom, /object-cover/);
});

test("corrected administration banners use LoanHub", () => {
  for (const path of [
    "app/(dashboard)/superadmin/companies/branches/_components/branch-view-dialog.tsx",
    "app/(dashboard)/superadmin/company-admins/_components/userEditDialog.tsx",
  ]) {
    assert.match(read(path), /banner="\/loanhub-horizontal-logo\.png"/);
  }
});
