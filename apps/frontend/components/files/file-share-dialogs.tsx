"use client";

import {
    Check,
    Clock3,
    Copy,
    ExternalLink,
    Link2,
    Loader2,
    Mail,
    MessageCircle,
    MessagesSquare,
    Send,
    Share2,
    ShieldCheck,
    UserRound,
    UsersRound,
    X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
    createChatConversation,
    listChatConversations,
    listChatDirectory,
    shareManagedFileInChat,
} from "@/api/chat";
import {
    createExternalFileShare,
    listExternalFileShares,
    revokeExternalFileShare,
} from "@/api/files";
import { getCompanySocialShareSettings } from "@/api/social-sharing";
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
import { SuggestionSearch } from "@/components/ui/suggestion-search";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { createUuid } from "@/lib/uuid";
import type { ChatConversation, ChatUser } from "@/types/chat";
import type {
    CompanySocialShareSettings,
    ExternalFileShare,
    ManagedFile,
} from "@/types/files";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

function randomClientId(): string {
    return createUuid();
}

export function InternalFileShareDialog({
    file,
    open,
    onOpenChange,
    chatPath,
}: {
    file: ManagedFile | null;
    open: boolean;
    onOpenChange: (open: boolean) => void;
    chatPath: string;
}) {
    const [tab, setTab] = useState("conversation");
    const [conversations, setConversations] = useState<ChatConversation[]>([]);
    const [directory, setDirectory] = useState<ChatUser[]>([]);
    const [selectedConversationId, setSelectedConversationId] = useState("");
    const [selectedUserIds, setSelectedUserIds] = useState<string[]>([]);
    const [search, setSearch] = useState("");
    const [message, setMessage] = useState("");
    const [loading, setLoading] = useState(false);
    const [sharing, setSharing] = useState(false);
    const [sharedConversationId, setSharedConversationId] = useState<string | null>(null);

    useEffect(() => {
        if (!open || !file) return;
        setMessage(`Shared document: ${file.original_name}`);
        setSharedConversationId(null);
        setSelectedUserIds([]);
        setSelectedConversationId("");
        setSearch("");
        setLoading(true);
        void Promise.all([listChatConversations(), listChatDirectory()])
            .then(([conversationItems, users]) => {
                setConversations(conversationItems);
                setDirectory(users);
            })
            .catch((error: unknown) => {
                toast.error(getErrorMessage(error, "Chat recipients could not be loaded."));
            })
            .finally(() => setLoading(false));
    }, [file, open]);

    const filteredUsers = useMemo(() => {
        const token = search.trim().toLowerCase();
        if (!token) return directory;
        return directory.filter((user) =>
            `${user.display_name} ${user.email ?? ""} ${user.phone} ${user.role} ${user.company_name ?? ""}`
                .toLowerCase()
                .includes(token),
        );
    }, [directory, search]);

    function toggleUser(userId: string) {
        setSelectedUserIds((current) =>
            current.includes(userId)
                ? current.filter((item) => item !== userId)
                : [...current, userId],
        );
    }

    async function share() {
        if (!file || sharing) return;
        if (tab === "conversation" && !selectedConversationId) {
            toast.error("Select a chat conversation.");
            return;
        }
        if (tab === "people" && selectedUserIds.length === 0) {
            toast.error("Select at least one person.");
            return;
        }

        setSharing(true);
        try {
            let conversationId = selectedConversationId;
            if (tab === "people") {
                const selectedNames = directory
                    .filter((user) => selectedUserIds.includes(user.id))
                    .map((user) => user.display_name);
                const conversation = await createChatConversation({
                    participant_ids: selectedUserIds,
                    title:
                        selectedNames.length > 1
                            ? `Document share: ${file.original_name}`
                            : undefined,
                    conversation_type: selectedNames.length > 1 ? "group" : "direct",
                    context_type: "managed_file",
                    context_id: file.id,
                });
                conversationId = conversation.id;
            }

            await shareManagedFileInChat(conversationId, file.id, {
                body: message.trim() || undefined,
                client_message_id: randomClientId(),
            });
            setSharedConversationId(conversationId);
            toast.success("The document was shared in LoanHub chat.");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "The document could not be shared internally."));
        } finally {
            setSharing(false);
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-2xl">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <MessagesSquare className="h-5 w-5 text-primary" />
                        Share internally
                    </DialogTitle>
                    <DialogDescription>
                        Share {file?.original_name ?? "this document"} with authorised LoanHub users. It will appear as a normal chat attachment.
                    </DialogDescription>
                </DialogHeader>

                {loading ? (
                    <div className="flex min-h-60 items-center justify-center">
                        <Loader2 className="h-6 w-6 animate-spin text-primary" />
                    </div>
                ) : sharedConversationId ? (
                    <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-200">
                        <div className="flex items-start gap-3">
                            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100 dark:bg-emerald-900">
                                <Check className="h-5 w-5" />
                            </div>
                            <div>
                                <p className="font-black">Shared successfully</p>
                                <p className="mt-1 text-sm leading-6">Recipients can open the managed file directly from the conversation.</p>
                            </div>
                        </div>
                        <Button
                            type="button"
                            className="mt-4 w-full"
                            onClick={() => window.location.assign(`${chatPath}?conversation=${sharedConversationId}`)}
                        >
                            <MessageCircle className="h-4 w-4" />
                            Open conversation
                        </Button>
                    </div>
                ) : (
                    <>
                        <Tabs value={tab} onValueChange={setTab}>
                            <TabsList className="grid h-11 w-full grid-cols-2 rounded-xl">
                                <TabsTrigger value="conversation" className="rounded-lg">
                                    <MessageCircle className="h-4 w-4" /> Existing chat
                                </TabsTrigger>
                                <TabsTrigger value="people" className="rounded-lg">
                                    <UsersRound className="h-4 w-4" /> Choose people
                                </TabsTrigger>
                            </TabsList>

                            <TabsContent value="conversation" className="mt-4">
                                <label className="text-xs font-black uppercase tracking-wide text-muted-foreground">Conversation</label>
                                <NativeSelect
                                    value={selectedConversationId}
                                    onChange={(event) => setSelectedConversationId(event.target.value)}
                                    className="mt-2 h-12 w-full rounded-xl border bg-background px-3 text-sm font-bold"
                                >
                                    <option value="">Select an existing conversation</option>
                                    {conversations.map((conversation) => (
                                        <option key={conversation.id} value={conversation.id}>
                                            {conversation.title} ({conversation.participants.length} participant{conversation.participants.length === 1 ? "" : "s"})
                                        </option>
                                    ))}
                                </NativeSelect>
                                {conversations.length === 0 && (
                                    <p className="mt-3 rounded-xl bg-muted/50 p-3 text-xs text-muted-foreground">No chat exists yet. Use “Choose people” to create one.</p>
                                )}
                            </TabsContent>

                            <TabsContent value="people" className="mt-4 space-y-3">
                                <SuggestionSearch
                                    value={search}
                                    onValueChange={setSearch}
                                    suggestions={directory.map((user) => ({
                                        value: user.display_name,
                                        label: user.display_name,
                                        description: `${user.role.replaceAll("_", " ")} · ${user.company_name ?? user.phone}`,
                                        keywords: [user.email ?? "", user.phone, user.role, user.company_name ?? ""],
                                    }))}
                                    placeholder="Type a name, phone, email or role..."
                                    suggestionLabel="LoanHub people"
                                    emptyMessage="No authorised user matches that search."
                                />
                                <div className="max-h-64 space-y-2 overflow-y-auto pr-1">
                                    {filteredUsers.map((user) => {
                                        const selected = selectedUserIds.includes(user.id);
                                        return (
                                            <button
                                                key={user.id}
                                                type="button"
                                                onClick={() => toggleUser(user.id)}
                                                className={`flex w-full items-center gap-3 rounded-2xl border p-3 text-left transition ${selected ? "border-primary bg-primary/5" : "hover:border-primary/40 hover:bg-muted/30"}`}
                                            >
                                                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                                                    <UserRound className="h-5 w-5" />
                                                </div>
                                                <div className="min-w-0 flex-1">
                                                    <p className="truncate font-black">{user.display_name}</p>
                                                    <p className="mt-1 truncate text-xs text-muted-foreground">{user.role.replaceAll("_", " ")} · {user.company_name ?? user.phone}</p>
                                                </div>
                                                <div className={`flex h-6 w-6 items-center justify-center rounded-full border ${selected ? "border-primary bg-primary text-primary-foreground" : ""}`}>
                                                    {selected && <Check className="h-3.5 w-3.5" />}
                                                </div>
                                            </button>
                                        );
                                    })}
                                </div>
                            </TabsContent>
                        </Tabs>

                        <div>
                            <label className="text-xs font-black uppercase tracking-wide text-muted-foreground">Message</label>
                            <Textarea
                                value={message}
                                onChange={(event) => setMessage(event.target.value)}
                                rows={3}
                                className="mt-2"
                                placeholder="Add a short note for the recipients..."
                            />
                        </div>

                        <div className="flex items-start gap-2 rounded-2xl bg-muted/50 p-3 text-xs leading-5 text-muted-foreground">
                            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                            Internal sharing does not create a public link. Only active participants in the selected LoanHub conversation can access the attachment.
                        </div>
                    </>
                )}

                {!sharedConversationId && (
                    <DialogFooter>
                        <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={sharing}>Cancel</Button>
                        <Button type="button" onClick={() => void share()} disabled={sharing}>
                            {sharing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                            Share in chat
                        </Button>
                    </DialogFooter>
                )}
            </DialogContent>
        </Dialog>
    );
}

