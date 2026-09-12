"use client";

import {
    BadgeCheck,
    Download,
    FileArchive,
    FileChartColumn,
    FileCheck2,
    FileText,
    FolderOpen,
    FolderTree,
    HardDrive,
    IdCard,
    Landmark,
    RefreshCcw,
    ReceiptText,
    ShieldCheck,
    Users,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { downloadManagedFile, listManagedFiles } from "@/api/files";
import { FileCenter } from "@/components/files/file-center";
import { ReportCenter } from "@/components/reports/report-center";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useTenant } from "@/provider/tenantProvider";
import { hasRole, REPORTING_ROLES } from "@/types/auth";
import type { ManagedFile } from "@/types/files";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";
import {
    documentFolderForCategory,
    documentFolderLabel,
    type DocumentFolderKey,
} from "@/components/documents/document-folders";

type DocumentTab = "overview" | "library" | "reports";

const FOLDERS: Array<{
    key: Exclude<DocumentFolderKey, "all">;
    icon: typeof FolderOpen;
    description: string;
}> = [
    { key: "letters", icon: FileText, description: "Letters, memoranda and editable correspondence published from the document studio." },
    { key: "contracts", icon: FileCheck2, description: "Credit agreements, signed contracts and annexures." },
    { key: "reports", icon: FileChartColumn, description: "Generated management, accounting and branch reports." },
    { key: "receipts", icon: ReceiptText, description: "Payment receipts, repayment slips and disbursement evidence." },
    { key: "finance", icon: Landmark, description: "Accounting exports, treasury records and expense evidence." },
    { key: "compliance", icon: ShieldCheck, description: "KYC, licences, identity and compliance evidence." },
    { key: "people", icon: Users, description: "Employee, staff, performance and HR records." },
    { key: "branding", icon: IdCard, description: "Company logos and approved document-branding assets." },
    { key: "general", icon: FileArchive, description: "Other operational records and uploaded documents." },
];

function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

