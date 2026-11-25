"use client";

import {useEffect, useState} from "react";
import {api} from "@/lib/api";
import {Button} from "@/components/ui/button";
import {useReduxTableField} from "@/store/hooks/useReduxTableField";

type Profile = {folio_number: string; disbursed_at: string | null; contract_reference: string | null; current_loan_terms: Record<string, string | number | null>; contract_profile: Record<string, string | boolean | null>};
type Borrowing = {sequence: number; loan_id: string; folio_number: string; loan_reference: string; disbursed_at: string; status: string; is_top_up: boolean; current_principal: string; current_amount_paid: string; current_balance: string; is_selected_loan: boolean};
type Payment = {sequence: number; payment_id: string; amount: string; currency: string; status: string; payment_method: string; created_at: string | null; completed_at: string | null; initiated_by: string | null; verified_by: string | null; receipt_number: string | null; allocations: {installment_number: number; amount: string}[]};
type Page<T> = {items: T[]; total: number; page: number; page_size: number; scope?: string; position?: number | null};
function useSequenceData<T>(url: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(false); setData(null);
    api.get<T>(url, {signal: controller.signal}).then(response => {
      if (!controller.signal.aborted) setData(response.data);
    }).catch(() => { if (!controller.signal.aborted) setError(true); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [url]);
  return {data, error, loading};
}
function Fields({values}: {values: [string, string | number | null | undefined][]}) {
  return <dl className="grid gap-3 sm:grid-cols-2">{values.map(([label,value]) =>
    <div key={label}><dt className="text-xs text-muted-foreground">{label}</dt><dd className="break-words font-medium">{value ?? "Not recorded"}</dd></div>)}</dl>;
}
function Pager({page,total,size,setPage}: {page:number;total:number;size:number;setPage:(p:number)=>void}) {
  return <div className="flex flex-wrap items-center gap-2"><Button type="button" variant="outline" disabled={page<=1} onClick={()=>setPage(page-1)}>Previous</Button><span className="text-xs">Page {page} · {total} records</span><Button type="button" variant="outline" disabled={page*size>=total} onClick={()=>setPage(page+1)}>Next</Button></div>;
}
function ProfileView({base}: {base:string}) {
  const {data,error,loading}=useSequenceData<Profile>(base+"/sequence-profile");
  if (loading) return <p>Loading recorded profile…</p>;
  if (error || !data) return <p role="alert">Profile unavailable or access restricted.</p>;
  const p=data.contract_profile, t=data.current_loan_terms;
  return <div className="space-y-3"><h4 className="font-semibold">Stored contract profile</h4><p className="text-xs text-muted-foreground">Not independently verified as issuance-time information. Legacy contract repair may have used later profile values.</p><Fields values={[
    ["Name",String(p.name ?? "Not recorded")],["Employee number",String(p.employee_number ?? "Not recorded")],["Occupation",String(p.occupation ?? "Not recorded")],["Employer",String(p.employer ?? "Not recorded")],["Bank",String(p.bank_name ?? "Not recorded")],["Account",String(p.bank_account_masked ?? "Not recorded")],["Contact 1",String(p.contact_1 ?? "Not recorded")],["Contact 2",String(p.contact_2 ?? "Not recorded")],["Folio",data.folio_number],["Disbursement date",data.disbursed_at],["Contract reference",data.contract_reference]]}/><h4 className="font-semibold border-t pt-3">Current loan terms</h4><Fields values={[["Principal (LSL)",t.principal_amount],["Total repayable (LSL)",t.total_repayable],["Paid (LSL)",t.amount_paid],["Remaining (LSL)",t.balance],["Instalments",t.repayment_period],["Status",t.status]]}/></div>;
}
function BorrowingView({base,loanId}: {base:string;loanId:string}) {
  const [page,setPage]=useReduxTableField("loan-sequence:"+loanId,"borrowingPage",1);
  const {data,error,loading}=useSequenceData<Page<Borrowing>>(base+"/borrowing-sequence?page="+page);
  if (loading) return <p>Loading borrowing sequence…</p>;
  if (error || !data) return <p role="alert">Borrowing sequence unavailable or access restricted.</p>;
  return <div className="space-y-3"><p className="text-xs text-muted-foreground">Recorded disbursements · {data.scope} scope · Includes top-ups; not independently reconciled.</p><p className="font-semibold">Selected loan position: {data.position ?? "Not recorded"}</p>{data.items.map(row=><article key={row.loan_id} className="rounded-md border p-3 space-y-2"><h4 className="font-semibold">#{row.sequence} · {row.loan_reference}{row.is_selected_loan?" · Selected":""}{row.is_top_up?" · Top-up":""}</h4><Fields values={[["Folio",row.folio_number],["Disbursed",row.disbursed_at],["Status",row.status],["Current principal (LSL)",row.current_principal],["Current paid (LSL)",row.current_amount_paid],["Current balance (LSL)",row.current_balance]]}/></article>)}<Pager page={page} size={data.page_size} total={data.total} setPage={setPage}/></div>;
}
function PaymentView({base,loanId}: {base:string;loanId:string}) {
  const [page,setPage]=useReduxTableField("loan-sequence:"+loanId,"paymentPage",1);
  const {data,error,loading}=useSequenceData<Page<Payment>>(base+"/payment-sequence?page="+page);
  if (loading) return <p>Loading payment sequence…</p>;
  if (error || !data) return <p role="alert">Payment sequence unavailable.</p>;
  return <div className="space-y-3"><p className="text-xs text-muted-foreground">All recorded repayment attempts, including failed and reversed payments. Allocations are currently retained records, not verified historical balances.</p>{data.items.map(row=><article key={row.payment_id} className="rounded-md border p-3 space-y-2"><h4 className="font-semibold">#{row.sequence} · {row.currency} {row.amount} · {row.status}</h4><Fields values={[["Created",row.created_at],["Completed",row.completed_at],["Method",row.payment_method],["Initiated by",row.initiated_by],["Verified by",row.verified_by],["Receipt",row.receipt_number]]}/>{row.allocations.length>0&&<ul className="text-xs">{row.allocations.map(a=><li key={a.installment_number}>Instalment {a.installment_number}: {row.currency} {a.amount}</li>)}</ul>}</article>)}<Pager page={page} size={data.page_size} total={data.total} setPage={setPage}/></div>;
}
export function LoanSequenceViews({loanId}: {loanId:string}) {
  const [view,setView]=useReduxTableField<"profile"|"borrowing"|"payments">("loan-sequence:"+loanId,"view","profile");
  const base="/loans/"+encodeURIComponent(loanId);
  return <section className="rounded-md border p-3 space-y-3 text-sm"><div className="flex flex-wrap gap-2">{([["profile","Client information"],["borrowing","Borrowing sequence"],["payments","Payment sequence"]] as const).map(([id,label])=><Button key={id} type="button" variant={view===id?"default":"outline"} aria-pressed={view===id} onClick={()=>setView(id)}>{label}</Button>)}</div>{view==="profile"?<ProfileView base={base}/>:view==="borrowing"?<BorrowingView base={base} loanId={loanId}/>:<PaymentView base={base} loanId={loanId}/>}</section>;
}
