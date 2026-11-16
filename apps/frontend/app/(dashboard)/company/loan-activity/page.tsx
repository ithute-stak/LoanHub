"use client";
import {useEffect,useState} from "react";
import Link from "next/link";
import { ArrowLeft, History, RefreshCcw, Search } from "lucide-react";
import {api} from "@/lib/api";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
type Activity={id:string;loan_reference:string;action:string;actor_name:string|null;actor_role:string|null;occurred_at:string;status:string};
type Result={items:Activity[];total:number};
export default function LoanActivityPage(){
  const [reference,setReference]=useState("");
  const [actor,setActor]=useState("");
  const [action,setAction]=useState("");
  const [startDate,setStartDate]=useState("");
  const [endDate,setEndDate]=useState("");
  const [page,setPage]=useState(1);
  const [total,setTotal]=useState(0);
  const [items,setItems]=useState<Activity[]>([]);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  async function load(){
    setBusy(true);setError("");
    try{
      const params=new URLSearchParams({page:String(page),page_size:"30"});
      if(reference)params.set("loan_reference",reference);
      if(actor)params.set("actor",actor);
      if(action)params.set("action",action);
      if(startDate)params.set("start_date",startDate);
      if(endDate)params.set("end_date",endDate);
      const response=await api.get<Result>(`/loans/activity/company?${params.toString()}`);
      setItems(response.data.items);
      setTotal(response.data.total);
    }catch{setError("Could not load loan activity. Company management access is required.");}
    finally{setBusy(false);}
  }
  useEffect(()=>{void load();},[page]);
  return <main className="loanhub-page space-y-5 pb-10">
    <section className="loanhub-hero flex flex-col gap-4 rounded-3xl border border-primary/10 bg-gradient-to-br from-primary/[0.08] via-background to-background p-5 shadow-sm sm:p-7 lg:flex-row lg:items-center lg:justify-between">
      <div className="max-w-3xl">
        <p className="flex items-center gap-2 text-xs font-black uppercase tracking-[0.16em] text-primary"><History className="h-4 w-4" /> Audit trail</p>
        <h1 className="mt-2 text-2xl font-black tracking-tight sm:text-3xl">Loan Activity Log</h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">Review recorded loan actions and responsible staff. Missing historical processors are not inferred.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" asChild><Link href="/company/loans"><ArrowLeft className="mr-2 h-4 w-4" /> Back to loans</Link></Button>
        <Button variant="outline" disabled={busy} onClick={()=>void load()}><RefreshCcw className={`mr-2 h-4 w-4 ${busy ? "animate-spin" : ""}`} /> Refresh</Button>
      </div>
    </section>
    <section className="loanhub-panel space-y-4 rounded-2xl border bg-card p-4 shadow-sm sm:p-5" aria-label="Activity filters">
      <div className="flex items-center justify-between gap-3"><div><h2 className="font-bold">Find activity</h2><p className="text-xs text-muted-foreground">Filter by loan, staff member, action or date range.</p></div><Search className="h-5 w-5 text-muted-foreground" /></div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      <Input placeholder="Loan reference" aria-label="Loan reference" value={reference} onChange={e=>setReference(e.target.value)}/>
      <Input placeholder="Employee" aria-label="Employee" value={actor} onChange={e=>setActor(e.target.value)}/>
      <Input placeholder="Action" aria-label="Action" value={action} onChange={e=>setAction(e.target.value)}/>
      <Input type="date" aria-label="From date" value={startDate} onChange={e=>setStartDate(e.target.value)}/>
      <Input type="date" aria-label="To date" value={endDate} onChange={e=>setEndDate(e.target.value)}/>
      <Button disabled={busy} onClick={()=>{if(page===1)void load();else setPage(1)}}><Search className="mr-2 h-4 w-4" /> Search activity</Button>
      </div>
    </section>
    {error&&<p role="alert" className="rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">{error}</p>}
    <section className="loanhub-panel overflow-hidden rounded-2xl border bg-card shadow-sm" aria-label="Loan activity results">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b bg-muted/20 px-4 py-3 sm:px-5"><h2 className="font-bold">Recorded actions</h2><span className="text-xs font-medium text-muted-foreground" aria-live="polite">{total} activities</span></div>
      <div className="overflow-x-auto"><table className="w-full min-w-[720px] text-sm">
      <thead><tr>{["When","Loan","Action","Staff","Role","Status"].map(h=><th key={h} className="whitespace-nowrap bg-muted/10 px-4 py-3 text-left text-xs font-bold uppercase tracking-wide text-muted-foreground">{h}</th>)}</tr></thead>
      <tbody>{items.map(x=><tr key={x.id} className="border-t transition-colors hover:bg-muted/30">
        <td className="px-4 py-3">{new Date(x.occurred_at).toLocaleString()}</td>
        <td className="p-2">{x.loan_reference}</td><td className="p-2">{x.action}</td>
        <td className="p-2">{x.actor_name||"Not recorded"}</td><td className="p-2">{x.actor_role||"—"}</td><td className="p-2">{x.status}</td>
      </tr>)}</tbody></table></div>
      {!busy&&!error&&items.length===0&&<div className="border-t px-5 py-10 text-center text-sm text-muted-foreground">No recorded loan actions found for these filters.</div>}
    </section>
    <div className="flex flex-wrap items-center justify-between gap-3 text-sm"><span className="text-muted-foreground">{total} recorded activities</span><div className="flex gap-2"><Button variant="outline" disabled={busy||page<=1} onClick={()=>setPage(v=>v-1)}>Previous</Button><span className="self-center">Page {page}</span><Button variant="outline" disabled={busy||page*30>=total} onClick={()=>setPage(v=>v+1)}>Next</Button></div></div>
  </main>;
}
