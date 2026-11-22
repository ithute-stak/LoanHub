/** Executable runtime validation of real Data Center replay envelopes.
 * Runs offline, with no production credentials or database writes.
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
const source = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "../lib/data-center-replay-validation.ts"), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022},
  reportDiagnostics:true,
});
assert.equal(compiled.diagnostics?.filter(d => d.category === ts.DiagnosticCategory.Error).length,0);
const exports = {};
new Script(compiled.outputText).runInContext(createContext({
  exports, module:{exports}, Set, Number, Array, Error,
}));
const {validateDataCenterReplay: validate} = exports;
const expected = {companyId:"company-A",generation:"generation-A",afterCursor:7};
function reply() {
  return {contract:"loanhub.data-center-replay.v1",
    company_id:"company-A",payloads_included:false,generation:"generation-A",
    from_cursor:7,next_cursor:8,high_watermark:8,has_more:false,
    events:[{cursor:8,resource:"clients",entity_id:"client-1",branch_id:null,action:"updated"}]};
}
test("accept exact company, generation and contiguous one-event replay",() => {
  assert.deepEqual(JSON.parse(JSON.stringify(validate(reply(),expected))),{nextCursor:8,hasMore:false});
});
test("accept empty caught-up page and honest multi-page pagination",() => {
  const empty = reply();
  empty.next_cursor = 7;empty.high_watermark=7;empty.events=[];
  assert.equal(validate(empty,expected).hasMore,false);
  const more = reply();
  more.high_watermark=9;more.has_more=true;
  assert.equal(validate(more,expected).hasMore,true);
});
test("reject other company, generation, payloads and incorrect contract",() => {
  for(const [field,value] of [
    ["company_id","company-B"],["generation","generation-B"],
    ["payloads_included",true],["contract","unexpected"],
    ["from_cursor",6],["has_more","false"],
  ]) {
    const item=reply();item[field]=value;
    assert.throws(()=>validate(item,expected),{message:/Data Center/});
  }
});
test("reject replay gaps, duplicates, rewind and forged cursor",() => {
  for(const cursor of [6,7,9,1.5,Number.MAX_SAFE_INTEGER+1]) {
    const item=reply();item.events[0].cursor=cursor;
    assert.throws(()=>validate(item,expected),{message:/Data Center/});
  }
  for(const [field,value] of [["next_cursor",9],["high_watermark",7],["has_more",true]]) {
    const item=reply();item[field]=value;
    assert.throws(()=>validate(item,expected),{message:/Data Center/});
  }
});
test("reject unexpected event kinds, actions and metadata",() => {
  for(const [field,value] of [
    ["resource","bankBalances"],["action","transfer"],["entity_id",""],
    ["branch_id",7],
  ]) {
    const item=reply();item.events[0][field]=value;
    assert.throws(()=>validate(item,expected),{message:/Data Center/});
  }
  const overflowing=reply();
  overflowing.events=Array.from({length:201},(_,i)=>({...reply().events[0],cursor:8+i}));
  assert.throws(()=>validate(overflowing,expected),{message:/Data Center/});
});
