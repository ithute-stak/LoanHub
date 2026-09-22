"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BadgeCheck,
  BellRing,
  CalendarClock,
  CheckCircle2,
  Database,
  RefreshCw,
  Search,
  ShieldCheck,
} from "lucide-react";

import { cdasBookingApi } from "@/api/cdasBooking";
import { cdasOfficialApi } from "@/api/cdasOfficial";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type {
  CdasAnalysisRecord,
  CdasBookingOpportunity,
} from "@/types/cdasBooking";
import type {
  CdasOfficialDeduction,
  CdasOfficialRefreshResponse,
} from "@/types/cdasOfficial";

type Tab = "official" | "history" | "upcoming" | "book-now" | "booked";

const DEDUCTION_STATUS: Record<string, string> = {
  "1": "Registered",
  "2": "Reserved",
  "3": "Reviewed",
  "4": "Approved",
  "5": "Active",
  "6": "Cancelled",
  "7": "Settled",
  "8": "Auto-settled / Expired",
  "9": "Deleted",
  "10": "Changed",
};

const DEDUCTION_TYPE: Record<string, string> = {
  "1": "Loan",
  "2": "Policy",
};

function money(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return `M ${Number(value).toLocaleString("en-ZA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function dateLabel(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-ZA", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function dateTimeLabel(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("en-ZA", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function errorMessage(error: any, fallback: string) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && typeof detail.message === "string") {
    return detail.message;
  }
  return error?.message || fallback;
}

function statusLabel(value: number | string | null) {
  if (value === null || value === undefined) return "—";
  const key = String(value).trim();
  return DEDUCTION_STATUS[key] || key;
}

function typeLabel(value: number | string | null) {
  if (value === null || value === undefined) return "—";
  const key = String(value).trim();
  return DEDUCTION_TYPE[key] || key;
}

function DeductionTable({ rows, title }: { rows: CdasOfficialDeduction[]; title: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{rows.length} deduction record{rows.length === 1 ? "" : "s"} returned by CDAS.</CardDescription>
      </CardHeader>
      <CardContent>
        {!rows.length ? (
          <div className="py-8 text-center text-sm text-muted-foreground">No deductions returned for this query.</div>
        ) : (
          <div className="overflow-x-auto rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Item / reference</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Deduction</TableHead>
                  <TableHead className="text-right">Principal</TableHead>
                  <TableHead>Effective</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row, index) => (
                  <TableRow key={`${row.deduction_id ?? "row"}-${row.reference_no ?? index}-${index}`}>
                    <TableCell>
                      <div className="font-medium">{row.item_code || "—"}</div>
                      <div className="text-xs text-muted-foreground">{row.reference_no || `Record ${index + 1}`}</div>
                    </TableCell>
                    <TableCell>{typeLabel(row.deduction_type)}</TableCell>
                    <TableCell><Badge variant="secondary">{statusLabel(row.deduction_status)}</Badge></TableCell>
                    <TableCell className="text-right font-medium">{money(row.deduction_amount)}</TableCell>
                    <TableCell className="text-right">{money(row.principal_amount)}</TableCell>
                    <TableCell>{row.effective_date || row.effective_month || "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function CdasBookingPage() {
  const [tab, setTab] = useState<Tab>("official");
  const [employeeNo, setEmployeeNo] = useState("");
  const [ownStatus, setOwnStatus] = useState("");
  const [officialResult, setOfficialResult] = useState<CdasOfficialRefreshResponse | null>(null);
  const [officialLoading, setOfficialLoading] = useState(false);
  const [error, setError] = useState("");
  const [items, setItems] = useState<CdasBookingOpportunity[]>([]);
  const [analyses, setAnalyses] = useState<CdasAnalysisRecord[]>([]);
  const [localLoading, setLocalLoading] = useState(false);

  const refreshLoanHub = useCallback(async () => {
    setLocalLoading(true);
    try {
      const [opportunities, history] = await Promise.all([
        cdasBookingApi.listOpportunities(),
        cdasBookingApi.listAnalyses(),
      ]);
      setItems(opportunities.items);
      setAnalyses(history.items);
    } finally {
      setLocalLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshLoanHub().catch(() => undefined);
  }, [refreshLoanHub]);

  const upcoming = useMemo(() => items.filter((item) => item.state === "UPCOMING"), [items]);
  const bookNow = useMemo(() => items.filter((item) => item.state === "BOOK_NOW"), [items]);
  const booked = useMemo(() => items.filter((item) => item.state === "BOOKED"), [items]);

  async function refreshFromCdas() {
    const employee = employeeNo.trim();
    if (!employee) {
      setError("Enter the employee number used by CDAS.");
      return;
    }

    const status = ownStatus.trim() ? Number(ownStatus) : undefined;
    if (status !== undefined && (!Number.isInteger(status) || status < 1 || status > 10)) {
      setError("Own-deduction status must be a CDAS status code from 1 to 10.");
      return;
    }

    setOfficialLoading(true);
    setError("");
    try {
      const response = await cdasOfficialApi.refreshEmployee({
        employee_no: employee,
        own_deduction_status: status,
      });
      setOfficialResult(response);
      await refreshLoanHub();
    } catch (requestError: any) {
      setError(errorMessage(requestError, "CDAS could not be refreshed."));
    } finally {
      setOfficialLoading(false);
    }
  }

  async function markBooked(id: string) {
    setError("");
    try {
      await cdasBookingApi.markBooked(id);
      await refreshLoanHub();
    } catch (requestError: any) {
      setError(errorMessage(requestError, "Could not mark the booking complete."));
    }
  }

  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: "official", label: "Official CDAS" },
    { id: "history", label: "Analysis History", count: analyses.length },
    { id: "upcoming", label: "Upcoming", count: upcoming.length },
    { id: "book-now", label: "Book Now", count: bookNow.length },
    { id: "booked", label: "Booked", count: booked.length },
  ];

  function History() {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-start gap-3">
            <div className="rounded-lg border bg-muted/40 p-2"><Database className="h-5 w-5" /></div>
            <div>
              <CardTitle>CDAS Analysis History</CardTitle>
              <CardDescription>
                Official API refreshes are archived as immutable structured snapshots. Refreshing unchanged CDAS data reuses the existing version; materially changed data creates a new version.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {!analyses.length ? (
            <div className="py-12 text-center text-sm text-muted-foreground">No CDAS snapshots have been archived yet.</div>
          ) : (
            <div className="overflow-x-auto rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Archived</TableHead>
                    <TableHead>Client</TableHead>
                    <TableHead>Employee no.</TableHead>
                    <TableHead>Affordability</TableHead>
                    <TableHead>Active deductions</TableHead>
                    <TableHead>Total deductions</TableHead>
                    <TableHead>State</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {analyses.map((record) => (
                    <TableRow key={record.id}>
                      <TableCell className="whitespace-nowrap">
                        <div>{dateTimeLabel(record.analyzed_at)}</div>
                        <div className="text-xs text-muted-foreground">{record.analyzed_by_name || "Company user"}</div>
                      </TableCell>
                      <TableCell className="font-medium">{record.client_name || "CDAS employee"}</TableCell>
                      <TableCell>{record.employee_no || record.client_reference || "—"}</TableCell>
                      <TableCell>{money(record.assessed_available_amount)}</TableCell>
                      <TableCell>{money(record.reported_active_monthly_deductions)}</TableCell>
                      <TableCell>{money(record.total_monthly_deductions)}</TableCell>
                      <TableCell>
                        <Badge variant={record.decision === "REVIEW_REQUIRED" ? "outline" : "secondary"}>
                          {record.decision === "REVIEW_REQUIRED" ? "Read snapshot" : record.decision.replaceAll("_", " ")}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  function Queue({ data, allowBook = false }: { data: CdasBookingOpportunity[]; allowBook?: boolean }) {
    if (!data.length) {
      return <Card><CardContent className="py-12 text-center text-sm text-muted-foreground">No records in this queue.</CardContent></Card>;
    }
    return (
      <div className="grid gap-4 lg:grid-cols-2">
        {data.map((item) => (
          <Card key={item.id} className={item.state === "BOOK_NOW" ? "border-primary/40" : ""}>
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle className="text-lg">{item.client_name || item.client_reference || "CDAS client"}</CardTitle>
                  <CardDescription>{item.opportunity_agency_name || "Existing booking monitor"}</CardDescription>
                </div>
                <Badge variant={item.state === "BOOK_NOW" ? "default" : "secondary"}>{item.state.replaceAll("_", " ")}</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div><div className="text-muted-foreground">Deduction</div><div className="font-semibold">{money(item.opportunity_deduction_amount)}</div></div>
                <div><div className="text-muted-foreground">Booking opens</div><div className="font-semibold">{dateLabel(item.booking_open_date)}</div></div>
                <div><div className="text-muted-foreground">Alerts start</div><div>{dateLabel(item.alert_start_date)}</div></div>
                <div><div className="text-muted-foreground">Expiry</div><div>{dateLabel(item.opportunity_expiry_date)}</div></div>
              </div>
              {item.state === "UPCOMING" && (
                <Alert>
                  <BellRing className="h-4 w-4" />
                  <AlertTitle>{item.days_until_booking} day(s) until booking</AlertTitle>
                  <AlertDescription>Existing LoanHub booking monitoring remains active.</AlertDescription>
                </Alert>
              )}
              {allowBook && (
                <Button className="w-full" onClick={() => void markBooked(item.id)}>
                  <CheckCircle2 className="mr-2 h-4 w-4" />Mark booking complete
                </Button>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  const snapshot = officialResult?.snapshot;
  const profile = snapshot?.profile;

  return (
    <div className="space-y-6 pb-10">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <CalendarClock className="h-6 w-6" />
            <h1 className="text-2xl font-semibold tracking-tight">CDAS Booking Centre</h1>
          </div>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            LoanHub now reads employee identity, affordability and deductions through the official CDAS Third Party API. CDAS credentials and tokens remain on the LoanHub backend.
          </p>
        </div>
        <Button variant="outline" disabled={localLoading} onClick={() => void refreshLoanHub()}>
          <RefreshCw className={`mr-2 h-4 w-4 ${localLoading ? "animate-spin" : ""}`} />
          Refresh LoanHub lists
        </Button>
      </div>

      <div className="flex flex-wrap gap-2 rounded-xl border bg-muted/30 p-2">
        {tabs.map((item) => (
          <Button key={item.id} variant={tab === item.id ? "default" : "ghost"} onClick={() => setTab(item.id)}>
            {item.label}
            {item.count !== undefined && <Badge variant="secondary" className="ml-2">{item.count}</Badge>}
          </Button>
        ))}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>CDAS action failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {tab === "official" && (
        <div className="space-y-5">
          <Alert>
            <ShieldCheck className="h-4 w-4" />
            <AlertTitle>Explicit refresh only</AlertTitle>
            <AlertDescription>
              Enter an employee number and press Refresh from CDAS. LoanHub does not call CDAS when this page opens, changes tab, or re-renders. This keeps the documented daily request allowance under control.
            </AlertDescription>
          </Alert>

          <Card>
            <CardHeader>
              <CardTitle>Read employee from CDAS</CardTitle>
              <CardDescription>
                The refresh performs employee identification, affordability and all-deductions reads. Supplying an own-deduction status also performs the documented company-deduction query for that status.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
                <div className="space-y-2">
                  <Label htmlFor="cdas-employee-no">CDAS employee number</Label>
                  <Input
                    id="cdas-employee-no"
                    value={employeeNo}
                    onChange={(event) => setEmployeeNo(event.target.value)}
                    placeholder="Enter EmployeeNo"
                    autoComplete="off"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="cdas-own-status">Our deduction status (optional)</Label>
                  <Input
                    id="cdas-own-status"
                    type="number"
                    min={1}
                    max={10}
                    value={ownStatus}
                    onChange={(event) => setOwnStatus(event.target.value)}
                    placeholder="e.g. 5 = Active"
                  />
                </div>
              </div>
              <LoadingButton loading={officialLoading} loadingText="Reading CDAS..." onClick={refreshFromCdas}>
                <Search className="h-4 w-4" />Refresh from CDAS
              </LoadingButton>
            </CardContent>
          </Card>

          {officialResult && snapshot && profile && (
            <>
              <Alert className="border-emerald-500/40 bg-emerald-50/50 dark:bg-emerald-950/20">
                <BadgeCheck className="h-4 w-4" />
                <AlertTitle>{officialResult.archive.created ? "New official CDAS version archived" : "CDAS data unchanged"}</AlertTitle>
                <AlertDescription>
                  {officialResult.archive.created
                    ? "LoanHub created a new immutable Analysis History version because this material CDAS snapshot was not already stored."
                    : "LoanHub reused the existing Analysis History version instead of creating a duplicate."}
                  {officialResult.checked_at ? ` Checked ${dateTimeLabel(officialResult.checked_at)}.` : ""}
                </AlertDescription>
              </Alert>

              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <Card><CardHeader className="pb-2"><CardDescription>Employee</CardDescription><CardTitle className="text-xl">{profile.full_name || "CDAS employee"}</CardTitle></CardHeader><CardContent className="text-sm text-muted-foreground">{profile.employee_no || "—"}</CardContent></Card>
                <Card><CardHeader className="pb-2"><CardDescription>Available deduction</CardDescription><CardTitle className="text-xl">{money(snapshot.capacity.assessed_available_amount)}</CardTitle></CardHeader><CardContent className="text-sm text-muted-foreground">Direct CDAS affordability response</CardContent></Card>
                <Card><CardHeader className="pb-2"><CardDescription>Active monthly deductions</CardDescription><CardTitle className="text-xl">{money(snapshot.reported_active_monthly_deductions)}</CardTitle></CardHeader><CardContent className="text-sm text-muted-foreground">Status 5 / Active rows</CardContent></Card>
                <Card><CardHeader className="pb-2"><CardDescription>Total returned deductions</CardDescription><CardTitle className="text-xl">{money(snapshot.total_monthly_deductions)}</CardTitle></CardHeader><CardContent className="text-sm text-muted-foreground">{snapshot.deductions.length} row(s)</CardContent></Card>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle>Employee details</CardTitle>
                  <CardDescription>Values returned by the official employee details endpoint.</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
                  <div><div className="text-muted-foreground">Name</div><div className="font-medium">{profile.name || "—"}</div></div>
                  <div><div className="text-muted-foreground">Surname</div><div className="font-medium">{profile.surname || "—"}</div></div>
                  <div><div className="text-muted-foreground">Date of birth</div><div className="font-medium">{dateLabel(profile.date_of_birth)}</div></div>
                  <div><div className="text-muted-foreground">Department</div><div className="font-medium">{profile.department || "—"}</div></div>
                  <div><div className="text-muted-foreground">Joining date</div><div className="font-medium">{dateLabel(profile.joining_date)}</div></div>
                  <div><div className="text-muted-foreground">Termination date</div><div className="font-medium">{dateLabel(profile.end_date)}</div></div>
                  <div><div className="text-muted-foreground">CDAS status</div><div className="font-medium">{snapshot.capacity.status.replaceAll("_", " ")}</div></div>
                  <div><div className="text-muted-foreground">API contract</div><div className="font-medium">CDAS v{snapshot.source_version}</div></div>
                </CardContent>
              </Card>

              <DeductionTable rows={snapshot.deductions} title="All third-party deductions" />
              {snapshot.official_api.own_deduction_status !== null && (
                <DeductionTable rows={snapshot.own_bookings} title={`Our deductions — status ${snapshot.official_api.own_deduction_status}`} />
              )}

              <Alert>
                <ShieldCheck className="h-4 w-4" />
                <AlertTitle>Read does not mean approve</AlertTitle>
                <AlertDescription>{snapshot.decision_message}</AlertDescription>
              </Alert>
            </>
          )}
        </div>
      )}

      {tab === "history" && <History />}
      {tab === "upcoming" && <Queue data={upcoming} />}
      {tab === "book-now" && <Queue data={bookNow} allowBook />}
      {tab === "booked" && <Queue data={booked} />}
    </div>
  );
}