const DEFAULT_CHANNELS = ["native", "copy", "whatsapp", "email"];

function socialUrl(channel: string, shareUrl: string, title: string, message: string): string | null {
    const url = encodeURIComponent(shareUrl);
    const text = encodeURIComponent(`${message}\n${title}`.trim());
    switch (channel) {
        case "whatsapp":
            return `https://wa.me/?text=${text}%0A${url}`;
        case "facebook":
            return `https://www.facebook.com/sharer/sharer.php?u=${url}`;
        case "linkedin":
            return `https://www.linkedin.com/sharing/share-offsite/?url=${url}`;
        case "x":
            return `https://twitter.com/intent/tweet?text=${text}&url=${url}`;
        case "telegram":
            return `https://t.me/share/url?url=${url}&text=${text}`;
        case "email":
            return `mailto:?subject=${encodeURIComponent(title)}&body=${text}%0A%0A${url}`;
        default:
            return null;
    }
}

export function ExternalFileShareDialog({
    file,
    open,
    onOpenChange,
    settingsPath,
}: {
    file: ManagedFile | null;
    open: boolean;
    onOpenChange: (open: boolean) => void;
    settingsPath: string;
}) {
    const [settings, setSettings] = useState<CompanySocialShareSettings | null>(null);
    const [shares, setShares] = useState<ExternalFileShare[]>([]);
    const [expiry, setExpiry] = useState("24");
    const [label, setLabel] = useState("");
    const [message, setMessage] = useState("");
    const [loading, setLoading] = useState(false);
    const [creating, setCreating] = useState(false);
    const [revokingId, setRevokingId] = useState<string | null>(null);
    const [createdShare, setCreatedShare] = useState<ExternalFileShare | null>(null);

    useEffect(() => {
        if (!open || !file) return;
        setLoading(true);
        setCreatedShare(null);
        setLabel(file.original_name);
        const settingsPromise = file.company_id
            ? getCompanySocialShareSettings(file.company_id)
            : Promise.resolve(null);
        void Promise.all([settingsPromise, listExternalFileShares(file.id)])
            .then(([socialSettings, shareItems]) => {
                setSettings(socialSettings);
                setShares(shareItems);
                setExpiry(String(socialSettings?.default_expiry_hours ?? 24));
                setMessage(
                    socialSettings?.default_message ??
                    "A secure LoanHub document has been shared with you.",
                );
            })
            .catch((error: unknown) => {
                toast.error(getErrorMessage(error, "External sharing information could not be loaded."));
            })
            .finally(() => setLoading(false));
    }, [file, open]);

    const enabled = file?.company_id ? Boolean(settings?.external_sharing_enabled) : true;
    const channels = settings?.enabled_channels?.length ? settings.enabled_channels : DEFAULT_CHANNELS;

    async function generate() {
        if (!file || creating) return;
        setCreating(true);
        try {
            const result = await createExternalFileShare(file.id, {
                expires_in_hours: Number(expiry),
                label: label.trim() || undefined,
                allow_download: true,
            });
            setCreatedShare(result);
            setShares((current) => [result, ...current]);
            toast.success("Secure external link generated.");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "A secure external link could not be created."));
        } finally {
            setCreating(false);
        }
    }

    async function copyUrl() {
        const url = createdShare?.share_url;
        if (!url) return;
        await navigator.clipboard.writeText(url);
        toast.success("Secure link copied.");
    }

    async function shareNative() {
        const url = createdShare?.share_url;
        if (!url) return;
        if (navigator.share) {
            await navigator.share({ title: file?.original_name, text: message, url });
            return;
        }
        await copyUrl();
    }

    function openChannel(channel: string) {
        const url = createdShare?.share_url;
        if (!url || !file) return;
        if (channel === "native") {
            void shareNative();
            return;
        }
        if (channel === "copy") {
            void copyUrl();
            return;
        }
        const destination = socialUrl(channel, url, file.original_name, message);
        if (destination) window.open(destination, "_blank", "noopener,noreferrer");
    }

    async function revoke(shareId: string) {
        if (!file) return;
        setRevokingId(shareId);
        try {
            await revokeExternalFileShare(file.id, shareId);
            setShares((current) =>
                current.map((item) =>
                    item.id === shareId ? { ...item, revoked_at: new Date().toISOString() } : item,
                ),
            );
            if (createdShare?.id === shareId) setCreatedShare(null);
            toast.success("External link revoked.");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "The link could not be revoked."));
        } finally {
            setRevokingId(null);
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-2xl">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Share2 className="h-5 w-5 text-primary" />
                        Share externally
                    </DialogTitle>
                    <DialogDescription>
                        Create a temporary public link, then share it through the social channels enabled by your company.
                    </DialogDescription>
                </DialogHeader>

                {loading ? (
                    <div className="flex min-h-60 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-primary" /></div>
                ) : !enabled ? (
                    <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
                        <p className="font-black">External sharing is disabled</p>
                        <p className="mt-1 text-sm leading-6">A company owner or administrator must enable it and choose permitted social channels in Company Settings.</p>
                        <Button type="button" className="mt-4" onClick={() => window.location.assign(`${settingsPath}?tab=social-sharing`)}>
                            Open social sharing settings
                        </Button>
                    </div>
                ) : (
                    <div className="space-y-5">
                        {!createdShare ? (
                            <div className="rounded-2xl border bg-muted/20 p-4 sm:p-5">
                                <div className="grid gap-4 sm:grid-cols-2">
                                    <div>
                                        <label className="text-xs font-black uppercase tracking-wide text-muted-foreground">Link expiry</label>
                                        <NativeSelect value={expiry} onChange={(event) => setExpiry(event.target.value)} className="mt-2 h-11 w-full rounded-xl border bg-background px-3 text-sm font-bold">
                                            <option value="1">1 hour</option>
                                            <option value="6">6 hours</option>
                                            <option value="24">24 hours</option>
                                            <option value="72">3 days</option>
                                            <option value="168">7 days</option>
                                        </NativeSelect>
                                    </div>
                                    <div>
                                        <label className="text-xs font-black uppercase tracking-wide text-muted-foreground">Link label</label>
                                        <Input value={label} onChange={(event) => setLabel(event.target.value)} className="mt-2 h-11" />
                                    </div>
                                </div>
                                <div className="mt-4">
                                    <label className="text-xs font-black uppercase tracking-wide text-muted-foreground">Share message</label>
                                    <Textarea value={message} onChange={(event) => setMessage(event.target.value)} rows={3} className="mt-2" />
                                </div>
                                <Button type="button" className="mt-4 w-full" onClick={() => void generate()} disabled={creating || file?.is_confidential}>
                                    {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Link2 className="h-4 w-4" />}
                                    Generate secure link
                                </Button>
                                {file?.is_confidential && (
                                    <p className="mt-3 text-xs font-bold text-red-600">Confidential files cannot be shared externally.</p>
                                )}
                            </div>
                        ) : (
                            <div className="rounded-2xl border border-primary/20 bg-primary/5 p-4 sm:p-5">
                                <div className="flex items-start gap-3">
                                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground"><Link2 className="h-5 w-5" /></div>
                                    <div className="min-w-0 flex-1">
                                        <p className="font-black">Secure link ready</p>
                                        <p className="mt-1 text-xs text-muted-foreground">Expires {new Date(createdShare.expires_at).toLocaleString("en-LS")}</p>
                                    </div>
                                </div>
                                <div className="mt-4 flex items-center gap-2 rounded-xl border bg-background p-2">
                                    <Input readOnly value={createdShare.share_url ?? ""} className="border-0 shadow-none" />
                                    <Button type="button" size="icon" variant="outline" onClick={() => void copyUrl()}><Copy className="h-4 w-4" /></Button>
                                </div>
                                <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
                                    {channels.map((channel) => (
                                        <Button key={channel} type="button" variant="outline" onClick={() => openChannel(channel)} className="capitalize">
                                            {channel === "email" ? <Mail className="h-4 w-4" /> : channel === "native" ? <Share2 className="h-4 w-4" /> : channel === "copy" ? <Copy className="h-4 w-4" /> : <ExternalLink className="h-4 w-4" />}
                                            {channel === "native" ? "Share" : channel}
                                        </Button>
                                    ))}
                                </div>
                            </div>
                        )}

                        <div>
                            <div className="flex items-center justify-between gap-3">
                                <div>
                                    <p className="font-black">Previous links</p>
                                    <p className="mt-1 text-xs text-muted-foreground">Links can be revoked immediately. Raw link tokens are never shown again after creation.</p>
                                </div>
                                <Clock3 className="h-5 w-5 text-muted-foreground" />
                            </div>
                            <div className="mt-3 max-h-48 space-y-2 overflow-y-auto">
                                {shares.length === 0 && <p className="rounded-xl bg-muted/40 p-3 text-xs text-muted-foreground">No external links have been created for this file.</p>}
                                {shares.map((share) => {
                                    const expired = new Date(share.expires_at).getTime() <= Date.now();
                                    const inactive = Boolean(share.revoked_at) || expired;
                                    return (
                                        <div key={share.id} className="flex items-center gap-3 rounded-xl border p-3">
                                            <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${inactive ? "bg-muted text-muted-foreground" : "bg-emerald-100 text-emerald-700"}`}>
                                                <Link2 className="h-4 w-4" />
                                            </div>
                                            <div className="min-w-0 flex-1">
                                                <p className="truncate text-sm font-black">{share.label ?? file?.original_name}</p>
                                                <p className="mt-1 text-xs text-muted-foreground">{inactive ? (share.revoked_at ? "Revoked" : "Expired") : `Expires ${new Date(share.expires_at).toLocaleString("en-LS")}`} · {share.access_count} access{share.access_count === 1 ? "" : "es"}</p>
                                            </div>
                                            {!inactive && (
                                                <Button type="button" size="icon" variant="outline" onClick={() => void revoke(share.id)} disabled={revokingId === share.id} title="Revoke link">
                                                    {revokingId === share.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <X className="h-4 w-4" />}
                                                </Button>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        </div>

                        <div className="flex items-start gap-2 rounded-2xl bg-muted/50 p-3 text-xs leading-5 text-muted-foreground">
                            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                            External sharing creates an expiring public link. Do not use it for confidential KYC, identity, payroll or protected borrower documents.
                        </div>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}
