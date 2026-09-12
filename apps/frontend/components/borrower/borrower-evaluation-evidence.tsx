"use client";

import {
    deleteManagedFile,
    downloadManagedFile,
    listManagedFiles,
    uploadManagedFile,
} from "@/api/files";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import type { ManagedFile } from "@/types/files";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";
import {
    CheckCircle2,
    Download,
    FileCheck2,
    Loader2,
    ShieldCheck,
    Trash2,
    Upload,
} from "lucide-react";
import { ChangeEvent, useCallback, useEffect, useMemo, useState } from "react";

const EVIDENCE_TYPES = [
    { value: "borrower_identity", label: "National ID or passport", required: true },
    { value: "borrower_proof_of_address", label: "Proof of address", required: true },
    { value: "borrower_payslip", label: "Payslip or income proof", required: true },
    { value: "borrower_bank_statement", label: "Bank statement", required: true },
    { value: "borrower_employment", label: "Employment letter or contract", required: false },
    { value: "borrower_existing_debt", label: "Existing loan statement", required: false },
    { value: "borrower_business", label: "Business registration or trading evidence", required: false },
    { value: "borrower_other", label: "Other supporting evidence", required: false },
] as const;

function fileSize(bytes: number) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function BorrowerEvaluationEvidence({
    borrowerId,
    sharingEnabled,
    onEvidenceChange,
}: {
    borrowerId: string;
    sharingEnabled: boolean;
    onEvidenceChange?: (fileIds: string[]) => void;
}) {
    const [category, setCategory] = useState<string>("borrower_identity");
    const [evidence, setEvidence] = useState<ManagedFile[]>([]);

    useEffect(() => {
        onEvidenceChange?.(evidence.map((file) => file.id));
    }, [evidence, onEvidenceChange]);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<ManagedFile | null>(null);
    const [removing, setRemoving] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const result = await listManagedFiles({ limit: 500 });
            setEvidence(
                result.items.filter(
                    (file) =>
                        file.linked_entity_type === "borrower_evaluation" &&
                        file.linked_entity_id === borrowerId,
                ),
            );
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not load evaluation evidence"));
        } finally {
            setLoading(false);
        }
    }, [borrowerId]);

    useEffect(() => {
        void load();
    }, [load]);

    const uploadedCategories = useMemo(
        () => new Set(evidence.map((file) => file.category)),
        [evidence],
    );
    const completedRequired = EVIDENCE_TYPES.filter(
        (item) => item.required && uploadedCategories.has(item.value),
    ).length;
    const requiredCount = EVIDENCE_TYPES.filter((item) => item.required).length;

    async function handleUpload(event: ChangeEvent<HTMLInputElement>) {
        const selected = Array.from(event.target.files ?? []);
        event.target.value = "";
        if (!selected.length) return;

        setUploading(true);
        try {
            for (const file of selected) {
                await uploadManagedFile({
                    file,
                    category,
                    visibility: "private",
                    description:
                        EVIDENCE_TYPES.find((item) => item.value === category)?.label ??
                        "Borrower evaluation evidence",
                    isConfidential: true,
                    linkedEntityType: "borrower_evaluation",
                    linkedEntityId: borrowerId,
                });
            }
            toast.success(
                selected.length === 1
                    ? "Evidence uploaded securely"
                    : `${selected.length} evidence files uploaded securely`,
            );
            await load();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not upload the evidence"));
        } finally {
            setUploading(false);
        }
    }

    async function removeConfirmed() {
        if (!deleteTarget) return;
        setRemoving(true);
        try {
            await deleteManagedFile(deleteTarget.id);
            toast.success("Evidence removed");
            setDeleteTarget(null);
            await load();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not remove the evidence"));
        } finally {
            setRemoving(false);
        }
    }

    return (
        <section className="rounded-3xl border bg-card p-6 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <div className="flex items-center gap-2">
                        <FileCheck2 className="h-5 w-5 text-primary" />
                        <h2 className="text-lg font-black">Evaluation evidence</h2>
                    </div>
                    <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
                        Add clear, recent evidence so an authorized lender can verify identity,
                        income, expenses and existing commitments. PDF, JPG and PNG are recommended.
                    </p>
                </div>
                <div className="rounded-2xl bg-primary/10 px-4 py-3 text-sm font-bold text-primary">
                    {completedRequired}/{requiredCount} core evidence groups supplied
                </div>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-[1fr_auto]">
                <label>
                    <span className="mb-2 block text-sm font-bold">Evidence type</span>
                    <NativeSelect
                        value={category}
                        onChange={(event) => setCategory(event.target.value)}
                        className="h-11 w-full rounded-xl border bg-background px-3"
                    >
                        {EVIDENCE_TYPES.map((item) => (
                            <option key={item.value} value={item.value}>
                                {item.label}{item.required ? " · core" : ""}
                            </option>
                        ))}
                    </NativeSelect>
                </label>
                <label className="self-end">
                    <Input
                        type="file"
                        multiple
                        accept=".pdf,.jpg,.jpeg,.png,.webp,.doc,.docx,.xls,.xlsx,.csv,text/plain"
                        onChange={(event) => void handleUpload(event)}
                        disabled={uploading}
                        className="sr-only"
                    />
                    <span className="inline-flex h-11 cursor-pointer items-center gap-2 rounded-xl bg-primary px-4 text-sm font-bold text-primary-foreground hover:opacity-90">
                        {uploading ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <Upload className="h-4 w-4" />
                        )}
                        {uploading ? "Scanning and encrypting..." : "Choose one or more files"}
                    </span>
                </label>
            </div>

            <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {EVIDENCE_TYPES.filter((item) => item.required).map((item) => {
                    const supplied = uploadedCategories.has(item.value);
                    return (
                        <div
                            key={item.value}
                            className="flex items-center gap-2 rounded-2xl border p-3 text-sm"
                        >
                            <CheckCircle2
                                className={
                                    supplied
                                        ? "h-4 w-4 text-green-600"
                                        : "h-4 w-4 text-muted-foreground"
                                }
                            />
                            <span className={supplied ? "font-bold" : "text-muted-foreground"}>
                                {item.label}
                            </span>
                        </div>
                    );
                })}
            </div>

            <div className="mt-5 rounded-2xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800 dark:border-blue-900 dark:bg-blue-950/30 dark:text-blue-300">
                <ShieldCheck className="mr-2 inline h-4 w-4" />
                Files are validated, malware-scanned and stored as confidential private evidence.
                {sharingEnabled
                    ? " Only lenders with paid or plan-authorized access to your visible request can download them."
                    : " Lenders cannot download them until you enable evidence sharing below."}
            </div>

            <div className="mt-5 space-y-3">
                {loading ? (
                    <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Loading evidence...
                    </div>
                ) : evidence.length ? (
                    evidence.map((file) => (
                        <div
                            key={file.id}
                            className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border p-4"
                        >
                            <div className="min-w-0">
                                <p className="truncate font-bold">{file.original_name}</p>
                                <p className="mt-1 text-xs text-muted-foreground">
                                    {EVIDENCE_TYPES.find((item) => item.value === file.category)?.label ??
                                        file.category}
                                    {" · "}
                                    {fileSize(file.size_bytes)}
                                    {" · "}
                                    {file.scan_status === "quarantined"
                                        ? "Quarantined"
                                        : "Security validated"}
                                </p>
                            </div>
                            <div className="flex gap-2">
                                <button
                                    type="button"
                                    onClick={() => void downloadManagedFile(file)}
                                    className="rounded-xl border p-2 hover:border-primary hover:text-primary"
                                    title="Download"
                                >
                                    <Download className="h-4 w-4" />
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setDeleteTarget(file)}
                                    className="rounded-xl border p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30"
                                    title="Remove"
                                >
                                    <Trash2 className="h-4 w-4" />
                                </button>
                            </div>
                        </div>
                    ))
                ) : (
                    <div className="rounded-2xl border border-dashed p-6 text-center text-sm text-muted-foreground">
                        No evaluation evidence has been uploaded yet.
                    </div>
                )}
            </div>

            <ConfirmDialog
                open={Boolean(deleteTarget)}
                onOpenChange={(open) => !open && !removing && setDeleteTarget(null)}
                title="Remove evaluation evidence?"
                description={`Remove ${deleteTarget?.original_name ?? "this file"}? This cannot be undone.`}
                confirmLabel="Remove evidence"
                destructive
                loading={removing}
                onConfirm={removeConfirmed}
            />
        </section>
    );
}
