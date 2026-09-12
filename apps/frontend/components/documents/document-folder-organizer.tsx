"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
    Eye,
    FileSpreadsheet,
    FileText,
    FileUp,
    Folder,
    FolderPlus,
    Globe2,
    Grid2X2,
    List,
    Loader2,
    Pencil,
    Share2,
    Trash2,
    UsersRound,
} from "lucide-react";

import {
    addWorkspaceDocumentCollaborator,
    createWorkspaceDocumentFolder,
    deleteWorkspaceDocumentFolder,
    fileMyUnassignedWorkspaceItems,
    getWorkspaceOfficeAccess,
    importWorkspaceDocument,
    listWorkspaceDocumentCollaborators,
    listWorkspaceDocumentFolderAssignments,
    listWorkspaceDocumentFolders,
    listWorkspaceDocuments,
    listWorkspaceSharingDirectory,
    moveWorkspaceDocumentToFolder,
    removeWorkspaceDocumentCollaborator,
    updateWorkspaceDocument,
    type WorkspaceDocumentFolder,
    type WorkspaceItemKind,
    type WorkspaceOfficeAccess,
    type WorkspaceSharingDirectoryUser,
} from "@/api/workspaceDocuments";
import { CustomDialog } from "@/components/ui/custom-dialog";
import type {
    DocumentPermission,
    DocumentVisibility,
    WorkspaceDocument,
    WorkspaceDocumentCollaborator,
} from "@/types/workspaceDocuments";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";


type StudioMode = "company" | "borrower" | "superadmin" | "platform";
type ViewMode = "tiles" | "list";
type VirtualFolder = "company-public" | "shared";
type SelectedFolder = string | VirtualFolder | null;

function defaultVisibility(mode: StudioMode): DocumentVisibility {
    // Company work is private by default. Staff deliberately promote a file to
    // Company public from the sharing dialog when everyone should see it.
    if (mode === "superadmin") return "platform";
    return "private";
}

function isVirtualFolder(value: SelectedFolder): value is VirtualFolder {
    return value === "company-public" || value === "shared";
}

