"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, CalendarDays, CheckCircle2, Clock3, RefreshCw } from "lucide-react";

import { cdasBookingApi } from "@/api/cdasBooking";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { CdasBookingCalendar, CdasBookingCalendarEvent } from "@/types/cdasBookingCalendar";

type CalendarView = "overdue" | "today" | "week" | "30" | "90" | "unscheduled" | "booked" | "all";

function money(value?: number | null) {
  return `M ${Number(value || 0).toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function dateLabel(value?: string | null) {
  if (!value) return "No date";
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString("en-ZA", { weekday: "short", day: "2-digit", month: "short", year: "numeric" });
}

function timingLabel(event: CdasBookingCalendarEvent) {
  if (event.state === "BOOKED") return "Booked";
  if (event.days_from_today === null) return "Booking date missing";
  if (event.days_from_today < 0) return `${Math.abs(event.days_from_today)} day(s) overdue`;
  if (event.days_from_today === 0) return "Book today";
  return `${event.days_from_today} day(s) to booking`;
}

function eventMatchesView(event: CdasBookingCalendarEvent, calendar: CdasBookingCalendar, view: CalendarView) {
  if (view === "all") return true;
  if (view === "booked") return event.state === "BOOKED";
  if (event.state === "BOOKED") return false;
  if (view === "overdue") return event.is_overdue;
  if (view === "today") return event.booking_date === calendar.as_of;
  if (view === "unscheduled") return !event.booking_date;
  if (!event.booking_date) return false;
  if (view === "week") return event.booking_date >= calendar.as_of && event.booking_date <= calendar.week_end;
  if (view === "30") return event.booking_date >= calendar.as_of && event.booking_date <= calendar.next_30_days_end;
  if (view === "90") return event.booking_date >= calendar.as_of && event.booking_date <= calendar.next_90_days_end;
  return true;
}

function EventCard({ event, onBooked, busy }: { event: CdasBookingCalendarEvent; onBooked: (id: string) => void; busy: boolean }) {
  const urgent = event.is_overdue || event.bucket === "TODAY";
  return <div className={`rounded-lg border p-4 ${urgent ? "border-amber-500/50 bg-amber-50/40 dark:bg-amber-950/20" : ""}`}>
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <div className="font-semibold">{event.client_name || event.client_reference || "CDAS client"}</div>
        <div className="mt-1 text-sm text-muted-foreground">{event.agency_name || "Agency not captured"}{event.reference_no ? ` • ${event.reference_no}` : ""}</div>
      </div>
      <Badge variant={event.is_overdue ? "outline" : event.state === "BOOK_NOW" ? "default" : "secondary"} className={event.is_overdue ? "border-amber-500 text-amber-700 dark:text-amber-300" : ""}>{event.is_overdue ? "OVERDUE" : event.state.replaceAll("_", " ")}</Badge>
    </div>

    <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
      <div><div className="text-xs text-muted-foreground">Booking date</div><div className="font-medium">{dateLabel(event.booking_date)}</div></div>
      <div><div className="text-xs text-muted-foreground">Timing</div><div className="font-medium">{timingLabel(event)}</div></div>
      <div><div className="text-xs text-muted-foreground">Deduction</div><div className="font-medium">{money(event.deduction_amount)}</div></div>
      <div><div className="text-xs text-muted-foreground">Expiry</div><div className="font-medium">{dateLabel(event.expiry_date)}</div></div>
    </div>

    {event.state !== "BOOKED" && event.booking_date && (event.is_overdue || event.days_from_today === 0) && <Button className="mt-4 w-full sm:w-auto" disabled={busy} onClick={() => onBooked(event.id)}><CheckCircle2 className="mr-2 h-4 w-4"/>{busy ? "Updating..." : "Mark booking complete"}</Button>}
  </div>;
}

export function CdasBookingCalendarView() {
  const [calendar, setCalendar] = useState<CdasBookingCalendar | null>(null);
  const [view, setView] = useState<CalendarView>("30");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setCalendar(await cdasBookingApi.getBookingCalendar());
    } catch {
      setError("Could not load the CDAS booking calendar.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  async function markBooked(id: string) {
    setBusyId(id);
    setError("");
    try {
      await cdasBookingApi.markBooked(id);
      await refresh();
    } catch {
      setError("Could not mark this CDAS booking complete.");
    } finally {
      setBusyId(null);
    }
  }

  const visible = useMemo(() => {
    if (!calendar) return [];
    return calendar.events.filter((event) => eventMatchesView(event, calendar, view));
  }, [calendar, view]);

  const grouped = useMemo(() => {
    const groups = new Map<string, CdasBookingCalendarEvent[]>();
    for (const event of visible) {
      const key = event.booking_date || "unscheduled";
      const values = groups.get(key) || [];
      values.push(event);
      groups.set(key, values);
    }
    return Array.from(groups.entries());
  }, [visible]);

  if (!calendar && loading) return <Card><CardContent className="py-16 text-center text-sm text-muted-foreground">Loading automatic booking calendar…</CardContent></Card>;
  if (!calendar) return <Card><CardContent className="py-10 text-center text-sm text-destructive">{error || "The booking calendar could not be loaded."}</CardContent></Card>;

  const views: Array<{ id: CalendarView; label: string; count?: number }> = [
    { id: "overdue", label: "Overdue", count: calendar.summary.overdue },
    { id: "today", label: "Today", count: calendar.summary.today },
    { id: "week", label: "This Week", count: calendar.summary.this_week },
    { id: "30", label: "Next 30 Days", count: calendar.summary.next_30_days },
    { id: "90", label: "Next 90 Days", count: calendar.summary.next_90_days },
    { id: "unscheduled", label: "Unscheduled", count: calendar.summary.unscheduled },
    { id: "booked", label: "Booked", count: calendar.summary.booked },
    { id: "all", label: "All", count: calendar.total },
  ];

  return <div className="space-y-5">
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="rounded-lg border bg-muted/40 p-2"><CalendarDays className="h-5 w-5"/></div>
            <div><CardTitle>Automatic CDAS Booking Calendar</CardTitle><CardDescription>Booking dates move automatically from upcoming to today and overdue. The 30- and 90-day counts are cumulative planning windows.</CardDescription></div>
          </div>
          <Button variant="outline" size="sm" onClick={() => void refresh()} disabled={loading}><RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}/>Refresh</Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">{error}</div>}
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <button type="button" onClick={() => setView("overdue")} className="rounded-lg border p-3 text-left transition hover:bg-muted/40"><div className="flex items-center gap-2 text-xs text-muted-foreground"><AlertTriangle className="h-4 w-4"/>Overdue</div><div className="mt-1 text-2xl font-semibold">{calendar.summary.overdue}</div></button>
          <button type="button" onClick={() => setView("today")} className="rounded-lg border p-3 text-left transition hover:bg-muted/40"><div className="flex items-center gap-2 text-xs text-muted-foreground"><Clock3 className="h-4 w-4"/>Today</div><div className="mt-1 text-2xl font-semibold">{calendar.summary.today}</div></button>
          <button type="button" onClick={() => setView("week")} className="rounded-lg border p-3 text-left transition hover:bg-muted/40"><div className="text-xs text-muted-foreground">This week</div><div className="mt-1 text-2xl font-semibold">{calendar.summary.this_week}</div></button>
          <button type="button" onClick={() => setView("30")} className="rounded-lg border p-3 text-left transition hover:bg-muted/40"><div className="text-xs text-muted-foreground">Next 30 days</div><div className="mt-1 text-2xl font-semibold">{calendar.summary.next_30_days}</div></button>
          <button type="button" onClick={() => setView("90")} className="rounded-lg border p-3 text-left transition hover:bg-muted/40"><div className="text-xs text-muted-foreground">Next 90 days</div><div className="mt-1 text-2xl font-semibold">{calendar.summary.next_90_days}</div></button>
        </div>
        <div className="flex flex-wrap gap-2">{views.map((item) => <Button key={item.id} size="sm" variant={view === item.id ? "default" : "outline"} onClick={() => setView(item.id)}>{item.label}<Badge variant="secondary" className="ml-2">{item.count}</Badge></Button>)}</div>
        <div className="text-xs text-muted-foreground">As of {dateLabel(calendar.as_of)} • {calendar.summary.open} open booking opportunities</div>
      </CardContent>
    </Card>

    {!grouped.length ? <Card><CardContent className="py-14 text-center text-sm text-muted-foreground">No CDAS bookings match this calendar view.</CardContent></Card> : grouped.map(([dateKey, events]) => <Card key={dateKey}>
      <CardHeader className="pb-3"><CardTitle className="text-base">{dateKey === "unscheduled" ? "Unscheduled" : dateLabel(dateKey)}</CardTitle><CardDescription>{events.length} booking record{events.length === 1 ? "" : "s"}</CardDescription></CardHeader>
      <CardContent className="space-y-3">{events.map((event) => <EventCard key={event.id} event={event} busy={busyId === event.id} onBooked={(id) => void markBooked(id)}/>)}</CardContent>
    </Card>)}
  </div>;
}
