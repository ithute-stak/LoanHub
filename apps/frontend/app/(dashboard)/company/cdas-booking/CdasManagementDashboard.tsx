"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CalendarClock,
  CheckCircle2,
  DatabaseZap,
  RefreshCw,
  ShieldCheck,
  Users,
  Workflow,
} from "lucide-react";

import { cdasBookingApi } from "@/api/cdasBooking";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { CdasManagementDashboard } from "@/types/cdasManagementDashboard";

function money(value: number) {
  return new Intl.NumberFormat("en-LS", {
    style: "currency",
    currency: "LSL",
    maximumFractionDigits: 2,
  }).format(value || 0);
}

function MetricCard({
  title,
  value,
  detail,
  href,
}: {
  title: string;
  value: string | number;
  detail: string;
  href?: string;
}) {
  const body = <Card className="h-full transition-colors hover:bg-muted/20">
    <CardHeader className="pb-2">
      <CardDescription>{title}</CardDescription>
      <CardTitle className="text-2xl">{value}</CardTitle>
    </CardHeader>
    <CardContent className="text-xs text-muted-foreground">{detail}</CardContent>
  </Card>;
  return href ? <Link href={href} className="block h-full">{body}</Link> : body;
}

function automationLabel(health: string) {
  switch (health) {
    case "healthy": return "Healthy";
    case "running": return "Running";
    case "needs_review": return "Needs review";
    case "needs_intervention": return "Needs intervention";
    default: return "Awaiting first run";
  }
}

