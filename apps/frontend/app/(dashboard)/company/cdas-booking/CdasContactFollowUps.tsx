"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { BellRing, RefreshCw } from "lucide-react";

import { cdasBookingApi } from "@/api/cdasBooking";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { CdasContactChannel, CdasContactOutcome, CdasFollowUpItem, CdasFollowUpWorkspace } from "@/types/cdasFollowUps";

const CHANNELS: Array<{ value: CdasContactChannel; label: string }> = [
  { value: "call", label: "Call" },
  { value: "whatsapp", label: "WhatsApp" },
  { value: "sms", label: "SMS" },
  { value: "email", label: "Email" },
  { value: "other", label: "Other" },
];

const OUTCOMES: Array<{ value: CdasContactOutcome; label: string }> = [
  { value: "no_answer", label: "No Answer" },
  { value: "interested", label: "Interested" },
  { value: "not_interested", label: "Not Interested" },
  { value: "call_back", label: "Call Back / Return Later" },
  { value: "documents_requested", label: "Documents Requested" },
  { value: "documents_received", label: "Documents Received" },
  { value: "submitted", label: "Submitted" },
  { value: "other", label: "Other" },
];

function dateTimeLabel(value?: string | null) {
  if (!value) return "Not scheduled";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("en-ZA", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function money(value?: number | null) {
  return `M ${Number(value || 0).toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function labelize(value?: string | null) {
  return String(value || "").replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

export function CdasContactFollowUpsView() {
  const [data, setData] = useState<CdasFollowUpWorkspace | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [channel, setChannel] = useState<CdasContactChannel>("call");
  const [outcome, setOutcome] = useState<CdasContactOutcome>("no_answer");
  const [notes, setNotes] = useState("");
  const [nextFollowUp, setNextFollowUp] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const workspace = await cdasBookingApi.getFollowUps();
      setData(workspace);
      setSelectedId((current) => current && workspace.items.some((item) => item.id === current) ? current : workspace.items[0]?.id || "");
    } catch {
      setError("Could not load CDAS contact follow-ups.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const visible = useMemo(() => {
    if (!data) return [];
    const needle = query.trim().toLowerCase();
    if (!needle) return data.items;
    return data.items.filter((item) => [item.client_name, item.client_reference, item.opportunity_agency_name].some((value) => String(value || "").toLowerCase().includes(needle)));
  }, [data, query]);

  const selected = useMemo<CdasFollowUpItem | null>(() => data?.items.find((item) => item.id === selectedId) || null, [data, selectedId]);

  async function assign(userId: string) {
    if (!selected) return;
    setSaving(true); setError("");
    try {
      await cdasBookingApi.assignOpportunity(selected.id, userId || null);
      await refresh();
    } catch (error: any) {
      setError(error?.response?.data?.detail || "Could not assign this opportunity.");
    } finally { setSaving(false); }
  }

  async function logContact() {
    if (!selected) return;
    setSaving(true); setError("");
    try {
      await cdasBookingApi.addContact(selected.id, {
        channel,
        outcome,
        notes: notes.trim() || undefined,
        next_follow_up_at: nextFollowUp ? new Date(nextFollowUp).toISOString() : undefined,
      });
      setNotes(""); setNextFollowUp("");
      await refresh();
    } catch (error: any) {
      setError(error?.response?.data?.detail || "Could not save the contact follow-up.");
    } finally { setSaving(false); }
  }

  if (!data && loading) return <Card><CardContent className="py-16 text-center text-sm text-muted-foreground">Loading contact follow-ups…</CardContent></Card>;
  if (!data) return <Card><CardContent className="py-10 text-center text-sm text-destructive">{error || "Contact follow-ups could not be loaded."}</CardContent></Card>;

  return <div className="space-y-5">
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3"><div className="rounded-lg border bg-muted/40 p-2"><BellRing className="h-5 w-5"/></div><div><CardTitle>CDAS Contact & Follow-Up Management</CardTitle><CardDescription>Assign opportunities to company officers and keep a permanent contact log with outcomes, notes and the next follow-up date.</CardDescription></div></div>
          <Button variant="outline" size="sm" onClick={() => void refresh()} disabled={loading}><RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}/>Refresh</Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">{error}</div>}
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Open</div><div className="text-xl font-semibold">{data.summary.open}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Unassigned</div><div className="text-xl font-semibold">{data.summary.unassigned}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Overdue follow-ups</div><div className="text-xl font-semibold">{data.summary.overdue_follow_ups}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Scheduled</div><div className="text-xl font-semibold">{data.summary.scheduled_follow_ups}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Contacted</div><div className="text-xl font-semibold">{data.summary.contacted}</div></div>
        </div>
        <Input aria-label="Search follow-ups" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search client, reference or agency" className="sm:max-w-md"/>
      </CardContent>
    </Card>

    <div className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
      <div className="space-y-3">
        {visible.map((item) => <button type="button" key={item.id} onClick={() => setSelectedId(item.id)} className={`w-full rounded-xl border p-4 text-left transition-colors ${selectedId === item.id ? "border-primary bg-primary/5" : "hover:bg-muted/30"}`}>
          <div className="flex items-start justify-between gap-2"><div><div className="font-semibold">{item.client_name || item.client_reference || "CDAS client"}</div><div className="text-xs text-muted-foreground">{item.opportunity_agency_name || "Agency not captured"}</div></div>{item.is_follow_up_overdue && <Badge variant="outline">Overdue</Badge>}</div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs"><div><span className="text-muted-foreground">Deduction</span><div>{money(item.opportunity_deduction_amount)}</div></div><div><span className="text-muted-foreground">Contacts</span><div>{item.contact_count}</div></div></div>
          <div className="mt-2 text-xs text-muted-foreground">Next: {dateTimeLabel(item.next_follow_up_at)}</div>
        </button>)}
        {!visible.length && <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">No opportunities match this view.</div>}
      </div>

      {selected && <div className="space-y-5">
        <Card>
          <CardHeader><div className="flex flex-wrap items-start justify-between gap-3"><div><CardTitle>{selected.client_name || selected.client_reference || "CDAS client"}</CardTitle><CardDescription>{selected.opportunity_agency_name || "Agency not captured"} • Pipeline: {labelize(selected.pipeline_stage)}</CardDescription></div><Badge variant="secondary">{selected.contact_count} contact{selected.contact_count === 1 ? "" : "s"}</Badge></div></CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2"><label className="text-sm font-medium" htmlFor="assigned-officer">Assigned officer</label><select id="assigned-officer" value={selected.assigned_to_user_id || ""} disabled={saving} onChange={(event) => void assign(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm"><option value="">Unassigned</option>{data.staff.map((staff) => <option key={staff.user_id} value={staff.user_id}>{staff.name} — {staff.role}</option>)}</select></div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Log contact</CardTitle><CardDescription>Record what happened and when this opportunity should be followed up again.</CardDescription></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2"><div className="space-y-2"><label className="text-sm font-medium">Channel</label><select value={channel} onChange={(event) => setChannel(event.target.value as CdasContactChannel)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">{CHANNELS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></div><div className="space-y-2"><label className="text-sm font-medium">Outcome</label><select value={outcome} onChange={(event) => setOutcome(event.target.value as CdasContactOutcome)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">{OUTCOMES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></div></div>
            <div className="space-y-2"><label className="text-sm font-medium">Notes</label><Textarea value={notes} onChange={(event) => setNotes(event.target.value)} maxLength={4000} placeholder="What did the client say? What is needed next?"/></div>
            <div className="space-y-2"><label className="text-sm font-medium" htmlFor="next-follow-up">Next follow-up</label><Input id="next-follow-up" type="datetime-local" value={nextFollowUp} onChange={(event) => setNextFollowUp(event.target.value)}/></div>
            <Button disabled={saving} onClick={() => void logContact()}>{saving ? "Saving…" : "Save contact follow-up"}</Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Contact history</CardTitle><CardDescription>Newest contact first. Existing entries are retained as the opportunity progresses.</CardDescription></CardHeader>
          <CardContent className="space-y-3">
            {!selected.contacts.length && <div className="py-8 text-center text-sm text-muted-foreground">No contact attempts recorded yet.</div>}
            {selected.contacts.map((contact) => <div key={contact.id} className="rounded-lg border p-4"><div className="flex flex-wrap items-start justify-between gap-2"><div className="font-medium">{labelize(contact.channel)} • {labelize(contact.outcome)}</div><div className="text-xs text-muted-foreground">{dateTimeLabel(contact.contacted_at)}</div></div>{contact.notes && <p className="mt-2 whitespace-pre-wrap text-sm">{contact.notes}</p>}<div className="mt-2 text-xs text-muted-foreground">Next follow-up: {dateTimeLabel(contact.next_follow_up_at)}</div></div>)}
          </CardContent>
        </Card>
      </div>}
    </div>
  </div>;
}
