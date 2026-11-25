/**
 * Executable regression coverage for the production Redux HTTP-cache reducer.
 * Exercises real reducer actions, not a reimplementation of its state machine.
 */
import assert from "node:assert/strict";
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
    reducer: { httpCache: reducer, auth: (state = auth) => state },
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

process.on("exit", () => rmSync(dir, {recursive:true,force:true}));
