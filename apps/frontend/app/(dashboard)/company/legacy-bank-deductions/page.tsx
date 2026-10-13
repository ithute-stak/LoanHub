"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Group = { id: string; code: string; name: string };
type Entry = { id: string; work_group_id: string; work_group: string; client_name: string; employer: string; masked_account: string; branch_code: string; amount: string; created_at?: string | null; created_by_name?: string | null; source?: string };
type Removed = { id: string; client_name: string; account_last4: string; amount: string };
const empty = { work_group_id: "", client_name: "", employer: "", account_number: "", branch_code: "", amount: "" };
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
  const [branchFilter,setBranchFilter] = useState("");
  const [employerFilter,setEmployerFilter] = useState("");
  const [creatorFilter,setCreatorFilter] = useState("");
  const [dateFrom,setDateFrom] = useState("");
  const [dateTo,setDateTo] = useState("");
  const [sortBy,setSortBy] = useState("newest");
  const [page,setPage] = useState(1);
  const [pageSize,setPageSize] = useState(25);
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
  const creators = useMemo(() => [...new Set(records.map(r => r.created_by_name).filter((v): v is string => !!v))].sort(), [records]);
  const employers = useMemo(() => [...new Set(records.map(r => r.employer).filter(Boolean))].sort(), [records]);
  const branches = useMemo(() => [...new Set(records.map(r => r.branch_code).filter(Boolean))].sort(), [records]);
  const visible = useMemo(() => records.filter(r => {
    const query = filter.trim().toLowerCase();
    return (!groupFilter || r.work_group_id === groupFilter)
      && (!branchFilter || r.branch_code === branchFilter)
      && (!employerFilter || r.employer === employerFilter)
      && (!creatorFilter || r.created_by_name === creatorFilter)
      && (!dateFrom || !!r.created_at && r.created_at.slice(0, 10) >= dateFrom)
      && (!dateTo || !!r.created_at && r.created_at.slice(0, 10) <= dateTo)
      && (!query || [r.client_name, r.employer, r.work_group, r.masked_account, r.branch_code, r.created_by_name ?? ""].some(x => x.toLowerCase().includes(query)));
  }).sort((a,b) => {
    if (sortBy === "name") return a.client_name.localeCompare(b.client_name);
    if (sortBy === "amount_high") return Number(b.amount)-Number(a.amount);
    if (sortBy === "amount_low") return Number(a.amount)-Number(b.amount);
    if (sortBy === "oldest") return (a.created_at ?? "").localeCompare(b.created_at ?? "");
    return (b.created_at ?? "").localeCompare(a.created_at ?? "");
  }), [records,filter,groupFilter,branchFilter,employerFilter,creatorFilter,dateFrom,dateTo,sortBy]);
  const totalPages = Math.max(1,Math.ceil(visible.length/pageSize));
  const currentPage = Math.min(page,totalPages);
  const pageRows = useMemo(() => visible.slice((currentPage-1)*pageSize,currentPage*pageSize),[visible,currentPage,pageSize]);
  const totalAmount = useMemo(() => visible.reduce((sum,r) => sum+Number(r.amount),0),[visible]);
  useEffect(() => setPage(1),[filter,groupFilter,branchFilter,employerFilter,creatorFilter,dateFrom,dateTo,sortBy,pageSize]);
  async function save() {
    if(!form.work_group_id||!form.client_name.trim()||!form.employer.trim()||!form.amount.trim()||(!editing&&!form.account_number.trim())){setStatus("Complete all required fields.");return;}
    setBusy(true);setStatus("");
    try {
      const payload=editing?{work_group_id:form.work_group_id,client_name:form.client_name,employer:form.employer,branch_code:form.branch_code,amount:form.amount}:form;
      if(editing) await api.patch("/legacy-bank-deductions/"+editing,payload);
      else await api.post("/legacy-bank-deductions/",payload);
      setForm({...empty});setEditing(null);await refresh();setStatus("Record saved.");
    } catch(e){setStatus(explain(e));}finally{setBusy(false);}
  }
  function startEdit(r:Entry){setEditing(r.id);setForm({work_group_id:r.work_group_id,client_name:r.client_name,employer:r.employer,account_number:"",branch_code:r.branch_code,amount:r.amount});window.scrollTo({top:0,behavior:"smooth"});}
  async function remove(r:Entry) {
    if(!window.confirm("Remove "+r.client_name+" from future bank exports? Managers can restore it."))return;
    setBusy(true);try{await api.delete("/legacy-bank-deductions/"+r.id);await refresh();setStatus("Record removed; recoverable by management.");}catch(e){setStatus(explain(e));}finally{setBusy(false);}
  }
  async function exportZip(combined = false){
    setBusy(true);setStatus("");
    try{
      const response=await api.get<Blob>(combined ? "/legacy-bank-deductions/combined-export.zip" : "/legacy-bank-deductions/export.zip",{responseType:"blob"});
      const url=URL.createObjectURL(response.data);
      const link=document.createElement("a");link.href=url;link.download=combined?"loanhub-combined-bank-submissions.zip":"loanhub-legacy-bank-submissions.zip";document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
      setStatus((combined?"Combined":"Legacy")+" bank ZIP generated. Handle this confidential file securely.");
    }catch(e){
      if (axios.isAxiosError(e) && e.response?.data instanceof Blob) {
        try {
          const result = JSON.parse(await e.response.data.text()) as {detail?: string | {message?: string; excluded?: Record<string,number>}};
          const detail = result.detail;
          if (typeof detail === "object" && detail) {
            const counts = Object.entries(detail.excluded ?? {}).map(([key,value]) => key.replaceAll("_"," ") + ": " + value).join(", ");
            setStatus((detail.message ?? "Export failed") + (counts ? ". " + counts : ""));
          } else setStatus(typeof detail === "string" ? detail : "Bank ZIP export was rejected.");
        } catch {setStatus("Unable to export ZIP. Please check server response and try again.");}
      } else setStatus(explain(e));
    }finally{setBusy(false);}
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
  async function deleteAllLegacy() {
    setBusy(true);setStatus("");
    try {
      const preview = await api.get<{count:number;recoverable:boolean}>("/legacy-bank-deductions/bulk-delete/preview");
      if (!preview.data.count) {setStatus("There are no active legacy records to remove.");return;}
      const typed = window.prompt("This will remove all "+preview.data.count+" active LEGACY bank deductions for this company from capture lists and exports. Existing loans are NOT deleted. Records remain recoverable. Type DELETE LEGACY RECORDS to continue:");
      if (typed !== "DELETE LEGACY RECORDS") {setStatus("Bulk removal cancelled.");return;}
      const response = await api.post<{deleted:number}>("/legacy-bank-deductions/bulk-delete",{
        confirmation:"DELETE LEGACY RECORDS",expected_count:preview.data.count
      });
      await refresh();setStatus(response.data.deleted+" legacy records removed from the active register. Existing system loans are unchanged.");
    } catch(e) {setStatus(explain(e));} finally {setBusy(false);}
  }
  async function loadRemoved(){
    setBusy(true);try{const r=await api.get<Removed[]>("/legacy-bank-deductions/deleted");setRemoved(r.data);setShowRemoved(true);}catch(e){setStatus(explain(e));}finally{setBusy(false);}
  }
  async function restore(id:string){
    if(!window.confirm("Restore this deduction to the active bank register?"))return;
    setBusy(true);try{await api.post("/legacy-bank-deductions/"+id+"/restore",{});await loadRemoved();await refresh();setStatus("Record restored.");}catch(e){setStatus(explain(e));}finally{setBusy(false);}
  }
  const fields = <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
    <label className="text-sm">Work group<select className="mt-1 w-full rounded-md border bg-background p-2" value={form.work_group_id} onChange={e=>setForm({...form,work_group_id:e.target.value})}><option value="">Choose work group</option>{groups.map(g=><option key={g.id} value={g.id}>{g.name}</option>)}</select></label>
    <label className="text-sm">Employer<Input className="mt-1" maxLength={120} placeholder="e.g. Motheo" value={form.employer} onChange={e=>setForm({...form,employer:e.target.value})}/></label>
    <label className="text-sm">Client name<Input className="mt-1" maxLength={120} value={form.client_name} onChange={e=>setForm({...form,client_name:e.target.value})}/></label>
    <label className="text-sm">Bank account{editing?" (unchanged)":""}<Input className="mt-1" inputMode="numeric" maxLength={20} disabled={!!editing} placeholder={editing?"Protected account":"Full account number"} value={form.account_number} onChange={e=>setForm({...form,account_number:e.target.value.replace(/\D/g,"")})}/></label>
    <label className="text-sm">Branch code (auto-filled from bank rules)<Input className="mt-1" inputMode="numeric" maxLength={6} value={form.branch_code} onChange={e=>setForm({...form,branch_code:e.target.value.replace(/\D/g,"")})}/></label>
    <label className="text-sm">Deduction (LSL)<Input className="mt-1" inputMode="decimal" value={form.amount} onChange={e=>setForm({...form,amount:e.target.value})}/></label>
  </div>;
  return <main className="mx-auto w-full space-y-5 px-3 py-5 lg:px-6">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-2xl font-semibold">Legacy bank deductions</h1><p className="text-sm text-muted-foreground">Capture historical deductions, validate CSV imports and create bank submission ZIPs.</p></div><div className="flex gap-2"><Button variant="outline" disabled={busy} onClick={()=>void loadRemoved()}>Restore records</Button><Button variant="destructive" disabled={busy||records.length===0} onClick={()=>void deleteAllLegacy()}>Delete all legacy records</Button><Button disabled={busy||records.length===0} onClick={()=>void exportZip()}>Export bank ZIP</Button><Button disabled={busy} onClick={()=>void exportZip(true)}>Export legacy + current loans</Button></div></div>
    {status&&<div role="status" className="rounded-lg border px-3 py-2 text-sm">{status}</div>}
    <section className="space-y-3 rounded-xl border bg-card p-4"><h2 className="font-semibold">{editing?"Edit deduction":"Capture deduction"}</h2>{fields}<div className="flex gap-2"><Button disabled={busy} onClick={()=>void save()}>{editing?"Save changes":"Save deduction"}</Button>{editing&&<Button variant="outline" onClick={()=>{setEditing(null);setForm({...empty});}}>Cancel</Button>}</div></section>
    <section className="space-y-3 rounded-xl border bg-card p-4"><h2 className="font-semibold">Bulk CSV import</h2><p className="text-sm text-muted-foreground">Choose a work group once, then upload CSV/XLSX columns: Client name, Account number, Amount, Employer. Select the work group once; branch codes are resolved by LoanHub.</p><div className="flex flex-wrap items-center gap-2"><select aria-label="Bulk import work group" className="rounded-md border bg-background px-3 py-2" value={bulkGroup} onChange={e=>{setBulkGroup(e.target.value);setPreview(null);}}><option value="">Choose CIVIL, FORCE or S/E</option>{groups.map(g=><option key={g.id} value={g.id}>{g.code} — {g.name}</option>)}</select><Input type="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" className="max-w-sm" onChange={e=>{setCsv(e.target.files?.[0]??null);setPreview(null);}}/><Button variant="outline" disabled={!csv||!bulkGroup||busy} onClick={()=>void importCsv(false)}>Preview validation</Button></div>{preview&&<div className="space-y-2 text-sm"><p>{preview.valid} ready, {preview.rejected} rejected</p>{preview.issues.slice(0,20).map(i=><p key={i.row} className="text-destructive">Row {i.row}: {i.reason}</p>)}<Button disabled={busy||preview.rejected>0||preview.valid===0} onClick={()=>void importCsv(true)}>Confirm import</Button></div>}</section>
    <section className="space-y-3 rounded-xl border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-semibold">Saved deductions ({visible.length} matching / {records.length} loaded)</h2>
        <p className="text-sm text-muted-foreground">Filtered total: M {totalAmount.toLocaleString("en-LS",{minimumFractionDigits:2,maximumFractionDigits:2})}</p>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <Input aria-label="Search records" placeholder="Client, employer, account, branch, creator" value={filter} onChange={e=>setFilter(e.target.value)}/>
        <select aria-label="Filter work group" className="rounded-md border bg-background px-2 py-2" value={groupFilter} onChange={e=>setGroupFilter(e.target.value)}><option value="">All groups</option>{groups.map(g=><option key={g.id} value={g.id}>{g.name}</option>)}</select>
        <select aria-label="Filter employer" className="rounded-md border bg-background px-2 py-2" value={employerFilter} onChange={e=>setEmployerFilter(e.target.value)}><option value="">All employers</option>{employers.map(name=><option key={name} value={name}>{name}</option>)}</select>
        <select aria-label="Filter branch" className="rounded-md border bg-background px-2 py-2" value={branchFilter} onChange={e=>setBranchFilter(e.target.value)}><option value="">All bank branches</option>{branches.map(code=><option key={code} value={code}>{code}</option>)}</select>
        <select aria-label="Filter captured by" className="rounded-md border bg-background px-2 py-2" value={creatorFilter} onChange={e=>setCreatorFilter(e.target.value)}><option value="">All capturers</option>{creators.map(name=><option key={name} value={name}>{name}</option>)}</select>
        <label className="text-xs text-muted-foreground">From date<Input aria-label="Captured after" type="date" value={dateFrom} onChange={e=>setDateFrom(e.target.value)}/></label>
        <label className="text-xs text-muted-foreground">To date<Input aria-label="Captured before" type="date" value={dateTo} onChange={e=>setDateTo(e.target.value)}/></label>
        <select aria-label="Sort records" className="rounded-md border bg-background px-2 py-2" value={sortBy} onChange={e=>setSortBy(e.target.value)}><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="name">Client A–Z</option><option value="amount_high">Amount high–low</option><option value="amount_low">Amount low–high</option></select>
        <div className="flex gap-2"><select aria-label="Rows per page" className="min-w-0 flex-1 rounded-md border bg-background px-2 py-2" value={pageSize} onChange={e=>setPageSize(Number(e.target.value))}>{[10,25,50,100].map(n=><option key={n} value={n}>{n} per page</option>)}</select><Button variant="outline" onClick={()=>{setFilter("");setGroupFilter("");setBranchFilter("");setEmployerFilter("");setCreatorFilter("");setDateFrom("");setDateTo("");setSortBy("newest");setPage(1);}}>Clear filters</Button></div>
      </div>
      <div className="overflow-x-auto"><table className="w-full min-w-[1040px] text-left text-sm"><thead><tr className="border-b"><th className="p-2">Work group</th><th className="p-2">Client</th><th className="p-2">Employer</th><th className="p-2">Account (masked)</th><th className="p-2">Branch</th><th className="p-2 text-right">Amount (LSL)</th><th className="p-2">Captured by</th><th className="p-2">Date</th><th className="p-2">Actions</th></tr></thead><tbody>{pageRows.map(r=><tr key={r.id} className="border-b"><td className="p-2">{r.work_group}</td><td className="p-2">{r.client_name}</td><td className="p-2">{r.employer || "Unassigned"}</td><td className="p-2 font-mono">{r.masked_account}</td><td className="p-2">{r.branch_code}</td><td className="p-2 text-right">{Number(r.amount).toFixed(2)}</td><td className="p-2">{r.created_by_name || "Not recorded"}</td><td className="p-2">{r.created_at ? new Date(r.created_at).toLocaleDateString() : "—"}</td><td className="p-2"><div className="flex gap-2"><Button size="sm" variant="outline" disabled={busy} onClick={()=>startEdit(r)}>Edit</Button><Button size="sm" variant="destructive" disabled={busy} onClick={()=>void remove(r)}>Remove</Button></div></td></tr>)}</tbody></table>{visible.length===0&&<p className="p-4 text-center text-sm text-muted-foreground">No matching records.</p>}</div>
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm"><span>Page {currentPage} of {totalPages} · {visible.length ? (currentPage-1)*pageSize+1 : 0}–{Math.min(currentPage*pageSize,visible.length)} of {visible.length}</span><div className="flex gap-2"><Button size="sm" variant="outline" disabled={currentPage<=1} onClick={()=>setPage(1)}>First</Button><Button size="sm" variant="outline" disabled={currentPage<=1} onClick={()=>setPage(currentPage-1)}>Previous</Button><Button size="sm" variant="outline" disabled={currentPage>=totalPages} onClick={()=>setPage(currentPage+1)}>Next</Button><Button size="sm" variant="outline" disabled={currentPage>=totalPages} onClick={()=>setPage(totalPages)}>Last</Button></div></div>
      {records.length>=1000&&<p className="text-xs text-amber-700">This screen currently loads at most 1,000 records. Server-side pagination is required for larger registers.</p>}
    </section>
    {showRemoved&&<section className="space-y-2 rounded-xl border bg-card p-4"><h2 className="font-semibold">Recover deleted records (management only)</h2>{removed.map(r=><div key={r.id} className="flex items-center justify-between gap-2 border-b py-2 text-sm"><span>{r.client_name} · ****{r.account_last4} · M {r.amount}</span><Button size="sm" variant="outline" disabled={busy} onClick={()=>void restore(r.id)}>Restore</Button></div>)}{removed.length===0&&<p className="text-sm">No deleted records.</p>}</section>}
  </main>;
}
