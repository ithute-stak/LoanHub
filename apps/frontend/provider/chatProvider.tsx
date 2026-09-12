"use client";

import {
    createContext,
    type ReactNode,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useRef,
    useState,
} from "react";

import { isAxiosError } from "axios";

import {
    getChatUnreadCount,
    listChatConversations,
    markChatConversationRead,
} from "@/api/chat";
import { useRealtime } from "@/provider/realtimeProvider";
import { useTenant } from "@/provider/tenantProvider";
import { useAppSelector } from "@/store/hooks";
import { isCompanyRole } from "@/types/auth";
import type {
    ChatConversation,
    ChatMessage,
} from "@/types/chat";

export type ChatRealtimeEvent = {
    conversation_id: string;
    message: ChatMessage;
};

type PresenceState = {
    is_online: boolean;
    last_seen_at: string | null;
};

type ChatContextValue = {
    conversations: ChatConversation[];
    unreadCount: number;
    loading: boolean;
    connected: boolean;
    latestEvent: ChatRealtimeEvent | null;
    typingUsers: Record<string, string[]>;
    presence: Record<string, PresenceState>;
    refresh: () => Promise<void>;
    markRead: (conversationId: string) => Promise<void>;
    sendTyping: (
        conversationId: string,
        isTyping: boolean,
    ) => void;
};

const ChatContext =
    createContext<ChatContextValue | null>(null);

