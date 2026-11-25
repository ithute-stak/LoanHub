/**
 * Executable regression coverage for the production Redux HTTP-cache reducer.
 * Exercises real reducer actions, not a reimplementation of its state machine.
 */
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { pathToFileURL, fileURLToPath } from "node:url";
import ts from "typescript";

// Keep the generated module beside frontend node_modules for bare package imports.
const root = new URL("../", import.meta.url);
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

process.on("exit", () => rmSync(dir, {recursive:true,force:true}));
