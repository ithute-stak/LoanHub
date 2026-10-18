"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Maximize2, UploadCloud, Plus } from "lucide-react";

type Group = { id: string; code: string; name: string };
type Entry = { id: string; work_group_id: string; work_group: string; client_name: string; employer: string; masked_account: string; branch_code: string; amount: string; created_at?: string | null; created_by_name?: string | null; source?: string };
type CustomGroup = { id: string; name: string; branch_code: string; work_group_id: string; employers: string[] };
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
  const [customGroups,setCustomGroups] = useState<CustomGroup[]>([]);
  const [customEditor,setCustomEditor] = useState(false);
  const [customEditing,setCustomEditing] = useState<string | null>(null);
  const [customName,setCustomName] = useState("");
  const [customBranch,setCustomBranch] = useState("");
  const [customWork,setCustomWork] = useState("");
  const [customEmployers,setCustomEmployers] = useState<string[]>([]);
  const [employerOptions,setEmployerOptions] = useState<string[]>([]);
  const [addingEmployer,setAddingEmployer] = useState(false);
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
  const [expandedTable,setExpandedTable] = useState(false);
  const [captureOpen,setCaptureOpen] = useState(false);
  const [importOpen,setImportOpen] = useState(false);
  const [confirmAction,setConfirmAction] = useState<{label:string;description:string;action:()=>Promise<void>} | null>(null);
  const refresh = useCallback(async () => {
    const [a,b,c,d] = await Promise.all([api.get<Group[]>("/legacy-bank-deductions/work-groups"),api.get<Entry[]>("/legacy-bank-deductions/"),api.get<string[]>("/legacy-bank-deductions/employers"),api.get<CustomGroup[]>("/legacy-bank-deductions/custom-groups")]);
    setGroups(a.data);setRecords(b.data);setEmployerOptions(c.data);setCustomGroups(d.data);
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
      setForm({...empty});setAddingEmployer(false);setEditing(null);setCaptureOpen(false);await refresh();setStatus("Record saved.");
    } catch(e){setStatus(explain(e));}finally{setBusy(false);}
  }
  function startEdit(r:Entry){setAddingEmployer(false);setEditing(r.id);setForm({work_group_id:r.work_group_id,client_name:r.client_name,employer:r.employer,account_number:"",branch_code:r.branch_code,amount:r.amount});setExpandedTable(false);setCaptureOpen(true);}
  async function remove(r:Entry) {

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

    setBusy(true);try{await api.post("/legacy-bank-deductions/"+id+"/restore",{});await loadRemoved();await refresh();setStatus("Record restored.");}catch(e){setStatus(explain(e));}finally{setBusy(false);}
  }

  const eligibleCustomEmployers = useMemo(() => [...new Set(records.filter(r =>
    r.branch_code === customBranch && r.work_group_id === customWork
  ).map(r => r.employer).filter(Boolean))].sort(), [records,customBranch,customWork]);
  function resetCustomEditor() {
    setCustomEditing(null);setCustomName("");setCustomBranch("");setCustomWork("");
    setCustomEmployers([]);setCustomEditor(false);
  }
  function editCustomGroup(group: CustomGroup) {
    setCustomEditing(group.id);setCustomName(group.name);setCustomBranch(group.branch_code);
    setCustomWork(group.work_group_id);setCustomEmployers([...group.employers]);setCustomEditor(true);
  }
  async function saveCustomGroup() {
    if (!customName.trim() || !customBranch || !customWork || !customEmployers.length) {
      setStatus("Choose a bank, a work group and at least one employer, then enter a group name.");return;
    }
    setBusy(true);setStatus("");
    try {
      const payload = {name:customName.trim(),branch_code:customBranch,work_group_id:customWork,employers:customEmployers};
      if (customEditing) await api.put("/legacy-bank-deductions/custom-groups/" + customEditing,payload);
      else await api.post("/legacy-bank-deductions/custom-groups",payload);
      await refresh();resetCustomEditor();setStatus("Custom bank deduction group saved.");
    } catch(e) {setStatus(explain(e));} finally {setBusy(false);}
  }
  async function deleteCustomGroup(group: CustomGroup) {

    setBusy(true);setStatus("");
    try {await api.delete("/legacy-bank-deductions/custom-groups/" + group.id);await refresh();setStatus("Custom group removed. Original deductions preserved.");}
    catch(e) {setStatus(explain(e));} finally {setBusy(false);}
  }
  async function exportCustomGroup(group: CustomGroup) {
    setBusy(true);setStatus("");
    try {
      const result=await api.get<Blob>("/legacy-bank-deductions/custom-groups/" + group.id + "/export.zip",{responseType:"blob"});
      const url=URL.createObjectURL(result.data);const link=document.createElement("a");
      link.href=url;link.download="loanhub-custom-bank-group.zip";document.body.appendChild(link);
      link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
      setStatus("Custom group ZIP generated. Handle this confidential bank file securely.");
    } catch(e) {
      if(axios.isAxiosError(e) && e.response?.data instanceof Blob) {
        try {const body=JSON.parse(await e.response.data.text()) as {detail?:string|{message?:string}};setStatus(typeof body.detail==="string"?body.detail:body.detail?.message??"Custom ZIP export failed.");}
        catch {setStatus("Custom ZIP export failed. Please check the bank details.");}
      } else setStatus(explain(e));
    } finally {setBusy(false);}
  }
  const customGroupSection = <section className="space-y-4 rounded-2xl border bg-card p-5 shadow-sm">
    <div className="flex flex-wrap items-center justify-between gap-2"><div><h2 className="font-semibold">Custom bank deduction groups</h2><p className="text-sm text-muted-foreground">Bank / branch → work group → selected employers. Original deductions stay unchanged.</p></div><Button disabled={busy} onClick={()=>{resetCustomEditor();setCustomEditor(true);}}>+ Create custom group</Button></div>
    <Dialog open={customEditor} onOpenChange={open=>{if(!open&&!busy)resetCustomEditor();}}><DialogContent className="sm:max-w-4xl max-h-[92vh] overflow-y-auto"><DialogHeader><DialogTitle>{customEditing?"Edit":"Create"} custom bank group</DialogTitle><DialogDescription>Select a bank and work group, then mark employers to combine into one bank CSV.</DialogDescription></DialogHeader><div className="space-y-5">

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <label className="text-sm">Bank / clearing branch
          <select aria-label="Custom group bank" className="mt-1 w-full rounded-md border bg-background p-2" value={customBranch} onChange={e=>{setCustomBranch(e.target.value);setCustomEmployers([]);}}>
            <option value="">Choose bank / branch</option>
            {[["FNB","280061"],["Standard Lesotho Bank","060667"],["Lesotho PostBank","500100"],["Nedbank","390161"]].filter(([,code])=>records.some(r=>r.branch_code===code)).map(([name,code])=><option key={code} value={code}>{name} — {code}</option>)}
          </select>
        </label>
        <label className="text-sm">Work group
          <select aria-label="Custom group work group" className="mt-1 w-full rounded-md border bg-background p-2" value={customWork} onChange={e=>{setCustomWork(e.target.value);setCustomEmployers([]);}}>
            <option value="">Choose work group</option>{groups.map(g=><option key={g.id} value={g.id}>{g.name}</option>)}
          </select>
        </label>
        <label className="text-sm">Custom group name<Input className="mt-1" maxLength={120} placeholder="e.g. CIVIL - Selected Employers" value={customName} onChange={e=>setCustomName(e.target.value)}/></label>
      </div>
      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2"><p className="text-sm font-medium">Mark employers ({customEmployers.length} selected)</p><div className="flex gap-2"><Button size="sm" variant="outline" onClick={()=>setCustomEmployers(eligibleCustomEmployers)}>Select all</Button><Button size="sm" variant="outline" onClick={()=>setCustomEmployers([])}>Clear</Button></div></div>
        {!customBranch||!customWork?<p className="text-sm text-muted-foreground">Choose bank and work group to list matching employers.</p>:null}
        {customBranch&&customWork&&!eligibleCustomEmployers.length?<p className="text-sm text-muted-foreground">No matching employers in the loaded register.</p>:null}
        <div className="grid max-h-[35vh] gap-2 overflow-y-auto rounded-xl border bg-muted/20 p-3 sm:grid-cols-2 lg:grid-cols-3">{eligibleCustomEmployers.map(name=><label key={name} className="flex items-center gap-2 rounded-md border p-2 text-sm"><input type="checkbox" checked={customEmployers.includes(name)} onChange={e=>setCustomEmployers(old=>e.target.checked?[...old,name]:old.filter(n=>n!==name))}/>{name}</label>)}</div>
      </div>
      <div className="flex flex-wrap justify-end gap-2 border-t pt-4"><Button variant="outline" disabled={busy} onClick={resetCustomEditor}>Cancel</Button><Button disabled={busy||!customName.trim()||!customBranch||!customWork||!customEmployers.length} onClick={()=>void saveCustomGroup()}>Save custom group</Button></div>
    </div></DialogContent></Dialog>
    <div className="grid gap-2 sm:grid-cols-2">{customGroups.map(group=><div key={group.id} className="space-y-3 rounded-xl border bg-background p-4 shadow-sm"><p className="font-semibold">{group.name}</p><p className="text-sm text-muted-foreground">{group.branch_code} · {groups.find(g=>g.id===group.work_group_id)?.name??"Work group"} · {group.employers.length} employers</p><div className="flex flex-wrap gap-2"><Button size="sm" disabled={busy} onClick={()=>void exportCustomGroup(group)}>Export ZIP</Button><Button size="sm" variant="outline" disabled={busy} onClick={()=>editCustomGroup(group)}>Edit</Button><Button size="sm" variant="destructive" disabled={busy} onClick={()=>setConfirmAction({label:"Remove custom group",description:"Remove "+group.name+"? Original deductions stay unchanged.",action:()=>deleteCustomGroup(group)})}>Remove</Button></div></div>)}</div>
    {!customGroups.length&&!customEditor?<p className="text-sm text-muted-foreground">No custom groups yet. Create one to select employers for a specific bank and work group.</p>:null}
  </section>;

  const fields = <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
    <label className="text-sm">Work group<select className="mt-1 w-full rounded-md border bg-background p-2" value={form.work_group_id} onChange={e=>setForm({...form,work_group_id:e.target.value})}><option value="">Choose work group</option>{groups.map(g=><option key={g.id} value={g.id}>{g.name}</option>)}</select></label>
    <label className="text-sm">Employer
      <select className="mt-1 w-full rounded-md border bg-background p-2" aria-label="Employer" value={addingEmployer?"__new__":(employerOptions.includes(form.employer)?form.employer:"__new__")} onChange={e=>{
        if(e.target.value==="__new__"){setAddingEmployer(true);setForm({...form,employer:""});}
        else {setAddingEmployer(false);setForm({...form,employer:e.target.value});}
      }}>
        <option value="__new__">+ Add new employer</option>
        {employerOptions.map(e=><option key={e} value={e}>{e}</option>)}
      </select>
      {(addingEmployer || !employerOptions.includes(form.employer))&&<Input className="mt-2" maxLength={120} placeholder="Enter new employer name" value={form.employer} onChange={e=>setForm({...form,employer:e.target.value})}/>}
    </label>
    <label className="text-sm">Client name<Input className="mt-1" maxLength={120} value={form.client_name} onChange={e=>setForm({...form,client_name:e.target.value})}/></label>
    <label className="text-sm">Bank account{editing?" (unchanged)":""}<Input className="mt-1" inputMode="numeric" maxLength={20} disabled={!!editing} placeholder={editing?"Protected account":"Full account number"} value={form.account_number} onChange={e=>setForm({...form,account_number:e.target.value.replace(/\D/g,"")})}/></label>
    <label className="text-sm">Branch code (auto-filled from bank rules)<Input className="mt-1" inputMode="numeric" maxLength={6} value={form.branch_code} onChange={e=>setForm({...form,branch_code:e.target.value.replace(/\D/g,"")})}/></label>
    <label className="text-sm">Deduction (LSL)<Input className="mt-1" inputMode="decimal" value={form.amount} onChange={e=>setForm({...form,amount:e.target.value})}/></label>
  </div>;
  return <main className="mx-auto w-full space-y-6 px-3 py-5 lg:px-6">
    <header className="rounded-2xl border bg-card p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div><p className="text-xs font-semibold uppercase tracking-widest text-primary">Bank operations</p><h1 className="mt-1 text-2xl font-bold tracking-tight">Legacy bank deductions</h1><p className="mt-1 text-sm text-muted-foreground">Manage employer groups, capture deductions, and prepare bank submission ZIPs.</p></div>
        <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={busy} onClick={()=>{setEditing(null);setForm({...empty});setCaptureOpen(true);}}><Plus className="mr-2 h-4 w-4"/>Capture</Button><Button variant="outline" disabled={busy} onClick={()=>setImportOpen(true)}><UploadCloud className="mr-2 h-4 w-4"/>Import CSV</Button><Button disabled={busy||!records.length} onClick={()=>void exportZip()}>Export bank ZIP</Button><Button variant="outline" disabled={busy} onClick={()=>void exportZip(true)}>Legacy + current loans</Button></div>
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl bg-muted/50 p-4"><p className="text-xs text-muted-foreground">Active deductions</p><p className="mt-1 text-2xl font-semibold tabular-nums">{records.length}</p></div>
        <div className="rounded-xl bg-muted/50 p-4"><p className="text-xs text-muted-foreground">Custom groups</p><p className="mt-1 text-2xl font-semibold tabular-nums">{customGroups.length}</p></div>
        <div className="rounded-xl bg-muted/50 p-4"><p className="text-xs text-muted-foreground">Filtered amount</p><p className="mt-1 text-2xl font-semibold tabular-nums">M {totalAmount.toLocaleString("en-LS",{minimumFractionDigits:2,maximumFractionDigits:2})}</p></div>
      </div>
    </header>
    {status&&<div role="status" className="rounded-lg border px-3 py-2 text-sm">{status}</div>}
    {customGroupSection}
    <Dialog open={captureOpen} onOpenChange={open=>{if(!open&&!busy){setCaptureOpen(false);setEditing(null);setForm({...empty});}}}><DialogContent className="sm:max-w-3xl"><DialogHeader><DialogTitle>{editing?"Edit deduction":"Capture deduction"}</DialogTitle><DialogDescription>Enter bank deduction information. Existing account numbers remain protected.</DialogDescription></DialogHeader>{fields}<div className="flex justify-end gap-2"><Button variant="outline" disabled={busy} onClick={()=>{setCaptureOpen(false);setEditing(null);setForm({...empty});}}>Cancel</Button><Button disabled={busy} onClick={()=>void save()}>{editing?"Save changes":"Save deduction"}</Button></div></DialogContent></Dialog>
    <Dialog open={importOpen} onOpenChange={setImportOpen}><DialogContent className="sm:max-w-2xl"><DialogHeader><DialogTitle>Import deductions</DialogTitle><DialogDescription>Upload CSV/XLSX with client, bank account, amount, and employer columns. Review validation before importing.</DialogDescription></DialogHeader><div className="space-y-4"><select aria-label="Bulk import work group" className="w-full rounded-md border bg-background p-2" value={bulkGroup} onChange={e=>{setBulkGroup(e.target.value);setPreview(null);}}><option value="">Choose CIVIL, FORCE or S/E</option>{groups.map(g=><option key={g.id} value={g.id}>{g.code} — {g.name}</option>)}</select><Input type="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={e=>{setCsv(e.target.files?.[0]??null);setPreview(null);}}/><Button variant="outline" disabled={!csv||!bulkGroup||busy} onClick={()=>void importCsv(false)}>Preview validation</Button>{preview&&<div className="space-y-2 rounded-xl border p-3"><p>{preview.valid} ready, {preview.rejected} rejected</p>{preview.issues.slice(0,20).map(i=><p className="text-sm text-destructive" key={i.row}>Row {i.row}: {i.reason}</p>)}<Button disabled={busy||preview.rejected>0||preview.valid===0} onClick={()=>void importCsv(true)}>Confirm import</Button></div>}</div></DialogContent></Dialog>
    <section className="space-y-3 rounded-xl border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-semibold">Saved deductions ({visible.length} matching / {records.length} loaded)</h2>
        <p className="text-sm text-muted-foreground">Filtered total: M {totalAmount.toLocaleString("en-LS",{minimumFractionDigits:2,maximumFractionDigits:2})}</p>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <Input aria-label="Search records" placeholder="Client, employer, account, branch, creator" value={filter} onChange={e=>setFilter(e.target.value)}/>
        <select aria-label="Filter work group" className="rounded-md border bg-background px-2 py-2" value={groupFilter} onChange={e=>setGroupFilter(e.target.value)}><option value="">All groups</option>{groups.map(g=><option key={g.id} value={g.id}>{g.name}</option>)}</select>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2"><p className="text-xs text-muted-foreground">Showing a quick preview. Open the register for advanced filters, sorting and all records.</p><Button variant="outline" onClick={()=>setExpandedTable(true)}><Maximize2 className="mr-2 h-4 w-4"/>Expand table</Button></div>
      <div className="overflow-x-auto rounded-xl border"><table className="w-full min-w-[610px] text-left text-sm"><thead className="bg-muted/50"><tr><th className="p-3">Client</th><th className="p-3">Employer</th><th className="p-3">Work group</th><th className="p-3">Bank branch</th><th className="p-3 text-right">Amount</th></tr></thead><tbody>{visible.slice(0,5).map(r=><tr key={r.id} className="border-t"><td className="p-3 font-medium">{r.client_name}</td><td className="p-3">{r.employer}</td><td className="p-3">{r.work_group}</td><td className="p-3 font-mono">{r.branch_code}</td><td className="p-3 text-right tabular-nums">M {Number(r.amount).toFixed(2)}</td></tr>)}</tbody></table>{!visible.length&&<p className="p-6 text-center text-muted-foreground">No matching deductions.</p>}</div>
      {records.length>=1000&&<p className="text-xs text-amber-700">This screen currently loads at most 1,000 records. Server-side pagination is required for larger registers.</p>}
    </section>
    <Dialog open={expandedTable} onOpenChange={setExpandedTable}><DialogContent className="!w-[min(98vw,1600px)] !max-w-none max-h-[94vh] overflow-y-auto p-4 sm:p-6"><DialogHeader><DialogTitle>Deduction register</DialogTitle><DialogDescription>{visible.length} matching deductions · M {totalAmount.toLocaleString("en-LS",{minimumFractionDigits:2})}. Advanced filters are available here.</DialogDescription></DialogHeader><div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">        <select aria-label="Filter employer" className="rounded-md border bg-background px-2 py-2" value={employerFilter} onChange={e=>setEmployerFilter(e.target.value)}><option value="">All employers</option>{employers.map(name=><option key={name} value={name}>{name}</option>)}</select>
        <select aria-label="Filter branch" className="rounded-md border bg-background px-2 py-2" value={branchFilter} onChange={e=>setBranchFilter(e.target.value)}><option value="">All bank branches</option>{branches.map(code=><option key={code} value={code}>{code}</option>)}</select>
        <select aria-label="Filter captured by" className="rounded-md border bg-background px-2 py-2" value={creatorFilter} onChange={e=>setCreatorFilter(e.target.value)}><option value="">All capturers</option>{creators.map(name=><option key={name} value={name}>{name}</option>)}</select>
        <label className="text-xs text-muted-foreground">From date<Input aria-label="Captured after" type="date" value={dateFrom} onChange={e=>setDateFrom(e.target.value)}/></label>
        <label className="text-xs text-muted-foreground">To date<Input aria-label="Captured before" type="date" value={dateTo} onChange={e=>setDateTo(e.target.value)}/></label>
        <select aria-label="Sort records" className="rounded-md border bg-background px-2 py-2" value={sortBy} onChange={e=>setSortBy(e.target.value)}><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="name">Client A–Z</option><option value="amount_high">Amount high–low</option><option value="amount_low">Amount low–high</option></select>
        <div className="flex gap-2"><select aria-label="Rows per page" className="min-w-0 flex-1 rounded-md border bg-background px-2 py-2" value={pageSize} onChange={e=>setPageSize(Number(e.target.value))}>{[10,25,50,100].map(n=><option key={n} value={n}>{n} per page</option>)}</select><Button variant="outline" onClick={()=>{setFilter("");setGroupFilter("");setBranchFilter("");setEmployerFilter("");setCreatorFilter("");setDateFrom("");setDateTo("");setSortBy("newest");setPage(1);}}>Clear filters</Button></div>

      </div><div className="min-h-0 flex-1 overflow-y-auto">      <div className="overflow-x-auto"><table className="w-full min-w-[1040px] text-left text-sm"><thead><tr className="border-b"><th className="p-2">Work group</th><th className="p-2">Client</th><th className="p-2">Employer</th><th className="p-2">Account (masked)</th><th className="p-2">Branch</th><th className="p-2 text-right">Amount (LSL)</th><th className="p-2">Captured by</th><th className="p-2">Date</th><th className="p-2">Actions</th></tr></thead><tbody>{pageRows.map(r=><tr key={r.id} className="border-b"><td className="p-2">{r.work_group}</td><td className="p-2">{r.client_name}</td><td className="p-2">{r.employer || "Unassigned"}</td><td className="p-2 font-mono">{r.masked_account}</td><td className="p-2">{r.branch_code}</td><td className="p-2 text-right">{Number(r.amount).toFixed(2)}</td><td className="p-2">{r.created_by_name || "Not recorded"}</td><td className="p-2">{r.created_at ? new Date(r.created_at).toLocaleDateString() : "—"}</td><td className="p-2"><div className="flex gap-2"><Button size="sm" variant="outline" disabled={busy} onClick={()=>startEdit(r)}>Edit</Button><Button size="sm" variant="destructive" disabled={busy} onClick={()=>setConfirmAction({label:"Remove deduction",description:"Remove "+r.client_name+" from future exports? Management can restore it.",action:()=>remove(r)})}>Remove</Button></div></td></tr>)}</tbody></table>{visible.length===0&&<p className="p-4 text-center text-sm text-muted-foreground">No matching records.</p>}</div>
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm"><span>Page {currentPage} of {totalPages} · {visible.length ? (currentPage-1)*pageSize+1 : 0}–{Math.min(currentPage*pageSize,visible.length)} of {visible.length}</span><div className="flex gap-2"><Button size="sm" variant="outline" disabled={currentPage<=1} onClick={()=>setPage(1)}>First</Button><Button size="sm" variant="outline" disabled={currentPage<=1} onClick={()=>setPage(currentPage-1)}>Previous</Button><Button size="sm" variant="outline" disabled={currentPage>=totalPages} onClick={()=>setPage(currentPage+1)}>Next</Button><Button size="sm" variant="outline" disabled={currentPage>=totalPages} onClick={()=>setPage(totalPages)}>Last</Button></div></div>
</div></DialogContent></Dialog>

    <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={busy} onClick={()=>void loadRemoved()}>Restore records</Button><Button variant="destructive" disabled={busy||records.length===0} onClick={()=>setConfirmAction({label:"Delete all legacy records",description:"This will remove all active legacy deductions from exports. They remain recoverable and current loans are not deleted.",action:deleteAllLegacy})}>Delete all legacy records</Button></div>
    {showRemoved&&<section className="space-y-2 rounded-xl border bg-card p-4"><h2 className="font-semibold">Recover deleted records (management only)</h2>{removed.map(r=><div key={r.id} className="flex items-center justify-between gap-2 border-b py-2 text-sm"><span>{r.client_name} · ****{r.account_last4} · M {r.amount}</span><Button size="sm" variant="outline" disabled={busy} onClick={()=>setConfirmAction({label:"Restore deduction",description:"Restore this saved deduction to active bank exports?",action:()=>restore(r.id)})}>Restore</Button></div>)}{removed.length===0&&<p className="text-sm">No deleted records.</p>}</section>}
    <Dialog open={!!confirmAction} onOpenChange={open=>{if(!open)setConfirmAction(null);}}><DialogContent><DialogHeader><DialogTitle>{confirmAction?.label}</DialogTitle><DialogDescription>{confirmAction?.description}</DialogDescription></DialogHeader><div className="flex justify-end gap-2"><Button variant="outline" onClick={()=>setConfirmAction(null)}>Cancel</Button><Button variant="destructive" disabled={busy} onClick={()=>{const action=confirmAction?.action;setConfirmAction(null);if(action)void action();}}>Confirm</Button></div></DialogContent></Dialog>
  </main>;
}
