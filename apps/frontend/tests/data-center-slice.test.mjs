import test from 'node:test';
import assert from 'node:assert/strict';
import reducer, {dataCenterActions, selectVerifiedDirectory} from '../dataCenterSlice.ts';
const empty=()=>({ids:[],byId:{}});
const scope=(companyId='company-A',branchId='branch-1')=>({userId:'user-1',companyId,role:'loan_officer',branchId});
const projection=(cursor=1,overrides={})=>{
  const s=overrides.scope??scope();
  const row=overrides.row??{id:'client-1',company_id:s.companyId,branch_id:s.branchId,full_name:'Example Client'};
  return {scope:s,cursor,ready:true,buckets:{clients:{ids:['client-1'],byId:{'client-1':row}},loans:empty(),payments:empty(),branches:empty(),staff:empty(),loanProducts:empty()}};
};
const initial=()=>reducer(undefined,{type:'none'});
test('authorized-looking atomic snapshot installs as one ready state',()=>{
 const s=reducer(initial(),dataCenterActions.install('session-1',projection()));
 assert.equal(s.cursor,1);
 assert.equal(selectVerifiedDirectory({dataCenter:s},'clients').records.length,1);
});
test('rejected sensitive fields never enter Redux',()=>{
 const row={id:'client-1',company_id:'company-A',branch_id:'branch-1',full_name:'Test',account_number:'1234'};
 assert.deepEqual(reducer(initial(),dataCenterActions.install('s',projection(1,{row}))),initial());
});
test('cross-company client cannot install',()=>{
 const row={id:'client-1',company_id:'company-B',branch_id:'branch-1',full_name:'Test'};
 assert.deepEqual(reducer(initial(),dataCenterActions.install('s',projection(1,{row}))),initial());
});
test('cross-branch client cannot install',()=>{
 const row={id:'client-1',company_id:'company-A',branch_id:'branch-2',full_name:'Test'};
 assert.deepEqual(reducer(initial(),dataCenterActions.install('s',projection(1,{row}))),initial());
});
test('stale and equal replay cursors cannot replace newer projection',()=>{
 const s=reducer(initial(),dataCenterActions.install('s',projection(7)));
 assert.strictEqual(reducer(s,dataCenterActions.commit('s',projection(7))),s);
 assert.strictEqual(reducer(s,dataCenterActions.commit('s',projection(6))),s);
 assert.equal(reducer(s,dataCenterActions.commit('s',projection(8))).cursor,8);
});
test('session switch must clear first and obsolete clear cannot erase current',()=>{
 const s=reducer(initial(),dataCenterActions.install('s1',projection(2)));
 assert.strictEqual(reducer(s,dataCenterActions.install('s2',projection(3))),s);
 assert.strictEqual(reducer(s,dataCenterActions.clear('s2')),s);
 const cleared=reducer(s,dataCenterActions.clear('s1'));
 assert.equal(cleared.sessionId,null);
 assert.equal(reducer(cleared,dataCenterActions.install('s2',projection(3))).sessionId,'s2');
});
test('disconnect hides data and stale session disconnect has no effect',()=>{
 const s=reducer(initial(),dataCenterActions.install('s',projection()));
 assert.strictEqual(reducer(s,dataCenterActions.disconnected('old')),s);
 const lost=reducer(s,dataCenterActions.disconnected('s'));
 assert.equal(selectVerifiedDirectory({dataCenter:lost},'clients').current,false);
 assert.equal(selectVerifiedDirectory({dataCenter:lost},'clients').records.length,0);
});
test('incomplete and malformed snapshots do not become current',()=>{
 let p=projection(); p.ready=false;
 assert.deepEqual(reducer(initial(),dataCenterActions.install('s',p)),initial());
 p=projection();delete p.buckets.staff;
 assert.deepEqual(reducer(initial(),dataCenterActions.install('s',p)),initial());
});