export function CdasManagementDashboardView() {
  const [data, setData] = useState<CdasManagementDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await cdasBookingApi.getManagementDashboard());
    } catch {
      setError("Unable to load the CDAS management dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const maxForecastValue = useMemo(
    () => Math.max(1, ...(data?.forecast_months || []).map((item) => item.monthly_deduction_value)),
    [data],
  );

  if (loading && !data) {
    return <div className="flex min-h-64 items-center justify-center text-sm text-muted-foreground">
      <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> Loading management dashboard…
    </div>;
  }

  return <div className="space-y-5">
    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
      <div>
        <div className="flex items-center gap-2">
          <BarChart3 className="h-6 w-6" />
          <h1 className="text-2xl font-semibold tracking-tight">CDAS Management Dashboard</h1>
        </div>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          Company-wide operational view of booking workload, follow-ups, exceptions, data quality and known future booking windows.
        </p>
      </div>
      <div className="flex items-center gap-2">
        {data?.as_of && <Badge variant="outline">As of {data.as_of}</Badge>}
        <Button variant="outline" onClick={() => void load()} disabled={loading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh
        </Button>
      </div>
    </div>

    <Alert>
      <ShieldCheck className="h-4 w-4" />
      <AlertTitle>Aggregate operational intelligence only</AlertTitle>
      <AlertDescription>
        This dashboard does not determine borrower approval, eligibility, loan amount, pricing, disbursement or revenue. Use the underlying CDAS workspaces to review individual records and source evidence.
      </AlertDescription>
    </Alert>

    {error && <Alert variant="destructive">
      <AlertTriangle className="h-4 w-4" />
      <AlertTitle>Dashboard unavailable</AlertTitle>
      <AlertDescription>{error}</AlertDescription>
    </Alert>}

    {data && <>
      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-5 w-5" />
          <h2 className="text-lg font-semibold">Daily CDAS automation</h2>
        </div>
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle className="text-base">03:45 borrower intelligence monitor</CardTitle>
                <CardDescription>{data.automation.message}</CardDescription>
              </div>
              <Badge variant={data.automation.healthy ? "secondary" : "destructive"}>
                {automationLabel(data.automation.health)}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-md border p-3"><div className="text-xs text-muted-foreground">Schedule</div><div className="mt-1 font-medium">{data.automation.schedule} · {data.automation.timezone}</div></div>
              <div className="rounded-md border p-3"><div className="text-xs text-muted-foreground">Profiles checked</div><div className="mt-1 text-xl font-semibold">{data.automation.checked_profiles}</div></div>
              <div className="rounded-md border p-3"><div className="text-xs text-muted-foreground">Ready for collection review</div><div className="mt-1 text-xl font-semibold">{data.automation.ready_profiles}</div></div>
              <div className="rounded-md border p-3"><div className="text-xs text-muted-foreground">Issues to review</div><div className="mt-1 text-xl font-semibold">{data.automation.issue_count}</div></div>
            </div>
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
              <span>Run date: {data.automation.run_date || "Not run yet"}</span>
              <span>No-capacity profiles: {data.automation.no_capacity_profiles}</span>
              <span>Eligible profiles: {data.automation.eligible_profiles}</span>
              <span>Provider writes: {data.automation.provider_writes}</span>
            </div>
            <p className="text-xs text-muted-foreground">
              Scheduled monitoring is read-only against CDAS. Registrations and changes stay behind exact-ID verification, borrower consent, role controls and the official lifecycle.
            </p>
          </CardContent>
        </Card>
      </section>

      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5" />
          <h2 className="text-lg font-semibold">Operations pulse</h2>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard title="Active opportunities" value={data.operations.active_opportunities} detail={`${money(data.operations.active_monthly_deduction_value)} monthly deduction value`} href="/company/cdas-booking/pipeline" />
          <MetricCard title="Overdue booking windows" value={data.operations.overdue_booking_windows} detail={`${data.operations.due_today} due today`} href="/company/cdas-booking/calendar" />
          <MetricCard title="Critical + high priority" value={data.operations.critical_priorities + data.operations.high_priorities} detail={`${data.operations.critical_priorities} critical · ${data.operations.high_priorities} high`} href="/company/cdas-booking/priorities" />
          <MetricCard title="Next 30 days" value={data.operations.next_30_days} detail={`${data.operations.booked_total} opportunities booked to date`} href="/company/cdas-booking/calendar" />
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <Workflow className="h-5 w-5" />
          <h2 className="text-lg font-semibold">Workflow attention</h2>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard title="Unassigned open" value={data.workflow.unassigned_open} detail="Open opportunities without an assigned officer" href="/company/cdas-booking/officer-performance" />
          <MetricCard title="Overdue follow-ups" value={data.workflow.overdue_follow_ups} detail={`${data.workflow.scheduled_follow_ups} scheduled follow-ups`} href="/company/cdas-booking/follow-ups" />
          <MetricCard title="Needs intervention" value={data.workflow.currently_failed} detail={`${data.workflow.retry_due} retry due · ${data.workflow.retryable} retryable`} href="/company/cdas-booking/failures" />
          <MetricCard title="Contacted open" value={data.workflow.contacted_open} detail={`${data.workflow.failure_attempts} recorded issue attempt(s)`} href="/company/cdas-booking/follow-ups" />
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2"><Workflow className="h-5 w-5"/><CardTitle className="text-base">Pipeline distribution</CardTitle></div>
            <CardDescription>Current opportunity count and monthly deduction value by workflow stage.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {data.pipeline_stages.map((stage) => <div key={stage.id} className="flex items-center justify-between gap-3 rounded-md border p-3">
              <div>
                <div className="font-medium">{stage.label}</div>
                <div className="text-xs text-muted-foreground">{money(stage.monthly_deduction_value)}</div>
              </div>
              <Badge variant="secondary">{stage.count}</Badge>
            </div>)}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2"><AlertTriangle className="h-5 w-5"/><CardTitle className="text-base">Issue breakdown</CardTitle></div>
            <CardDescription>Recorded booking exceptions grouped by controlled operational reason.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {data.failure_reasons.length > 0 ? data.failure_reasons.map((reason) => <div key={reason.reason_code} className="flex items-center justify-between gap-3 rounded-md border p-3">
              <span className="text-sm">{reason.reason_label}</span>
              <Badge variant="outline">{reason.count}</Badge>
            </div>) : <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">No operational issues have been recorded.</div>}
          </CardContent>
        </Card>
      </div>

      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <DatabaseZap className="h-5 w-5" />
          <h2 className="text-lg font-semibold">Data quality and review</h2>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard title="Profiles with issues" value={data.data_quality.profiles_with_issues} detail={`${data.data_quality.profiles_checked} profiles checked · ${data.data_quality.total_issues} issue(s)`} href="/company/cdas-booking/data-quality" />
          <MetricCard title="Blocker profiles" value={data.data_quality.blocker_clients} detail={`${data.data_quality.blocker_issues} blocker issue(s) · ${money(data.data_quality.excluded_monthly_amount)} excluded`} href="/company/cdas-booking/data-quality" />
          <MetricCard title="Duplicate review pairs" value={data.data_quality.duplicate_candidate_pairs} detail={`${data.data_quality.high_confidence_duplicate_pairs} high-confidence pair(s)`} href="/company/cdas-booking/duplicates" />
          <MetricCard title="Materially changed profiles" value={data.data_quality.clients_with_material_changes} detail={`${data.data_quality.material_changes} material field/deduction change(s)`} href="/company/cdas-booking/changes" />
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <CalendarClock className="h-5 w-5" />
          <h2 className="text-lg font-semibold">Known booking-window forecast</h2>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard title="Book now windows" value={data.forecast.book_now_count} detail={money(data.forecast.book_now_value)} href="/company/cdas-booking/forecast" />
          <MetricCard title="Next 3 months" value={data.forecast.next_3_months.opportunity_count || 0} detail={money(data.forecast.next_3_months.monthly_deduction_value || 0)} href="/company/cdas-booking/forecast" />
          <MetricCard title="12-month scheduled" value={data.forecast.next_12_months.opportunity_count || 0} detail={money(data.forecast.next_12_months.monthly_deduction_value || 0)} href="/company/cdas-booking/forecast" />
          <MetricCard title="Peak month" value={data.forecast.peak_month || "—"} detail={money(data.forecast.peak_month_value)} href="/company/cdas-booking/forecast" />
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">12-month outlook</CardTitle>
            <CardDescription>Known competitor deduction booking-open windows by calendar month.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.forecast_months.map((month) => <div key={month.month} className="grid gap-2 md:grid-cols-[100px_1fr_180px] md:items-center">
              <div className="text-sm font-medium">{month.label}</div>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-foreground/70" style={{ width: `${Math.max(0, Math.min(100, (month.monthly_deduction_value / maxForecastValue) * 100))}%` }} />
              </div>
              <div className="text-sm text-muted-foreground md:text-right">{month.opportunity_count} window(s) · {money(month.monthly_deduction_value)}</div>
            </div>)}
          </CardContent>
        </Card>
      </section>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2"><Users className="h-5 w-5"/><CardTitle className="text-base">Top employers in forecast</CardTitle></div>
            <CardDescription>Aggregate known booking-window value only.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {data.top_employers.map((item) => <div key={item.employer} className="flex items-center justify-between gap-3 rounded-md border p-3">
              <div><div className="font-medium">{item.employer}</div><div className="text-xs text-muted-foreground">{item.book_now_count} book now · {item.scheduled_count} scheduled</div></div>
              <span className="text-sm font-medium">{money(item.total_opportunity_value)}</span>
            </div>)}
            {data.top_employers.length === 0 && <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">No employer forecast concentration yet.</div>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2"><CheckCircle2 className="h-5 w-5"/><CardTitle className="text-base">Top competitor agencies in forecast</CardTitle></div>
            <CardDescription>Aggregate known booking-window value only.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {data.top_agencies.map((item) => <div key={item.agency} className="flex items-center justify-between gap-3 rounded-md border p-3">
              <div><div className="font-medium">{item.agency}</div><div className="text-xs text-muted-foreground">{item.book_now_count} book now · {item.scheduled_count} scheduled</div></div>
              <span className="text-sm font-medium">{money(item.total_opportunity_value)}</span>
            </div>)}
            {data.top_agencies.length === 0 && <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">No agency forecast concentration yet.</div>}
          </CardContent>
        </Card>
      </div>
    </>}
  </div>;
}
