"use client";


import { createUuid } from "@/lib/uuid";
import { Input } from "@/components/ui/input";
import { SuggestionSearch } from "@/components/ui/suggestion-search";
import { Textarea } from "@/components/ui/textarea";
import {
    ArrowLeft,
    Download,
    FileText,
    Loader2,
    MessageCircleMore,
    Paperclip,
    Plus,
    Search,
    Send,
    Users,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "@/utils/toast";

import {
    createChatConversation,
    listChatDirectory,
    listChatMessages,
    sendChatFile,
    sendChatMessage,
} from "@/api/chat";
import { downloadManagedFile } from "@/api/files";
import { IthutePoweredBy } from "@/components/brand/ithute-brand";
import { Button } from "@/components/ui/button";
import { CustomDialog } from "@/components/ui/custom-dialog";
import { DialogFooter } from "@/components/ui/dialog";
import { LoadingButton } from "@/components/ui/loading-button";
import { VoiceRecorderButton } from "@/components/chat/voice-recorder-button";
import { SecureAudioPlayer } from "@/components/chat/secure-audio-player";
import { useChat } from "@/provider/chatProvider";
import { useAppSelector } from "@/store/hooks";
import type { ChatConversation, ChatMessage, ChatUser } from "@/types/chat";
import { getErrorMessage } from "@/utils/apiError";

function formatTime(value: string): string {
    return new Intl.DateTimeFormat("en-LS", {
        hour: "2-digit",
        minute: "2-digit",
    }).format(new Date(value));
}

function conversationPreview(conversation: ChatConversation): string {
    if (!conversation.last_message) return "Start the conversation";
    if (conversation.last_message.deleted_at) return "Message deleted";
    if (conversation.last_message.attachments.length) {
        return `Document: ${conversation.last_message.attachments[0].original_name}`;
    }
    return conversation.last_message.body ?? "New message";
}

export function ChatWorkspace({ mode }: { mode: "company" | "borrower" | "superadmin" }) {
    const user = useAppSelector((state) => state.auth.user);
    const {
        conversations,
        loading,
        connected,
        latestEvent,
        typingUsers,
        presence,
        refresh,
        markRead,
        sendTyping,
    } = useChat();

    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [messageLoading, setMessageLoading] = useState(false);
    const [sending, setSending] = useState(false);
    const [composer, setComposer] = useState("");
    const [search, setSearch] = useState("");
    const [newOpen, setNewOpen] = useState(false);
    const [directory, setDirectory] = useState<ChatUser[]>([]);
    const [selectedUsers, setSelectedUsers] = useState<string[]>([]);
    const [groupTitle, setGroupTitle] = useState("");
    const [creating, setCreating] = useState(false);
    const [mobileConversationOpen, setMobileConversationOpen] = useState(false);
    const fileInputRef = useRef<HTMLInputElement | null>(null);
    const endRef = useRef<HTMLDivElement | null>(null);
    const typingTimer = useRef<number | null>(null);

    const selected = conversations.find((item) => item.id === selectedId) ?? null;
    const visibleConversations = useMemo(() => {
        const token = search.trim().toLowerCase();
        if (!token) return conversations;
        return conversations.filter((item) =>
            `${item.title} ${conversationPreview(item)}`.toLowerCase().includes(token),
        );
    }, [conversations, search]);

    async function loadMessages(conversationId: string) {
        setMessageLoading(true);
        try {
            const items = await listChatMessages(conversationId);
            setMessages(items);
            await markRead(conversationId);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not load conversation"));
        } finally {
            setMessageLoading(false);
        }
    }

    useEffect(() => {
        if (selectedId || conversations.length === 0) return;
        const timer = window.setTimeout(() => setSelectedId(conversations[0].id), 0);
        return () => window.clearTimeout(timer);
    }, [conversations, selectedId]);

    useEffect(() => {
        if (!selectedId) return;
        const timer = window.setTimeout(() => void loadMessages(selectedId), 0);
        return () => window.clearTimeout(timer);
    }, [selectedId]);

    useEffect(() => {
        if (!latestEvent || latestEvent.conversation_id !== selectedId) return;
        const timer = window.setTimeout(() => {
            setMessages((current) => {
                const exists = current.some(
                    (item) => item.id === latestEvent.message.id,
                );
                if (exists) {
                    return current.map((item) =>
                        item.id === latestEvent.message.id
                            ? latestEvent.message
                            : item,
                    );
                }
                return [...current, latestEvent.message];
            });
            void markRead(latestEvent.conversation_id);
        }, 0);
        return () => window.clearTimeout(timer);
    }, [latestEvent, markRead, selectedId]);

    useEffect(() => {
        endRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    async function openNewConversation() {
        setNewOpen(true);
        try {
            setDirectory(await listChatDirectory());
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not load chat directory"));
        }
    }

    async function createConversation() {
        if (!selectedUsers.length) {
            toast.error("Select at least one person");
            return;
        }
        setCreating(true);
        try {
            const conversation = await createChatConversation({
                participant_ids: selectedUsers,
                title: groupTitle.trim() || undefined,
                conversation_type: selectedUsers.length > 1 ? "group" : "direct",
            });
            await refresh();
            setSelectedId(conversation.id);
            setMobileConversationOpen(true);
            setNewOpen(false);
            setSelectedUsers([]);
            setGroupTitle("");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not create conversation"));
        } finally {
            setCreating(false);
        }
    }

    async function submitMessage() {
        if (!selected || !composer.trim() || sending) return;
        setSending(true);
        const text = composer.trim();
        setComposer("");
        try {
            const message = await sendChatMessage(selected.id, {
                body: text,
                client_message_id: createUuid(),
            });
            setMessages((current) => [...current, message]);
            await refresh();
        } catch (error: unknown) {
            setComposer(text);
            toast.error(getErrorMessage(error, "Message could not be sent"));
        } finally {
            setSending(false);
        }
    }

    async function uploadFile(file: File) {
        if (!selected) return;
        setSending(true);
        try {
            const message = await sendChatFile(selected.id, {
                file,
                body: composer.trim() || undefined,
                clientMessageId: createUuid(),
            });
            setComposer("");
            setMessages((current) => [...current, message]);
            await refresh();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Document could not be shared"));
        } finally {
            setSending(false);
            if (fileInputRef.current) fileInputRef.current.value = "";
        }
    }

    function handleTyping(value: string) {
        setComposer(value);
        if (!selected) return;
        sendTyping(selected.id, true);
        if (typingTimer.current) window.clearTimeout(typingTimer.current);
        typingTimer.current = window.setTimeout(() => sendTyping(selected.id, false), 1200);
    }

    return (
        <main className="overflow-hidden rounded-3xl border bg-card shadow-sm">
            <header className="flex items-center justify-between border-b bg-gradient-to-r from-primary/10 via-background to-emerald-500/10 p-5">
                <div>
                    <div className="flex items-center gap-2 text-primary">
                        <MessageCircleMore className="h-5 w-5" />
                        <span className="text-xs font-black uppercase tracking-[0.15em]">
                            LoanHub Connect
                        </span>
                    </div>
                    <h1 className="mt-2 text-2xl font-black">Secure platform chat</h1>
                    <p className="mt-1 text-sm text-muted-foreground">
                        Direct and group conversations, voice notes, PDFs, images and office documents. Messages and files are encrypted at rest.
                    </p>
                </div>
                <div className="hidden text-right sm:block">
                    <p className={`text-xs font-black ${connected ? "text-emerald-600" : "text-amber-600"}`}>
                        {connected ? "Realtime connected" : "Reconnecting"}
                    </p>
                    <IthutePoweredBy />
                </div>
            </header>

            <div className="grid min-h-[680px] lg:grid-cols-[340px_minmax(0,1fr)]">
                <aside className={`${mobileConversationOpen ? "hidden" : "flex"} flex-col border-r lg:flex`}>
                    <div className="space-y-3 border-b p-4">
                        <button
                            type="button"
                            onClick={() => void openNewConversation()}
                            className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-primary text-sm font-black text-primary-foreground"
                        >
                            <Plus className="h-4 w-4" /> New conversation
                        </button>
                        <SuggestionSearch
                            value={search}
                            onValueChange={setSearch}
                            suggestions={conversations.map((conversation) => ({
                                value: conversation.title || conversation.reference,
                                label: conversation.title || conversation.reference,
                                description: conversationPreview(conversation),
                                keywords: [
                                    conversation.reference,
                                    conversation.conversation_type,
                                    ...conversation.participants.flatMap((participant) => [
                                        participant.user.display_name,
                                        participant.user.email ?? "",
                                        participant.user.phone,
                                    ]),
                                ],
                            }))}
                            placeholder="Type a person, group or message preview..."
                            suggestionLabel="Conversations"
                            emptyMessage="No conversation matches that text."
                        />
                    </div>

                    <div className="flex-1 overflow-y-auto">
                        {visibleConversations.map((conversation) => (
                            <button
                                type="button"
                                key={conversation.id}
                                onClick={() => {
                                    setSelectedId(conversation.id);
                                    setMobileConversationOpen(true);
                                }}
                                className={`flex w-full gap-3 border-b p-4 text-left transition hover:bg-muted/50 ${
                                    selectedId === conversation.id ? "bg-primary/5" : ""
                                }`}
                            >
                                <div className="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                                    {conversation.is_group ? <Users className="h-5 w-5" /> : <MessageCircleMore className="h-5 w-5" />}
                                    {!conversation.is_group && (() => { const other = conversation.participants.find((item) => item.user.id !== user?.id)?.user; const online = other ? (presence[other.id]?.is_online ?? other.is_online) : false; return <span className={`absolute bottom-0 right-0 h-3 w-3 rounded-full ring-2 ring-card ${online ? "bg-emerald-500" : "bg-slate-400"}`} />; })()}
                                </div>
                                <div className="min-w-0 flex-1">
                                    <div className="flex items-center justify-between gap-2">
                                        <p className="truncate text-sm font-black">{conversation.title}</p>
                                        {conversation.last_message_at && (
                                            <span className="shrink-0 text-[10px] text-muted-foreground">
                                                {formatTime(conversation.last_message_at)}
                                            </span>
                                        )}
                                    </div>
                                    <div className="mt-1 flex items-center gap-2">
                                        <p className="line-clamp-1 flex-1 text-xs text-muted-foreground">
                                            {conversationPreview(conversation)}
                                        </p>
                                        {conversation.unread_count > 0 && (
                                            <span className="flex min-h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-black text-primary-foreground">
                                                {conversation.unread_count}
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </button>
                        ))}

                        {!loading && visibleConversations.length === 0 && (
                            <div className="p-8 text-center text-sm text-muted-foreground">
                                No conversations yet. Start a secure chat with an authorised platform user.
                            </div>
                        )}
                        {loading && <div className="p-8 text-center text-sm text-muted-foreground">Loading conversations...</div>}
                    </div>
                </aside>

                <section className={`${mobileConversationOpen ? "flex" : "hidden"} min-w-0 flex-col lg:flex`}>
                    {selected ? (
                        <>
                            <div className="flex items-center gap-3 border-b p-4">
                                <button
                                    type="button"
                                    onClick={() => setMobileConversationOpen(false)}
                                    className="rounded-xl border p-2 lg:hidden"
                                >
                                    <ArrowLeft className="h-4 w-4" />
                                </button>
                                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
                                    {selected.is_group ? <Users className="h-5 w-5" /> : <MessageCircleMore className="h-5 w-5" />}
                                </div>
                                <div className="min-w-0 flex-1">
                                    <p className="truncate font-black">{selected.title}</p>
                                    <p className="truncate text-xs text-muted-foreground">
                                        {selected.participants.map((item) => item.user.display_name).join(", ")} · {selected.participants.some((item) => item.user.id !== user?.id && (presence[item.user.id]?.is_online ?? item.user.is_online)) ? "online" : "offline"}
                                    </p>
                                    {(typingUsers[selected.id]?.length ?? 0) > 0 && (
                                        <p className="text-[11px] font-bold text-emerald-600">Someone is typing...</p>
                                    )}
                                </div>
                            </div>

                            <div className="flex-1 space-y-3 overflow-y-auto bg-muted/20 p-4 sm:p-6">
                                {messageLoading && (
                                    <div className="flex justify-center p-8"><Loader2 className="h-6 w-6 animate-spin text-primary" /></div>
                                )}
                                {messages.map((message) => {
                                    const mine = message.sender?.id === user?.id;
                                    return (
                                        <article key={message.id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
                                            <div className={`max-w-[86%] rounded-2xl px-4 py-3 shadow-sm sm:max-w-[72%] ${
                                                mine ? "rounded-br-md bg-primary text-primary-foreground" : "rounded-bl-md border bg-card"
                                            }`}>
                                                {!mine && (
                                                    <p className="mb-1 text-[11px] font-black text-primary">
                                                        {message.sender?.display_name ?? "LoanHub user"}
                                                    </p>
                                                )}
                                                {message.deleted_at ? (
                                                    <p className="text-sm italic opacity-70">This message was deleted</p>
                                                ) : (
                                                    <>
                                                        {message.body && <p className="whitespace-pre-wrap text-sm leading-6">{message.body}</p>}
                                                        {message.attachments.map((file) =>
                                                            message.message_type === "voice" || file.mime_type.startsWith("audio/") ? (
                                                                <SecureAudioPlayer key={file.id} file={file} mine={mine} />
                                                            ) : (
                                                                <button type="button" key={file.id} onClick={() => void downloadManagedFile(file)} className={`mt-2 flex w-full items-center gap-3 rounded-xl border p-3 text-left ${mine ? "border-white/25 bg-white/10" : "bg-muted/40"}`}>
                                                                    <FileText className="h-5 w-5 shrink-0" /><span className="min-w-0 flex-1"><span className="block truncate text-xs font-black">{file.original_name}</span><span className="block text-[10px] opacity-70">{(file.size_bytes / 1024).toFixed(1)} KB</span></span><Download className="h-4 w-4" />
                                                                </button>
                                                            ),
                                                        )}
                                                    </>
                                                )}
                                                <p className={`mt-1 text-right text-[10px] ${mine ? "text-primary-foreground/70" : "text-muted-foreground"}`}>
                                                    {formatTime(message.created_at)}{message.edited_at ? " · edited" : ""}
                                                </p>
                                            </div>
                                        </article>
                                    );
                                })}
                                <div ref={endRef} />
                            </div>

                            <div className="border-t p-3 sm:p-4">
                                <Input
                                    ref={fileInputRef}
                                    type="file"
                                    accept=".pdf,.png,.jpg,.jpeg,.webp,.doc,.docx,.xls,.xlsx,.csv,.txt,.webm,.ogg,.mp3,.wav,.m4a,audio/*"
                                    className="hidden"
                                    onChange={(event) => {
                                        const file = event.target.files?.[0];
                                        if (file) void uploadFile(file);
                                    }}
                                />
                                <div className="flex items-end gap-2">
                                    <button
                                        type="button"
                                        onClick={() => fileInputRef.current?.click()}
                                        disabled={sending}
                                        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border transition hover:border-primary hover:text-primary disabled:opacity-50"
                                        title="Share PDF or document"
                                    >
                                        <Paperclip className="h-5 w-5" />
                                    </button>
                                    <VoiceRecorderButton disabled={sending} onRecorded={uploadFile} />
                                    <Textarea
                                        value={composer}
                                        onChange={(event) => handleTyping(event.target.value)}
                                        onKeyDown={(event) => {
                                            if (event.key === "Enter" && !event.shiftKey) {
                                                event.preventDefault();
                                                void submitMessage();
                                            }
                                        }}
                                        rows={1}
                                        placeholder="Write a message"
                                        className="min-h-11 max-h-32 flex-1 resize-none rounded-xl border bg-background px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-primary/20"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => void submitMessage()}
                                        disabled={!composer.trim() || sending}
                                        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground disabled:opacity-50"
                                    >
                                        {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                                    </button>
                                </div>
                                <p className="mt-2 text-[10px] text-muted-foreground">
                                    Maximum 25 MB for documents and 20 MB for voice notes. Files are validated and encrypted at rest.
                                </p>
                            </div>
                        </>
                    ) : (
                        <div className="flex flex-1 items-center justify-center p-8 text-center">
                            <div>
                                <MessageCircleMore className="mx-auto h-14 w-14 text-primary/40" />
                                <h2 className="mt-4 text-xl font-black">Choose a conversation</h2>
                                <p className="mt-2 max-w-sm text-sm text-muted-foreground">
                                    Securely communicate across LoanHub without exposing private phone numbers.
                                </p>
                            </div>
                        </div>
                    )}
                </section>
            </div>

            <CustomDialog open={newOpen} onOpenChange={(open) => !creating && setNewOpen(open)} title="New conversation" description="Only authorised users in your communication scope are shown." contentClassName="sm:max-w-xl">
                <div className="space-y-4 p-6 sm:p-8">
                        <Input
                            value={groupTitle}
                            onChange={(event) => setGroupTitle(event.target.value)}
                            placeholder="Group name (optional)"
                            className="h-11 w-full rounded-xl border bg-background px-3 text-sm"
                        />
                        <div className="max-h-96 divide-y overflow-y-auto rounded-2xl border">
                            {directory.map((person) => {
                                const checked = selectedUsers.includes(person.id);
                                return (
                                    <label key={person.id} className="flex cursor-pointer items-center gap-3 p-4 hover:bg-muted/40">
                                        <Input
                                            type="checkbox"
                                            checked={checked}
                                            onChange={() => setSelectedUsers((current) =>
                                                checked ? current.filter((id) => id !== person.id) : [...current, person.id],
                                            )}
                                        />
                                        <div className="min-w-0 flex-1">
                                            <p className="truncate text-sm font-black">{person.display_name}</p>
                                            <p className="truncate text-xs text-muted-foreground">
                                                {person.company_name ?? "LoanHub platform"} · {person.role.replaceAll("_", " ")} · {(presence[person.id]?.is_online ?? person.is_online) ? "online" : "offline"}
                                            </p>
                                        </div>
                                    </label>
                                );
                            })}
                            {directory.length === 0 && <p className="p-8 text-center text-sm text-muted-foreground">No authorised contacts were found.</p>}
                        </div>
                    <DialogFooter className="mx-0 mb-0">
                        <Button type="button" variant="outline" onClick={() => setNewOpen(false)} disabled={creating}>Cancel</Button>
                        <LoadingButton type="button" onClick={() => void createConversation()} disabled={!selectedUsers.length} loading={creating}>
                            Create chat
                        </LoadingButton>
                    </DialogFooter>
                </div>
            </CustomDialog>
        </main>
    );
}
