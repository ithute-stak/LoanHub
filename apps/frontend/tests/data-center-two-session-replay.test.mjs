/** Two independent in-memory browser-session models against the production replay validator.
 * This checks protocol isolation and reconnect catch-up without credentials,
 * real WebSockets, browser APIs, finance APIs or production writes.
 * Live browser certification remains a separate gate.
 */
import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {createRequire} from "node:module";
import {Script,createContext} from "node:vm";
import {fileURLToPath} from "node:url";
import {dirname,join} from "node:path";

const require=createRequire(import.meta.url);
const ts=require("typescript");
const src=readFileSync(join(dirname(fileURLToPath(import.meta.url)),"../lib/data-center-replay-validation.ts"),"utf8");
const js=ts.transpileModule(src,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022},reportDiagnostics:true});
assert.equal(js.diagnostics?.filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
const exports={};
new Script(js.outputText).runInContext(createContext({exports,module:{exports},Set,Number,Array,Error}));
const {validateDataCenterReplay}=exports;

const event=(cursor)=>({cursor,resource:"clients",entity_id:"synthetic-"+cursor,branch_id:null,action:"updated"});
const envelope=(company,generation,after,high,events)=>({
  contract:"loanhub.data-center-replay.v1",company_id:company,
  payloads_included:false,generation,from_cursor:after,
  next_cursor:events.length?events.at(-1).cursor:after,
  high_watermark:high,has_more:(events.length?events.at(-1).cursor:after)<high,
  events,
});
class BrowserSession {
  constructor(company,generation,cursor=0){
    this.company=company;this.generation=generation;this.cursor=cursor;
    this.connected=true;this.accepted=[];
  }
  disconnect(){this.connected=false;}
  reconnect(){this.connected=true;}
  consume(response){
    if(!this.connected)throw Error("Offline session cannot consume replay");
    const {nextCursor}=validateDataCenterReplay(response,{
      companyId:this.company,generation:this.generation,afterCursor:this.cursor,
    });
    this.accepted.push(...response.events.map(e=>e.cursor));
    this.cursor=nextCursor;
  }
  revoke(){this.company=null;this.generation=null;this.cursor=0;this.accepted=[];this.connected=false;}
}
test("two independent sessions catch up to identical cursor after one was disconnected",()=>{
  const a=new BrowserSession("company-A","gen-A",4);
  const b=new BrowserSession("company-A","gen-A",4);
  b.disconnect();
  a.consume(envelope("company-A","gen-A",4,6,[event(5),event(6)]));
  assert.equal(a.cursor,6);
  assert.equal(b.cursor,4);
  b.reconnect();
  b.consume(envelope("company-A","gen-A",4,6,[event(5),event(6)]));
  assert.deepEqual(b.accepted,[5,6]);assert.equal(b.cursor,a.cursor);
});
test("paginated replay after reconnect stays gap-free and does not double-apply events",()=>{
  const a=new BrowserSession("company-A","gen-A",7);
  a.consume(envelope("company-A","gen-A",7,11,[event(8),event(9)]));
  a.consume(envelope("company-A","gen-A",9,11,[event(10),event(11)]));
  assert.deepEqual(a.accepted,[8,9,10,11]);
  assert.equal(a.cursor,11);
  assert.throws(()=>a.consume(envelope("company-A","gen-A",9,11,[event(10),event(11)])),/Data Center/);
  assert.deepEqual(a.accepted,[8,9,10,11]);
});
test("other company, stale generation, missing event and malformed payload cannot advance state",()=>{
  const a=new BrowserSession("company-A","gen-A",3);
  for(const response of [
    envelope("company-B","gen-A",3,4,[event(4)]),
    envelope("company-A","old-gen",3,4,[event(4)]),
    envelope("company-A","gen-A",3,5,[event(5)]),
    {...envelope("company-A","gen-A",3,4,[event(4)]),payloads_included:true},
  ])assert.throws(()=>a.consume(response),/Data Center/);
  assert.equal(a.cursor,3);
  assert.deepEqual(a.accepted,[]);
});
test("revoke prevents queued replay and new company requires a distinct session",()=>{
  const a=new BrowserSession("company-A","gen-A",3);
  a.revoke();
  assert.equal(a.cursor,0);assert.deepEqual(a.accepted,[]);
  assert.throws(()=>a.consume(envelope("company-A","gen-A",3,4,[event(4)])),/Offline/);
  const b=new BrowserSession("company-B","gen-B",0);
  assert.throws(()=>b.consume(envelope("company-A","gen-A",0,1,[event(1)])),/Data Center/);
  b.consume(envelope("company-B","gen-B",0,1,[event(1)]));
  assert.equal(b.cursor,1);
});
