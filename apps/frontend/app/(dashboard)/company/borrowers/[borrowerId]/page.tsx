"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowLeft,
  BadgeCheck,
  Banknote,
  CalendarClock,
  CheckCircle2,
  Clock3,
  FileText,
  Gavel,
  Mail,
  Mic2,
  Phone,
  PhoneCall,
  RefreshCcw,
  Scale,
  ShieldAlert,
  UserRound,
  WalletCards,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { borrowerWorkspaceApi, type BorrowerWorkspaceContext } from "@/api/borrowerWorkspace";
import { callsApi } from "@/api/calls";
import { collectionsApi } from "@/api/collections";
import { getCompanyClientProfile } from "@/api/companyClients";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { CallClientDetail, ClientCall } from "@/types/calls";
import type { CollectionAction, CollectionWorkspaceCase } from "@/types/collections";
import type { CompanyClientProfile } from "@/types/companyClient";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

type CollectionActivity = CollectionAction & {
  case_reference: string;
  loan_reference: string;
};

type TimelineItem = {
  id: string;
  at: string | null;
  kind: "call" | "collection" | "case";
  title: string;
  detail: string;
  meta?: string;
};

function money(value: number | null | undefined) {
  return new Intl.NumberFormat("en-LS", {
    style: "currency",
    currency: "LSL",
    maximumFractionDigits: 2,
  }).format(Number(value ?? 0));
}

