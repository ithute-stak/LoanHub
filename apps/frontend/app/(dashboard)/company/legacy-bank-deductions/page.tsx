"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Group = { id: string; code: string; name: string };
type Entry = { id: string; work_group_id: string; work_group: string; client_name: string; masked_account: string; branch_code: string; amount: string };
type Removed = { id: string; client_name: string; account_last4: string; amount: string };
const empty = { work_group_id: "", client_name: "", account_number: "", branch_code: "", amount: "" };
function explain(error: unknown) {
  if (typeof error === "object" && error && "response" in error) {
    const response = (error as {response?: {data?: {detail?: unknown}}}).response;
    return typeof response?.data?.detail === "string" ? response.data.detail : JSON.stringify(response?.data?.detail ?? "Request failed");
  }
  return error instanceof Error ? error.message : "Request failed";
}
export default function LegacyBankDeductionsPage() {
  const [groups,setGroups] = useState<Group[]>([]);
  const [records,setRecords] = useState<Entry[]>([]);
  const [form,setForm] = useState({...empty});
  const [editing,setEditing] = useState<string | null>(null);
  const [filter,setFilter] = useState("");
  const [groupFilter,setGroupFilter] = useState("");
  const [status,setStatus] = useState("");
  const [busy,setBusy] = useState(false);
  const [preview,setPreview] = useState<{valid:number;rejected:number;issues:{row:number;reason:string}[]}|null>(null);
  const [csv,setCsv] = useState<File|null>(null);
  const [bulkGroup,setBulkGroup] = useState("");
  const [removed,setRemoved] = useState<Removed[]>([]);
  const [showRemoved,setShowRemoved] = useState(false);
  const refresh = useCallback(async () => {
    const [a,b] = await Promise.all([api.get<Group[]>("/legacy-bank-deductions/work-groups"),api.get<Entry[]>("/legacy-bank-deductions/")]);
    setGroups(a.data);setRecords(b.data);
  },[]);
  useEffect(()=>{void refresh().catch(e=>setStatus(explain(e)));},[refresh]);
  const visible=useMemo(()=>records.filter(r=>(!groupFilter||r.work_group_id===groupFilter)&&
    [r.client_name,r.work_group,r.masked_account,r.branch_code].some(x=>x.toLowerCase().includes(filter.toLowerCase()))),[records,filter,groupFilter]);
  async function save() {
    if(!form.work_group_id||!form.client_name.trim()||!form.branch_code.trim()||!form.amount.trim()||(!editing&&!form.account_number.trim())){setStatus("Complete all required fields.");return;}
    setBusy(true);setStatus("");
    try {
      const payload=editing?{work_group_id:form.work_group_id,client_name:form.client_name,branch_code:form.branch_code,amount:form.amount}:form;
      if(editing) await api.patch("/legacy-bank-deductions/"+editing,payload);
      else await api.post("/legacy-bank-deductions/",payload);
      setForm({...empty});setEditing(null);await refresh();setStatus("Record saved.");
    } catch(e){setStatus(explain(e));}finally{setBusy(false);}
  }
  function startEdit(r:Entry){setEditing(r.id);setForm({work_group_id:r.work_group_id,client_name:r.client_name,account_number:"",branch_code:r.branch_code,amount:r.amount});window.scrollTo({top:0,behavior:"smooth"});}
  async function remove(r:Entry) {
    if(!window.confirm("Remove "+r.client_name+" from future bank exports? Managers can restore it."))return;
    setBusy(true);try{await api.delete("/legacy-bank-deductions/"+r.id);await refresh();setStatus("Record removed; recoverable by management.");}catch(e){setStatus(explain(e));}finally{setBusy(false);}
  }
  async function exportZip(){
    setBusy(true);setStatus("");
    try{
      const response=await api.get<Blob>("/legacy-bank-deductions/export.zip",{responseType:"blob"});
      const url=URL.createObjectURL(response.data);
      const link=document.createElement("a");link.href=url;link.download="loanhub-legacy-bank-submissions.zip";document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
      setStatus("Bank ZIP generated. Handle this confidential file securely.");
    }catch(e){setStatus(explain(e));}finally{setBusy(false);}
  }
  async function importCsv(commit:boolean){
    if(!csv||!bulkGroup){setStatus("Select CIVIL, FORCE or S/E before importing.");return;}
    setBusy(true);setStatus("");
    try{
      const data=new FormData();data.append("file",csv);
      const response=await api.post("/legacy-bank-deductions/import-csv?preview="+(!commit)+"&work_group_id="+encodeURIComponent(bulkGroup),data);
      if(commit){setCsv(null);setPreview(null);await refresh();setStatus("Imported "+response.data.saved+" records.");}
      else{setPreview(response.data);setStatus("Preview ready. Review rejected rows before confirming.");}
    }catch(e){setStatus(explain(e));}finally{setBusy(false);}
  }
  async function loadRemoved(){
    setBusy(true);try{const r=await api.get<Removed[]>("/legacy-bank-deductions/deleted");setRemoved(r.data);setShowRemoved(true);}catch(e){setStatus(explain(e));}finally{setBusy(false);}
  }
  async function restore(id:string){
    if(!window.confirm("Restore this deduction to the active bank register?"))return;
    setBusy(true);try{await api.post("/legacy-bank-deductions/"+id+"/restore",{});await loadRemoved();await refresh();setStatus("Record restored.");}catch(e){setStatus(explain(e));}finally{setBusy(false);}
  }
  const fields = <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
    <label className="text-sm">Work group<select className="mt-1 w-full rounded-md border bg-background p-2" value={form.work_group_id} onChange={e=>setForm({...form,work_group_id:e.target.value})}><option value="">Choose work group</option>{groups.map(g=><option key={g.id} value={g.id}>{g.name}</option>)}</select></label>
    <label className="text-sm">Client name<Input className="mt-1" maxLength={120} value={form.client_name} onChange={e=>setForm({...form,client_name:e.target.value})}/></label>
    <label className="text-sm">Bank account{editing?" (unchanged)":""}<Input className="mt-1" inputMode="numeric" maxLength={20} disabled={!!editing} placeholder={editing?"Protected account":"Full account number"} value={form.account_number} onChange={e=>setForm({...form,account_number:e.target.value.replace(/\D/g,"")})}/></label>
    <label className="text-sm">Branch code<Input className="mt-1" inputMode="numeric" maxLength={6} value={form.branch_code} onChange={e=>setForm({...form,branch_code:e.target.value.replace(/\D/g,"")})}/></label>
    <label className="text-sm">Deduction (LSL)<Input className="mt-1" inputMode="decimal" value={form.amount} onChange={e=>setForm({...form,amount:e.target.value})}/></label>
  </div>;
  return <main className="mx-auto w-full space-y-5 px-3 py-5 lg:px-6">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-2xl font-semibold">Legacy bank deductions</h1><p className="text-sm text-muted-foreground">Capture historical deductions, validate CSV imports and create bank submission ZIPs.</p></div><div className="flex gap-2"><Button variant="outline" disabled={busy} onClick={()=>void loadRemoved()}>Restore records</Button><Button disabled={busy||records.length===0} onClick={()=>void exportZip()}>Export bank ZIP</Button></div></div>
    {status&&<div role="status" className="rounded-lg border px-3 py-2 text-sm">{status}</div>}
    <section className="space-y-3 rounded-xl border bg-card p-4"><h2 className="font-semibold">{editing?"Edit deduction":"Capture deduction"}</h2>{fields}<div className="flex gap-2"><Button disabled={busy} onClick={()=>void save()}>{editing?"Save changes":"Save deduction"}</Button>{editing&&<Button variant="outline" onClick={()=>{setEditing(null);setForm({...empty});}}>Cancel</Button>}</div></section>
    <section className="space-y-3 rounded-xl border bg-card p-4"><h2 className="font-semibold">Bulk CSV import</h2><p className="text-sm text-muted-foreground">Choose a work group once, then upload CSV columns: Client name, Account number, Amount. Branch codes can be added later before bank ZIP export.</p><div className="flex flex-wrap items-center gap-2"><select aria-label="Bulk import work group" className="rounded-md border bg-background px-3 py-2" value={bulkGroup} onChange={e=>{setBulkGroup(e.target.value);setPreview(null);}}><option value="">Choose CIVIL, FORCE or S/E</option>{groups.map(g=><option key={g.id} value={g.id}>{g.code} — {g.name}</option>)}</select><Input type="file" accept=".csv,text/csv" className="max-w-sm" onChange={e=>{setCsv(e.target.files?.[0]??null);setPreview(null);}}/><Button variant="outline" disabled={!csv||!bulkGroup||busy} onClick={()=>void importCsv(false)}>Preview validation</Button></div>{preview&&<div className="space-y-2 text-sm"><p>{preview.valid} ready, {preview.rejected} rejected</p>{preview.issues.slice(0,20).map(i=><p key={i.row} className="text-destructive">Row {i.row}: {i.reason}</p>)}<Button disabled={busy||preview.rejected>0||preview.valid===0} onClick={()=>void importCsv(true)}>Confirm import</Button></div>}</section>
    <section className="space-y-3 rounded-xl border bg-card p-4"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-semibold">Saved deductions ({visible.length} of {records.length})</h2><div className="flex gap-2"><Input aria-label="Search records" placeholder="Search client, account or branch" value={filter} onChange={e=>setFilter(e.target.value)}/><select aria-label="Filter work group" className="rounded-md border bg-background px-2" value={groupFilter} onChange={e=>setGroupFilter(e.target.value)}><option value="">All groups</option>{groups.map(g=><option key={g.id} value={g.id}>{g.name}</option>)}</select></div></div><div className="overflow-x-auto"><table className="w-full min-w-[750px] text-left text-sm"><thead><tr className="border-b"><th className="p-2">Work group</th><th className="p-2">Client</th><th className="p-2">Account (masked)</th><th className="p-2">Branch</th><th className="p-2 text-right">Amount (LSL)</th><th className="p-2">Actions</th></tr></thead><tbody>{visible.map(r=><tr key={r.id} className="border-b"><td className="p-2">{r.work_group}</td><td className="p-2">{r.client_name}</td><td className="p-2 font-mono">{r.masked_account}</td><td className="p-2">{r.branch_code}</td><td className="p-2 text-right">{Number(r.amount).toFixed(2)}</td><td className="p-2"><div className="flex gap-2"><Button size="sm" variant="outline" disabled={busy} onClick={()=>startEdit(r)}>Edit</Button><Button size="sm" variant="destructive" disabled={busy} onClick={()=>void remove(r)}>Remove</Button></div></td></tr>)}</tbody></table>{visible.length===0&&<p className="p-4 text-center text-sm text-muted-foreground">No matching records.</p>}</div></section>
    {showRemoved&&<section className="space-y-2 rounded-xl border bg-card p-4"><h2 className="font-semibold">Recover deleted records (management only)</h2>{removed.map(r=><div key={r.id} className="flex items-center justify-between gap-2 border-b py-2 text-sm"><span>{r.client_name} · ****{r.account_last4} · M {r.amount}</span><Button size="sm" variant="outline" disabled={busy} onClick={()=>void restore(r.id)}>Restore</Button></div>)}{removed.length===0&&<p className="text-sm">No deleted records.</p>}</section>}
  </main>;
}
