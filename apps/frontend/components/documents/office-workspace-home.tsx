"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
    BarChart3,
    BookOpenCheck,
    FileSpreadsheet,
    FileText,
    FileUp,
    FolderTree,
    Landmark,
    LayoutTemplate,
    Loader2,
    ReceiptText,
} from "lucide-react";

import { DocumentStudioHome } from "@/components/documents/document-studio-home";
import { DocumentFolderOrganizer } from "@/components/documents/document-folder-organizer";
import {
    createWorkspaceSpreadsheet,
    importWorkspaceSpreadsheet,
} from "@/api/workspaceSpreadsheets";
import type { DocumentVisibility } from "@/types/workspaceDocuments";
import type { SpreadsheetTemplate } from "@/types/workspaceSpreadsheets";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

type StudioMode = "company" | "borrower" | "superadmin" | "platform";
type WorkspaceArea = "documents" | "spreadsheets";
type DocumentWorkspaceView = "organize" | "create";

type SheetTemplate = {
    key: SpreadsheetTemplate;
    title: string;
    description: string;
    icon: typeof FileSpreadsheet;
};

const spreadsheetTemplates: SheetTemplate[] = [
    {
        key: "blank",
        title: "Blank spreadsheet",
        description: "Start with an Excel-style workbook and build your own calculations, lists and schedules.",
        icon: FileSpreadsheet,
    },
    {
        key: "loan_portfolio",
        title: "Loan portfolio",
        description: "Track loan reference, borrower, principal, balance, installments, due dates and status.",
        icon: Landmark,
    },
    {
        key: "cashbook",
        title: "Cashbook",
        description: "Professional money-in, money-out and running-balance working sheet.",
        icon: ReceiptText,
    },
    {
        key: "collections",
        title: "Collections tracker",
        description: "Organise overdue accounts, contact activity, promises and collection ownership.",
        icon: BookOpenCheck,
    },
    {
        key: "budget",
        title: "Budget & variance",
        description: "Budget, actual, variance and percentage analysis with starter formulas.",
        icon: BarChart3,
    },
];

function visibilityForMode(mode: StudioMode): DocumentVisibility {
    // Company staff work starts private. A staff member can deliberately make
    // an item Company public or share it with named colleagues from its folder.
    if (mode === "superadmin") return "platform";
    return "private";
}

