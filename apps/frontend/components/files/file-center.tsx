"use client";


import { Input } from "@/components/ui/input";
import { SuggestionSearch } from "@/components/ui/suggestion-search";
import { Textarea } from "@/components/ui/textarea";
import { NativeSelect } from "@/components/ui/native-select";
import {
    Download,
    File,
    FileText,
    FolderOpen,
    Grid2X2,
    List,
    Loader2,
    MessageCircle,
    Share2,
    ShieldCheck,
    Trash2,
    Upload,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "@/utils/toast";

import {
    deleteManagedFile,
    downloadManagedFile,
    listManagedFiles,
    uploadManagedFile,
} from "@/api/files";
import { IthutePoweredBy } from "@/components/brand/ithute-brand";
import { ExternalFileShareDialog, InternalFileShareDialog } from "@/components/files/file-share-dialogs";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import type { ManagedFile } from "@/types/files";
import { getErrorMessage } from "@/utils/apiError";
import { documentFolderForCategory, documentFolderLabel } from "@/components/documents/document-folders";

function fileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function FileCenter({
    mode,
    embedded = false,
    initialCategory = "all",
}: {
    mode: "company" | "borrower" | "superadmin";
    embedded?: boolean;
    initialCategory?: string;
}) {
    const [files, setFiles] = useState<ManagedFile[]>([]);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [search, setSearch] = useState("");
    const [folderFilter, setFolderFilter] = useState(initialCategory);
    const [uploadCategory, setUploadCategory] = useState("general");
    const [viewMode, setViewMode] = useState<"cards" | "list">("cards");
    const [description, setDescription] = useState("");
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [deleteTarget, setDeleteTarget] = useState<ManagedFile | null>(null);
    const [removing, setRemoving] = useState(false);
    const [internalShareFile, setInternalShareFile] = useState<ManagedFile | null>(null);
    const [externalShareFile, setExternalShareFile] = useState<ManagedFile | null>(null);

    async function load() {
        setLoading(true);
        try {
            const result = await listManagedFiles({ limit: 500 });
            setFiles(result.items);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not load documents"));
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        const timer = window.setTimeout(() => void load(), 0);
        return () => window.clearTimeout(timer);
    }, []);

    useEffect(() => {
        setFolderFilter(initialCategory);
    }, [initialCategory]);

    const filtered = useMemo(() => {
        const token = search.trim().toLowerCase();
        return files.filter((file) => {
            const matchesCategory = folderFilter === "all" || file.category === folderFilter || documentFolderForCategory(file.category) === folderFilter;
            const matchesSearch = !token || `${file.original_name} ${file.reference} ${file.description ?? ""}`.toLowerCase().includes(token);
            return matchesCategory && matchesSearch;
        });
    }, [files, folderFilter, search]);

    async function submitUpload() {
        if (!selectedFile) {
            toast.error("Choose a file first");
            return;
        }
        setUploading(true);
        try {
            const record = await uploadManagedFile({
                file: selectedFile,
                category: uploadCategory,
                visibility: mode === "borrower" ? "private" : mode === "superadmin" ? "platform" : "company",
                description: description.trim() || undefined,
            });
            setFiles((current) => [record, ...current]);
            setSelectedFile(null);
            setDescription("");
            toast.success("Document uploaded securely");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Document could not be uploaded"));
        } finally {
            setUploading(false);
        }
    }

    async function removeConfirmed() {
        if (!deleteTarget) return;
        setRemoving(true);
        try {
            await deleteManagedFile(deleteTarget.id);
            setFiles((current) => current.filter((item) => item.id !== deleteTarget.id));
            toast.success("Document removed");
            setDeleteTarget(null);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Document could not be removed"));
        } finally {
            setRemoving(false);
        }
    }

    return (
        <main className="space-y-6">
{!embedded && (
            <section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8">
                <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-primary/10 blur-3xl" />
                <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <div className="flex items-center gap-2 text-primary"><FolderOpen className="h-5 w-5" /><span className="text-xs font-black uppercase tracking-[0.16em]">Document centre</span></div>
                        <h1 className="mt-2 text-3xl font-black">Secure files and records</h1>
                        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
                            Organise reports, agreements, PDFs and operational evidence in one permission-controlled file centre.
                        </p>
                    </div>
                    <IthutePoweredBy />
                </div>
            </section>
            )}

            <section className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
                <article className="rounded-3xl border bg-card p-5 shadow-sm">
                    <div className="flex items-center gap-2"><Upload className="h-5 w-5 text-primary" /><h2 className="text-lg font-black">Upload document</h2></div>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">Files are checksum-verified and downloaded through authenticated API routes.</p>
                    <div className="mt-5 space-y-4">
                        <label className="block rounded-2xl border border-dashed p-5 text-center hover:border-primary">
                            <Input
                                type="file"
                                accept=".pdf,.png,.jpg,.jpeg,.webp,.doc,.docx,.xls,.xlsx,.csv,.txt"
                                className="hidden"
                                onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
                            />
                            <FileText className="mx-auto h-8 w-8 text-primary" />
                            <p className="mt-3 text-sm font-black">{selectedFile?.name ?? "Choose a file"}</p>
                            <p className="mt-1 text-xs text-muted-foreground">Maximum 25 MB</p>
                        </label>
                        <NativeSelect value={uploadCategory} onChange={(event) => setUploadCategory(event.target.value)} className="h-11 w-full rounded-xl border bg-background px-3 text-sm font-bold">
                            <option value="general">General records</option>
                            <option value="contracts">Contracts and agreements</option>
                            <option value="reports">Reports and statements</option>
                            <option value="receipts">Receipts and slips</option>
                            <option value="finance">Finance and accounting</option>
                            <option value="compliance">Compliance and KYC</option>
                            <option value="people">People and HR</option>
                            <option value="branding">Brand assets</option>
                        </NativeSelect>
                        <Textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Description or filing note" rows={3} className="w-full rounded-xl border bg-background p-3 text-sm" />
                        <button type="button" onClick={() => void submitUpload()} disabled={!selectedFile || uploading} className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-primary text-sm font-black text-primary-foreground disabled:opacity-50">
                            {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />} Upload securely
                        </button>
                    </div>
                    <div className="mt-5 flex items-start gap-2 rounded-2xl bg-muted/50 p-3 text-xs text-muted-foreground"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" /> Confidential documents should only be shared with authorised roles.</div>
                </article>

                <article className="overflow-hidden rounded-3xl border bg-card shadow-sm">
                    <div className="space-y-4 border-b p-5">
                        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                            <div>
                                <h2 className="text-lg font-black">Document library</h2>
                                <p className="mt-1 text-sm text-muted-foreground">{filtered.length} visible of {files.length} stored document{files.length === 1 ? "" : "s"}</p>
                            </div>
                            <div className="flex items-center gap-2">
                                <button type="button" onClick={() => setViewMode("cards")} className={`rounded-xl border p-2.5 ${viewMode === "cards" ? "border-primary bg-primary/10 text-primary" : ""}`} title="Card view">
                                    <Grid2X2 className="h-4 w-4" />
                                </button>
                                <button type="button" onClick={() => setViewMode("list")} className={`rounded-xl border p-2.5 ${viewMode === "list" ? "border-primary bg-primary/10 text-primary" : ""}`} title="List view">
                                    <List className="h-4 w-4" />
                                </button>
                            </div>
                        </div>
                        <div className="grid gap-3 md:grid-cols-[220px_minmax(0,1fr)]">
                            <NativeSelect value={folderFilter} onChange={(event) => setFolderFilter(event.target.value)} className="h-11 w-full rounded-xl border bg-background px-3 text-sm font-bold">
                                <option value="all">All folders</option>
                                <option value="general">General records</option>
                                <option value="letters">Letters & correspondence</option>
                                <option value="contracts">Contracts & agreements</option>
                                <option value="reports">Reports & statements</option>
                                <option value="receipts">Receipts & slips</option>
                                <option value="finance">Finance & accounting</option>
                                <option value="compliance">Compliance & KYC</option>
                                <option value="people">People & HR</option>
                                <option value="branding">Brand assets</option>
                            </NativeSelect>
                            <SuggestionSearch
                                value={search}
                                onValueChange={setSearch}
                                suggestions={files.map((file) => ({
                                    value: file.original_name,
                                    label: file.original_name,
                                    description: `${file.reference} · ${documentFolderLabel(documentFolderForCategory(file.category))}`,
                                    keywords: [file.id, file.reference, file.category, file.description ?? "", file.mime_type ?? ""],
                                }))}
                                placeholder="Type a document name, reference, folder or category..."
                                suggestionLabel="Stored documents"
                                emptyMessage="No document matches that text."
                            />
                        </div>
                    </div>

                    {viewMode === "cards" ? (
                        <div className="grid gap-4 p-4 sm:grid-cols-2 2xl:grid-cols-3">
                            {filtered.map((file) => (
                                <article key={file.id} className="group rounded-2xl border bg-muted/10 p-4 transition hover:border-primary hover:shadow-sm">
                                    <div className="flex items-start gap-3">
                                        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                                            <File className="h-5 w-5" />
                                        </div>
                                        <div className="min-w-0 flex-1">
                                            <p className="truncate font-black" title={file.original_name}>{file.original_name}</p>
                                            <p className="mt-1 truncate font-mono text-[11px] text-muted-foreground">{file.reference}</p>
                                        </div>
                                    </div>
                                    <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
                                        <span className="rounded-full bg-primary/10 px-2.5 py-1 font-bold text-primary">{documentFolderLabel(documentFolderForCategory(file.category))}</span>
                                        <span className="rounded-full bg-muted px-2.5 py-1 font-semibold">{fileSize(file.size_bytes)}</span>
                                        {file.is_confidential && <span className="rounded-full bg-amber-100 px-2.5 py-1 font-bold text-amber-800 dark:bg-amber-950/40 dark:text-amber-300">Confidential</span>}
                                    </div>
                                    <p className="mt-3 line-clamp-2 min-h-10 text-xs leading-5 text-muted-foreground">{file.description || "No filing note was added."}</p>
                                    <div className="mt-4 flex items-center justify-between gap-3 border-t pt-3">
                                        <span className="text-xs text-muted-foreground">{new Date(file.created_at).toLocaleDateString("en-LS")}</span>
                                        <DocumentActions
                                            file={file}
                                            mode={mode}
                                            onInternalShare={setInternalShareFile}
                                            onExternalShare={setExternalShareFile}
                                            onDelete={setDeleteTarget}
                                        />
                                    </div>
                                </article>
                            ))}
                        </div>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full min-w-[760px] text-left text-sm">
                                <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground"><tr><th className="px-5 py-3">Document</th><th className="px-5 py-3">Folder</th><th className="px-5 py-3">Size</th><th className="px-5 py-3">Uploaded</th><th className="px-5 py-3 text-right">Actions</th></tr></thead>
                                <tbody className="divide-y">
                                    {filtered.map((file) => (
                                        <tr key={file.id} className="hover:bg-muted/20">
                                            <td className="px-5 py-4"><div className="flex items-center gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary"><File className="h-5 w-5" /></div><div className="min-w-0"><p className="max-w-sm truncate font-black">{file.original_name}</p><p className="mt-1 text-xs text-muted-foreground">{file.reference}</p></div></div></td>
                                            <td className="px-5 py-4"><span className="rounded-full bg-muted px-2.5 py-1 text-xs font-bold">{documentFolderLabel(documentFolderForCategory(file.category))}</span></td>
                                            <td className="px-5 py-4 font-semibold">{fileSize(file.size_bytes)}</td>
                                            <td className="px-5 py-4 text-muted-foreground">{new Date(file.created_at).toLocaleDateString("en-LS")}</td>
                                            <td className="px-5 py-4"><div className="flex justify-end"><DocumentActions file={file} mode={mode} onInternalShare={setInternalShareFile} onExternalShare={setExternalShareFile} onDelete={setDeleteTarget} /></div></td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                    {!loading && filtered.length === 0 && <p className="p-10 text-center text-sm text-muted-foreground">No documents match the selected folder and search.</p>}
                    {loading && <div className="flex justify-center p-10"><Loader2 className="h-6 w-6 animate-spin text-primary" /></div>}
                </article>
            </section>
            <InternalFileShareDialog
                file={internalShareFile}
                open={Boolean(internalShareFile)}
                onOpenChange={(next) => !next && setInternalShareFile(null)}
                chatPath={mode === "borrower" ? "/borrower/chat" : mode === "superadmin" ? "/superadmin/chat" : "/company/chat"}
            />
            <ExternalFileShareDialog
                file={externalShareFile}
                open={Boolean(externalShareFile)}
                onOpenChange={(next) => !next && setExternalShareFile(null)}
                settingsPath="/company/settings"
            />
            <ConfirmDialog
                open={Boolean(deleteTarget)}
                onOpenChange={(open) => !open && !removing && setDeleteTarget(null)}
                title="Remove document?"
                description={`Remove ${deleteTarget?.original_name ?? "this document"}? This action cannot be undone.`}
                confirmLabel="Remove document"
                destructive
                loading={removing}
                onConfirm={removeConfirmed}
            />
        </main>
    );
}


function DocumentActions({
    file,
    mode,
    onInternalShare,
    onExternalShare,
    onDelete,
}: {
    file: ManagedFile;
    mode: "company" | "borrower" | "superadmin";
    onInternalShare: (file: ManagedFile) => void;
    onExternalShare: (file: ManagedFile) => void;
    onDelete: (file: ManagedFile) => void;
}) {
    return (
        <div className="flex gap-2">
            <button type="button" onClick={() => void downloadManagedFile(file)} className="rounded-xl border p-2 hover:border-primary hover:text-primary" title="Download">
                <Download className="h-4 w-4" />
            </button>
            <button type="button" onClick={() => onInternalShare(file)} className="rounded-xl border p-2 hover:border-primary hover:text-primary" title="Share internally in chat">
                <MessageCircle className="h-4 w-4" />
            </button>
            {mode !== "borrower" && (
                <button type="button" onClick={() => onExternalShare(file)} className="rounded-xl border p-2 hover:border-primary hover:text-primary" title="Share externally">
                    <Share2 className="h-4 w-4" />
                </button>
            )}
            <button type="button" onClick={() => onDelete(file)} className="rounded-xl border p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30" title="Remove">
                <Trash2 className="h-4 w-4" />
            </button>
        </div>
    );
}
