"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Download, FileText, RefreshCw, ShieldCheck } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { useTenant } from "@/provider/tenantProvider";
import { COMPANY_MANAGEMENT_ROLES, hasRole } from "@/types/auth";
import { getErrorMessage } from "@/utils/apiError";

const ROOT = "/cdas/government-employees";
const MAX_SELECTION = 20;

type Candidate = { employee_number: string; borrower_id: string | null; status: string; sources: string[]; requires_manual_review: boolean };
type Discovery = { complete: boolean; total: number | null; page: number; items: Candidate[]; message?: string };
type Assessment = { record_id: string; reference: string; employee_number: string; assessed_at: string; decision: string; maximum_affordable_installment: string; proposed_installment: string; status?: string };
type Batch = { batch_id: string; status: string; total_count: number; finished_count: number };
type Preflight = { ready_count: number; review_count: number; minimum_estimated_provider_requests: number; budget_remaining_at_preflight: number; budget_preflight_sufficient: boolean; candidates: { borrower_id: string; employee_number: string; status: string }[] };
type Selection = { borrower_id: string; employee_number: string; proposed_monthly_installment: string };
type RecordedAssessment = { ok: boolean; status: string; borrower_id?: string; record_id?: string; reference?: string; decision?: string; assessed_at?: string; review_reason_codes?: string[] };

