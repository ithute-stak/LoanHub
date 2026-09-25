"use client";

import Link from "next/link";
import { useMemo, useState, type FormEvent } from "react";
import { AlertCircle, ArrowLeft, Download, FileDown, Loader2, ShieldAlert } from "lucide-react";

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

type CdasDocument = {
    FileName?: string;
    DocumentTye?: string;
    Year?: number;
    Month?: number;
    Content?: string | number[];
    [key: string]: unknown;
};

type DocumentResponse = { ok: boolean; document: CdasDocument };

function decodeDocument(content: string | number[]): Uint8Array {
    if (Array.isArray(content)) return Uint8Array.from(content);
    const binary = window.atob(content);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
        bytes[index] = binary.charCodeAt(index);
    }
    return bytes;
}

export default function CdasDocumentsPage() {
    const { activeRole } = useTenant();
    const canManage = hasRole(activeRole, COMPANY_MANAGEMENT_ROLES);
    const now = useMemo(() => new Date(), []);
    const [year, setYear] = useState(now.getFullYear());
    const [month, setMonth] = useState(now.getMonth() + 1);
    const [documentType, setDocumentType] = useState(2);
    const [document, setDocument] = useState<CdasDocument | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    async function retrieveDocument(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!canManage || loading) return;
        setLoading(true);
        setError(null);
        setDocument(null);
        try {
            const response = await api.post<DocumentResponse>("/cdas/documents", {
                year,
                month,
                document_type: documentType,
            });
            setDocument(response.data.document);
        } catch (requestError: unknown) {
            setError(getErrorMessage(requestError, "CDAS document retrieval failed."));
        } finally {
            setLoading(false);
        }
    }

    function downloadDocument() {
        if (!document?.Content) return;
        try {
            const bytes = decodeDocument(document.Content);
            const blob = new Blob([bytes], { type: "application/octet-stream" });
            const url = URL.createObjectURL(blob);
            const anchor = window.document.createElement("a");
            anchor.href = url;
            anchor.download = document.FileName || `cdas-${year}-${month}.bin`;
            anchor.click();
            window.setTimeout(() => URL.revokeObjectURL(url), 0);
        } catch {
            setError("CDAS returned document content that could not be decoded for download.");
        }
    }

    if (!canManage) {
        return (
            <div className="loanhub-page space-y-5">
                <Button asChild variant="ghost"><Link href="/company/cdas"><ArrowLeft className="h-4 w-4" /> Back to CDAS workspace</Link></Button>
                <Alert variant="destructive">
                    <ShieldAlert className="h-4 w-4" />
                    <AlertTitle>Company management permission required</AlertTitle>
                    <AlertDescription>CDAS statement and transaction files are restricted to the company owner or company administrator.</AlertDescription>
                </Alert>
            </div>
        );
    }

    return (
        <div className="loanhub-page space-y-5 2xl:space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <Button asChild variant="ghost"><Link href="/company/cdas"><ArrowLeft className="h-4 w-4" /> Back to CDAS workspace</Link></Button>
                <Badge variant="secondary">Manual document retrieval</Badge>
            </div>

            <section className="rounded-2xl border bg-card p-5 shadow-sm 2xl:rounded-3xl 2xl:p-7">
                <h1 className="flex items-center gap-2 text-2xl font-black tracking-tight sm:text-3xl">
                    <FileDown className="h-7 w-7 text-primary" /> CDAS statements & transactions
                </h1>
                <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground">
                    Retrieve an output file or statement for a specific month using the official CDAS get_document operation. LoanHub does not poll for reports; if CDAS says a report is not ready, that provider response is shown to you.
                </p>
            </section>

            <Card>
                <CardHeader>
                    <CardTitle>Request document</CardTitle>
                    <CardDescription>Document type 1 is Output File and type 2 is Statement, as defined by the CDAS reference document.</CardDescription>
                </CardHeader>
                <CardContent>
                    <form className="space-y-5" onSubmit={retrieveDocument}>
                        <div className="grid gap-4 sm:grid-cols-3">
                            <div className="space-y-2">
                                <Label htmlFor="cdas-document-year">Year</Label>
                                <Input id="cdas-document-year" type="number" min={1} max={9999} value={year} onChange={(event) => setYear(Number(event.target.value))} />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="cdas-document-month">Month</Label>
                                <select id="cdas-document-month" value={month} onChange={(event) => setMonth(Number(event.target.value))} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
                                    {Array.from({ length: 12 }, (_, index) => index + 1).map((value) => <option key={value} value={value}>{value}</option>)}
                                </select>
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="cdas-document-type">Document type</Label>
                                <select id="cdas-document-type" value={documentType} onChange={(event) => setDocumentType(Number(event.target.value))} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
                                    <option value={1}>1 — Output File</option>
                                    <option value={2}>2 — Statement</option>
                                </select>
                            </div>
                        </div>
                        <Button type="submit" disabled={loading}>
                            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileDown className="h-4 w-4" />}
                            Retrieve from CDAS
                        </Button>
                    </form>
                </CardContent>
            </Card>

            {error && (
                <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertTitle>CDAS document unavailable</AlertTitle>
                    <AlertDescription>{error}</AlertDescription>
                </Alert>
            )}

            {document && (
                <Card>
                    <CardHeader>
                        <CardTitle>Retrieved document</CardTitle>
                        <CardDescription>The provider's documented response key is spelled DocumentTye; LoanHub preserves it rather than silently renaming provider data.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                            <div className="rounded-xl border p-4"><p className="text-xs font-bold uppercase text-muted-foreground">File name</p><p className="mt-1 break-all font-bold">{document.FileName || "—"}</p></div>
                            <div className="rounded-xl border p-4"><p className="text-xs font-bold uppercase text-muted-foreground">Document type</p><p className="mt-1 font-bold">{document.DocumentTye || "—"}</p></div>
                            <div className="rounded-xl border p-4"><p className="text-xs font-bold uppercase text-muted-foreground">Year</p><p className="mt-1 font-bold">{document.Year ?? "—"}</p></div>
                            <div className="rounded-xl border p-4"><p className="text-xs font-bold uppercase text-muted-foreground">Month</p><p className="mt-1 font-bold">{document.Month ?? "—"}</p></div>
                        </div>
                        <Button type="button" variant="outline" onClick={downloadDocument} disabled={!document.Content}>
                            <Download className="h-4 w-4" /> Download provider file
                        </Button>
                    </CardContent>
                </Card>
            )}

            <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>No background report polling</AlertTitle>
                <AlertDescription>
                    A report request occurs only when you press Retrieve from CDAS. The documented provider response “Reports not ready yet” remains a normal manual response and does not start a retry loop.
                </AlertDescription>
            </Alert>
        </div>
    );
}