export function ChatProvider({
    children,
}: {
    children: ReactNode;
}) {
    const userId = useAppSelector(
        (state) => state.auth.user?.id ?? null,
    );
    const userRole = useAppSelector(
        (state) => state.auth.user?.role ?? null,
    );
    const authInitialized = useAppSelector(
        (state) => state.auth.initialized,
    );
    const { activeCompanyId, activeRole } = useTenant();
    const tenantReady =
        !isCompanyRole(userRole) ||
        Boolean(activeCompanyId && activeRole);
    const { connected, send, subscribe } =
        useRealtime();

    const [conversations, setConversations] =
        useState<ChatConversation[]>([]);
    const [unreadCount, setUnreadCount] =
        useState(0);
    const [loading, setLoading] =
        useState(false);
    const [latestEvent, setLatestEvent] =
        useState<ChatRealtimeEvent | null>(null);
    const [typingUsers, setTypingUsers] =
        useState<Record<string, string[]>>({});
    const [presence, setPresence] =
        useState<Record<string, PresenceState>>({});

    const refreshInFlightRef = useRef<Promise<void> | null>(
        null,
    );
    const refreshTimerRef = useRef<number | null>(null);

    const refresh = useCallback(async () => {
        if (!userId || !tenantReady) {
            setConversations([]);
            setUnreadCount(0);
            setPresence({});
            return;
        }

        if (refreshInFlightRef.current) {
            return refreshInFlightRef.current;
        }

        const operation = (async () => {
            setLoading(true);

            try {
                const [items, unread] =
                    await Promise.all([
                        listChatConversations(),
                        getChatUnreadCount(),
                    ]);

                setConversations(items);
                setUnreadCount(unread);

                const next: Record<
                    string,
                    PresenceState
                > = {};

                for (const conversation of items) {
                    for (const participant of conversation.participants) {
                        next[participant.user.id] = {
                            is_online:
                                participant.user.is_online,
                            last_seen_at:
                                participant.user.last_seen_at,
                        };
                    }
                }

                setPresence((current) => ({
                    ...current,
                    ...next,
                }));
            } finally {
                setLoading(false);
                refreshInFlightRef.current = null;
            }
        })();

        refreshInFlightRef.current = operation;
        return operation;
    }, [tenantReady, userId]);

    const refreshSilently = useCallback(() => {
        void refresh().catch((error: unknown) => {
            const status = isAxiosError(error)
                ? error.response?.status
                : undefined;

            // Authentication and tenant scope can change while a background
            // refresh is running. The foreground chat page still receives
            // errors from `refresh`; polling must not create an unhandled
            // rejection or trigger the Next.js development error overlay.
            if (status === 401 || status === 403 || status === 409) {
                return;
            }

            console.error("Could not refresh chat in the background", error);
        });
    }, [refresh]);

    const scheduleRefresh = useCallback(() => {
        if (refreshTimerRef.current !== null) {
            return;
        }

        refreshTimerRef.current = window.setTimeout(() => {
            refreshTimerRef.current = null;
            refreshSilently();
        }, 250);
    }, [refreshSilently]);

    const markRead = useCallback(
        async (conversationId: string) => {
            await markChatConversationRead(conversationId);

            setConversations((current) =>
                current.map((item) =>
                    item.id === conversationId
                        ? {
                              ...item,
                              unread_count: 0,
                          }
                        : item,
                ),
            );

            setUnreadCount(
                await getChatUnreadCount(),
            );
        },
        [],
    );

    const sendTyping = useCallback(
        (
            conversationId: string,
            isTyping: boolean,
        ) => {
            send({
                type: "CHAT_TYPING",
                conversation_id: conversationId,
                is_typing: isTyping,
            });
        },
        [send],
    );

    useEffect(() => {
        if (!authInitialized || !userId || !tenantReady) {
            const resetTimer = window.setTimeout(() => {
                setConversations([]);
                setUnreadCount(0);
            }, 0);
            return () => window.clearTimeout(resetTimer);
        }

        const initialTimer = window.setTimeout(refreshSilently, 0);

        const interval = window.setInterval(() => {
            if (document.visibilityState === "visible") {
                refreshSilently();
            }
        }, 45_000);

        const handleFocus = () => {
            refreshSilently();
        };

        window.addEventListener("focus", handleFocus);

        return () => {
            window.clearTimeout(initialTimer);
            window.clearInterval(interval);
            window.removeEventListener(
                "focus",
                handleFocus,
            );

            if (refreshTimerRef.current !== null) {
                window.clearTimeout(
                    refreshTimerRef.current,
                );
                refreshTimerRef.current = null;
            }
        };
    }, [
        activeCompanyId,
        activeRole,
        authInitialized,
        refreshSilently,
        tenantReady,
        userId,
    ]);

    useEffect(() => {
        return subscribe((payload) => {
            const eventType = String(
                payload.type ?? "",
            );

            if (
                [
                    "CHAT_MESSAGE_CREATED",
                    "CHAT_MESSAGE_UPDATED",
                    "CHAT_MESSAGE_DELETED",
                ].includes(eventType)
            ) {
                const conversationId = String(
                    payload.conversation_id ?? "",
                );
                const message = payload.message as
                    | ChatMessage
                    | undefined;

                if (conversationId && message) {
                    setLatestEvent({
                        conversation_id: conversationId,
                        message,
                    });
                    scheduleRefresh();
                }

                return;
            }

            if (eventType === "CHAT_TYPING") {
                const conversationId = String(
                    payload.conversation_id ?? "",
                );
                const typingUserId = String(
                    payload.user_id ?? "",
                );
                const isTyping = Boolean(
                    payload.is_typing,
                );

                if (!conversationId || !typingUserId) {
                    return;
                }

                setTypingUsers((current) => {
                    const known = new Set(
                        current[conversationId] ?? [],
                    );

                    if (isTyping) {
                        known.add(typingUserId);
                    } else {
                        known.delete(typingUserId);
                    }

                    return {
                        ...current,
                        [conversationId]: [...known],
                    };
                });

                return;
            }

            if (eventType === "PRESENCE_CHANGED") {
                const presenceUserId = String(
                    payload.user_id ?? "",
                );

                if (!presenceUserId) {
                    return;
                }

                setPresence((current) => ({
                    ...current,
                    [presenceUserId]: {
                        is_online: Boolean(
                            payload.is_online,
                        ),
                        last_seen_at:
                            typeof payload.last_seen_at ===
                            "string"
                                ? payload.last_seen_at
                                : null,
                    },
                }));
            }
        });
    }, [scheduleRefresh, subscribe]);

    const value = useMemo<ChatContextValue>(
        () => ({
            conversations,
            unreadCount,
            loading,
            connected,
            latestEvent,
            typingUsers,
            presence,
            refresh,
            markRead,
            sendTyping,
        }),
        [
            connected,
            conversations,
            latestEvent,
            loading,
            markRead,
            presence,
            refresh,
            sendTyping,
            typingUsers,
            unreadCount,
        ],
    );

    return (
        <ChatContext.Provider value={value}>
            {children}
        </ChatContext.Provider>
    );
}

export function useChat(): ChatContextValue {
    const context = useContext(ChatContext);

    if (!context) {
        throw new Error(
            "useChat must be used inside ChatProvider",
        );
    }

    return context;
}
