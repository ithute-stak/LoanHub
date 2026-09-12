"use client";

import Link from "next/link";
import {
  ArrowLeft,
  BadgeCheck,
  Building2,
  CheckCircle2,
  Clock3,
  Handshake,
  RefreshCcw,
  RotateCcw,
  Send,
  ShieldCheck,
  SlidersHorizontal,
  UsersRound,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { lelefaCollectionsApi } from "@/api/lelefaCollections";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { formatDateTime, formatMoney, titleCase } from "@/lib/format";
import type {
  LelefaCandidateResponse,
  LelefaCollectionRules,
  LelefaCollectionSettings,
  LelefaReferral,
} from "@/types/lelefaCollections";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

const EMPTY_RULES: LelefaCollectionRules = {
  min_days_past_due: 120,
  min_overdue_amount: 0,
  min_outstanding_balance: 0,
  stages: [],
  priorities: [],
  exclude_active_promises: true,
  exclude_legal_handover: false,
  share_national_id: false,
  share_employment: false,
};

function ToggleRow({
  checked,
  onChange,
  title,
  detail,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  title: string;
  detail: string;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-xl border p-3">
      <input
        type="checkbox"
        className="mt-1 h-4 w-4 accent-primary"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span>
        <span className="block text-sm font-bold">{title}</span>
        <span className="mt-1 block text-xs leading-5 text-muted-foreground">{detail}</span>
      </span>
    </label>
  );
}

function statusVariant(value: string) {
  if (["active", "accepted", "received", "offer_received"].includes(value)) return "default" as const;
  if (["rejected", "failed_delivery"].includes(value)) return "destructive" as const;
  return "secondary" as const;
}

export default function LelefaManagedCollectionsPage() {
  const [settings, setSettings] = useState<LelefaCollectionSettings | null>(null);
  const [rules, setRules] = useState<LelefaCollectionRules>(EMPTY_RULES);
  const [enabled, setEnabled] = useState(false);
  const [candidateData, setCandidateData] = useState<LelefaCandidateResponse | null>(null);
  const [referrals, setReferrals] = useState<LelefaReferral[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [workingReferralId, setWorkingReferralId] = useState<string | null>(null);

  const load = useCallback(async (showToast = false) => {
    setLoading(true);
    try {
      const [settingsValue, candidateValue, referralValue] = await Promise.all([
        lelefaCollectionsApi.settings(),
        lelefaCollectionsApi.candidates(),
        lelefaCollectionsApi.referrals(),
      ]);
      setSettings(settingsValue);
      setEnabled(settingsValue.enabled);
      setRules(settingsValue.rules);
      setCandidateData(candidateValue);
      setReferrals(referralValue);
      setSelected((current) => {
        const allowed = new Set(candidateValue.candidates.filter((item) => !item.already_referred).map((item) => item.collection_case_id));
        return new Set([...current].filter((id) => allowed.has(id)));
      });
      if (showToast) toast.success("Lelefa managed collections refreshed.");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Lelefa managed collections could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const availableCandidates = useMemo(
    () => candidateData?.candidates.filter((item) => !item.already_referred) ?? [],
    [candidateData],
  );
  const selectedCandidates = useMemo(
    () => availableCandidates.filter((item) => selected.has(item.collection_case_id)),
    [availableCandidates, selected],
  );
  const selectedOutstanding = useMemo(
    () => selectedCandidates.reduce((sum, item) => sum + Number(item.outstanding_balance || 0), 0),
    [selectedCandidates],
  );

  async function saveSettings() {
    setSaving(true);
    try {
      const updated = await lelefaCollectionsApi.updateSettings({ enabled, rules });
      setSettings(updated);
      setEnabled(updated.enabled);
      setRules(updated.rules);
      await load();
      toast.success(updated.enabled ? "Lelefa managed collections is enabled." : "Lelefa managed collections is switched off.");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The managed-collections settings could not be saved."));
    } finally {
      setSaving(false);
    }
  }

  async function sendReferral() {
    if (selected.size === 0) {
      toast.warning("Select at least one eligible client account first.");
      return;
    }
    setSending(true);
    try {
      const created = await lelefaCollectionsApi.createReferral([...selected], note);
      setSelected(new Set());
      setNote("");
      await load();
      const delivery = created.data.delivery?.status;
      if (delivery === "sent") toast.success("The selected debt portfolio was securely referred to Lelefa.");
      else toast.warning("The referral was saved. Server-to-server delivery is waiting for bridge configuration or retry.");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The selected accounts could not be referred to Lelefa."));
    } finally {
      setSending(false);
    }
  }

  async function retryReferral(referral: LelefaReferral) {
    setWorkingReferralId(referral.id);
    try {
      await lelefaCollectionsApi.retryReferral(referral.id);
      await load();
      toast.success("Referral delivery retried.");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The referral could not be retried."));
    } finally {
      setWorkingReferralId(null);
    }
  }

  async function decideOffer(referral: LelefaReferral, decision: "accept" | "reject") {
    const verb = decision === "accept" ? "accept" : "reject";
    if (!window.confirm(`${verb[0].toUpperCase()}${verb.slice(1)} Lelefa's offer for ${referral.reference}?`)) return;
    setWorkingReferralId(referral.id);
    try {
      await lelefaCollectionsApi.decideOffer(referral.id, decision);
      await load();
      toast.success(`Lelefa offer ${decision === "accept" ? "accepted" : "rejected"}.`);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The offer decision could not be sent."));
    } finally {
      setWorkingReferralId(null);
    }
  }

  function selectAllAvailable() {
    setSelected(new Set(availableCandidates.map((item) => item.collection_case_id)));
  }

  return (
    <div className="space-y-6 p-4 sm:p-6 lg:p-8">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <Button asChild variant="ghost" size="sm" className="mb-2 -ml-2">
            <Link href="/company/collections"><ArrowLeft className="h-4 w-4" />Collections</Link>
          </Button>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-3xl font-black tracking-tight">Lelefa managed collections</h1>
            <Badge variant={enabled ? "default" : "secondary"}>{enabled ? "Enabled" : "Off"}</Badge>
            <Badge variant={settings?.bridge_configured ? "default" : "outline"}>
              {settings?.bridge_configured ? "Secure bridge ready" : "Bridge configuration required"}
            </Badge>
          </div>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground">
            Identify difficult arrears using your own rules, choose exactly which client accounts to share, send a controlled referral to Lelefa Debt Collectors, and accept a commercial offer before external collection work starts.
          </p>
        </div>
        <Button variant="outline" disabled={loading} onClick={() => void load(true)}>
          <RefreshCcw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card><CardContent className="p-5"><p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Eligible now</p><p className="mt-2 text-2xl font-black">{availableCandidates.length}</p><p className="mt-1 text-xs text-muted-foreground">After your configured rules</p></CardContent></Card>
        <Card><CardContent className="p-5"><p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Eligible balance</p><p className="mt-2 text-2xl font-black">{formatMoney(candidateData?.candidate_total_outstanding ?? 0)}</p><p className="mt-1 text-xs text-muted-foreground">Not already referred</p></CardContent></Card>
        <Card><CardContent className="p-5"><p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Selected</p><p className="mt-2 text-2xl font-black">{selected.size}</p><p className="mt-1 text-xs text-muted-foreground">{formatMoney(selectedOutstanding)} outstanding</p></CardContent></Card>
        <Card><CardContent className="p-5"><p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Referrals</p><p className="mt-2 text-2xl font-black">{referrals.length}</p><p className="mt-1 text-xs text-muted-foreground">Agreement workflow history</p></CardContent></Card>
      </div>

      <Card className="border-primary/20 bg-primary/[.025]">
        <CardContent className="grid gap-4 p-5 lg:grid-cols-[auto_1fr] lg:items-center">
          <div className="rounded-2xl bg-primary/10 p-3 text-primary"><ShieldCheck className="h-6 w-6" /></div>
          <div>
            <p className="font-black">Controlled sharing by design</p>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              Enabling the service does not automatically send every borrower. LoanHub shows rule-matched candidates and requires explicit selection. Bank account numbers and documents are never included automatically; identity and employment fields remain optional.
            </p>
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="candidates" className="space-y-5">
        <TabsList className="h-auto flex-wrap">
          <TabsTrigger value="candidates">Select clients</TabsTrigger>
          <TabsTrigger value="rules">Switch & rules</TabsTrigger>
          <TabsTrigger value="referrals">Requests & offers</TabsTrigger>
        </TabsList>

        <TabsContent value="candidates" className="space-y-4">
          {!enabled ? (
            <Card className="border-dashed"><CardContent className="p-6 text-sm text-muted-foreground">Switch the service on under <strong>Switch & rules</strong> before a portfolio can be sent.</CardContent></Card>
          ) : null}
          <Card>
            <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3 space-y-0">
              <div><CardTitle className="flex items-center gap-2"><UsersRound className="h-5 w-5 text-primary" />Rule-matched clients</CardTitle><CardDescription className="mt-1">Default qualification is 120+ days past due. Refine the rule whenever your collection policy changes.</CardDescription></div>
              <div className="flex gap-2"><Button variant="outline" size="sm" onClick={selectAllAvailable}>Select all eligible</Button><Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>Clear</Button></div>
            </CardHeader>
            <CardContent className="space-y-3">
              {candidateData?.candidates.map((item) => {
                const disabled = item.already_referred;
                return (
                  <label key={item.collection_case_id} className={`grid gap-3 rounded-2xl border p-4 transition md:grid-cols-[auto_minmax(0,1.3fr)_repeat(3,minmax(110px,.6fr))] md:items-center ${disabled ? "opacity-60" : "cursor-pointer hover:border-primary/40"}`}>
                    <input type="checkbox" className="h-4 w-4 accent-primary" disabled={disabled} checked={selected.has(item.collection_case_id)} onChange={(event) => setSelected((current) => { const next = new Set(current); if (event.target.checked) next.add(item.collection_case_id); else next.delete(item.collection_case_id); return next; })} />
                    <div className="min-w-0"><p className="font-black">{item.borrower_name}</p><p className="mt-1 text-xs text-muted-foreground">{item.loan_reference} · {item.phone || "No phone"}</p><div className="mt-2 flex flex-wrap gap-1"><Badge variant="outline">{titleCase(item.stage)}</Badge><Badge variant="outline">{titleCase(item.priority)}</Badge>{disabled ? <Badge variant="secondary">Already referred</Badge> : null}</div></div>
                    <div><p className="text-xs font-bold text-muted-foreground">Past due</p><p className="mt-1 font-black">{item.days_past_due} days</p></div>
                    <div><p className="text-xs font-bold text-muted-foreground">Overdue</p><p className="mt-1 font-black">{formatMoney(item.overdue_amount)}</p></div>
                    <div><p className="text-xs font-bold text-muted-foreground">Outstanding</p><p className="mt-1 font-black">{formatMoney(item.outstanding_balance)}</p></div>
                  </label>
                );
              })}
              {!loading && (candidateData?.candidates.length ?? 0) === 0 ? <div className="rounded-2xl border border-dashed p-10 text-center text-sm text-muted-foreground">No collection cases currently match the configured Lelefa rules.</div> : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><Send className="h-5 w-5 text-primary" />Create controlled referral</CardTitle><CardDescription>Only the selected snapshots are included. Lelefa must send an offer and your company must accept it before the referred accounts become active at Lelefa.</CardDescription></CardHeader>
            <CardContent className="space-y-4">
              <div><Label htmlFor="referral-note">Referral note (optional)</Label><Textarea id="referral-note" className="mt-2" rows={3} value={note} onChange={(event) => setNote(event.target.value)} placeholder="Reason for handover, preferred treatment, constraints, or commercial context…" /></div>
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-muted/40 p-4"><div><p className="font-black">{selected.size} selected account{selected.size === 1 ? "" : "s"}</p><p className="text-sm text-muted-foreground">{formatMoney(selectedOutstanding)} total outstanding balance</p></div><Button disabled={!enabled || selected.size === 0 || sending} onClick={() => void sendReferral()}><Send className="h-4 w-4" />{sending ? "Sending…" : "Send request to Lelefa"}</Button></div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="rules" className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><SlidersHorizontal className="h-5 w-5 text-primary" />Managed collections policy</CardTitle><CardDescription>The switch enables the workflow. These rules only identify candidates; they never auto-send borrowers.</CardDescription></CardHeader>
            <CardContent className="space-y-5">
              <ToggleRow checked={enabled} onChange={setEnabled} title="Allow Lelefa Debt Collectors referrals" detail="When off, LoanHub will not permit new external collection referrals for this company." />
              <div className="grid gap-4 md:grid-cols-3">
                <div><Label>Minimum days past due</Label><Input className="mt-2" type="number" min={1} value={rules.min_days_past_due} onChange={(event) => setRules((value) => ({ ...value, min_days_past_due: Number(event.target.value || 1) }))} /></div>
                <div><Label>Minimum overdue amount</Label><Input className="mt-2" type="number" min={0} step="0.01" value={rules.min_overdue_amount} onChange={(event) => setRules((value) => ({ ...value, min_overdue_amount: Number(event.target.value || 0) }))} /></div>
                <div><Label>Minimum outstanding balance</Label><Input className="mt-2" type="number" min={0} step="0.01" value={rules.min_outstanding_balance} onChange={(event) => setRules((value) => ({ ...value, min_outstanding_balance: Number(event.target.value || 0) }))} /></div>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div><Label>Allowed collection stages</Label><Input className="mt-2" value={rules.stages.join(", ")} onChange={(event) => setRules((value) => ({ ...value, stages: event.target.value.split(",").map((item) => item.trim()).filter(Boolean) }))} placeholder="Leave blank for any stage, or legal, late_arrears…" /></div>
                <div><Label>Allowed priorities</Label><Input className="mt-2" value={rules.priorities.join(", ")} onChange={(event) => setRules((value) => ({ ...value, priorities: event.target.value.split(",").map((item) => item.trim()).filter(Boolean) }))} placeholder="Leave blank for any priority, or high, critical…" /></div>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <ToggleRow checked={rules.exclude_active_promises} onChange={(value) => setRules((current) => ({ ...current, exclude_active_promises: value }))} title="Exclude active promises to pay" detail="Keep clients with a current promise inside your internal collection process." />
                <ToggleRow checked={rules.exclude_legal_handover} onChange={(value) => setRules((current) => ({ ...current, exclude_legal_handover: value }))} title="Exclude cases already handed to legal" detail="Avoid duplicating an existing legal handover unless you intentionally allow it." />
                <ToggleRow checked={rules.share_national_id} onChange={(value) => setRules((current) => ({ ...current, share_national_id: value }))} title="Include identity number in selected referrals" detail="Off by default. Enable only when your collection mandate requires the additional identifier." />
                <ToggleRow checked={rules.share_employment} onChange={(value) => setRules((current) => ({ ...current, share_employment: value }))} title="Include employment fields" detail="Off by default. Shares employer, role and employment status only for explicitly selected accounts." />
              </div>
              <div className="flex justify-end"><Button disabled={saving} onClick={() => void saveSettings()}><BadgeCheck className="h-4 w-4" />{saving ? "Saving…" : "Save policy"}</Button></div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="referrals" className="space-y-4">
          {referrals.map((referral) => {
            const offer = referral.data.offer;
            const delivery = referral.data.delivery;
            const pending = workingReferralId === referral.id;
            return (
              <Card key={referral.id}>
                <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3 space-y-0">
                  <div><div className="flex flex-wrap items-center gap-2"><CardTitle>{referral.reference}</CardTitle><Badge variant={statusVariant(referral.status)}>{titleCase(referral.status)}</Badge></div><CardDescription className="mt-1">Submitted {formatDateTime(referral.created_at)} · {(referral.data.items ?? []).length} accounts · {formatMoney(referral.amount)}</CardDescription></div>
                  {delivery?.status && delivery.status !== "sent" && !["active", "accepted", "rejected"].includes(referral.status) ? <Button size="sm" variant="outline" disabled={pending} onClick={() => void retryReferral(referral)}><RotateCcw className="h-4 w-4" />Retry delivery</Button> : null}
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded-xl bg-muted/40 p-3"><p className="text-xs font-bold text-muted-foreground">Delivery</p><p className="mt-1 font-bold">{titleCase(delivery?.status || "queued")}</p>{delivery?.message ? <p className="mt-1 text-xs text-destructive">{delivery.message}</p> : null}</div>
                    <div className="rounded-xl bg-muted/40 p-3"><p className="text-xs font-bold text-muted-foreground">Lelefa request</p><p className="mt-1 font-bold">{referral.data.remote_referral_id ? "Received by Lelefa" : "Awaiting receipt"}</p></div>
                    <div className="rounded-xl bg-muted/40 p-3"><p className="text-xs font-bold text-muted-foreground">Agreement</p><p className="mt-1 font-bold">{offer ? "Offer available" : "Awaiting Lelefa offer"}</p></div>
                  </div>
                  {offer ? (
                    <div className="rounded-2xl border border-primary/20 bg-primary/[.025] p-4">
                      <div className="flex items-center gap-2"><Handshake className="h-5 w-5 text-primary" /><p className="font-black">Lelefa commercial offer</p></div>
                      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                        <div><p className="text-xs text-muted-foreground">Commission</p><p className="font-black">{offer.commission_percent}%</p></div>
                        <div><p className="text-xs text-muted-foreground">Onboarding</p><p className="font-black">{formatMoney(offer.onboarding_fee)}</p></div>
                        <div><p className="text-xs text-muted-foreground">Legal action fee</p><p className="font-black">{formatMoney(offer.legal_action_fee)}</p></div>
                        <div><p className="text-xs text-muted-foreground">Settlement authority</p><p className="font-black">Up to {offer.max_settlement_discount_percent}%</p></div>
                        <div><p className="text-xs text-muted-foreground">Term</p><p className="font-black">{offer.engagement_term_months} months</p></div>
                      </div>
                      {offer.notes ? <p className="mt-4 whitespace-pre-wrap text-sm text-muted-foreground">{offer.notes}</p> : null}
                      {referral.data.decision ? <div className="mt-4 rounded-xl bg-muted/50 p-3 text-sm"><strong>Decision:</strong> {titleCase(referral.data.decision.decision)} · {titleCase(referral.data.decision.status)}</div> : null}
                      {!referral.data.decision && referral.status === "offer_received" ? <div className="mt-4 flex flex-wrap gap-2"><Button disabled={pending} onClick={() => void decideOffer(referral, "accept")}><CheckCircle2 className="h-4 w-4" />Accept offer</Button><Button disabled={pending} variant="destructive" onClick={() => void decideOffer(referral, "reject")}>Reject offer</Button></div> : null}
                    </div>
                  ) : <div className="flex items-center gap-3 rounded-xl border border-dashed p-4 text-sm text-muted-foreground"><Clock3 className="h-5 w-5" />Lelefa reviews the portfolio first. No external collection mandate becomes active until an offer is returned and your company accepts it.</div>}
                </CardContent>
              </Card>
            );
          })}
          {!loading && referrals.length === 0 ? <Card className="border-dashed"><CardContent className="p-10 text-center text-sm text-muted-foreground"><Building2 className="mx-auto mb-3 h-7 w-7" />No Lelefa collection requests have been created yet.</CardContent></Card> : null}
        </TabsContent>
      </Tabs>
    </div>
  );
}
