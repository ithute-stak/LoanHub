"use client";

import {useEffect, useState} from "react";
import {api} from "@/lib/api";
import {Button} from "@/components/ui/button";
import {LoanSequenceViews} from "./loan-sequence-views";
import {useTenant} from "@/provider/tenantProvider";
import {useAppSelector} from "@/store/hooks";

type FieldChange = {field: string; before_recorded: boolean; after_recorded: boolean; before: string | number | null; after: string | number | null};
type BalanceImpact = {evidence: string; before: string | null; after: string | null; delta: string | null};
type LoanEvent = {
  id: string;
  action: string;
  actor_name: string | null;
  actor_role: string | null;
  occurred_at: string | null;
  description: string | null;
  source: "audit" | "loan_record";
  status: string;
  changes?: FieldChange[];
  balance_impact?: BalanceImpact;
};
type History = {items: LoanEvent[]; count: number; history_limit: number; history_truncated?: boolean};

export function LoanActivityPanel({loanId}: {loanId: string}) {
  const {activeCompanyId, activeBranchId, activeRole} = useTenant();
  const userId = useAppSelector(state => state.auth.user?.id);
  return <LoanActivityContent key={JSON.stringify([userId, activeCompanyId, activeBranchId, activeRole, loanId])} loanId={loanId}/>;
}

function displayValue(recorded: boolean, value: string | number | null) {
  return !recorded ? "Not recorded" : value === null ? "Empty (recorded)" : String(value);
}

function LoanActivityContent({loanId}: {loanId: string}) {
  const [open, setOpen] = useState(false);
  const [result, setResult] = useState<History | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => { setOpen(false); setResult(null); setError(""); }, [loanId]);

  async function acknowledge() {
    setLoading(true);
    setError("");
    try {
      await api.post(`/loans/${encodeURIComponent(loanId)}/processing-acknowledgement`);
      await load();
    } catch {
      setError("Unable to record processing acknowledgement. Only authorized lending staff can record it.");
      setOpen(true);
    } finally { setLoading(false); }
  }

  async function load() {
    setOpen(true);
    setLoading(true);
    setError("");
    try {
      const response = await api.get<History>(`/loans/${encodeURIComponent(loanId)}/activity`);
      setResult(response.data);
    } catch {
      setError("The activity history could not be loaded. Please check your permissions or try again.");
    } finally {
      setLoading(false);
    }
  }

  return <section className="rounded-xl border p-4 space-y-3">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div>
        <h3 className="font-semibold">Loan Sequence History</h3>
        <p className="text-xs text-muted-foreground">Recorded actions, responsible staff, field changes and loan balance evidence.</p>
      </div>
      <div className="flex flex-wrap gap-2"><Button type="button" variant="outline" disabled={loading} onClick={() => void acknowledge()}>Acknowledge processing</Button>
      <Button type="button" variant="outline" onClick={() => open ? setOpen(false) : void load()}>
        {open ? "Hide history" : "View history"}
      </Button></div>
    </div>
    {open && <LoanSequenceViews loanId={loanId}/>}
    {open && (loading ? <p className="text-sm">Loading loan activity…</p> : error ?
      <p role="alert" className="text-sm text-destructive">{error}</p> : result?.items.length ?
      <div className="space-y-3">
      {result.history_truncated && <p role="status" className="text-sm text-muted-foreground">History exceeds the current display limit. Additional events are not shown.</p>}
      <ol className="space-y-3">
        {result.items.map((entry) => <li key={entry.id} className="rounded-lg border border-l-4 border-l-red-600 p-3 space-y-2 text-sm">
          <p className="font-medium">{entry.action.replace(/_/g, " ")}</p>
          <p>{entry.actor_name || "Actor not recorded"}{entry.actor_role ? ` · ${entry.actor_role}` : ""}</p>
          <p className="text-xs text-muted-foreground">{entry.occurred_at ? new Date(entry.occurred_at).toLocaleString() : "Time not recorded"} · {entry.source === "audit" ? "Audit event" : "Loan record"}</p>
          {entry.description ? <p className="text-xs text-muted-foreground">{entry.description}</p> : null}
          <p className="text-xs">Recorded status: {entry.status}</p>
          {entry.balance_impact?.evidence === "recorded_loan_balance" ? <dl className="grid grid-cols-1 gap-2 rounded-md bg-muted p-2 sm:grid-cols-3">
            {([["Previous balance", entry.balance_impact.before], ["Balance change", entry.balance_impact.delta], ["New balance", entry.balance_impact.after]] as const).map(([label, value]) => <div key={label}><dt className="text-xs text-muted-foreground">{label}</dt><dd className="font-semibold tabular-nums">LSL {value ?? "Not recorded"}</dd></div>)}
          </dl> : <p className="text-xs text-muted-foreground">{entry.balance_impact?.evidence === "not_confirmed" ? "Financial movement not confirmed" : "Historical balance impact not recorded"}</p>}
          {!!entry.changes?.length && <details className="rounded-md border p-2"><summary className="cursor-pointer font-medium">Recorded field changes ({entry.changes.length})</summary><dl className="mt-2 space-y-2">{entry.changes.map(change => <div key={change.field} className="grid gap-1 border-t pt-2 sm:grid-cols-3"><dt className="font-medium">{change.field.replace(/_/g, " ")}</dt><dd className="break-all"><span className="text-muted-foreground">Before: </span>{displayValue(change.before_recorded, change.before)}</dd><dd className="break-all"><span className="text-muted-foreground">After: </span>{displayValue(change.after_recorded, change.after)}</dd></div>)}</dl></details>}
        </li>)}
      </ol></div> :
      <p className="text-sm text-muted-foreground">No recorded processing actions were found for this loan. Historical activity cannot be reconstructed without evidence.</p>)}
  </section>;
}
