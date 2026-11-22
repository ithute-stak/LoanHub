/** Executable fail-closed state tests without enabling the production bridge.
 * The TypeScript reducer is transpiled in memory; no source files are modified.
 */
import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {createRequire} from "node:module";
import {Script, createContext} from "node:vm";
import {fileURLToPath} from "node:url";
import {dirname, join} from "node:path";

const require = createRequire(import.meta.url);
const ts = require("typescript");
const here = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(here, "../store/slices/dataCenterSlice.ts"), "utf8");
const js = ts.transpileModule(source, {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022},
  reportDiagnostics: true,
});
assert.equal(js.diagnostics?.filter(item => item.category === ts.DiagnosticCategory.Error).length, 0);
const exportsObject = {};
new Script(js.outputText, {filename: "dataCenterSlice.js"}).runInContext(
  createContext({exports: exportsObject, module: {exports: exportsObject}, Object, Array, Set, Number, JSON})
);
const {default: reducer, dataCenterActions: actions, selectVerifiedDirectory: select} = exportsObject;
const KINDS = ["clients", "loans", "payments", "branches", "staff", "loanProducts"];
const scope = {userId:"user-1", companyId:"company-1", role:"company_owner", branchId:null};

function projection({company="company-1", cursor=0, badField=null, missing=null} = {}) {
  const buckets = Object.fromEntries(KINDS.filter(k => k !== missing).map(kind => {
    const id = kind + "-record";
    const row = {id, company_id:company, branch_id:null, status:"active"};
    if (badField && kind === "payments") row[badField] = "should-never-escape";
    return [kind, {ids:[id],byId:{[id]:row}}];
  }));
  return {scope:{...scope,companyId:company},cursor,ready:true,buckets};
}

test("authorized complete six-bucket snapshot installs and is selectable", () => {
  const state = reducer(undefined,actions.install("session-A",projection()));
  assert.equal(state.ready,true);
  assert.equal(state.sessionId,"session-A");
  assert.equal(state.cursor,0);
  assert.equal(select({dataCenter:state},"loans").records[0].id,"loans-record");
});

test("no installation for incomplete, cross-tenant or sensitive rows", () => {
  for(const patch of [
    {missing:"loans"},
    {badField:"account_number"},
    {company:"company-2"},
  ]) {
    const candidate = projection(patch);
    if(patch.company === "company-2") candidate.scope.companyId = "company-1";
    const state = reducer(undefined,actions.install("session-A",candidate));
    assert.equal(state.ready,false);
  }
});

test("old session cannot overwrite, clear or re-scope current session", () => {
  const ready = reducer(undefined,actions.install("session-A",projection({cursor:5})));
  assert.equal(reducer(ready,actions.install("session-B",projection({cursor:6}))),ready);
  assert.equal(reducer(ready,actions.clear("session-B")),ready);
  const other = projection({cursor:6});
  other.scope.userId = "another-user";
  assert.equal(reducer(ready,actions.install("session-A",other)),ready);
  assert.equal(reducer(ready,actions.install("session-A",projection({cursor:4}))),ready);
  assert.equal(reducer(ready,actions.commit("session-A",projection({cursor:5}))),ready);
});

test("connection loss denies selectors until fresh verified snapshot", () => {
  let state = reducer(undefined,actions.install("session-A",projection({cursor:5})));
  state = reducer(state,actions.disconnected("session-A"));
  assert.equal(state.ready,false);
  assert.equal(select({dataCenter:state},"payments").current,false);
  assert.equal(select({dataCenter:state},"payments").records.length,0);
  state = reducer(state,actions.install("session-A",projection({cursor:6})));
  assert.equal(state.ready,true);
  state = reducer(state,actions.clear("session-A"));
  assert.equal(state.ready,false);
  assert.equal(state.sessionId,null);
  assert.equal(Object.keys(state.buckets).length,0);
});

test("foreign session cannot commit and valid same-scope forward cursor can", () => {
  let state = reducer(undefined,actions.install("session-A",projection({cursor:7})));
  assert.equal(reducer(state,actions.commit("session-B",projection({cursor:8}))),state);
  state = reducer(state,actions.commit("session-A",projection({cursor:8})));
  assert.equal(state.cursor,8);
  assert.equal(state.ready,true);
});

test("reject malformed cursors and duplicate or missing bucket identifiers", () => {
  const bad = [
    projection({cursor:-1}),
    projection({cursor:Number.MAX_SAFE_INTEGER+1}),
  ];
  const duplicate = projection();
  duplicate.buckets.clients.ids.push("clients-record");
  bad.push(duplicate);
  const missing = projection();
  delete missing.buckets.clients.byId["clients-record"];
  bad.push(missing);
  for(const candidate of bad) {
    assert.equal(reducer(undefined,actions.install("session-A",candidate)).ready,false);
  }
});