export function DocumentWorkspace() {
    const params = useSearchParams();
    const { activeRole } = useTenant();
    const canUseReports = hasRole(activeRole, REPORTING_ROLES);
    const requestedTab = params.get("tab");
    const initialTab: DocumentTab = requestedTab === "reports" && canUseReports
        ? "reports"
        : requestedTab === "library"
          ? "library"
          : "overview";

    const [tab, setTab] = useState<DocumentTab>(initialTab);
    const [files, setFiles] = useState<ManagedFile[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedFolder, setSelectedFolder] = useState<DocumentFolderKey>("all");

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const result = await listManagedFiles({ limit: 500 });
            setFiles(result.items);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not load the document workspace."));
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        const timer = window.setTimeout(() => void load(), 0);
        return () => window.clearTimeout(timer);
    }, [load]);

    useEffect(() => {
        if (requestedTab === "reports" && canUseReports) setTab("reports");
        else if (requestedTab === "library") setTab("library");
    }, [canUseReports, requestedTab]);

    const folderCounts = useMemo(() => {
        const counts = new Map<DocumentFolderKey, number>();
        for (const file of files) {
            const folder = documentFolderForCategory(file.category);
            counts.set(folder, (counts.get(folder) ?? 0) + 1);
        }
        return counts;
    }, [files]);

    const storageBytes = useMemo(
        () => files.reduce((total, file) => total + Number(file.size_bytes || 0), 0),
        [files],
    );
    const confidentialCount = files.filter((file) => file.is_confidential).length;
    const generatedCount = files.filter((file) => Boolean(file.linked_entity_type)).length;
    const recentFiles = [...files]
        .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime())
        .slice(0, 6);

    function openFolder(folder: DocumentFolderKey) {
        setSelectedFolder(folder);
        setTab("library");
    }

    return (
        <main className="space-y-6">
            <section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8">
                <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-primary/10 blur-3xl" />
                <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <div className="flex items-center gap-2 text-primary">
                            <FolderTree className="h-5 w-5" />
                            <span className="text-xs font-black uppercase tracking-[0.16em]">Controlled document intelligence</span>
                        </div>
                        <h1 className="mt-2 text-3xl font-black tracking-tight">Documents</h1>
                        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                            Store, organise, generate, share and retrieve every report, contract, receipt and operational record from one secure workspace.
                        </p>
                    </div>
                    <button
                        type="button"
                        onClick={() => void load()}
                        className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border bg-background px-4 text-sm font-black hover:border-primary hover:text-primary"
                    >
                        <RefreshCcw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
                        Refresh documents
                    </button>
                </div>
            </section>

            <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <SummaryCard icon={FileText} label="Stored documents" value={files.length.toLocaleString()} note="All permitted company records" />
                <SummaryCard icon={HardDrive} label="Storage used" value={formatSize(storageBytes)} note="Across visible managed files" />
                <SummaryCard icon={BadgeCheck} label="System generated" value={generatedCount.toLocaleString()} note="Reports, contracts, receipts and slips" />
                <SummaryCard icon={ShieldCheck} label="Confidential" value={confidentialCount.toLocaleString()} note="Restricted records requiring care" />
            </section>

            <Tabs value={tab} onValueChange={(value) => setTab(value as DocumentTab)} className="space-y-5">
                <TabsList className="h-auto w-full flex-wrap justify-start rounded-2xl border bg-card p-1.5">
                    <TabsTrigger value="overview" className="min-w-36 rounded-xl px-4 py-2.5">Folder overview</TabsTrigger>
                    <TabsTrigger value="library" className="min-w-36 rounded-xl px-4 py-2.5">Document library</TabsTrigger>
                    {canUseReports && (
                        <TabsTrigger value="reports" className="min-w-36 rounded-xl px-4 py-2.5">Generate reports</TabsTrigger>
                    )}
                </TabsList>

                <TabsContent value="overview" className="space-y-6">
                    <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                        {FOLDERS.map(({ key, icon: Icon, description }) => (
                            <button
                                key={key}
                                type="button"
                                onClick={() => openFolder(key)}
                                className="group rounded-3xl border bg-card p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-primary hover:shadow-md"
                            >
                                <div className="flex items-start justify-between gap-4">
                                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary transition group-hover:bg-primary group-hover:text-primary-foreground">
                                        <Icon className="h-6 w-6" />
                                    </div>
                                    <span className="rounded-full bg-muted px-2.5 py-1 text-xs font-black">
                                        {folderCounts.get(key) ?? 0}
                                    </span>
                                </div>
                                <p className="mt-4 font-black">{documentFolderLabel(key)}</p>
                                <p className="mt-1 text-xs leading-5 text-muted-foreground">{description}</p>
                            </button>
                        ))}
                    </section>

                    <section className="overflow-hidden rounded-3xl border bg-card shadow-sm">
                        <div className="flex items-center justify-between gap-4 border-b p-5">
                            <div>
                                <h2 className="text-lg font-black">Recently added</h2>
                                <p className="mt-1 text-sm text-muted-foreground">The latest records available in your current company and role scope.</p>
                            </div>
                            <button type="button" onClick={() => openFolder("all")} className="text-sm font-black text-primary">Open library</button>
                        </div>
                        <div className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-3">
                            {recentFiles.map((file) => (
                                <article key={file.id} className="rounded-2xl border bg-muted/15 p-4">
                                    <div className="flex items-start gap-3">
                                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                                            <FileText className="h-5 w-5" />
                                        </div>
                                        <div className="min-w-0 flex-1">
                                            <p className="truncate font-black">{file.original_name}</p>
                                            <p className="mt-1 text-xs text-muted-foreground">{documentFolderLabel(documentFolderForCategory(file.category))}</p>
                                        </div>
                                        <button type="button" onClick={() => void downloadManagedFile(file)} className="rounded-xl border p-2 hover:border-primary hover:text-primary" title="Download">
                                            <Download className="h-4 w-4" />
                                        </button>
                                    </div>
                                    <div className="mt-3 flex items-center justify-between gap-3 text-xs text-muted-foreground">
                                        <span className="font-mono">{file.reference}</span>
                                        <span>{formatSize(file.size_bytes)}</span>
                                    </div>
                                </article>
                            ))}
                            {!loading && recentFiles.length === 0 && (
                                <p className="col-span-full p-8 text-center text-sm text-muted-foreground">No documents are available yet.</p>
                            )}
                        </div>
                    </section>
                </TabsContent>

                <TabsContent value="library">
                    <FileCenter mode="company" embedded initialCategory={selectedFolder} />
                </TabsContent>

                {canUseReports && (
                    <TabsContent value="reports">
                        <ReportCenter mode="company" embedded />
                    </TabsContent>
                )}
            </Tabs>
        </main>
    );
}

function SummaryCard({
    icon: Icon,
    label,
    value,
    note,
}: {
    icon: typeof FileText;
    label: string;
    value: string;
    note: string;
}) {
    return (
        <article className="rounded-3xl border bg-card p-5 shadow-sm">
            <div className="flex items-start justify-between gap-4">
                <div>
                    <p className="text-xs font-black uppercase tracking-[0.12em] text-muted-foreground">{label}</p>
                    <p className="mt-2 text-2xl font-black">{value}</p>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">{note}</p>
                </div>
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                    <Icon className="h-5 w-5" />
                </div>
            </div>
        </article>
    );
}
