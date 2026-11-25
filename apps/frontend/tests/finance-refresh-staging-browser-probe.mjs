/**
 * Opt-in, read-only browser certification for LoanHub company Finance.
 * Requires two independently provisioned synthetic company accounts.
 *
 * Install Playwright outside the committed dependency tree and provision
 * storageState files outside this repository:
 *   npm install --no-save playwright
 *   LOANHUB_E2E_BASE_URL=https://sandbox.example.test \
 *   LOANHUB_E2E_STATE_A=/secure/company-a.json \
 *   LOANHUB_E2E_COMPANY_A=synthetic-company-a \
 *   LOANHUB_E2E_STATE_B=/secure/company-b.json \
 *   LOANHUB_E2E_COMPANY_B=synthetic-company-b \
 *   node apps/frontend/tests/finance-refresh-staging-browser-probe.mjs
 *
 * Never use live customer accounts or production. Does not record response
 * bodies, IDs, financial amounts, cookies, or screenshots.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const keys = [
  "LOANHUB_E2E_BASE_URL",
  "LOANHUB_E2E_STATE_A",
  "LOANHUB_E2E_COMPANY_A",
  "LOANHUB_E2E_STATE_B",
  "LOANHUB_E2E_COMPANY_B",
];
for (const key of keys) {
  assert.ok(process.env[key], `Missing ${key}; browser certification did not start`);
}
const base = new URL(process.env.LOANHUB_E2E_BASE_URL);
assert.equal(base.protocol, "https:", "Only HTTPS staging environments are accepted");
assert.match(base.hostname, /(^|[.-])(sandbox|staging|stage|test)([.-]|$)/i,
  "Refusing to test a host without an explicit staging or sandbox hostname");
assert.notEqual(process.env.LOANHUB_E2E_COMPANY_A, process.env.LOANHUB_E2E_COMPANY_B,
  "Use two distinct synthetic company IDs");
assert.notEqual(process.env.LOANHUB_E2E_STATE_A, process.env.LOANHUB_E2E_STATE_B,
  "Use two independent browser authentication states");
for (const key of ["LOANHUB_E2E_STATE_A", "LOANHUB_E2E_STATE_B"]) {
  const state = JSON.parse(readFileSync(process.env[key], "utf8"));
  assert.ok(Array.isArray(state.cookies) && Array.isArray(state.origins),
    "Invalid Playwright storage state");
}

let playwright;
try {
  playwright = await import("playwright");
} catch {
  throw new Error("Playwright is an opt-in dependency; install it outside production CI");
}
const paths = [
  "/finance-config/company/agreements",
  "/finance-config/company/charge-ledger",
  "/finance-config/company/claims",
];
const browser = await playwright.chromium.launch({ headless: true });
const results = [];
async function certify(stateFile, expectedCompany, label) {
  const context = await browser.newContext({ storageState: stateFile });
  const page = await context.newPage();
  try {
    // This probe is strictly read-only: abort any financial write before it
    // reaches even the isolated sandbox backend.
    await page.route("**/api/v1/**", route => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      if (!["GET", "HEAD", "OPTIONS"].includes(request.method()) &&
          /\/(loans|payments|finance-config|accounting|collections)(\/|$)/.test(path)) {
        return route.abort("blockedbyclient");
      }
      return route.continue();
    });
    await page.goto(new URL("/company/finance", base), {
      waitUntil: "domcontentloaded", timeout: 30000,
    });
    const refresh = page.getByRole("button", { name: "Refresh records" });
    await refresh.waitFor({ state: "visible", timeout: 30000 });
    const requests = paths.map(path => page.waitForResponse(response => {
      const request = response.request();
      const requestPath = new URL(response.url()).pathname;
      if (request.method() !== "GET" || !requestPath.endsWith(path)) return false;
      assert.equal(request.headers()["x-company-id"], expectedCompany,
        `${label}: Finance request company mismatch`);
      assert.equal(response.status(), 200,
        `${label}: Finance refresh failed with HTTP ${response.status()}`);
      assert.notEqual(response.headers()["x-loanhub-client-cache"], "HIT",
        `${label}: clicked Refresh but received a cache hit`);
      return true;
    }, {timeout: 30000}));
    await refresh.click();
    await Promise.all(requests);
    results.push({ session: label, result: "PASS", refreshedTables: paths.length });
  } finally {
    await context.close();
  }
}
try {
  await Promise.all([
    certify(process.env.LOANHUB_E2E_STATE_A, process.env.LOANHUB_E2E_COMPANY_A, "A"),
    certify(process.env.LOANHUB_E2E_STATE_B, process.env.LOANHUB_E2E_COMPANY_B, "B"),
  ]);
  assert.equal(results.length, 2, "Both independent company sessions must pass");
  console.log(JSON.stringify({probe:"finance-refresh-staging-readonly",result:"PASS",results}));
} finally {
  await browser.close();
}
