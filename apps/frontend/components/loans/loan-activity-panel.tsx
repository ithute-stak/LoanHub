"use client";

import {useEffect, useState} from "react";
import {api} from "@/lib/api";
import {Button} from "@/components/ui/button";

type LoanEvent = {
  id: string;
  action: string;
  actor_name: string | null;
  actor_role: string | null;
  occurred_at: string | null;
  description: string | null;
  source: "audit" | "loan_record";
  status: string;
};
type History = {items: LoanEvent[]; count: number; history_limit: number};

export function LoanActivityPanel({loanId}: {loanId: string}) {
  const [open, setOpen] = useState(false);
  const [result, setResult] = useState<History | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => { setOpen(false); setResult(null); setError(""); }, [loanId]);

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
        <h3 className="font-semibold">Loan Activity Log</h3>
        <p className="text-xs text-muted-foreground">Recorded actions and verified approval/disbursement actors.</p>
      </div>
      <Button type="button" variant="outline" onClick={() => open ? setOpen(false) : void load()}>
        {open ? "Hide history" : "View activity"}
      </Button>
    </div>
    {open && (loading ? <p className="text-sm">Loading loan activity…</p> : error ?
      <p role="alert" className="text-sm text-destructive">{error}</p> : result?.items.length ?
      <ol className="space-y-3">
        {result.items.map((entry) => <li key={entry.id} className="border-l-2 pl-3 text-sm">
          <p className="font-medium">{entry.action.replace(/_/g, " ")}</p>
          <p>{entry.actor_name || "Actor not recorded"}{entry.actor_role ? ` · ${entry.actor_role}` : ""}</p>
          <p className="text-xs text-muted-foreground">{entry.occurred_at ? new Date(entry.occurred_at).toLocaleString() : "Time not recorded"} · {entry.source === "audit" ? "Audit event" : "Loan record"}</p>
          {entry.description ? <p className="text-xs text-muted-foreground">{entry.description}</p> : null}
        </li>)}
      </ol> :
      <p className="text-sm text-muted-foreground">No recorded processing actions were found for this loan. Historical activity cannot be reconstructed without evidence.</p>)}
  </section>;
}