export function DocumentFolderOrganizer({
    basePath,
    mode,
    resourceKind = "document",
}: {
    basePath: string;
    mode: StudioMode;
    resourceKind?: Exclude<WorkspaceItemKind, "all">;
}) {
    const importRef = useRef<HTMLInputElement>(null);
    const [folders, setFolders] = useState<WorkspaceDocumentFolder[]>([]);
    const [documents, setDocuments] = useState<WorkspaceDocument[]>([]);
    const [assignments, setAssignments] = useState<Record<string, string>>({});
    const [access, setAccess] = useState<WorkspaceOfficeAccess | null>(null);
    const [selectedFolder, setSelectedFolder] = useState<SelectedFolder>(null);
    const [folderName, setFolderName] = useState("");
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState(false);
    const [viewMode, setViewMode] = useState<ViewMode>("tiles");

    const [shareTarget, setShareTarget] = useState<WorkspaceDocument | null>(null);
    const [shareDirectory, setShareDirectory] = useState<WorkspaceSharingDirectoryUser[]>([]);
    const [collaborators, setCollaborators] = useState<WorkspaceDocumentCollaborator[]>([]);
    const [shareUserId, setShareUserId] = useState("");
    const [sharePermission, setSharePermission] = useState<DocumentPermission>("view");
    const [sharingBusy, setSharingBusy] = useState(false);

    const itemLabel = resourceKind === "spreadsheet" ? "workbook" : "document";
    const ItemIcon = resourceKind === "spreadsheet" ? FileSpreadsheet : FileText;
    const storageKey = `loanhub-office-${resourceKind}-view`;

    const load = useCallback(async () => {
        setLoading(true);
        try {
            // This also creates the staff member's personal root folder, named
            // after them, and safely files legacy unassigned work into it.
            await fileMyUnassignedWorkspaceItems(resourceKind);
            const [accessRow, folderRows, assignmentRows, documentRows] = await Promise.all([
                getWorkspaceOfficeAccess(),
                listWorkspaceDocumentFolders(resourceKind),
                listWorkspaceDocumentFolderAssignments(resourceKind),
                listWorkspaceDocuments({ kind: resourceKind, limit: 300 }),
            ]);
            setAccess(accessRow);
            setFolders(folderRows);
            setAssignments(assignmentRows);
            setDocuments(documentRows.items);

            setSelectedFolder((current) => {
                if (current && !isVirtualFolder(current) && !folderRows.some((row) => row.id === current)) {
                    return accessRow.is_company_owner ? null : (folderRows.find((row) => row.can_manage && row.is_personal)?.id ?? null);
                }
                if (current !== null) return current;
                if (accessRow.is_company_owner) return null;
                return folderRows.find((row) => row.can_manage && row.is_personal)?.id ?? null;
            });
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, `Could not load ${itemLabel} folders.`));
        } finally {
            setLoading(false);
        }
    }, [itemLabel, resourceKind]);

    useEffect(() => {
        const saved = window.localStorage.getItem(storageKey);
        if (saved === "tiles" || saved === "list") setViewMode(saved);
        void load();
    }, [load, storageKey]);

    const myFolderIds = useMemo(
        () => new Set(folders.filter((folder) => folder.can_manage).map((folder) => folder.id)),
        [folders],
    );
    const myOwnerId = useMemo(
        () => folders.find((folder) => folder.can_manage && folder.is_personal)?.owner_user_id ?? null,
        [folders],
    );
    const companyPublic = useMemo(
        () => documents.filter((document) => document.visibility === "company"),
        [documents],
    );
    const sharedWithMe = useMemo(
        () => documents.filter((document) =>
            !access?.is_company_owner
            && myOwnerId
            && document.owner_user_id !== myOwnerId
            && document.visibility !== "company"
        ),
        [access?.is_company_owner, documents, myOwnerId],
    );

    const visibleDocuments = useMemo(() => {
        if (selectedFolder === "company-public") return companyPublic;
        if (selectedFolder === "shared") return sharedWithMe;
        if (selectedFolder) {
            return documents.filter((document) => assignments[document.id] === selectedFolder);
        }
        if (access?.is_company_owner) return documents;
        return documents.filter((document) => {
            const folderId = assignments[document.id];
            return document.owner_user_id === myOwnerId && (!folderId || myFolderIds.has(folderId));
        });
    }, [access?.is_company_owner, assignments, companyPublic, documents, myFolderIds, myOwnerId, selectedFolder, sharedWithMe]);

    const ownerGroups = useMemo(() => {
        const groups = new Map<string, WorkspaceDocumentFolder[]>();
        for (const folder of folders) {
            const key = folder.owner_display_name || "Staff member";
            const current = groups.get(key) ?? [];
            current.push(folder);
            groups.set(key, current);
        }
        return [...groups.entries()].sort(([left], [right]) => left.localeCompare(right));
    }, [folders]);

    function chooseView(next: ViewMode) {
        setViewMode(next);
        window.localStorage.setItem(storageKey, next);
    }

    async function createFolder() {
        const name = folderName.trim();
        if (!name) return;
        setBusy(true);
        try {
            await createWorkspaceDocumentFolder(name);
            setFolderName("");
            toast.success("Folder created.");
            await load();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not create the folder."));
        } finally {
            setBusy(false);
        }
    }

    async function removeFolder(folder: WorkspaceDocumentFolder) {
        if (!folder.can_manage) return;
        setBusy(true);
        try {
            await deleteWorkspaceDocumentFolder(folder.id);
            if (selectedFolder === folder.id) setSelectedFolder(null);
            toast.success(`Folder removed. Its ${itemLabel}s were kept.`);
            await load();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not remove the folder."));
        } finally {
            setBusy(false);
        }
    }

    async function move(documentId: string, folderId: string | null) {
        try {
            await moveWorkspaceDocumentToFolder(documentId, folderId);
            setAssignments((current) => {
                const next = { ...current };
                if (folderId) next[documentId] = folderId;
                else delete next[documentId];
                return next;
            });
            toast.success(folderId ? `${itemLabel} moved.` : `${itemLabel} moved out of its folder.`);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, `Could not move the ${itemLabel}.`));
        }
    }

    async function importDocument(file: File) {
        setBusy(true);
        try {
            const folderId = selectedFolder && !isVirtualFolder(selectedFolder) && myFolderIds.has(selectedFolder)
                ? selectedFolder
                : null;
            const imported = await importWorkspaceDocument(file, {
                folderId,
                visibility: defaultVisibility(mode),
            });
            if (imported.warning) toast.info(imported.warning);
            toast.success(`${file.name} is ready to edit.`);
            window.location.assign(`${basePath}/${imported.id}`);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not import the document."));
        } finally {
            setBusy(false);
            if (importRef.current) importRef.current.value = "";
        }
    }

    async function openShare(document: WorkspaceDocument) {
        if (!document.can_manage) return;
        setShareTarget(document);
        setSharingBusy(true);
        try {
            const [people, rows] = await Promise.all([
                listWorkspaceSharingDirectory(),
                listWorkspaceDocumentCollaborators(document.id),
            ]);
            setShareDirectory(people);
            setCollaborators(rows);
            setShareUserId(people[0]?.user_id ?? "");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not load sharing options."));
        } finally {
            setSharingBusy(false);
        }
    }

    async function addShare() {
        if (!shareTarget || !shareUserId) return;
        setSharingBusy(true);
        try {
            await addWorkspaceDocumentCollaborator(shareTarget.id, {
                user_id: shareUserId,
                permission: sharePermission,
            });
            setCollaborators(await listWorkspaceDocumentCollaborators(shareTarget.id));
            toast.success("Sharing updated.");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not share this item."));
        } finally {
            setSharingBusy(false);
        }
    }

    async function removeShare(userId: string) {
        if (!shareTarget) return;
        setSharingBusy(true);
        try {
            await removeWorkspaceDocumentCollaborator(shareTarget.id, userId);
            setCollaborators((current) => current.filter((row) => row.user_id !== userId));
            toast.success("Direct access removed.");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not remove access."));
        } finally {
            setSharingBusy(false);
        }
    }

    async function changeVisibility(visibility: DocumentVisibility) {
        if (!shareTarget) return;
        setSharingBusy(true);
        try {
            const updated = await updateWorkspaceDocument(shareTarget.id, {
                visibility,
                expected_version: shareTarget.version,
                create_revision: false,
            });
            setShareTarget(updated);
            setDocuments((current) => current.map((row) => row.id === updated.id ? updated : row));
            toast.success(visibility === "company" ? "Visible to everyone in the company." : "Returned to private access.");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not change visibility."));
        } finally {
            setSharingBusy(false);
        }
    }

    const selectedTitle = selectedFolder === "company-public"
        ? "Company public"
        : selectedFolder === "shared"
          ? "Shared with me"
          : selectedFolder
            ? folders.find((folder) => folder.id === selectedFolder)?.name ?? "Folder"
            : access?.is_company_owner
              ? "Owner overview"
              : `My ${resourceKind === "spreadsheet" ? "spreadsheets" : "documents"}`;

    function ItemActions({ document }: { document: WorkspaceDocument }) {
        const managedFolders = folders.filter((folder) => folder.can_manage);
        return (
            <div className="flex flex-wrap items-center gap-2">
                {document.can_manage && (
                    <select
                        value={assignments[document.id] ?? ""}
                        onChange={(event) => void move(document.id, event.target.value || null)}
                        className="h-9 min-w-0 rounded-xl border bg-background px-2 text-xs font-semibold sm:max-w-48"
                        aria-label={`Move ${document.title} to folder`}
                    >
                        <option value="">No folder</option>
                        {managedFolders.map((folder) => (
                            <option key={folder.id} value={folder.id}>{folder.name}</option>
                        ))}
                    </select>
                )}
                {document.can_manage && (
                    <button
                        type="button"
                        onClick={() => void openShare(document)}
                        className="inline-flex h-9 items-center gap-1.5 rounded-xl border px-3 text-xs font-black hover:bg-muted"
                    >
                        <Share2 className="h-3.5 w-3.5" /> Share
                    </button>
                )}
            </div>
        );
    }

    return (
        <>
            <section className="overflow-hidden rounded-3xl border bg-card shadow-sm">
                <div className="flex flex-col gap-4 border-b bg-muted/20 p-4 lg:flex-row lg:items-center lg:justify-between md:p-5">
                    <div>
                        <div className="flex items-center gap-2 text-sm font-black">
                            <Folder className="h-4 w-4" />
                            {resourceKind === "spreadsheet" ? "Spreadsheet folders" : "Document folders"}
                        </div>
                        <p className="mt-1 max-w-2xl text-xs leading-5 text-muted-foreground">
                            {access?.is_company_owner
                                ? "Owner overview includes every staff member's company work. Staff ownership remains intact; editing still requires ownership or edit sharing."
                                : `Your work is filed under your staff-name folder. You also see company-public and directly shared ${itemLabel}s.`}
                        </p>
                    </div>
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                        <div className="flex gap-2">
                            <input
                                value={folderName}
                                onChange={(event) => setFolderName(event.target.value)}
                                onKeyDown={(event) => { if (event.key === "Enter") void createFolder(); }}
                                placeholder="New folder"
                                className="h-10 min-w-0 flex-1 rounded-xl border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/30 sm:w-44"
                            />
                            <button type="button" disabled={busy || !folderName.trim()} onClick={() => void createFolder()} className="inline-flex h-10 items-center gap-2 rounded-xl border bg-background px-3 text-sm font-bold hover:bg-muted disabled:opacity-50">
                                <FolderPlus className="h-4 w-4" /> Create
                            </button>
                        </div>
                        {resourceKind === "document" && (
                            <>
                                <input
                                    ref={importRef}
                                    type="file"
                                    accept=".docx,.pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/pdf"
                                    className="hidden"
                                    onChange={(event) => { const file = event.target.files?.[0]; if (file) void importDocument(file); }}
                                />
                                <button type="button" disabled={busy} onClick={() => importRef.current?.click()} className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground disabled:opacity-50">
                                    {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileUp className="h-4 w-4" />} Import Word / PDF
                                </button>
                            </>
                        )}
                    </div>
                </div>

                <div className="grid min-h-[320px] lg:grid-cols-[270px_minmax(0,1fr)]">
                    <aside className="border-b p-3 lg:border-b-0 lg:border-r">
                        {access?.is_company_owner && (
                            <button type="button" onClick={() => setSelectedFolder(null)} className={`mb-1 flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left text-sm ${selectedFolder === null ? "bg-primary/10 font-black text-primary" : "hover:bg-muted"}`}>
                                <span className="inline-flex items-center gap-2"><UsersRound className="h-4 w-4" />Owner overview</span>
                                <span className="text-xs text-muted-foreground">{documents.length}</span>
                            </button>
                        )}
                        {mode === "company" && (
                            <button type="button" onClick={() => setSelectedFolder("company-public")} className={`mb-1 flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left text-sm ${selectedFolder === "company-public" ? "bg-primary/10 font-black text-primary" : "hover:bg-muted"}`}>
                                <span className="inline-flex items-center gap-2"><Globe2 className="h-4 w-4" />Company public</span>
                                <span className="text-xs text-muted-foreground">{companyPublic.length}</span>
                            </button>
                        )}
                        {!access?.is_company_owner && sharedWithMe.length > 0 && (
                            <button type="button" onClick={() => setSelectedFolder("shared")} className={`mb-2 flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left text-sm ${selectedFolder === "shared" ? "bg-primary/10 font-black text-primary" : "hover:bg-muted"}`}>
                                <span className="inline-flex items-center gap-2"><Share2 className="h-4 w-4" />Shared with me</span>
                                <span className="text-xs text-muted-foreground">{sharedWithMe.length}</span>
                            </button>
                        )}

                        <div className="max-h-[460px] space-y-3 overflow-y-auto pr-1">
                            {ownerGroups.map(([ownerName, ownerFolders]) => (
                                <div key={ownerName}>
                                    {access?.is_company_owner && (
                                        <p className="mb-1 px-3 text-[10px] font-black uppercase tracking-[0.12em] text-muted-foreground">{ownerName}</p>
                                    )}
                                    <div className="space-y-1">
                                        {ownerFolders.map((folder) => (
                                            <div key={folder.id} className={`group flex items-center rounded-xl ${selectedFolder === folder.id ? "bg-primary/10 text-primary" : "hover:bg-muted"}`}>
                                                <button type="button" onClick={() => setSelectedFolder(folder.id)} className="flex min-w-0 flex-1 items-center gap-2 px-3 py-2.5 text-left text-sm">
                                                    <Folder className="h-4 w-4 shrink-0" />
                                                    <span className="truncate font-semibold">{folder.name}</span>
                                                    <span className="ml-auto text-xs text-muted-foreground">{folder.document_count}</span>
                                                </button>
                                                {folder.can_manage && !folder.is_personal && (
                                                    <button type="button" title="Delete folder" disabled={busy || folder.child_count > 0} onClick={() => void removeFolder(folder)} className="mr-1 rounded-lg p-2 opacity-60 hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100 disabled:cursor-not-allowed disabled:opacity-20">
                                                        <Trash2 className="h-3.5 w-3.5" />
                                                    </button>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </aside>

                    <div className="min-w-0 p-4">
                        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                            <div>
                                <h3 className="font-black">{selectedTitle}</h3>
                                <p className="mt-0.5 text-xs text-muted-foreground">{visibleDocuments.length} {itemLabel}{visibleDocuments.length === 1 ? "" : "s"}</p>
                            </div>
                            <div className="inline-flex w-fit rounded-xl border bg-muted/20 p-1" aria-label="Choose folder view">
                                <button type="button" onClick={() => chooseView("tiles")} className={`inline-flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-xs font-black ${viewMode === "tiles" ? "bg-background shadow-sm" : "text-muted-foreground"}`}><Grid2X2 className="h-3.5 w-3.5" /> Tiles</button>
                                <button type="button" onClick={() => chooseView("list")} className={`inline-flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-xs font-black ${viewMode === "list" ? "bg-background shadow-sm" : "text-muted-foreground"}`}><List className="h-3.5 w-3.5" /> List</button>
                            </div>
                        </div>

                        {loading ? (
                            <div className="flex h-36 items-center justify-center text-muted-foreground"><Loader2 className="h-5 w-5 animate-spin" /></div>
                        ) : visibleDocuments.length === 0 ? (
                            <div className="rounded-2xl border border-dashed p-8 text-center text-sm text-muted-foreground">No {itemLabel}s are in this view yet.</div>
                        ) : viewMode === "tiles" ? (
                            <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
                                {visibleDocuments.map((document) => (
                                    <article key={document.id} className="rounded-2xl border bg-background p-4 transition hover:border-primary/50 hover:shadow-sm">
                                        <Link href={`${basePath}/${document.id}`} className="block">
                                            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary"><ItemIcon className="h-5 w-5" /></span>
                                            <h4 className="mt-3 line-clamp-2 font-black">{document.title}</h4>
                                            <p className="mt-1 truncate text-xs text-muted-foreground">{document.reference} · v{document.version}</p>
                                        </Link>
                                        <div className="mt-3 flex flex-wrap gap-1.5 text-[10px] font-bold">
                                            <span className="rounded-full bg-muted px-2 py-1">{document.owner_display_name}</span>
                                            {document.visibility === "company" && <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-1 text-emerald-800"><Globe2 className="h-3 w-3" />Company public</span>}
                                            {document.collaborator_count > 0 && <span className="rounded-full bg-primary/10 px-2 py-1 text-primary">Shared · {document.collaborator_count}</span>}
                                            {!document.can_edit && <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-1"><Eye className="h-3 w-3" />View only</span>}
                                        </div>
                                        <div className="mt-4 border-t pt-3"><ItemActions document={document} /></div>
                                    </article>
                                ))}
                            </div>
                        ) : (
                            <div className="overflow-hidden rounded-2xl border">
                                {visibleDocuments.map((document) => (
                                    <div key={document.id} className="flex flex-col gap-3 border-b p-3 last:border-b-0 sm:flex-row sm:items-center">
                                        <Link href={`${basePath}/${document.id}`} className="flex min-w-0 flex-1 items-center gap-3">
                                            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary"><ItemIcon className="h-4 w-4" /></span>
                                            <span className="min-w-0">
                                                <span className="block truncate text-sm font-black">{document.title}</span>
                                                <span className="block truncate text-xs text-muted-foreground">{document.owner_display_name} · {document.reference} · v{document.version}</span>
                                            </span>
                                        </Link>
                                        <div className="flex items-center gap-2">
                                            {document.visibility === "company" && <Globe2 className="h-4 w-4 text-emerald-600" aria-label="Company public" />}
                                            {document.can_edit ? <Pencil className="h-4 w-4 text-muted-foreground" aria-label="Can edit" /> : <Eye className="h-4 w-4 text-muted-foreground" aria-label="View only" />}
                                        </div>
                                        <ItemActions document={document} />
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </section>

            <CustomDialog
                open={Boolean(shareTarget)}
                onOpenChange={(open) => {
                    if (!open && !sharingBusy) setShareTarget(null);
                }}
                title={shareTarget ? `Share ${shareTarget.title}` : "Share workspace item"}
                description="Keep it private, make it public inside this company, or give selected staff view/edit access."
                contentClassName="sm:max-w-2xl"
            >
                {shareTarget && (
                    <div className="space-y-5 py-2">
                        {mode === "company" && (
                            <div className="rounded-2xl border p-4">
                                <p className="text-sm font-black">Company visibility</p>
                                <p className="mt-1 text-xs leading-5 text-muted-foreground">Private items stay with you and direct collaborators. Company public items can be seen by all staff in this company.</p>
                                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                                    <button type="button" disabled={sharingBusy} onClick={() => void changeVisibility("private")} className={`rounded-xl border p-3 text-left text-sm ${shareTarget.visibility === "private" ? "border-primary bg-primary/10 text-primary" : "hover:bg-muted"}`}><span className="block font-black">Private</span><span className="mt-1 block text-xs text-muted-foreground">Owner + direct shares only</span></button>
                                    <button type="button" disabled={sharingBusy} onClick={() => void changeVisibility("company")} className={`rounded-xl border p-3 text-left text-sm ${shareTarget.visibility === "company" ? "border-emerald-600 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400" : "hover:bg-muted"}`}><span className="block font-black">Company public</span><span className="mt-1 block text-xs text-muted-foreground">Visible to everyone in company</span></button>
                                </div>
                            </div>
                        )}

                        <div className="rounded-2xl border p-4">
                            <p className="text-sm font-black">Share with a staff member</p>
                            <div className="mt-3 grid gap-2 sm:grid-cols-[minmax(0,1fr)_120px_auto]">
                                <select value={shareUserId} onChange={(event) => setShareUserId(event.target.value)} className="h-10 min-w-0 rounded-xl border bg-background px-3 text-sm" disabled={sharingBusy}>
                                    <option value="">Select staff member...</option>
                                    {shareDirectory.map((person) => <option key={person.user_id} value={person.user_id}>{person.display_name} · {person.role.replaceAll("_", " ")}</option>)}
                                </select>
                                <select value={sharePermission} onChange={(event) => setSharePermission(event.target.value as DocumentPermission)} className="h-10 rounded-xl border bg-background px-3 text-sm" disabled={sharingBusy}>
                                    <option value="view">Can view</option>
                                    <option value="edit">Can edit</option>
                                </select>
                                <button type="button" onClick={() => void addShare()} disabled={sharingBusy || !shareUserId} className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground disabled:opacity-50">{sharingBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Share2 className="h-4 w-4" />} Share</button>
                            </div>
                        </div>

                        <div>
                            <p className="mb-2 text-sm font-black">Direct access</p>
                            {collaborators.length === 0 ? (
                                <div className="rounded-xl border border-dashed p-4 text-center text-xs text-muted-foreground">No direct collaborators yet.</div>
                            ) : (
                                <div className="space-y-2">
                                    {collaborators.map((row) => (
                                        <div key={row.id} className="flex items-center justify-between gap-3 rounded-xl border p-3">
                                            <div className="min-w-0"><p className="truncate text-sm font-black">{row.display_name}</p><p className="truncate text-xs text-muted-foreground">{row.permission === "edit" ? "Can edit" : "Can view"}</p></div>
                                            <button type="button" onClick={() => void removeShare(row.user_id)} disabled={sharingBusy} className="rounded-lg border px-3 py-1.5 text-xs font-black hover:bg-destructive/10 hover:text-destructive disabled:opacity-50">Remove</button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </CustomDialog>
        </>
    );
}