async function downloadPdf(path: string, filename: string) {
    // Use the same authenticated client and company scope headers as other LoanHub requests.
    const response = await api.get<Blob>(path, { responseType: "blob" });
    const url = URL.createObjectURL(response.data);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function GovernmentAffordabilityPage() {
    const { activeRole } = useTenant();
    const canManage = hasRole(activeRole, COMPANY_MANAGEMENT_ROLES);
    const [page, setPage] = useState(1);
    const [discovery, setDiscovery] = useState<Discovery | null>(null);
    const [assessments, setAssessments] = useState<Assessment[]>([]);
    const [batches, setBatches] = useState<Batch[]>([]);
    const [selected, setSelected] = useState<Record<string, Selection>>({});
    const [consentReference, setConsentReference] = useState("");
    const [preflight, setPreflight] = useState<Preflight | null>(null);
    const [busy, setBusy] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);
    const [individual, setIndividual] = useState<Selection | null>(null);
    const [authorityConfirmed, setAuthorityConfirmed] = useState(false);
    const [individualResult, setIndividualResult] = useState<RecordedAssessment | null>(null);

    const refresh = useCallback(async () => {
        if (!canManage) return;
        setBusy("refresh");
        setError(null);
        try {
            const [candidates, records, drafts] = await Promise.all([
                api.get<Discovery>(ROOT, { params: { page, page_size: 50 } }),
                api.get<{ items: Assessment[] }>(ROOT + "/affordability-records", { params: { page: 1, page_size: 25 } }),
                api.get<{ items: Batch[] }>(ROOT + "/bulk/batches", { params: { page: 1, page_size: 25 } }),
            ]);
            setDiscovery(candidates.data);
            setAssessments(records.data.items);
            setBatches(drafts.data.items);
        } catch (cause) {
            setError(getErrorMessage(cause, "Unable to load CDAS affordability workspace."));
        } finally {
            setBusy(null);
        }
    }, [canManage, page]);

    useEffect(() => { void refresh(); }, [refresh]);

    function toggle(item: Candidate) {
        if (!item.borrower_id || item.requires_manual_review) return;
        setPreflight(null);
        setSelected(previous => {
            if (previous[item.borrower_id!]) {
                const next = { ...previous };
                delete next[item.borrower_id!];
                return next;
            }
            if (Object.keys(previous).length >= MAX_SELECTION) return previous;
            return { ...previous, [item.borrower_id!]: {
                borrower_id: item.borrower_id!, employee_number: item.employee_number,
                proposed_monthly_installment: "",
            } };
        });
    }

    function changeInstallment(borrowerId: string, amount: string) {
        setPreflight(null);
        setSelected(previous => ({
            ...previous,
            [borrowerId]: { ...previous[borrowerId], proposed_monthly_installment: amount },
        }));
    }

    function selectionPayload(): Selection[] {
        const items = Object.values(selected);
        if (!items.length) throw new Error("Select at least one unambiguous employee.");
        if (items.some(item => !item.proposed_monthly_installment || !Number.isFinite(Number(item.proposed_monthly_installment)) || Number(item.proposed_monthly_installment) <= 0)) {
            throw new Error("Enter a positive proposed monthly instalment for each selected employee.");
        }
        return items;
    }

    function selectIndividual(item: Candidate) {
        if (!item.borrower_id || item.requires_manual_review) return;
        setIndividual({ borrower_id: item.borrower_id, employee_number: item.employee_number, proposed_monthly_installment: "" });
        setAuthorityConfirmed(false);
        setIndividualResult(null);
        setError(null);
    }

    async function assessIndividual() {
        if (!individual || !authorityConfirmed || busy !== null) return;
        const amount = individual.proposed_monthly_installment;
        if (!/^\d+(?:\.\d{1,2})?$/.test(amount) || Number(amount) <= 0 || Number(amount) > 9999999999999) {
            setError("Enter a valid positive instalment in maloti, with no more than two decimal places.");
            return;
        }
        setBusy("individual");
        setError(null);
        setNotice(null);
        setIndividualResult(null);
        try {
            // Each click may cause billable CDAS requests. Never run this on mount,
            // automatically retry it, or call preview followed by record.
            const response = await api.post<RecordedAssessment>(ROOT + "/affordability-records", {
                borrower_id: individual.borrower_id,
                employee_number: individual.employee_number,
                proposed_monthly_installment: amount,
                authorisation_confirmed: true,
            });
            setIndividualResult(response.data);
            setAuthorityConfirmed(false);
            if (response.data.status === "assessment_recorded") {
                setNotice("Assessment saved. Review its decision and download the PDF from the result below.");
                try {
                    const history = await api.get<{ items: Assessment[] }>(
                        ROOT + "/affordability-records", { params: { page: 1, page_size: 25 } },
                    );
                    setAssessments(history.data.items);
                } catch {
                    setNotice("Assessment saved successfully, but history could not refresh. The PDF is available below.");
                }
            } else if (response.data.status === "identity_review_required") {
                setNotice("CDAS identity requires manual review. No affordability assessment was saved.");
            } else {
                setNotice("The assessment did not produce a saved result. Review the status before trying again.");
            }
        } catch (cause) {
            // A network failure does not prove that the provider request failed.
            setError(getErrorMessage(cause, "The assessment result is uncertain. Check saved history before submitting another CDAS request."));
        } finally {
            setBusy(null);
        }
    }

    async function runPreflight() {
        setError(null);
        setNotice(null);
        setBusy("preflight");
        try {
            const response = await api.post<Preflight>(ROOT + "/bulk/preflight", { employees: selectionPayload() });
            setPreflight(response.data);
            setNotice("Preflight completed without contacting CDAS. Review all candidates before saving a draft.");
        } catch (cause) {
            setError(getErrorMessage(cause, "Preflight was not completed."));
        } finally {
            setBusy(null);
        }
    }

    async function saveDraft() {
        setError(null);
        setNotice(null);
        if (!preflight || preflight.review_count || preflight.ready_count !== Object.keys(selected).length) {
            setError("Run a successful preflight for all selected employees first.");
            return;
        }
        if (consentReference.trim().length < 6) {
            setError("Provide the supporting consent evidence reference (at least 6 characters).");
            return;
        }
        setBusy("draft");
        try {
            const request = { employees: selectionPayload(), consent_evidence_reference: consentReference.trim(),
                idempotency_key: crypto.randomUUID() };
            const response = await api.post<{ batch_id: string }>(ROOT + "/bulk/batches", request);
            setSelected({});
            setPreflight(null);
            setNotice("Draft batch " + response.data.batch_id + " saved. Execution is disabled; no CDAS request was sent.");
            await refresh();
        } catch (cause) {
            setError(getErrorMessage(cause, "Draft was not saved."));
        } finally {
            setBusy(null);
        }
    }

    async function cancelDraft(batchId: string) {
        setError(null);
        setBusy("cancel");
        try {
            await api.post(ROOT + "/bulk/batches/" + batchId + "/cancel");
            setNotice("Draft cancelled.");
            await refresh();
        } catch (cause) {
            setError(getErrorMessage(cause, "Could not cancel the draft."));
        } finally {
            setBusy(null);
        }
    }

    async function requestPdf(path: string, filename: string) {
        setError(null);
        setBusy("pdf");
        try {
            await downloadPdf(path, filename);
        } catch (cause) {
            setError(getErrorMessage(cause, "Could not download the report."));
        } finally {
            setBusy(null);
        }
    }

    if (!canManage) {
        return <Alert variant="destructive"><AlertTitle>Management access required</AlertTitle><AlertDescription>Only authorised company managers can access government employee affordability records.</AlertDescription></Alert>;
    }

    return (
        <div className="space-y-6 pb-12">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-2">
                    <Button asChild variant="ghost" size="sm"><Link href="/company/cdas"><ArrowLeft className="mr-2 h-4 w-4" />CDAS workspace</Link></Button>
                    <h1 className="text-2xl font-bold tracking-tight">Government employee affordability</h1>
                    <p className="text-sm text-muted-foreground">Discover employees, review saved assessments and prepare controlled CDAS batches.</p>
                </div>
                <Button variant="outline" onClick={() => void refresh()} disabled={busy !== null}><RefreshCw className="mr-2 h-4 w-4" />Refresh</Button>
            </div>
            <Alert><ShieldCheck className="h-4 w-4" /><AlertTitle>Bulk execution is disabled</AlertTitle><AlertDescription>Drafts do not contact CDAS or approve loans. A consent reference is not proof of consent; evidence must be verified before future execution.</AlertDescription></Alert>
            {error && <Alert variant="destructive"><AlertTitle>Action unsuccessful</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
            {notice && <Alert><AlertDescription>{notice}</AlertDescription></Alert>}
            <div className="grid gap-4 sm:grid-cols-3">
                <Card><CardHeader><CardDescription>Employee candidates</CardDescription><CardTitle>{discovery?.total ?? "—"}</CardTitle></CardHeader></Card>
                <Card><CardHeader><CardDescription>Selected employees</CardDescription><CardTitle>{Object.keys(selected).length} / {MAX_SELECTION}</CardTitle></CardHeader></Card>
                <Card><CardHeader><CardDescription>Recent saved assessments</CardDescription><CardTitle>{assessments.length}</CardTitle></CardHeader></Card>
            </div>
            <Card>
                <CardHeader><CardTitle>1. Select employees</CardTitle><CardDescription>Only company-linked records with no known identity conflict can be selected. The CDAS identity must still be verified when an assessment is performed.</CardDescription></CardHeader>
                <CardContent className="space-y-3">
                    {discovery && !discovery.complete && <Alert variant="destructive"><AlertDescription>{discovery.message || "Discovery is incomplete. Do not treat this as the full employee register."}</AlertDescription></Alert>}
                    {discovery?.items.map(item => {
                        const chosen = item.borrower_id ? selected[item.borrower_id] : undefined;
                        return <div key={item.employee_number} className="flex flex-wrap items-center gap-3 rounded-xl border p-3">
                            <input type="checkbox" aria-label={"Select " + item.employee_number} checked={Boolean(chosen)} disabled={!item.borrower_id || item.requires_manual_review || (!chosen && Object.keys(selected).length >= MAX_SELECTION)}
                                onChange={() => toggle(item)} />
                            <div className="min-w-36 flex-1"><p className="font-semibold">{item.employee_number}</p><p className="text-xs text-muted-foreground">{item.borrower_id || "Multiple borrowers / review required"}</p></div>
                            <Badge variant="outline">{item.status.replaceAll("_", " ")}</Badge>
                            {item.borrower_id && !item.requires_manual_review && <Button size="sm" variant="outline" disabled={busy !== null}
                                onClick={() => selectIndividual(item)}>Assess individually</Button>}
                            {chosen && <div className="w-44"><Label htmlFor={"payment-" + item.borrower_id}>Proposed instalment (M)</Label><Input id={"payment-" + item.borrower_id} type="number" min="0.01" step="0.01" value={chosen.proposed_monthly_installment}
                                onChange={event => changeInstallment(item.borrower_id!, event.target.value)} /></div>}
                        </div>;
                    })}
                    {!discovery?.items.length && <p className="text-sm text-muted-foreground">No employee candidates on this page.</p>}
                    <div className="flex items-center justify-between">
                        <Button variant="outline" disabled={page <= 1 || busy !== null} onClick={() => setPage(p => p - 1)}>Previous</Button>
                        <span className="text-sm text-muted-foreground">Page {page}</span>
                        <Button variant="outline" disabled={busy !== null || !discovery?.complete || (discovery.items.length < 50)} onClick={() => setPage(p => p + 1)}>Next</Button>
                    </div>
                </CardContent>
            </Card>
            <Card>
                <CardHeader><CardTitle>2. Individual CDAS assessment</CardTitle>
                    <CardDescription>Verify one employee against live CDAS, apply LoanHub's configured affordability policy, and save a report. This may consume provider credits. It never approves a loan.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    {!individual && <p className="text-sm text-muted-foreground">Choose “Assess individually” beside an employee above to begin.</p>}
                    {individual && <>
                        <div className="rounded-xl border p-3 text-sm">
                            <p className="font-semibold">Employee: {individual.employee_number}</p>
                            <p className="break-all text-xs text-muted-foreground">Borrower: {individual.borrower_id}</p>
                        </div>
                        <div className="max-w-xs space-y-2">
                            <Label htmlFor="single-installment">Proposed monthly instalment (M)</Label>
                            <Input id="single-installment" type="number" min="0.01" step="0.01"
                                value={individual.proposed_monthly_installment}
                                onChange={event => {
                                    setIndividual({ ...individual, proposed_monthly_installment: event.target.value });
                                    setIndividualResult(null);
                                    setAuthorityConfirmed(false);
                                }} />
                        </div>
                        <label className="flex items-start gap-3 text-sm">
                            <input type="checkbox" className="mt-1" checked={authorityConfirmed}
                                onChange={event => setAuthorityConfirmed(event.target.checked)} />
                            <span>I confirm I have lawful authority to request this employee's CDAS identity and affordability data. I understand this is a billable live provider lookup, not a loan approval.</span>
                        </label>
                        <Button disabled={busy !== null || !authorityConfirmed || !individual.proposed_monthly_installment}
                            onClick={() => void assessIndividual()}>Verify, assess and save report</Button>
                    </>}
                    {individualResult?.status === "identity_review_required" && <Alert variant="destructive">
                        <AlertTitle>Identity mismatch — manual review</AlertTitle>
                        <AlertDescription>{(individualResult.review_reason_codes || []).join(", ") || "Identity details do not match."} No assessment was saved.</AlertDescription>
                    </Alert>}
                    {individualResult?.status === "assessment_recorded" && <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border p-4">
                        <div className="space-y-1">
                            <p className="font-semibold">{individualResult.reference}</p>
                            <p className="text-sm">Policy decision: <strong>{individualResult.decision || "Review"}</strong></p>
                            <p className="text-xs text-muted-foreground">Saved {individualResult.assessed_at || "now"} · Not a lending approval</p>
                        </div>
                        <Button variant="outline" disabled={busy !== null || !individualResult.record_id}
                            onClick={() => void requestPdf(ROOT + "/affordability-records/" + individualResult.record_id + "/pdf",
                                "affordability-" + individualResult.record_id + ".pdf")}>
                            <FileText className="mr-2 h-4 w-4" />Download assessment PDF
                        </Button>
                    </div>}
                </CardContent>
            </Card>
            <Card>
                <CardHeader><CardTitle>3. Validate and save a draft</CardTitle><CardDescription>Preflight checks selected records and estimates CDAS usage without contacting the provider.</CardDescription></CardHeader>
                <CardContent className="space-y-4">
                    <Button onClick={() => void runPreflight()} disabled={busy !== null || !Object.keys(selected).length}>Run safe preflight</Button>
                    {preflight && <div className="rounded-xl border p-4 text-sm space-y-2">
                        <p><strong>Ready:</strong> {preflight.ready_count} · <strong>Require review:</strong> {preflight.review_count}</p>
                        <p>Minimum estimated CDAS requests: {preflight.minimum_estimated_provider_requests} · Current remaining budget: {preflight.budget_remaining_at_preflight}</p>
                        {!preflight.budget_preflight_sufficient && <p className="text-destructive">Provider budget may be insufficient for later execution.</p>}
                        {preflight.candidates.filter(item => item.status !== "ready_for_live_verification").map(item => <p key={item.borrower_id}>{item.employee_number}: {item.status.replaceAll("_", " ")}</p>)}
                    </div>}
                    <div className="max-w-lg space-y-2"><Label htmlFor="consent-reference">Consent evidence reference</Label><Input id="consent-reference" value={consentReference} onChange={event => setConsentReference(event.target.value)} placeholder="Reference to consent documentation" /></div>
                    <Button disabled={busy !== null || !preflight || preflight.review_count > 0 || !preflight.ready_count} onClick={() => void saveDraft()}>Save draft batch (no CDAS calls)</Button>
                </CardContent>
            </Card>
            <Card>
                <CardHeader><CardTitle>4. Draft batches</CardTitle><CardDescription>Saved company batches. Execution is disabled.</CardDescription></CardHeader>
                <CardContent className="space-y-3">
                    {batches.map(batch => <div key={batch.batch_id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3">
                        <div><p className="text-sm font-medium">{batch.batch_id}</p><p className="text-xs text-muted-foreground">{batch.total_count} employees · {batch.finished_count} processed · {batch.status}</p></div>
                        {batch.status === "draft" && <Button variant="outline" size="sm" disabled={busy !== null} onClick={() => void cancelDraft(batch.batch_id)}>Cancel draft</Button>}
                    </div>)}
                    {!batches.length && <p className="text-sm text-muted-foreground">No saved batches yet.</p>}
                </CardContent>
            </Card>
            <Card>
                <CardHeader><CardTitle>5. Affordability assessment history</CardTitle><CardDescription>Saved assessments only. Downloading reports does not send new CDAS requests.</CardDescription></CardHeader>
                <CardContent className="space-y-3">
                    <Button variant="outline" disabled={busy !== null} onClick={() => void requestPdf(ROOT + "/affordability-summary.pdf", "government-affordability-summary.pdf")}><Download className="mr-2 h-4 w-4" />Consolidated management PDF</Button>
                    {assessments.map(item => <div key={item.record_id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3">
                        <div><p className="text-sm font-medium">{item.reference || item.record_id}</p><p className="text-xs text-muted-foreground">{item.employee_number || "Integrity review"} · {item.decision || item.status || "Review"} · {item.assessed_at || "Date unavailable"}</p></div>
                        {!item.status && <Button size="sm" variant="outline" disabled={busy !== null} onClick={() => void requestPdf(ROOT + "/affordability-records/" + item.record_id + "/pdf", "affordability-" + item.record_id + ".pdf")}><FileText className="mr-2 h-4 w-4" />PDF</Button>}
                    </div>)}
                    {!assessments.length && <p className="text-sm text-muted-foreground">No saved assessments yet.</p>}
                </CardContent>
            </Card>
        </div>
    );
}
