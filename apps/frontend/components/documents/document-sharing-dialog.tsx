"use client";

import { Loader2, Search, Trash2, UserPlus, UsersRound } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
    addWorkspaceDocumentCollaborator,
    listWorkspaceDocumentCollaborators,
    removeWorkspaceDocumentCollaborator,
} from "@/api/workspaceDocuments";
import { listChatDirectory } from "@/api/chat";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import type { ChatUser } from "@/types/chat";
import type {
    DocumentPermission,
    WorkspaceDocument,
    WorkspaceDocumentCollaborator,
} from "@/types/workspaceDocuments";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

export function DocumentSharingDialog({
    document,
    open,
    onOpenChange,
}: {
    document: WorkspaceDocument | null;
    open: boolean;
    onOpenChange: (open: boolean) => void;
}) {
    const [collaborators, setCollaborators] = useState<WorkspaceDocumentCollaborator[]>([]);
    const [directory, setDirectory] = useState<ChatUser[]>([]);
    const [search, setSearch] = useState("");
    const [selectedUserId, setSelectedUserId] = useState("");
    const [permission, setPermission] = useState<DocumentPermission>("view");
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);

    const load = useCallback(async () => {
        if (!document || !open) return;
        setLoading(true);
        try {
            const [current, users] = await Promise.all([
                listWorkspaceDocumentCollaborators(document.id),
                listChatDirectory(),
            ]);
            setCollaborators(current);
            setDirectory(users);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not load document sharing."));
        } finally {
            setLoading(false);
        }
    }, [document, open]);

    useEffect(() => {
        void load();
    }, [load]);

    const availableUsers = useMemo(() => {
        const existing = new Set(collaborators.map((item) => item.user_id));
        const token = search.trim().toLowerCase();
        return directory.filter((user) => {
            if (existing.has(user.id)) return false;
            if (!token) return true;
            return `${user.display_name} ${user.email ?? ""} ${user.phone} ${user.role}`
                .toLowerCase()
                .includes(token);
        });
    }, [collaborators, directory, search]);

    async function addCollaborator() {
        if (!document || !selectedUserId) {
            toast.error("Choose a user to share with.");
            return;
        }
        setSaving(true);
        try {
            const added = await addWorkspaceDocumentCollaborator(document.id, {
                user_id: selectedUserId,
                permission,
            });
            setCollaborators((current) => [added, ...current.filter((item) => item.user_id !== added.user_id)]);
            setSelectedUserId("");
            toast.success(`Shared with ${added.display_name}`);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not share the document."));
        } finally {
            setSaving(false);
        }
    }

    async function remove(userId: string) {
        if (!document) return;
        try {
            await removeWorkspaceDocumentCollaborator(document.id, userId);
            setCollaborators((current) => current.filter((item) => item.user_id !== userId));
            toast.success("Document access removed");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not remove access."));
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-2xl">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <UsersRound className="h-5 w-5 text-primary" />
                        Share editable document
                    </DialogTitle>
                    <DialogDescription>
                        Give authorised LoanHub users view-only or editing access. The owner remains in control.
                    </DialogDescription>
                </DialogHeader>

                {loading ? (
                    <div className="flex justify-center p-10"><Loader2 className="h-6 w-6 animate-spin text-primary" /></div>
                ) : (
                    <div className="space-y-5">
                        <section className="rounded-2xl border bg-muted/20 p-4">
                            <div className="relative">
                                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                <Input value={search} onChange={(event) => setSearch(event.target.value)} className="pl-9" placeholder="Search people by name, phone, email or role" />
                            </div>
                            <div className="mt-3 grid gap-3 sm:grid-cols-[minmax(0,1fr)_150px_auto]">
                                <NativeSelect value={selectedUserId} onChange={(event) => setSelectedUserId(event.target.value)} className="h-10 rounded-xl border bg-background px-3">
                                    <option value="">Select a user</option>
                                    {availableUsers.slice(0, 100).map((user) => (
                                        <option key={user.id} value={user.id}>{user.display_name} · {user.role}</option>
                                    ))}
                                </NativeSelect>
                                <NativeSelect value={permission} onChange={(event) => setPermission(event.target.value as DocumentPermission)} className="h-10 rounded-xl border bg-background px-3">
                                    <option value="view">Can view</option>
                                    <option value="edit">Can edit</option>
                                </NativeSelect>
                                <Button type="button" onClick={() => void addCollaborator()} disabled={saving || !selectedUserId} className="h-10">
                                    {saving ? <Loader2 className="animate-spin" /> : <UserPlus />}
                                    Share
                                </Button>
                            </div>
                        </section>

                        <section>
                            <h3 className="text-sm font-black">People with access</h3>
                            <div className="mt-3 divide-y overflow-hidden rounded-2xl border">
                                {collaborators.map((item) => (
                                    <div key={item.id} className="flex items-center gap-3 bg-card p-4">
                                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 font-black text-primary">
                                            {item.display_name.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase()}
                                        </div>
                                        <div className="min-w-0 flex-1">
                                            <p className="truncate font-black">{item.display_name}</p>
                                            <p className="truncate text-xs text-muted-foreground">{item.email ?? item.phone ?? "LoanHub user"}</p>
                                        </div>
                                        <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-black text-primary">{item.permission === "edit" ? "Can edit" : "Can view"}</span>
                                        <Button type="button" variant="ghost" size="icon" onClick={() => void remove(item.user_id)} aria-label={`Remove ${item.display_name}`}>
                                            <Trash2 className="text-red-600" />
                                        </Button>
                                    </div>
                                ))}
                                {collaborators.length === 0 && <p className="p-6 text-center text-sm text-muted-foreground">This document has not been shared with anyone yet.</p>}
                            </div>
                        </section>
                    </div>
                )}

                <DialogFooter showCloseButton />
            </DialogContent>
        </Dialog>
    );
}
