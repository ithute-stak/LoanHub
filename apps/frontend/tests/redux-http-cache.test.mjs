/**
 * Executable regression coverage for the production Redux HTTP-cache reducer.
 * Exercises real reducer actions, not a reimplementation of its state machine.
 */
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";
import { pathToFileURL, fileURLToPath } from "node:url";
import ts from "typescript";
import axios from "axios";
import { configureStore } from "@reduxjs/toolkit";

// Keep the generated module beside frontend node_modules for bare package imports.
const source = readFileSync(new URL("../store/features/slices/httpCacheSlice.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const dir = mkdtempSync(fileURLToPath(new URL("../.http-cache-test-", import.meta.url)));
const modulePath = join(dir, "httpCacheSlice.mjs");
writeFileSync(modulePath, compiled);
const { default: reducer, cacheStored, cacheHit, cacheScopeInvalidated, cacheTagsInvalidated, cacheCleared } =
  await import(pathToFileURL(modulePath).href);

const scopeA = "user-1:company-A:loan_officer:branch-1";
const scopeB = "user-1:company-B:loan_officer:branch-2";
const initial = () => reducer(undefined, {type: "@@init"});
const entry = (scope, url = "/loans/") => ({
  key: `http:${scope}|${url}`, scope, url,
  resourceTags: ["loans", "summary"], data: [{id:"loan-1"}],
  status: 200, statusText: "OK", headers: {"content-type":"application/json"},
  storedAt: 100, expiresAt: 200, staleUntil: 300, lastAccessedAt: 100,
});

test("company and branch-scoped entries coexist without sharing keys", () => {
  let state = reducer(initial(), cacheStored(entry(scopeA)));
  state = reducer(state, cacheStored(entry(scopeB)));
  assert.equal(Object.keys(state.entries).length, 2);
  assert.notEqual(state.entries[entry(scopeA).key].scope, state.entries[entry(scopeB).key].scope);
  assert.deepEqual(state.entries[entry(scopeA).key].data, [{id:"loan-1"}]);
});

test("successful-mutation scope invalidation removes only the affected tenant", () => {
  let state = reducer(initial(), cacheStored(entry(scopeA)));
  state = reducer(state, cacheStored(entry(scopeB)));
  const oldRevision = state.revision;
  state = reducer(state, cacheScopeInvalidated({scope:scopeA}));
  assert.equal(state.entries[entry(scopeA).key], undefined);
  assert.ok(state.entries[entry(scopeB).key]);
  assert.equal(state.revision, oldRevision + 1);
});

test("tag invalidation is tenant-scoped and invalidates in-flight GET revisions", () => {
  let state = reducer(initial(), cacheStored(entry(scopeA)));
  state = reducer(state, cacheStored(entry(scopeB)));
  const revision = state.revision;
  state = reducer(state, cacheTagsInvalidated({scope:scopeA,tags:["loans"]}));
  assert.equal(state.entries[entry(scopeA).key], undefined);
  assert.ok(state.entries[entry(scopeB).key]);
  assert.equal(state.revision, revision + 1);
  // An in-flight read must be invalidated even when there are no cached entries yet.
  const emptyRevision = initial().revision;
  assert.equal(reducer(initial(), cacheScopeInvalidated({scope:scopeA})).revision, emptyRevision + 1);
});

test("logout-style cache clear erases all cached companies and bumps revision", () => {
  let state = reducer(initial(), cacheStored(entry(scopeA)));
  state = reducer(state, cacheStored(entry(scopeB)));
  const revision = state.revision;
  state = reducer(state, cacheCleared());
  assert.deepEqual(state.entries, {});
  assert.equal(state.revision, revision + 1);
});

test("cache hits do not mutate the tenant-scoping identity", () => {
  const e = entry(scopeA);
  const state = reducer(reducer(initial(), cacheStored(e)), cacheHit({key:e.key,accessedAt:110}));
  assert.equal(state.entries[e.key].scope, scopeA);
  assert.equal(state.entries[e.key].lastAccessedAt, 110);
});

// Contract coverage for mutation interception and in-flight response rejection.
// These checks complement, but do not replace, an integration test with an Axios adapter.
test("HTTP adapter invalidates successful mutations and rejects pre-invalidation read caching", () => {
  const httpSource = readFileSync(new URL("../lib/http-cache.ts", import.meta.url), "utf8");
  assert.match(httpSource, /method !== "get"/);
  assert.match(httpSource, /response\.status >= 400/);
  assert.match(httpSource, /cacheScopeInvalidated\(\{ scope \}\)/);
  assert.match(httpSource, /requestRevision === store\.getState\(\)\.httpCache\.revision/);
  assert.match(httpSource, /forceRefresh = config\.loanHubCache\?\.mode === "refresh"/);
});


// Execute the actual Axios cache adapter against a deterministic in-memory network.
// Only type-only imports are erased; the production cache implementation runs unchanged.
const adapterSource = readFileSync(new URL("../lib/http-cache.ts", import.meta.url), "utf8");
const transpiledAdapter = ts.transpileModule(adapterSource, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText.replace("@/store/features/slices/httpCacheSlice", "./httpCacheSlice.mjs");
assert.doesNotMatch(transpiledAdapter, /from ["']@\//);
writeFileSync(join(dir, "http-cache.mjs"), transpiledAdapter);
const { installReduxHttpCache } = await import(pathToFileURL(join(dir, "http-cache.mjs")).href);

function createCacheClient(userId, adapter) {
  const auth = {
    user: {
      id: userId,
      role: "loan_officer",
      memberships: [
        { company_id: "company-A", branch_id: "branch-1", role: "loan_officer", is_active: true },
        { company_id: "company-B", branch_id: "branch-2", role: "loan_officer", is_active: true },
      ],
    },
  };
  const store = configureStore({
    reducer: { httpCache: reducer, auth: (state = auth, action) =>
      action.type === "test/auth/set" ? {user:action.payload} : state },
  });
  const client = axios.create({baseURL:"https://api.loanhub.co.ls/api/v1", adapter});
  installReduxHttpCache(client, store);
  return {store, client};
}
const headersFor = (company) => ({
  "X-Company-ID": company, "X-Active-Role": "loan_officer",
});
const response = (config, data) => ({
  config, status:200, statusText:"OK",
  headers:{"Content-Type":"application/json"}, data,
});

test("real Axios adapter caches GET, invalidates on successful loan mutation and re-fetches", async () => {
  let total = 100;
  let getCount = 0;
  const {client, store} = createCacheClient("mutation-integration", async (config) => {
    if (config.method === "get") {
      getCount++;
      return response(config, {total});
    }
    if (config.method === "post") {
      total = 200;
      return response(config, {ok:true});
    }
    throw new Error("Unexpected request");
  });
  const config = {headers:headersFor("company-A")};
  assert.equal((await client.get("/loans/", config)).data.total, 100);
  assert.equal((await client.get("/loans/", config)).data.total, 100);
  assert.equal(getCount, 1, "second GET should hit Redux cache");
  await client.post("/loans/", {amount:100}, config);
  assert.equal(Object.keys(store.getState().httpCache.entries).length, 0);
  assert.equal((await client.get("/loans/", config)).data.total, 200);
  assert.equal(getCount, 2, "successful mutation must force a fresh GET");
});

test("real Axios adapter never reuses company A's GET for company B", async () => {
  const requests = [];
  const {client} = createCacheClient("tenant-integration", async (config) => {
    const company = config.headers.get("X-Company-ID");
    requests.push(company);
    return response(config, {company});
  });
  const a = {headers:headersFor("company-A")};
  const b = {headers:headersFor("company-B")};
  assert.equal((await client.get("/loans/", a)).data.company, "company-A");
  assert.equal((await client.get("/loans/", b)).data.company, "company-B");
  assert.equal((await client.get("/loans/", a)).data.company, "company-A");
  assert.deepEqual(requests, ["company-A", "company-B"]);
});

test("in-flight GET started before successful mutation cannot refill the Redux cache", async () => {
  let completeOldRead;
  let getCount = 0;
  const {client, store} = createCacheClient("inflight-integration", (config) => {
    if (config.method === "post") {
      return Promise.resolve(response(config, {ok:true}));
    }
    if (config.method === "get") {
      getCount++;
      if (getCount === 1) {
        return new Promise((resolve) => { completeOldRead = () => resolve(response(config, {total:100})); });
      }
      return Promise.resolve(response(config, {total:200}));
    }
    throw new Error("Unexpected request");
  });
  const config = {headers:headersFor("company-A")};
  const originalRead = client.get("/loans/", config);
  // Axios may schedule the adapter after the current microtask.
  for (let attempt = 0; attempt < 10 && !completeOldRead; attempt++) await Promise.resolve();
  assert.equal(typeof completeOldRead, "function");
  await client.post("/loans/", {amount:100}, config);
  completeOldRead();
  assert.equal((await originalRead).data.total, 100);
  assert.equal(Object.keys(store.getState().httpCache.entries).length, 0);
  assert.equal((await client.get("/loans/", config)).data.total, 200);
  assert.equal(getCount, 2);
});


test("successful disbursement, repayment and top-up invalidate current company's loan and payment tables", async () => {
  for (const mutationPath of [
    "/loans/loan-1/disburse",
    "/loans/repayments",
    "/origination/applications/compact-top-up",
  ]) {
    let amount = 100;
    const calls = [];
    const {client, store} = createCacheClient("financial-" + mutationPath, async (config) => {
      calls.push(config.method + " " + config.url);
      if (config.method === "post") {
        amount = 200;
        return response(config, {ok:true});
      }
      return response(config, {amount});
    });
    const a = {headers:headersFor("company-A")};
    const b = {headers:headersFor("company-B")};
    const read = (requestConfig, path) => client.get(path, requestConfig);
    assert.equal((await read(a, "/loans/")).data.amount, 100);
    assert.equal((await read(a, "/payments/")).data.amount, 100);
    assert.equal((await read(b, "/loans/")).data.amount, 100);
    assert.equal((await read(a, "/loans/")).data.amount, 100);
    assert.equal(Object.values(store.getState().httpCache.entries).filter(entry => entry.scope.includes("company-B")).length, 1, `Company B cache must exist before ${mutationPath}; entries=${JSON.stringify(Object.values(store.getState().httpCache.entries).map(({scope,url})=>({scope,url})))}; calls=${JSON.stringify(calls)}`);
    await client.post(mutationPath, {amount:100}, a);
    const keys = Object.values(store.getState().httpCache.entries);
    assert.equal(keys.filter(entry => entry.scope.includes("company-A")).length, 0);
    assert.equal(keys.filter(entry => entry.scope.includes("company-B")).length, 1);
    assert.equal((await read(a, "/loans/")).data.amount, 200);
    assert.equal((await read(a, "/payments/")).data.amount, 200);
    assert.equal(calls.filter(value => value === "get /loans/").length, 3);
  }
});

test("failed financial mutation leaves valid cached reads intact", async () => {
  let gets = 0;
  const {client, store} = createCacheClient("failed-write", async (config) => {
    if (config.method === "post") {
      throw new Error("Payment rejected");
    }
    gets++;
    return response(config, {balance:100});
  });
  const config = {headers:headersFor("company-A")};
  await client.get("/loans/", config);
  const revision = store.getState().httpCache.revision;
  await assert.rejects(client.post("/loans/repayments", {amount:30}, config), /Payment rejected/);
  assert.equal(store.getState().httpCache.revision, revision);
  assert.equal((await client.get("/loans/", config)).data.balance, 100);
  assert.equal(gets, 1);
});

test("forced manual refresh bypasses a valid cached GET without affecting other tenants", async () => {
  let version = 0;
  const {client, store} = createCacheClient("forced-refresh", async config =>
    response(config, {version:++version}));
  const a = {headers:headersFor("company-A")};
  const b = {headers:headersFor("company-B")};
  assert.equal((await client.get("/loans/", a)).data.version, 1);
  assert.equal((await client.get("/loans/", b)).data.version, 2);
  assert.equal((await client.get("/loans/", a)).data.version, 1);
  assert.equal((await client.get("/loans/", {...a, loanHubCache:{mode:"refresh"}})).data.version, 3);
  assert.equal((await client.get("/loans/", a)).data.version, 3);
  assert.equal((await client.get("/loans/", b)).data.version, 2);
  assert.equal(Object.keys(store.getState().httpCache.entries).length, 2);
});

test("company Finance manual Refresh bypasses cached agreements, ledger and claims", () => {
  const apiSource = readFileSync(new URL("../api/finance.ts", import.meta.url), "utf8");
  const pageSource = readFileSync(new URL("../app/(dashboard)/company/finance/page.tsx", import.meta.url), "utf8");
  for (const name of ["listCompanyAgreements", "listCompanyChargeLedger", "listCompanyChargeClaims"]) {
    assert.match(apiSource, new RegExp(`export async function ${name}\\(options\\?: \\{ refresh\\?: boolean \\}\\)`));
    assert.match(pageSource, new RegExp(`${name}\\(\\{ refresh \\}\\)`));
  }
  assert.equal(apiSource.split('loanHubCache: options?.refresh ? { mode: "refresh" }').length - 1, 3);
  assert.ok(pageSource.includes('onClick={() => void load(true)}><RefreshCcw'));
});

test("delayed repayment invalidates its originating branch even after active membership switches", async () => {
  let resolvePayment;
  let networkReads = 0;
  const {client, store} = createCacheClient("branch-race", config => {
    if (config.method === "post") {
      return new Promise(resolve => { resolvePayment = () => resolve(response(config, {ok:true})); });
    }
    networkReads++;
    return Promise.resolve(response(config, {version:networkReads}));
  });
  const a = {headers:headersFor("company-A")};
  const b = {headers:headersFor("company-B")};
  assert.equal((await client.get("/loans/", a)).data.version, 1);
  assert.equal((await client.get("/loans/", b)).data.version, 2);
  assert.equal((await client.get("/loans/", a)).data.version, 1);
  const oldScope = Object.values(store.getState().httpCache.entries)
    .find(entry => entry.scope.includes("company-A"))?.scope;
  assert.match(oldScope, /company-A:loan_officer:branch-1$/);
  const payment = client.post("/loans/repayments", {amount:75}, a);
  for (let attempt = 0; attempt < 20 && !resolvePayment; attempt++) await Promise.resolve();
  assert.equal(typeof resolvePayment, "function", "repayment must have started on branch-1");
  const currentUser = store.getState().auth.user;
  store.dispatch({type:"test/auth/set", payload:{
    ...currentUser,
    memberships: currentUser.memberships.map(m =>
      m.company_id === "company-A" ? {...m,branch_id:"branch-9"} : m),
  }});
  // The selected branch changed while the network payment was still in flight.
  resolvePayment();
  await payment;
  const entries = Object.values(store.getState().httpCache.entries);
  assert.equal(entries.some(entry => entry.scope === oldScope), false,
    "the original branch's cached loan figures must be invalidated");
  assert.equal(entries.some(entry => entry.scope.includes("company-B")), true,
    "a different company's cache must remain untouched");
  assert.equal((await client.get("/loans/", a)).data.version, 3,
    "the new membership must fetch its own independent financial records");
});

test("adapter returning a new response config fails closed on mutation scope loss", async () => {
  const {client, store} = createCacheClient("config-replacement", async config => {
    if (config.method === "post") {
      return response({...config}, {ok:true});
    }
    return response(config, {ok:true});
  });
  const a = {headers:headersFor("company-A")};
  const b = {headers:headersFor("company-B")};
  await client.get("/loans/", a);
  await client.get("/loans/", b);
  assert.equal(Object.keys(store.getState().httpCache.entries).length, 2);
  await client.post("/loans/repayments", {amount:50}, a);
  assert.equal(Object.keys(store.getState().httpCache.entries).length, 0,
    "unknown mutation origin must not leave finance caches stale");
});

test("manual refresh cannot be overwritten by a slower earlier read", async () => {
  let finishOld;
  let reads = 0;
  const {client,store} = createCacheClient("refresh-order", config => {
    reads++;
    if (reads === 1) {
      return new Promise(resolve => { finishOld = () => resolve(response(config, {balance:100})); });
    }
    return Promise.resolve(response(config, {balance:200}));
  });
  const config = {headers:headersFor("company-A")};
  const staleRead = client.get("/loans/", config);
  for (let attempt = 0; attempt < 20 && !finishOld; attempt++) await Promise.resolve();
  assert.equal(typeof finishOld, "function");
  const refreshed = await client.get("/loans/", {...config, loanHubCache:{mode:"refresh"}});
  assert.equal(refreshed.data.balance,200);
  finishOld();
  assert.equal((await staleRead).data.balance,100);
  assert.equal((await client.get("/loans/", config)).data.balance,200);
  assert.equal(reads,2,"an older response must not replace the refreshed cache entry");
  assert.equal(Object.values(store.getState().httpCache.entries)[0].data.balance,200);
});

test("Axios clients with separate Redux stores never share a pending GET", async () => {
  let finishFirst;
  let firstReads = 0;
  let secondReads = 0;
  const a = createCacheClient("same-user", config => {
    firstReads++;
    return new Promise(resolve => { finishFirst = () => resolve(response(config, {origin:"first"})); });
  });
  const b = createCacheClient("same-user", async config => {
    secondReads++;
    return response(config, {origin:"second"});
  });
  const config = {headers:headersFor("company-A")};
  const pending = a.client.get("/loans/", config);
  for (let attempt = 0; attempt < 20 && !finishFirst; attempt++) await Promise.resolve();
  assert.equal(typeof finishFirst,"function");
  assert.equal((await b.client.get("/loans/", config)).data.origin,"second");
  finishFirst();
  assert.equal((await pending).data.origin,"first");
  assert.equal(firstReads,1);
  assert.equal(secondReads,1);
});

test("opt-in Finance browser certification is syntactically valid and write-blocked", () => {
  const filename = fileURLToPath(new URL("./finance-refresh-staging-browser-probe.mjs", import.meta.url));
  execFileSync(process.execPath, ["--check", filename]);
  const probe = readFileSync(filename, "utf8");
  assert.match(probe, /LOANHUB_E2E_CONFIRM_SYNTHETIC/);
  assert.match(probe, /route\.abort\("blockedbyclient"\)/);
  assert.match(probe, /\["GET", "HEAD", "OPTIONS"\]\.includes\(request\.method\(\)\)/);
  assert.match(probe, /page\.waitForResponse/);
  for (const path of [
    "/finance-config/company/agreements",
    "/finance-config/company/charge-ledger",
    "/finance-config/company/claims",
  ]) assert.ok(probe.includes(path), `Missing read-only refresh check: ${path}`);
});

test("stale cache remains usable when background revalidation fails", async () => {
  let calls = 0;
  let failRevalidation;
  const {client, store} = createCacheClient("stale-error", config => {
    calls++;
    if (calls === 1) return Promise.resolve(response(config, {balance:100}));
    return new Promise((resolve, reject) => {
      failRevalidation = () => reject(new Error("Temporary network outage"));
    });
  });
  const config = {
    headers: headersFor("company-A"),
    loanHubCache: {ttlMs:0, staleWhileRevalidateMs:60000},
  };
  assert.equal((await client.get("/loans/", config)).data.balance, 100);
  const stale = await client.get("/loans/", config);
  assert.equal(stale.data.balance,100,"stale financial data must be labelled but remain readable");
  assert.equal(stale.headers.get("X-LoanHub-Client-Cache"),"STALE");
  for (let i=0; i<20 && !failRevalidation; i++) await Promise.resolve();
  assert.equal(typeof failRevalidation,"function");
  failRevalidation();
  // Flush the rejected adapter promise, cleanup finally, and its error observer.
  for (let i=0; i<20; i++) await Promise.resolve();
  assert.equal(calls,2);
  const cacheEntries=Object.values(store.getState().httpCache.entries);
  assert.equal(cacheEntries.length,1);
  assert.equal(cacheEntries[0].data.balance,100,
    "a failed background refresh must never replace cached financial data");
});

process.on("exit", () => rmSync(dir, {recursive:true,force:true}));
