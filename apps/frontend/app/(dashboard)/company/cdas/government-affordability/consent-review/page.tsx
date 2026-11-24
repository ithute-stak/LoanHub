"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Download, RefreshCw, ShieldCheck } from "lucide-react";

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
type ConsentRow = {
    evidence_id: string;
    borrower_id: string;
    employee_number: string;
    reference: string;
    status: string;
    document_id: string;
    managed_file_id: string | null;
};
type Review = {
    evidenceId: string;
    managedFileId: string;
    digest: string;
    confirmedDocument: boolean;
    confirmedIdentity: boolean;
    confirmedConsent: boolean;
    confirmedPurpose: boolean;
    reason: string;
    expiry: string;
};

function todayPlus(days: number): string {
    const date = new Date(Date.now() + days * 86400000);
    return date.toISOString().slice(0, 10);
}

function toHex(bytes: ArrayBuffer): string {
    return Array.from(new Uint8Array(bytes)).map(byte => byte.toString(16).padStart(2, "0")).join("");
}

export default function GovernmentCdasConsentReviewPage() {
    const { activeRole } = useTenant();
    const canManage = hasRole(activeRole, COMPANY_MANAGEMENT_ROLES);
    const [rows, setRows] = useState<ConsentRow[]>([]);
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);
    const [review, setReview] = useState<Review | null>(null);
    const [decisionEvidenceId, setDecisionEvidenceId] = useState<string | null>(null);
    const [decisionReason, setDecisionReason] = useState("");

    const [busy, setBusy] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);

    const refresh = useCallback(async () => {
        if (!canManage) return;
        setBusy("refresh");
        setError(null);
        try {
            const response = await api.get<{ total: number; items: ConsentRow[] }>(
                ROOT + "/consent-evidence", { params: { page, page_size: 25 } },
            );
            setRows(response.data.items);
            setTotal(response.data.total);
        } catch (cause) {
            setError(getErrorMessage(cause, "Could not load the consent-review register."));
        } finally {
            setBusy(null);
        }
    }, [canManage, page]);

    useEffect(() => { void refresh(); }, [refresh]);

    async function downloadForReview(row: ConsentRow) {
        if (!row.managed_file_id || row.status !== "pending") {
            setError("Only pending evidence with a managed file can be reviewed.");
            return;
        }
        setBusy("document");
        setError(null);
        setReview(null);
        try {
            // Authentication and tenant access are enforced by LoanHub's file API.
            // Do not use a raw storage URL, external link, or public share.
            const result = await api.get<Blob>(
                "/files/" + encodeURIComponent(row.managed_file_id) + "/download",
                { responseType: "blob" },
            );
            const data = result.data;
            if (data.size === 0 || data.size > 20 * 1024 * 1024) {
                throw new Error("Consent evidence exceeds review size limits.");
            }
            const digest = toHex(await crypto.subtle.digest("SHA-256", await data.arrayBuffer()));
            const objectUrl = URL.createObjectURL(data);
            const anchor = document.createElement("a");
            anchor.href = objectUrl;
            anchor.download = "cdas-consent-review-" + row.evidence_id + ".pdf";
            document.body.appendChild(anchor);
            anchor.click();
            anchor.remove();
            window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
            setReview({
                evidenceId: row.evidence_id,
                managedFileId: row.managed_file_id,
                digest,
                confirmedDocument: false,
                confirmedIdentity: false,
                confirmedConsent: false,
                confirmedPurpose: false,
                reason: "",
                expiry: todayPlus(30),
            });
            setNotice("File retrieved. Open it, inspect the contents and confirm the correct borrower and purpose.");
        } catch (cause) {
            setError(getErrorMessage(cause, "Unable to retrieve the protected consent document."));
        } finally {
            setBusy(null);
        }
    }

    async function submitDecision(row: ConsentRow, decision: "approve" | "reject" | "revoke") {
        if (decision !== "approve" && (decisionEvidenceId !== row.evidence_id || decisionReason.trim().length < 8)) {
            setError("A reason of at least 8 characters is required for this decision.");
            return;
        }
        setBusy("decision");
        setError(null);
        setNotice(null);
        try {
            if (decision === "approve") {
                if (!review || review.evidenceId !== row.evidence_id || review.managedFileId !== row.managed_file_id) {
                    throw new Error("Retrieve the exact consent document before approval.");
                }
                if (!review.confirmedDocument || !review.confirmedIdentity ||
                    !review.confirmedConsent || !review.confirmedPurpose || review.reason.trim().length < 12) {
                    throw new Error("Complete all independent review confirmations and the reason.");
                }
                if (!review.expiry) throw new Error("An approval expiry is required.");
                await api.post(ROOT + "/consent-evidence/" + encodeURIComponent(row.evidence_id) + "/approve", {
                    reviewed_document_sha256: review.digest,
                    document_reviewed: true,
                    borrower_identity_checked: true,
                    borrower_consent_checked: true,
                    purpose_confirmed: true,
                    reason: review.reason.trim(),
                    expires_at: new Date(review.expiry + "T23:59:59.000Z").toISOString(),
                });
                setNotice("Consent evidence approved and audited. This did not contact CDAS.");
            } else {
                await api.post(ROOT + "/consent-evidence/" + encodeURIComponent(row.evidence_id) + "/decision", {
                    decision, reason: decisionReason.trim(),
                });
                setNotice(decision === "revoke"
                    ? "Consent evidence revoked. Subsequent CDAS lookups require a new valid consent review."
                    : "Consent evidence rejected. No CDAS request was made.");
            }
            setDecisionEvidenceId(null);
            setDecisionReason("");
            setReview(null);
            await refresh();
        } catch (cause) {
            setError(getErrorMessage(cause, "Consent review could not be saved."));
        } finally {
            setBusy(null);
        }
    }

    if (!canManage) {
        return <Alert variant="destructive"><AlertTitle>Company management access required</AlertTitle><AlertDescription>You cannot review CDAS consent evidence with this role.</AlertDescription></Alert>;
    }

    return <div className="space-y-5 pb-12">
        <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-2">
                <Button asChild variant="ghost" size="sm"><Link href="/company/cdas/government-affordability"><ArrowLeft className="mr-2 h-4 w-4" />Affordability</Link></Button>
                <h1 className="text-2xl font-bold tracking-tight">CDAS consent review</h1>
                <p className="text-sm text-muted-foreground">Independent, company-scoped review of borrower consent documents.</p>
            </div>
            <Button variant="outline" disabled={busy !== null} onClick={() => void refresh()}><RefreshCw className="mr-2 h-4 w-4" />Refresh</Button>
        </div>
        <Alert><ShieldCheck className="h-4 w-4" /><AlertTitle>Review before approval</AlertTitle>
            <AlertDescription>Download and inspect the real document. Confirm that the borrower authorised this exact CDAS affordability purpose. A matching checksum alone does not prove legal consent. Approval does not contact CDAS or approve any loan.</AlertDescription>
        </Alert>
        {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
        {notice && <Alert><AlertDescription>{notice}</AlertDescription></Alert>}
        <Card>
            <CardHeader><CardTitle>Evidence queue</CardTitle><CardDescription>{total} record(s), page {page}. Only pending evidence can be approved.</CardDescription></CardHeader>
            <CardContent className="space-y-3">
                {rows.map(row => <div key={row.evidence_id} className="space-y-3 rounded-xl border p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0 space-y-1 text-sm">
                            <p className="font-semibold">{row.reference}</p>
                            <p>Employee number: {row.employee_number}</p>
                            <p className="break-all text-xs text-muted-foreground">Borrower: {row.borrower_id}</p>
                            <p className="break-all text-xs text-muted-foreground">Managed file: {row.managed_file_id || "Not linked"}</p>
                        </div>
                        <Badge variant="outline">{row.status.replaceAll("_", " ")}</Badge>
                    </div>
                    {row.status === "pending" && <div className="flex flex-wrap gap-2">
                        <Button size="sm" variant="outline" disabled={busy !== null || !row.managed_file_id} onClick={() => void downloadForReview(row)}>
                            <Download className="mr-2 h-4 w-4" />Download evidence
                        </Button>
                        <Button size="sm" variant="outline" disabled={busy !== null}
                            onClick={() => { setDecisionEvidenceId(row.evidence_id); setDecisionReason(""); setReview(null); setError(null); }}>Reject consent</Button>
                    </div>}
                    {row.status === "approved" && <Button size="sm" variant="destructive" disabled={busy !== null}
                        onClick={() => { setDecisionEvidenceId(row.evidence_id); setDecisionReason(""); setReview(null); setError(null); }}>
                        Revoke consent
                    </Button>}
                    {(row.status === "pending" || row.status === "approved") && decisionEvidenceId === row.evidence_id &&
                        <div className="space-y-3 rounded-lg border p-3">
                            <p className="text-sm font-medium">{row.status === "approved" ? "Revoke approved consent" : "Reject pending evidence"}</p>
                            <p className="text-xs text-muted-foreground">This decision is audited. A revoked or rejected record cannot authorise further CDAS requests.</p>
                            <Label htmlFor={"decision-reason-" + row.evidence_id}>Decision reason</Label>
                            <Input id={"decision-reason-" + row.evidence_id} value={decisionReason} maxLength={400}
                                onChange={event => setDecisionReason(event.target.value)}
                                placeholder={row.status === "approved" ? "Why is consent being revoked?" : "Why is this evidence rejected?"} />
                            <div className="flex flex-wrap gap-2">
                                <Button variant={row.status === "approved" ? "destructive" : "default"} size="sm"
                                    disabled={busy !== null || decisionReason.trim().length < 8}
                                    onClick={() => void submitDecision(row, row.status === "approved" ? "revoke" : "reject")}>
                                    Confirm {row.status === "approved" ? "revocation" : "rejection"}
                                </Button>
                                <Button size="sm" variant="outline" disabled={busy !== null}
                                    onClick={() => { setDecisionEvidenceId(null); setDecisionReason(""); }}>Cancel</Button>
                            </div>
                        </div>}
                    {row.status === "pending" && review?.evidenceId === row.evidence_id && <div className="space-y-3 rounded-lg border p-3">
                        <p className="text-sm font-medium">Reviewing downloaded document</p>
                        <p className="break-all font-mono text-xs">SHA-256: {review.digest}</p>
                        {([
                            ["confirmedDocument", "I inspected the downloaded document and its contents."],
                            ["confirmedIdentity", "The borrower identity and employee number match this application."],
                            ["confirmedConsent", "The borrower explicitly authorised this CDAS lookup."],
                            ["confirmedPurpose", "The consent covers CDAS government-employee affordability."],
                        ] as const).map(([key, text]) =>
                            <label key={key} className="flex items-start gap-2 text-sm">
                                <input type="checkbox" checked={review[key]} onChange={event => setReview({ ...review, [key]: event.target.checked })} />
                                <span>{text}</span>
                            </label>,
                        )}
                        <div className="grid gap-3 sm:grid-cols-2">
                            <div className="space-y-1">
                                <Label htmlFor={"expiry-" + row.evidence_id}>Expires on</Label>
                                <Input id={"expiry-" + row.evidence_id} type="date" min={todayPlus(0)} max={todayPlus(89)}
                                    value={review.expiry} onChange={event => setReview({ ...review, expiry: event.target.value })} />
                            </div>
                            <div className="space-y-1">
                                <Label htmlFor={"reason-" + row.evidence_id}>Review reason / evidence notes</Label>
                                <Input id={"reason-" + row.evidence_id} value={review.reason} maxLength={400}
                                    onChange={event => setReview({ ...review, reason: event.target.value })} placeholder="What confirms borrower consent?" />
                            </div>
                        </div>
                        <Button disabled={busy !== null || !review.confirmedDocument || !review.confirmedIdentity ||
                            !review.confirmedConsent || !review.confirmedPurpose || review.reason.trim().length < 12}
                            onClick={() => void submitDecision(row, "approve")}>Approve this consent evidence</Button>
                    </div>}
                </div>)}
                {!rows.length && <p className="text-sm text-muted-foreground">No consent evidence records on this page.</p>}
                <div className="flex items-center justify-between">
                    <Button variant="outline" disabled={page <= 1 || busy !== null} onClick={() => setPage(value => value - 1)}>Previous</Button>
                    <span className="text-sm text-muted-foreground">Page {page}</span>
                    <Button variant="outline" disabled={busy !== null || page * 25 >= total} onClick={() => setPage(value => value + 1)}>Next</Button>
                </div>
            </CardContent>
        </Card>
    </div>;
}
