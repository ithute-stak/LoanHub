/**
 * Staging-only, read-only browser probe for two independent authenticated contexts.
 * Requires externally provisioned synthetic accounts with Playwright storage states.
 * This probe does NOT certify missed-event recovery, mutations, or capture.
 *
 * Usage:
 *   npm install --no-save playwright
 *   LOANHUB_E2E_BASE_URL=https://staging.example.test \
 *   LOANHUB_E2E_STATE_A=/secure/a.json \
 *   LOANHUB_E2E_STATE_B=/secure/b.json \
 *   LOANHUB_E2E_COMPANY_ID=synthetic-company-id \
 *   node apps/frontend/tests/data-center-staging-browser-probe.mjs
 *
 * Do not commit storage states, customer data, HAR files, or credentials.
 */
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";

const required=["LOANHUB_E2E_BASE_URL","LOANHUB_E2E_STATE_A","LOANHUB_E2E_STATE_B","LOANHUB_E2E_COMPANY_ID"];
for(const key of required) {
  if(!process.env[key]) throw new Error(`Missing ${key}; staging browser probe not started`);
}
const base=new URL(process.env.LOANHUB_E2E_BASE_URL);
assert.equal(base.protocol,"https:","Only HTTPS environments allowed");
const expectedCompany=process.env.LOANHUB_E2E_COMPANY_ID;
const states=[process.env.LOANHUB_E2E_STATE_A,process.env.LOANHUB_E2E_STATE_B];
assert.notEqual(states[0],states[1],"Use two independently provisioned storage states");
for(const filename of states){
  const state=JSON.parse(readFileSync(filename,"utf8"));
  assert.ok(Array.isArray(state.cookies) && Array.isArray(state.origins),"Invalid Playwright storageState");
}
let playwright;
try {playwright=await import("playwright");}
catch {throw new Error("Install Playwright locally; this opt-in probe is not a CI dependency");}
const browser=await playwright.chromium.launch({headless:true});
const outcomes=[];
// Both contexts run concurrently so a second session cannot hide a first-session failure.
async function checkContext(stateFile, label) {
  const context=await browser.newContext({storageState:stateFile});
  const page=await context.newPage();
  const sockets=[];
  const openedSockets=[];
  const previews=[];
  const failures=[];
  page.on("websocket",socket=>{
    try {
      if(new URL(socket.url()).pathname.endsWith("/ws")) {
        sockets.push(socket);
        // A websocket event alone does not prove a successful handshake.
        socket.on("socketerror",()=>failures.push("WebSocket connection failed"));
        openedSockets.push(socket);
      }
    } catch { /* URL ignored */ }
  });
  page.on("response",async response=>{
    const path=new URL(response.url()).pathname;
    if(!path.endsWith("/realtime/data-center/snapshot-preview")) return;
    if(response.status()!==200) {failures.push(`snapshot HTTP ${response.status()}`);return;}
    try {
      const data=await response.json();
      // Store only verification metadata. Never print or persist row payloads.
      previews.push({
        contract:data.contract,ready:data.ready,
        complete:data.complete_data_center_snapshot,
        replay:data.replay_supported,
        company:data.scope?.companyId,
        generation:typeof data.generation==="string" && !!data.generation,
        cursor:Number.isSafeInteger(data.cursor) && data.cursor>=0,
      });
    } catch {failures.push("snapshot response not valid JSON");}
  });
  try {
    await page.goto(base.toString(),{waitUntil:"domcontentloaded",timeout:30000});
    await page.waitForFunction(()=>document.readyState==="complete",null,{timeout:15000});
    // Bridge requires an authenticated realtime socket and the opt-in staging build.
    await page.waitForTimeout(7000);
    assert.equal(failures.length,0,`${label}: snapshot API failure`);
    assert.ok(openedSockets.length>0,`${label}: authenticated WebSocket not observed`);
    assert.ok(previews.length>0,`${label}: Data Center snapshot not observed; check staging flag/auth/role`);
    const first=previews.at(-1);
    assert.equal(first.contract,"loanhub.directory-preview.v1");
    assert.equal(first.company,expectedCompany,`${label}: tenant scope mismatch`);
    assert.equal(first.ready,true,`${label}: server not ready`);
    assert.equal(first.complete,true,`${label}: incomplete snapshot`);
    assert.equal(first.replay,true,`${label}: replay unsupported`);
    assert.equal(first.generation,true);
    assert.equal(first.cursor,true);
    // Reload is a safe, read-only browser lifecycle probe (not missed-event recovery).
    await page.reload({waitUntil:"domcontentloaded",timeout:30000});
    await page.waitForTimeout(7000);
    assert.ok(sockets.length>=2,`${label}: no socket after reload`);
    assert.ok(previews.length>=2,`${label}: no verified snapshot after reload`);
    assert.equal(previews.at(-1).company,expectedCompany);
    outcomes.push({session:label,result:"PASS",socketReconnectAfterReload:true,snapshotAfterReload:true});
  } finally {
    await context.close();
  }
}
try {
  await Promise.all(states.map((state,i)=>checkContext(state,i===0?"A":"B")));
  assert.equal(outcomes.length,2,"Both independent browser contexts must pass");
  console.log(JSON.stringify({probe:"data-center-staging-read-only",result:"PASS",outcomes}));
} finally {
  await browser.close();
}
