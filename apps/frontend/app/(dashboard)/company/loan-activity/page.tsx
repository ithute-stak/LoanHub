"use client";
import {useEffect,useState} from "react";
import Link from "next/link";
import {api} from "@/lib/api";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
type Activity={id:string;loan_reference:string;action:string;actor_name:string|null;actor_role:string|null;occurred_at:string;status:string};
type Result={items:Activity[];total:number};
export default function LoanActivityPage(){
  const [reference,setReference]=useState("");
  const [actor,setActor]=useState("");
  const [action,setAction]=useState("");
  const [items,setItems]=useState<Activity[]>([]);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  async function load(){
    setBusy(true);setError("");
    try{
      const params=new URLSearchParams({page:"1",page_size:"100"});
      if(reference)params.set("loan_reference",reference);
      if(actor)params.set("actor",actor);
      if(action)params.set("action",action);
      const response=await api.get<Result>(`/loans/activity/company?${params.toString()}`);
      setItems(response.data.items);
    }catch{setError("Could not load loan activity. Company management access is required.");}
    finally{setBusy(false);}
  }
  useEffect(()=>{void load();},[]);
  return <main className="space-y-4 p-4">
    <div className="flex items-center justify-between"><h1 className="text-xl font-bold">Loan Activity Log</h1><Link href="/company/loans">Back to loans</Link></div>
    <p className="text-sm text-muted-foreground">Actions recorded by LoanHub; missing historical processors are not inferred.</p>
    <div className="grid gap-2 sm:grid-cols-4">
      <Input placeholder="Loan reference" aria-label="Loan reference" value={reference} onChange={e=>setReference(e.target.value)}/>
      <Input placeholder="Employee" aria-label="Employee" value={actor} onChange={e=>setActor(e.target.value)}/>
      <Input placeholder="Action" aria-label="Action" value={action} onChange={e=>setAction(e.target.value)}/>
      <Button disabled={busy} onClick={()=>void load()}>Search activity</Button>
    </div>
    {error&&<p role="alert" className="text-destructive">{error}</p>}
    <div className="overflow-x-auto rounded-lg border"><table className="w-full text-sm">
      <thead><tr>{["When","Loan","Action","Staff","Role","Status"].map(h=><th key={h} className="p-2 text-left">{h}</th>)}</tr></thead>
      <tbody>{items.map(x=><tr key={x.id} className="border-t">
        <td className="p-2">{new Date(x.occurred_at).toLocaleString()}</td>
        <td className="p-2">{x.loan_reference}</td><td className="p-2">{x.action}</td>
        <td className="p-2">{x.actor_name||"Not recorded"}</td><td className="p-2">{x.actor_role||"—"}</td><td className="p-2">{x.status}</td>
      </tr>)}</tbody></table></div>
    {!busy&&!error&&items.length===0&&<p>No recorded loan actions found.</p>}
  </main>;
}
