import { readFileSync, existsSync, readdirSync } from "node:fs";
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

test("repository source audit identifies modal surfaces outside shared wrappers", () => {
  const root = new URL("../", import.meta.url);
  const approved = new Set([
    "components/ui/dialog.tsx", "components/ui/alert-dialog.tsx",
    "components/ui/sheet.tsx", "components/ui/drawer.tsx",
  ]);
  const findings = [];
  let scanned = 0;
  function walk(dir, prefix) {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = prefix + entry.name;
      const url = new URL(entry.name + (entry.isDirectory() ? "/" : ""), dir);
      if (entry.isDirectory()) { walk(url, path + "/"); continue; }
      if (!/\.[jt]sx?$/.test(entry.name)) continue;
      scanned++;
      if (approved.has(path)) continue;
      const source = readFileSync(url, "utf8");
      const pattern = /<dialog\b|\brole\s*=\s*["'](?:alert)?dialog["']|\baria-modal\s*=\s*(?:["']true["']|\{true\})|<(?:DialogPrimitive|AlertDialogPrimitive|SheetPrimitive|DrawerPrimitive)\.Content\b|from\s+["']@radix-ui\/react-(?:alert-)?dialog["']/g;
      for (const match of source.matchAll(pattern)) {
        const line = source.slice(0, match.index).split("\n").length;
        findings.push(path + ":" + line + " " + match[0]);
      }
    }
  }
  for (const dir of ["app", "components"]) walk(new URL(dir + "/", root), dir + "/");
  assert.ok(scanned > 0);
  console.log("Modal audit scanned " + scanned + " source files.");
  console.log(findings.length ? "Review potential bypasses:\n" + findings.join("\n") : "No matching bypass patterns found.");
  const reviewedBranded = new Set([
    "components/navigation/mobile-app-navigation.tsx",
    "components/portal/portal-shell.tsx",
  ]);
  const unresolved = findings.filter((finding) => {
    const path = finding.split(":")[0];
    if (reviewedBranded.has(path)) return !/<DialogBrand\s*\/>/.test(read(path));
    if (path === "components/system/mobile-pull-to-refresh.tsx" &&
        finding.endsWith("role='dialog'")) {
      return !read(path).includes("[role='dialog']");
    }
    return true;
  });
  assert.deepEqual(unresolved, [], "Unreviewed modal branding bypasses detected");
});