export function OfficeWorkspaceHome({
    basePath,
    mode,
}: {
    basePath: string;
    mode: StudioMode;
}) {
    const router = useRouter();
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [creating, setCreating] = useState<SpreadsheetTemplate | "import" | null>(null);
    const [activeArea, setActiveArea] = useState<WorkspaceArea>("documents");
    const [documentView, setDocumentView] = useState<DocumentWorkspaceView>("organize");

    async function createSpreadsheet(template: SheetTemplate) {
        setCreating(template.key);
        try {
            const created = await createWorkspaceSpreadsheet({
                title: template.key === "blank" ? "Untitled workbook" : template.title,
                template: template.key,
                visibility: visibilityForMode(mode),
            });
            router.push(`${basePath}/${created.id}`);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not create the spreadsheet."));
        } finally {
            setCreating(null);
        }
    }

    async function importSpreadsheet(file: File) {
        setCreating("import");
        try {
            const created = await importWorkspaceSpreadsheet(file, {
                visibility: visibilityForMode(mode),
            });
            toast.success(`${file.name} is ready to edit in LoanHub.`);
            router.push(`${basePath}/${created.id}`);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not import the spreadsheet."));
        } finally {
            setCreating(null);
            if (fileInputRef.current) fileInputRef.current.value = "";
        }
    }

    return (
        <div className="space-y-5 pb-8">
            <section className="overflow-hidden rounded-3xl border bg-card shadow-sm">
                <div className="bg-gradient-to-br from-primary/10 via-background to-emerald-500/10 p-5 md:p-7">
                    <div className="max-w-3xl">
                        <p className="text-xs font-black uppercase tracking-[0.18em] text-primary">LoanHub Office Workspace</p>
                        <h1 className="mt-2 text-2xl font-black tracking-tight md:text-3xl">Documents and spreadsheets, organised by people and folders</h1>
                        <p className="mt-2 text-sm leading-6 text-muted-foreground">
                            Staff work stays private by default under the staff member&apos;s named folder. Company-public and directly shared work is visible to the right people, while the company owner has an oversight view across the company.
                        </p>
                    </div>
                </div>

                <div className="grid gap-3 border-t bg-muted/20 p-3 sm:grid-cols-2 md:p-4">
                    <button
                        type="button"
                        onClick={() => setActiveArea("documents")}
                        className={`group flex items-center gap-4 rounded-2xl border p-4 text-left transition ${activeArea === "documents" ? "border-primary bg-primary text-primary-foreground shadow-sm" : "bg-background hover:border-primary/50 hover:bg-primary/5"}`}
                    >
                        <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${activeArea === "documents" ? "bg-primary-foreground/15" : "bg-primary/10 text-primary"}`}>
                            <FileText className="h-5 w-5" />
                        </span>
                        <span className="min-w-0">
                            <span className="block font-black">Documents</span>
                            <span className={`mt-0.5 block text-xs ${activeArea === "documents" ? "text-primary-foreground/80" : "text-muted-foreground"}`}>Staff folders, Word/PDF import, templates and sharing</span>
                        </span>
                    </button>

                    <button
                        type="button"
                        onClick={() => setActiveArea("spreadsheets")}
                        className={`group flex items-center gap-4 rounded-2xl border p-4 text-left transition ${activeArea === "spreadsheets" ? "border-emerald-600 bg-emerald-600 text-white shadow-sm" : "bg-background hover:border-emerald-500/50 hover:bg-emerald-500/5"}`}
                    >
                        <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${activeArea === "spreadsheets" ? "bg-white/15" : "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"}`}>
                            <FileSpreadsheet className="h-5 w-5" />
                        </span>
                        <span className="min-w-0">
                            <span className="block font-black">Spreadsheets</span>
                            <span className={`mt-0.5 block text-xs ${activeArea === "spreadsheets" ? "text-white/80" : "text-muted-foreground"}`}>Foldered workbooks, Excel/CSV import and company sharing</span>
                        </span>
                    </button>
                </div>
            </section>

            {activeArea === "documents" ? (
                <section className="space-y-4">
                    <div className="rounded-2xl border bg-card p-2 shadow-sm">
                        <div className="grid gap-2 sm:grid-cols-2">
                            <button
                                type="button"
                                onClick={() => setDocumentView("organize")}
                                className={`flex items-center gap-3 rounded-xl px-4 py-3 text-left transition ${documentView === "organize" ? "bg-primary text-primary-foreground shadow-sm" : "hover:bg-muted"}`}
                            >
                                <FolderTree className="h-5 w-5 shrink-0" />
                                <span>
                                    <span className="block text-sm font-black">Organize & share</span>
                                    <span className={`block text-xs ${documentView === "organize" ? "text-primary-foreground/75" : "text-muted-foreground"}`}>Staff folders, list/tile view, imports and access</span>
                                </span>
                            </button>
                            <button
                                type="button"
                                onClick={() => setDocumentView("create")}
                                className={`flex items-center gap-3 rounded-xl px-4 py-3 text-left transition ${documentView === "create" ? "bg-primary text-primary-foreground shadow-sm" : "hover:bg-muted"}`}
                            >
                                <LayoutTemplate className="h-5 w-5 shrink-0" />
                                <span>
                                    <span className="block text-sm font-black">Create & browse</span>
                                    <span className={`block text-xs ${documentView === "create" ? "text-primary-foreground/75" : "text-muted-foreground"}`}>Templates, document cards and editor access</span>
                                </span>
                            </button>
                        </div>
                    </div>

                    {documentView === "organize" ? (
                        <DocumentFolderOrganizer basePath={basePath} mode={mode} resourceKind="document" />
                    ) : (
                        <div className="[&>main>section:first-child]:hidden">
                            <DocumentStudioHome basePath={basePath} mode={mode} />
                        </div>
                    )}
                </section>
            ) : (
                <section className="space-y-4">
                    <section className="overflow-hidden rounded-3xl border bg-card shadow-sm">
                        <div className="flex flex-col gap-4 border-b bg-gradient-to-br from-emerald-500/10 via-background to-emerald-500/5 p-5 md:flex-row md:items-center md:justify-between md:p-6">
                            <div>
                                <div className="flex items-center gap-2 text-emerald-700 dark:text-emerald-400">
                                    <FileSpreadsheet className="h-5 w-5" />
                                    <span className="text-xs font-black uppercase tracking-[0.16em]">Spreadsheet workspace</span>
                                </div>
                                <h2 className="mt-2 text-xl font-black tracking-tight md:text-2xl">Create or import a workbook</h2>
                                <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">New workbooks are filed under your staff-name folder automatically. Use the folder workspace below to reorganize or share them.</p>
                            </div>
                            <div>
                                <input
                                    ref={fileInputRef}
                                    type="file"
                                    accept=".xlsx,.xlsm,.csv,.tsv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv,text/tab-separated-values"
                                    className="hidden"
                                    onChange={(event) => {
                                        const file = event.target.files?.[0];
                                        if (file) void importSpreadsheet(file);
                                    }}
                                />
                                <button
                                    type="button"
                                    disabled={creating !== null}
                                    onClick={() => fileInputRef.current?.click()}
                                    className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 text-sm font-black text-white shadow-sm transition hover:bg-emerald-700 disabled:opacity-60 sm:w-auto"
                                >
                                    {creating === "import" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileUp className="h-4 w-4" />}
                                    Import Excel / CSV
                                </button>
                            </div>
                        </div>

                        <div className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-5">
                            {spreadsheetTemplates.map((template) => {
                                const Icon = template.icon;
                                return (
                                    <button
                                        key={template.key}
                                        type="button"
                                        disabled={creating !== null}
                                        onClick={() => void createSpreadsheet(template)}
                                        className="group rounded-2xl border bg-background p-4 text-left transition hover:-translate-y-0.5 hover:border-emerald-500 hover:shadow-md disabled:opacity-60"
                                    >
                                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-700 dark:text-emerald-400">
                                            {creating === template.key ? <Loader2 className="h-5 w-5 animate-spin" /> : <Icon className="h-5 w-5" />}
                                        </div>
                                        <p className="mt-3 font-black">{template.title}</p>
                                        <p className="mt-1 text-xs leading-5 text-muted-foreground">{template.description}</p>
                                    </button>
                                );
                            })}
                        </div>
                        <div className="border-t bg-muted/20 px-5 py-3 text-xs leading-5 text-muted-foreground">
                            Excel import supports modern <strong>.xlsx</strong> workbooks, macro-enabled <strong>.xlsm</strong> content without carrying executable macros, and <strong>.csv/.tsv</strong> data. Export edited workbooks back to Excel at any time.
                        </div>
                    </section>

                    <DocumentFolderOrganizer basePath={basePath} mode={mode} resourceKind="spreadsheet" />
                </section>
            )}
        </div>
    );
}