function dateTime(value: string | null | undefined) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function titleCase(value: string | null | undefined) {
  return String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function duration(seconds: number | null | undefined) {
  const total = Math.max(0, Number(seconds ?? 0));
  const minutes = Math.floor(total / 60);
  return `${minutes}:${String(total % 60).padStart(2, "0")}`;
}

function MetricCard({
  label,
  value,
  note,
  icon: Icon,
}: {
  label: string;
  value: string;
  note: string;
  icon: typeof Banknote;
}) {
  return (
    <Card className="rounded-2xl border-border/70 shadow-sm">
      <CardContent className="flex min-h-28 items-start justify-between gap-4 p-5">
        <div className="min-w-0">
          <p className="text-xs font-bold uppercase tracking-[0.08em] text-muted-foreground">{label}</p>
          <p className="mt-2 break-words text-2xl font-black tracking-tight">{value}</p>
          <p className="mt-1 text-xs text-muted-foreground">{note}</p>
        </div>
        <div className="rounded-xl bg-primary/10 p-2.5 text-primary">
          <Icon className="h-5 w-5" />
        </div>
      </CardContent>
    </Card>
  );
}

function EmptyState({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed p-8 text-center text-sm text-muted-foreground">
      {children}
    </div>
  );
}

export default function CompanyBorrowerCommandPage() {
  const params = useParams<{ borrowerId: string }>();
  const borrowerId = params.borrowerId;
  const [context, setContext] = useState<BorrowerWorkspaceContext | null>(null);
  const [profile, setProfile] = useState<CompanyClientProfile | null>(null);
  const [callDetail, setCallDetail] = useState<CallClientDetail | null>(null);
  const [collectionCases, setCollectionCases] = useState<CollectionWorkspaceCase[]>([]);
  const [collectionActivities, setCollectionActivities] = useState<CollectionActivity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recordingUrl, setRecordingUrl] = useState<string | null>(null);
  const [playingRecordingId, setPlayingRecordingId] = useState<string | null>(null);

  const load = useCallback(async (showToast = false) => {
    if (!borrowerId) return;
    setLoading(true);
    setError(null);
    try {
      const resolved = await borrowerWorkspaceApi.context(borrowerId);
      setContext(resolved);

      const [profileResult, callsResult, collectionsResult] = await Promise.allSettled([
        getCompanyClientProfile(resolved.account_id),
        callsApi.getClient(borrowerId),
        collectionsApi.workspace({ search: resolved.name }),
      ]);

      setProfile(profileResult.status === "fulfilled" ? profileResult.value : null);
      setCallDetail(callsResult.status === "fulfilled" ? callsResult.value : null);

      const borrowerCases = collectionsResult.status === "fulfilled"
        ? collectionsResult.value.cases.filter((item) => item.borrower_id === borrowerId)
        : [];
      setCollectionCases(borrowerCases);

      if (borrowerCases.length) {
        const actionResults = await Promise.allSettled(
          borrowerCases.map(async (item) => ({
            item,
            actions: await collectionsApi.listActions(item.id),
          })),
        );
        setCollectionActivities(
          actionResults.flatMap((result) => {
            if (result.status !== "fulfilled") return [];
            return result.value.actions.map((action) => ({
              ...action,
              case_reference: result.value.item.case_reference,
              loan_reference: result.value.item.loan_reference,
            }));
          }),
        );
      } else {
        setCollectionActivities([]);
      }

      if (showToast) toast.success("Borrower workspace refreshed.");
    } catch (loadError: unknown) {
      setError(getErrorMessage(loadError, "The borrower workspace could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [borrowerId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => () => {
    if (recordingUrl) URL.revokeObjectURL(recordingUrl);
  }, [recordingUrl]);

  const calls = callDetail?.recent_calls ?? [];
  const profileLoans = profile?.loans ?? [];

  const collectionOutstanding = useMemo(
    () => collectionCases.reduce((sum, item) => sum + Number(item.outstanding_balance || 0), 0),
    [collectionCases],
  );
  const collectionRecovered = useMemo(
    () => collectionCases.reduce((sum, item) => sum + Number(item.recovered_amount || 0), 0),
    [collectionCases],
  );
  const collectionOverdue = useMemo(
    () => collectionCases.reduce((sum, item) => sum + Number(item.overdue_amount || 0), 0),
    [collectionCases],
  );

  const assigned = profile?.stats.lifetime_principal_total
    ?? (collectionOutstanding + collectionRecovered);
  const recovered = profile?.stats.lifetime_paid_total ?? collectionRecovered;
  const outstanding = profile?.stats.outstanding_balance ?? collectionOutstanding;
  const overdue = profile
    ? profile.loans.filter((loan) => loan.is_overdue).reduce((sum, loan) => sum + Number(loan.balance || 0), 0)
    : collectionOverdue;
  const recoveryBase = recovered + outstanding;
  const recoveryRate = recoveryBase > 0 ? (recovered / recoveryBase) * 100 : 0;
  const contactPoints = Number(Boolean(context?.phone)) + Number(Boolean(context?.email));
  const contactability = contactPoints * 50;
  const brokenPromises = collectionCases.filter((item) => item.promise_status === "broken");
  const openLegalCases = collectionCases.filter((item) => item.stage === "legal" || item.legal_handover_at);
  const alertCount = brokenPromises.length + openLegalCases.length + collectionCases.filter((item) => item.days_past_due > 0).length;

  const recommendedAction = useMemo(() => {
    if (brokenPromises.length) {
      return {
        title: "Review broken promise",
        note: `${brokenPromises.length} collection case${brokenPromises.length === 1 ? " has" : "s have"} a broken payment promise.`,
        level: "High",
      };
    }
    if (openLegalCases.length) {
      return {
        title: "Review legal recovery",
        note: `${openLegalCases.length} case${openLegalCases.length === 1 ? " is" : "s are"} in legal recovery.`,
        level: "High",
      };
    }
    const overdueCases = collectionCases.filter((item) => item.days_past_due > 0);
    if (overdueCases.length) {
      return {
        title: "Contact borrower about arrears",
        note: `${money(collectionOverdue)} is currently overdue across ${overdueCases.length} collection case${overdueCases.length === 1 ? "" : "s"}.`,
        level: "High",
      };
    }
    const promises = collectionCases
      .filter((item) => item.promise_date && item.promise_status && item.promise_status !== "kept")
      .sort((a, b) => String(a.promise_date).localeCompare(String(b.promise_date)));
    if (promises[0]) {
      return {
        title: "Follow up payment promise",
        note: `Promise due ${dateTime(promises[0].promise_date)} for ${money(promises[0].promise_amount)}.`,
        level: "Medium",
      };
    }
    if (!calls.length && context?.phone) {
      return {
        title: "Make first contact",
        note: "No recent borrower call is visible in the authorised call register.",
        level: "Normal",
      };
    }
    return {
      title: "Continue scheduled servicing",
      note: "No urgent collection exception is visible for this borrower.",
      level: "Normal",
    };
  }, [brokenPromises, calls.length, collectionCases, collectionOverdue, context?.phone, openLegalCases]);

  const timeline = useMemo<TimelineItem[]>(() => {
    const callItems: TimelineItem[] = calls.map((call) => ({
      id: `call-${call.id}`,
      at: call.started_at,
      kind: "call",
      title: `${titleCase(call.direction)} call · ${titleCase(call.status)}`,
      detail: call.notes || call.outcome || `Call with ${call.employee_name || "LoanHub staff"}`,
      meta: `${call.phone_number} · ${duration(call.duration_seconds)}`,
    }));
    const collectionItems: TimelineItem[] = collectionActivities.map((action) => ({
      id: `collection-${action.id}`,
      at: action.performed_at,
      kind: "collection",
      title: titleCase(action.activity_type),
      detail: action.notes || action.outcome || "Collection activity recorded.",
      meta: `${action.case_reference} · ${action.loan_reference}`,
    }));
    const caseItems: TimelineItem[] = (profile?.recent_case_entries ?? []).map((entry) => ({
      id: `case-${entry.id}`,
      at: entry.created_at,
      kind: "case",
      title: entry.title || titleCase(entry.category),
      detail: entry.body,
      meta: `${titleCase(entry.entry_type)} · ${titleCase(entry.status)}`,
    }));
    return [...callItems, ...collectionItems, ...caseItems].sort((a, b) => {
      const left = a.at ? new Date(a.at).getTime() : 0;
      const right = b.at ? new Date(b.at).getTime() : 0;
      return right - left;
    });
  }, [calls, collectionActivities, profile?.recent_case_entries]);

  async function playRecording(call: ClientCall) {
    if (!call.recording || call.recording.status !== "available") return;
    setPlayingRecordingId(call.recording.id);
    try {
      const blob = await callsApi.playRecording(call.recording.id);
      if (recordingUrl) URL.revokeObjectURL(recordingUrl);
      setRecordingUrl(URL.createObjectURL(blob));
    } catch (playError: unknown) {
      toast.error(getErrorMessage(playError, "The recording could not be played."));
    } finally {
      setPlayingRecordingId(null);
    }
  }

  if (loading && !context) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center p-6 text-muted-foreground">
        <RefreshCcw className="mr-2 h-5 w-5 animate-spin" /> Loading borrower command centre…
      </div>
    );
  }

  if (error || !context) {
    return (
      <div className="p-4 sm:p-6 lg:p-8">
        <Card className="mx-auto max-w-2xl border-destructive/30">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><AlertTriangle className="h-5 w-5 text-destructive" /> Borrower workspace unavailable</CardTitle>
            <CardDescription>{error || "The borrower could not be resolved in this company."}</CardDescription>
          </CardHeader>
          <CardContent className="flex gap-2">
            <Button variant="outline" asChild><Link href="/company/clients"><ArrowLeft className="h-4 w-4" />Clients</Link></Button>
            <Button onClick={() => void load()}><RefreshCcw className="h-4 w-4" />Retry</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-5 p-4 sm:p-6 lg:p-8">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="ghost" size="sm" asChild><Link href="/company/clients"><ArrowLeft className="h-4 w-4" />Clients</Link></Button>
            <Badge variant={context.account_status === "active" ? "default" : "secondary"}>{titleCase(context.account_status)}</Badge>
            <Badge variant="outline">Borrower command centre</Badge>
          </div>
          <h1 className="mt-3 break-words text-3xl font-black tracking-tight sm:text-4xl">{context.name}</h1>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
            <span className="font-mono">{context.account_reference}</span>
            {context.phone ? <span>{context.phone}</span> : null}
            {context.email ? <span className="break-all">{context.email}</span> : null}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => void load(true)} disabled={loading}>
            <RefreshCcw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh
          </Button>
          <Button asChild disabled={!context.phone}>
            <Link href={`/company/calls?borrower=${encodeURIComponent(context.borrower_id)}&phone=${encodeURIComponent(context.phone || "")}`}>
              <PhoneCall className="h-4 w-4" />Call borrower
            </Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        <MetricCard label="Assigned" value={money(assigned)} note="Lifetime principal" icon={WalletCards} />
        <MetricCard label="Recovered" value={money(recovered)} note="LoanHub repayments" icon={CheckCircle2} />
        <MetricCard label="Outstanding" value={money(outstanding)} note="Current exposure" icon={Banknote} />
        <MetricCard label="Overdue" value={money(overdue)} note="Arrears exposure" icon={Clock3} />
        <MetricCard label="Recovery rate" value={`${recoveryRate.toFixed(1)}%`} note="Recovered vs open exposure" icon={BadgeCheck} />
        <MetricCard label="Contactability" value={`${contactability}%`} note={`${alertCount} attention item${alertCount === 1 ? "" : "s"}`} icon={Phone} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.7fr)_minmax(320px,0.7fr)]">
        <Card className="rounded-2xl">
          <CardHeader>
            <CardTitle className="text-base">Quick actions</CardTitle>
            <CardDescription>Actions use LoanHub’s existing controlled lending, call, collection and document workflows.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            <Button variant="outline" className="justify-start" asChild>
              <Link href={`/company/calls?borrower=${encodeURIComponent(context.borrower_id)}&phone=${encodeURIComponent(context.phone || "")}`}><Phone className="h-4 w-4" />Call</Link>
            </Button>
            <Button variant="outline" className="justify-start" asChild>
              <Link href="/company/collections"><ShieldAlert className="h-4 w-4" />Collections</Link>
            </Button>
            <Button variant="outline" className="justify-start" asChild>
              <Link href={`/company/documents?client=${encodeURIComponent(context.account_id)}`}><FileText className="h-4 w-4" />Letters & documents</Link>
            </Button>
            <Button variant="outline" className="justify-start" asChild>
              <Link href={`/company/origination/new?borrower=${encodeURIComponent(context.borrower_id)}`}><BadgeCheck className="h-4 w-4" />Assessment</Link>
            </Button>
          </CardContent>
        </Card>

        <Card className="rounded-2xl border-primary/20 bg-primary/[0.03]">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base"><ShieldAlert className="h-5 w-5 text-primary" />Next recommended action</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xl font-black">{recommendedAction.title}</p>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{recommendedAction.note}</p>
            <Badge className="mt-4" variant={recommendedAction.level === "High" ? "destructive" : "secondary"}>{recommendedAction.level}</Badge>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="overview" className="space-y-4">
        <div className="overflow-x-auto rounded-xl border bg-card p-1">
          <TabsList className="h-auto min-w-[760px] justify-start bg-transparent">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="timeline">Interaction wall</TabsTrigger>
            <TabsTrigger value="calls">Calls & recordings</TabsTrigger>
            <TabsTrigger value="collections">Promises & collections</TabsTrigger>
            <TabsTrigger value="loans">Loans</TabsTrigger>
            <TabsTrigger value="documents">Documents & legal</TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-[minmax(280px,0.8fr)_minmax(0,1.7fr)]">
            <Card className="rounded-2xl">
              <CardHeader><CardTitle className="flex items-center gap-2 text-base"><UserRound className="h-5 w-5 text-primary" />Identity & contact</CardTitle></CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div><p className="text-xs font-bold text-muted-foreground">NAME</p><p className="font-semibold">{context.name}</p></div>
                <div><p className="text-xs font-bold text-muted-foreground">ID / PASSPORT</p><p className="font-semibold">{context.national_id || context.passport_number || "Not recorded"}</p></div>
                <div><p className="text-xs font-bold text-muted-foreground">TELEPHONE</p><p className="font-semibold">{context.phone || "Not recorded"}</p></div>
                <div><p className="text-xs font-bold text-muted-foreground">EMAIL</p><p className="break-all font-semibold">{context.email || "Not recorded"}</p></div>
                <div><p className="text-xs font-bold text-muted-foreground">ADDRESS</p><p className="font-semibold">{context.physical_address || [context.town_or_village, context.district].filter(Boolean).join(", ") || "Not recorded"}</p></div>
                <div><p className="text-xs font-bold text-muted-foreground">EMPLOYMENT</p><p className="font-semibold">{[context.job_title, context.employer_name].filter(Boolean).join(" · ") || titleCase(context.employment_status) || "Not recorded"}</p></div>
              </CardContent>
            </Card>

            <div className="space-y-4">
              <Card className="rounded-2xl">
                <CardHeader><CardTitle className="text-base">Account exposure</CardTitle><CardDescription>Loans linked to this company-borrower relationship.</CardDescription></CardHeader>
                <CardContent>
                  {profileLoans.length ? (
                    <div className="space-y-3">
                      {profileLoans.map((loan) => (
                        <div key={loan.id} className="grid gap-3 rounded-xl border p-4 md:grid-cols-[1.2fr_repeat(4,minmax(100px,0.7fr))] md:items-center">
                          <div><p className="font-mono text-xs text-muted-foreground">{loan.loan_reference}</p><p className="font-bold">{titleCase(loan.status)}</p></div>
                          <div><p className="text-xs text-muted-foreground">Principal</p><p className="font-bold">{money(loan.principal_amount)}</p></div>
                          <div><p className="text-xs text-muted-foreground">Paid</p><p className="font-bold">{money(loan.amount_paid)}</p></div>
                          <div><p className="text-xs text-muted-foreground">Outstanding</p><p className="font-bold">{money(loan.balance)}</p></div>
                          <div><p className="text-xs text-muted-foreground">Arrears</p><Badge variant={loan.is_overdue ? "destructive" : "secondary"}>{loan.is_overdue ? `${loan.overdue_installment_count} overdue` : "Current"}</Badge></div>
                        </div>
                      ))}
                    </div>
                  ) : callDetail?.loans.length ? (
                    <div className="space-y-3">
                      {callDetail.loans.map((loan) => (
                        <div key={loan.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border p-4">
                          <div><p className="font-mono text-xs text-muted-foreground">{loan.loan_reference}</p><p className="font-bold">{titleCase(loan.status)}</p></div>
                          <div className="text-right"><p className="text-xs text-muted-foreground">Balance</p><p className="font-bold">{money(loan.balance)}</p></div>
                        </div>
                      ))}
                    </div>
                  ) : <EmptyState>No company loan exposure is visible for this borrower.</EmptyState>}
                </CardContent>
              </Card>

              <div className="grid gap-4 md:grid-cols-2">
                <Card className="rounded-2xl">
                  <CardHeader><CardTitle className="text-base">Current commitments</CardTitle></CardHeader>
                  <CardContent>
                    {collectionCases.some((item) => item.promise_date) ? collectionCases.filter((item) => item.promise_date).map((item) => (
                      <div key={item.id} className="mb-3 rounded-xl border p-3 last:mb-0">
                        <div className="flex items-center justify-between gap-2"><p className="font-bold">{item.case_reference}</p><Badge variant="outline">{titleCase(item.promise_status)}</Badge></div>
                        <p className="mt-1 text-sm text-muted-foreground">{money(item.promise_amount)} due {dateTime(item.promise_date)}</p>
                      </div>
                    )) : <EmptyState>No open payment promise.</EmptyState>}
                  </CardContent>
                </Card>
                <Card className="rounded-2xl">
                  <CardHeader><CardTitle className="text-base">Attention required</CardTitle></CardHeader>
                  <CardContent>
                    {alertCount ? (
                      <div className="space-y-2 text-sm">
                        {brokenPromises.length ? <p className="flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-destructive" />{brokenPromises.length} broken promise(s)</p> : null}
                        {openLegalCases.length ? <p className="flex items-center gap-2"><Scale className="h-4 w-4 text-destructive" />{openLegalCases.length} legal recovery case(s)</p> : null}
                        {collectionCases.filter((item) => item.days_past_due > 0).length ? <p className="flex items-center gap-2"><Clock3 className="h-4 w-4 text-destructive" />{collectionCases.filter((item) => item.days_past_due > 0).length} overdue case(s)</p> : null}
                      </div>
                    ) : <EmptyState>No active collection alerts.</EmptyState>}
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="timeline">
          <Card className="rounded-2xl">
            <CardHeader><CardTitle>Interaction wall</CardTitle><CardDescription>Calls, collections and borrower case activity in one chronological view.</CardDescription></CardHeader>
            <CardContent>
              {timeline.length ? (
                <div className="space-y-3">
                  {timeline.map((item) => (
                    <div key={item.id} className="grid gap-3 rounded-xl border p-4 sm:grid-cols-[auto_minmax(0,1fr)_auto] sm:items-start">
                      <div className="rounded-lg bg-muted p-2">
                        {item.kind === "call" ? <Phone className="h-4 w-4" /> : item.kind === "collection" ? <ShieldAlert className="h-4 w-4" /> : <FileText className="h-4 w-4" />}
                      </div>
                      <div className="min-w-0"><p className="font-bold">{item.title}</p><p className="mt-1 whitespace-pre-wrap text-sm text-muted-foreground">{item.detail}</p>{item.meta ? <p className="mt-2 text-xs font-medium text-muted-foreground">{item.meta}</p> : null}</div>
                      <p className="text-xs text-muted-foreground sm:text-right">{dateTime(item.at)}</p>
                    </div>
                  ))}
                </div>
              ) : <EmptyState>No interaction history is visible yet.</EmptyState>}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="calls" className="space-y-4">
          {recordingUrl ? (
            <Card className="rounded-2xl border-primary/30">
              <CardContent className="p-4"><audio className="w-full" controls autoPlay src={recordingUrl} /></CardContent>
            </Card>
          ) : null}
          <Card className="rounded-2xl">
            <CardHeader><CardTitle>Calls & recordings</CardTitle><CardDescription>Borrower-specific call history. Playback still uses LoanHub recording authorisation and retention controls.</CardDescription></CardHeader>
            <CardContent>
              {calls.length ? (
                <div className="space-y-3">
                  {calls.map((call) => (
                    <div key={call.id} className="grid gap-3 rounded-xl border p-4 lg:grid-cols-[minmax(0,1.4fr)_repeat(3,minmax(110px,0.6fr))_auto] lg:items-center">
                      <div><p className="font-bold">{titleCase(call.direction)} call</p><p className="text-sm text-muted-foreground">{call.phone_number} · {call.employee_name || "LoanHub staff"}</p>{call.notes ? <p className="mt-1 text-sm">{call.notes}</p> : null}</div>
                      <div><p className="text-xs text-muted-foreground">Status</p><Badge variant="outline">{titleCase(call.status)}</Badge></div>
                      <div><p className="text-xs text-muted-foreground">Duration</p><p className="font-semibold">{duration(call.duration_seconds)}</p></div>
                      <div><p className="text-xs text-muted-foreground">Started</p><p className="text-sm font-semibold">{dateTime(call.started_at)}</p></div>
                      <Button size="sm" variant="outline" disabled={!call.recording || call.recording.status !== "available" || playingRecordingId === call.recording?.id} onClick={() => void playRecording(call)}>
                        <Mic2 className="h-4 w-4" />{playingRecordingId === call.recording?.id ? "Loading…" : "Play"}
                      </Button>
                    </div>
                  ))}
                </div>
              ) : <EmptyState>No authorised calls are visible for this borrower.</EmptyState>}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="collections">
          <Card className="rounded-2xl">
            <CardHeader><CardTitle>Promises & collections</CardTitle><CardDescription>Loan-level recovery cases, promises, ownership and follow-up dates.</CardDescription></CardHeader>
            <CardContent>
              {collectionCases.length ? (
                <div className="space-y-4">
                  {collectionCases.map((item) => (
                    <div key={item.id} className="rounded-xl border p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div><p className="font-mono text-xs text-muted-foreground">{item.case_reference}</p><p className="font-black">{item.loan_reference}</p></div>
                        <div className="flex flex-wrap gap-2"><Badge variant="outline">{titleCase(item.stage)}</Badge><Badge variant={item.days_past_due > 0 ? "destructive" : "secondary"}>{item.days_past_due} days past due</Badge></div>
                      </div>
                      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                        <div><p className="text-xs text-muted-foreground">Outstanding</p><p className="font-bold">{money(item.outstanding_balance)}</p></div>
                        <div><p className="text-xs text-muted-foreground">Overdue</p><p className="font-bold">{money(item.overdue_amount)}</p></div>
                        <div><p className="text-xs text-muted-foreground">Recovered</p><p className="font-bold">{money(item.recovered_amount)}</p></div>
                        <div><p className="text-xs text-muted-foreground">Promise</p><p className="font-bold">{item.promise_date ? `${money(item.promise_amount)} · ${dateTime(item.promise_date)}` : "—"}</p></div>
                        <div><p className="text-xs text-muted-foreground">Next action</p><p className="font-bold">{dateTime(item.next_action_at)}</p></div>
                      </div>
                    </div>
                  ))}
                  <Button variant="outline" asChild><Link href="/company/collections"><ShieldAlert className="h-4 w-4" />Open controlled collections workspace</Link></Button>
                </div>
              ) : <EmptyState>No active collection case is visible for this borrower.</EmptyState>}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="loans">
          <Card className="rounded-2xl">
            <CardHeader><CardTitle>Loan portfolio</CardTitle><CardDescription>Company loans associated with this borrower.</CardDescription></CardHeader>
            <CardContent>
              {profileLoans.length ? (
                <div className="grid gap-4 xl:grid-cols-2">
                  {profileLoans.map((loan) => (
                    <Card key={loan.id} className="shadow-none">
                      <CardHeader><div className="flex items-start justify-between gap-3"><div><CardTitle className="text-base">{loan.loan_reference}</CardTitle><CardDescription>{titleCase(loan.status)} · {titleCase(loan.risk_level)} risk</CardDescription></div><Badge variant={loan.is_overdue ? "destructive" : "secondary"}>{loan.is_overdue ? "Overdue" : "Current"}</Badge></div></CardHeader>
                      <CardContent className="grid gap-3 sm:grid-cols-2">
                        <div><p className="text-xs text-muted-foreground">Principal</p><p className="font-bold">{money(loan.principal_amount)}</p></div>
                        <div><p className="text-xs text-muted-foreground">Total repayable</p><p className="font-bold">{money(loan.total_repayable)}</p></div>
                        <div><p className="text-xs text-muted-foreground">Paid</p><p className="font-bold">{money(loan.amount_paid)}</p></div>
                        <div><p className="text-xs text-muted-foreground">Balance</p><p className="font-bold">{money(loan.balance)}</p></div>
                        <div><p className="text-xs text-muted-foreground">Installment</p><p className="font-bold">{money(loan.installment_amount)}</p></div>
                        <div><p className="text-xs text-muted-foreground">Maturity</p><p className="font-bold">{dateTime(loan.maturity_date)}</p></div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              ) : <EmptyState>Detailed loan profile is unavailable for this active role, or this borrower has no company loans.</EmptyState>}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="documents">
          <div className="grid gap-4 lg:grid-cols-2">
            <Card className="rounded-2xl">
              <CardHeader><CardTitle className="flex items-center gap-2"><FileText className="h-5 w-5 text-primary" />Documents & letters</CardTitle><CardDescription>Borrower profile documents remain protected by the existing document permissions.</CardDescription></CardHeader>
              <CardContent>
                {profile?.documents.length ? (
                  <div className="space-y-2">
                    {profile.documents.map((document) => (
                      <div key={document.id} className="flex items-center justify-between gap-3 rounded-xl border p-3"><div className="min-w-0"><p className="truncate font-bold">{document.original_name}</p><p className="text-xs text-muted-foreground">{titleCase(document.document_type)} · {dateTime(document.created_at)}</p></div>{document.is_confidential ? <Badge variant="outline">Confidential</Badge> : null}</div>
                    ))}
                  </div>
                ) : <EmptyState>No borrower documents are visible for this role.</EmptyState>}
                <Button className="mt-4" variant="outline" asChild><Link href={`/company/documents?client=${encodeURIComponent(context.account_id)}`}><FileText className="h-4 w-4" />Open letters & documents</Link></Button>
              </CardContent>
            </Card>
            <Card className="rounded-2xl">
              <CardHeader><CardTitle className="flex items-center gap-2"><Gavel className="h-5 w-5 text-primary" />Legal & case history</CardTitle><CardDescription>Recorded legal actions and case notes for this company-client relationship.</CardDescription></CardHeader>
              <CardContent>
                {(profile?.recent_case_entries ?? []).length ? (
                  <div className="space-y-3">
                    {(profile?.recent_case_entries ?? []).map((entry) => (
                      <div key={entry.id} className="rounded-xl border p-3"><div className="flex flex-wrap items-center justify-between gap-2"><p className="font-bold">{entry.title || titleCase(entry.category)}</p><Badge variant="outline">{titleCase(entry.status)}</Badge></div><p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">{entry.body}</p><p className="mt-2 text-xs text-muted-foreground">{dateTime(entry.created_at)}{entry.reference_number ? ` · ${entry.reference_number}` : ""}</p></div>
                    ))}
                  </div>
                ) : openLegalCases.length ? (
                  <div className="space-y-3">{openLegalCases.map((item) => <div key={item.id} className="rounded-xl border p-3"><p className="font-bold">{item.case_reference}</p><p className="text-sm text-muted-foreground">Legal handover {dateTime(item.legal_handover_at)} · {item.loan_reference}</p></div>)}</div>
                ) : <EmptyState>No legal action is visible for this borrower.</EmptyState>}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      <div className="flex flex-wrap gap-2 border-t pt-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1"><CalendarClock className="h-3.5 w-3.5" />Account opened {dateTime(context.opened_at)}</span>
        {context.email ? <span className="flex items-center gap-1"><Mail className="h-3.5 w-3.5" />Email available</span> : null}
        {context.phone ? <span className="flex items-center gap-1"><Phone className="h-3.5 w-3.5" />Phone available</span> : null}
      </div>
    </div>
  );
}
