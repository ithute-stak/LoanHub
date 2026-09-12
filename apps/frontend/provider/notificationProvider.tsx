"use client";

import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useRef,
    useState,
    type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import { toast } from "@/utils/toast";

import {
    archiveNotification as archiveNotificationRequest,
    listNotifications,
    markAllNotificationsRead,
    markNotificationRead,
} from "@/api/notifications";
import { useTenant } from "@/provider/tenantProvider";
import { useRealtime } from "@/provider/realtimeProvider";
import { useAppSelector } from "@/store/hooks";
import type { AppNotification } from "@/types/notification";
import { getErrorMessage } from "@/utils/apiError";
import {
    isAttentionNotification,
} from "@/utils/notificationAttention";

export type NotificationContextValue = {
    notifications: AppNotification[];
    attentionNotifications: AppNotification[];
    unreadCount: number;
    attentionUnreadCount: number;
    total: number;
    loading: boolean;
    loadingMore: boolean;
    hasMore: boolean;
    connected: boolean;
    error: string | null;
    refresh: () => Promise<void>;
    loadMore: () => Promise<void>;
    markRead: (notificationId: string) => Promise<void>;
    markAllRead: () => Promise<void>;
    archive: (notificationId: string) => Promise<void>;
    openNotification: (notification: AppNotification) => Promise<void>;
};

const NotificationContext =
    createContext<NotificationContextValue | null>(null);

function normalizeRealtimeNotification(
    payload: Record<string, unknown>,
): AppNotification | null {
    if (
        payload.type !==
            "NOTIFICATION_CREATED" ||
        typeof payload.id !== "string"
    ) {
        return null;
    }

    const createdAt =
        typeof payload.created_at === "string"
            ? payload.created_at
            : new Date().toISOString();

    return {
        id: payload.id,
        user_id: String(payload.user_id ?? ""),
        actor_user_id:
            typeof payload.actor_user_id === "string"
                ? payload.actor_user_id
                : null,
        company_id:
            typeof payload.company_id === "string"
                ? payload.company_id
                : null,
        branch_id:
            typeof payload.branch_id === "string"
                ? payload.branch_id
                : null,
        title: String(payload.title ?? "Notification"),
        message: String(payload.message ?? ""),
        notification_type: String(
            payload.notification_type ?? "system",
        ) as AppNotification["notification_type"],
        event_type: String(
            payload.event_type ?? "system.event",
        ),
        action: String(payload.action ?? "view"),
        entity_type:
            typeof payload.entity_type === "string"
                ? payload.entity_type
                : null,
        entity_id:
            typeof payload.entity_id === "string"
                ? payload.entity_id
                : null,
        action_url:
            typeof payload.action_url === "string"
                ? payload.action_url
                : null,
        icon:
            typeof payload.icon === "string"
                ? payload.icon
                : null,
        priority: String(
            payload.priority ?? "normal",
        ),
        data:
            payload.data &&
            typeof payload.data === "object"
                ? (payload.data as Record<
                      string,
                      unknown
                  >)
                : {},
        is_read: false,
        read_at: null,
        is_archived: false,
        archived_at: null,
        created_at: createdAt,
        updated_at: createdAt,
    };
}

export function NotificationProvider({
    children,
}: {
    children: ReactNode;
}) {
    const router = useRouter();
    const { activeCompanyId } = useTenant();
    const { connected, subscribe } = useRealtime();
    const user = useAppSelector(
        (state) => state.auth.user,
    );
    const authInitialized = useAppSelector(
        (state) => state.auth.initialized,
    );

    const [notifications, setNotifications] =
        useState<AppNotification[]>([]);
    const [attentionNotifications, setAttentionNotifications] =
        useState<AppNotification[]>([]);
    const [unreadCount, setUnreadCount] =
        useState(0);
    const [attentionUnreadCount, setAttentionUnreadCount] =
        useState(0);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] =
        useState(false);
    const [loadingMore, setLoadingMore] =
        useState(false);
    const [error, setError] =
        useState<string | null>(null);

    const loadedPageRef = useRef(1);
    const seenRealtimeIdsRef = useRef(new Set<string>());
    const pageSize = 50;

    const refresh = useCallback(async () => {
        if (!user) {
            setNotifications([]);
            setAttentionNotifications([]);
            setUnreadCount(0);
            setAttentionUnreadCount(0);
            setTotal(0);
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const [result, attentionResult] =
                await Promise.all([
                    listNotifications({
                        page: 1,
                        page_size: pageSize,
                    }),
                    listNotifications({
                        page: 1,
                        page_size: 10,
                        unread_only: true,
                        attention_only: true,
                    }),
                ]);

            loadedPageRef.current = 1;
            seenRealtimeIdsRef.current = new Set(
                result.items.map((item) => item.id),
            );
            setNotifications(result.items);
            setAttentionNotifications(
                attentionResult.items,
            );
            setUnreadCount(result.unread_count);
            setAttentionUnreadCount(
                attentionResult.unread_count,
            );
            setTotal(result.total);
        } catch (requestError: unknown) {
            setError(
                getErrorMessage(
                    requestError,
                    "Could not load notifications.",
                ),
            );
        } finally {
            setLoading(false);
        }
    }, [user]);

    const loadMore = useCallback(async () => {
        if (
            !user ||
            loadingMore ||
            notifications.length >= total
        ) {
            return;
        }

        setLoadingMore(true);
        setError(null);

        try {
            const nextPage =
                loadedPageRef.current + 1;
            const result = await listNotifications({
                page: nextPage,
                page_size: pageSize,
            });

            loadedPageRef.current = nextPage;
            setNotifications((current) => {
                const known = new Set(
                    current.map((item) => item.id),
                );
                return [
                    ...current,
                    ...result.items.filter(
                        (item) => !known.has(item.id),
                    ),
                ];
            });
            setUnreadCount(result.unread_count);
            setTotal(result.total);
        } catch (requestError: unknown) {
            const message = getErrorMessage(
                requestError,
                "Could not load more notifications.",
            );
            setError(message);
            toast.error(message);
        } finally {
            setLoadingMore(false);
        }
    }, [
        loadingMore,
        notifications.length,
        total,
        user,
    ]);

    useEffect(() => {
        if (!authInitialized) {
            return;
        }

        const timer = window.setTimeout(() => void refresh(), 0);
        return () => window.clearTimeout(timer);
    }, [
        activeCompanyId,
        authInitialized,
        refresh,
    ]);

    useEffect(() => {
        if (!user) {
            return;
        }

        const poll = window.setInterval(() => {
            if (document.visibilityState === "visible") {
                void refresh();
            }
        }, 60_000);

        const handleFocus = () => {
            void refresh();
        };

        window.addEventListener("focus", handleFocus);

        return () => {
            window.clearInterval(poll);
            window.removeEventListener("focus", handleFocus);
        };
    }, [refresh, user]);

    useEffect(() => {
        return subscribe((payload) => {
            const notification =
                normalizeRealtimeNotification(payload);

            if (
                !notification ||
                seenRealtimeIdsRef.current.has(
                    notification.id,
                )
            ) {
                return;
            }

            seenRealtimeIdsRef.current.add(
                notification.id,
            );

            setNotifications((current) => [
                notification,
                ...current.filter(
                    (item) =>
                        item.id !== notification.id,
                ),
            ].slice(0, 100));

            setUnreadCount(
                (current) => current + 1,
            );
            setTotal((current) => current + 1);

            if (isAttentionNotification(notification)) {
                setAttentionNotifications((current) => [
                    notification,
                    ...current.filter(
                        (item) =>
                            item.id !== notification.id,
                    ),
                ].slice(0, 10));
                setAttentionUnreadCount(
                    (current) => current + 1,
                );
            }

            toast(notification.title, {
                description: notification.message,
                action: notification.action_url
                    ? {
                          label: "Open",
                          onClick: () => {
                              void openNotificationRef.current?.(
                                  notification,
                              );
                          },
                      }
                    : undefined,
            });
        });
    }, [subscribe]);

    const markRead = useCallback(
        async (notificationId: string) => {
            const existing =
                notifications.find(
                    (item) =>
                        item.id === notificationId,
                ) ??
                attentionNotifications.find(
                    (item) =>
                        item.id === notificationId,
                );

            if (!existing || existing.is_read) {
                return;
            }

            setNotifications((current) =>
                current.map((item) =>
                    item.id === notificationId
                        ? {
                              ...item,
                              is_read: true,
                              read_at:
                                  new Date().toISOString(),
                          }
                        : item,
                ),
            );
            setUnreadCount((current) =>
                Math.max(0, current - 1),
            );

            if (isAttentionNotification(existing)) {
                setAttentionNotifications((current) =>
                    current.filter(
                        (item) =>
                            item.id !== notificationId,
                    ),
                );
                setAttentionUnreadCount((current) =>
                    Math.max(0, current - 1),
                );
            }

            try {
                await markNotificationRead(
                    notificationId,
                );
            } catch (requestError: unknown) {
                await refresh();
                throw requestError;
            }
        },
        [
            attentionNotifications,
            notifications,
            refresh,
        ],
    );

    const markAllRead = useCallback(
        async () => {
            if (unreadCount === 0) {
                return;
            }

            const timestamp =
                new Date().toISOString();

            setNotifications((current) =>
                current.map((item) => ({
                    ...item,
                    is_read: true,
                    read_at:
                        item.read_at ?? timestamp,
                })),
            );
            setUnreadCount(0);
            setAttentionNotifications([]);
            setAttentionUnreadCount(0);

            try {
                await markAllNotificationsRead();
            } catch (requestError: unknown) {
                await refresh();
                throw requestError;
            }
        },
        [refresh, unreadCount],
    );

    const archive = useCallback(
        async (notificationId: string) => {
            const existing =
                notifications.find(
                    (item) =>
                        item.id === notificationId,
                ) ??
                attentionNotifications.find(
                    (item) =>
                        item.id === notificationId,
                );

            setNotifications((current) =>
                current.filter(
                    (item) =>
                        item.id !==
                        notificationId,
                ),
            );
            setTotal((current) =>
                Math.max(0, current - 1),
            );

            setAttentionNotifications((current) =>
                current.filter(
                    (item) =>
                        item.id !== notificationId,
                ),
            );

            if (existing && !existing.is_read) {
                setUnreadCount((current) =>
                    Math.max(0, current - 1),
                );
                if (isAttentionNotification(existing)) {
                    setAttentionUnreadCount((current) =>
                        Math.max(0, current - 1),
                    );
                }
            }

            try {
                await archiveNotificationRequest(
                    notificationId,
                );
            } catch (requestError: unknown) {
                await refresh();
                throw requestError;
            }
        },
        [
            attentionNotifications,
            notifications,
            refresh,
        ],
    );

    const openNotification = useCallback(
        async (
            notification: AppNotification,
        ) => {
            try {
                await markRead(notification.id);
            } catch {
                // Navigation is still useful if marking as read fails.
            }

            if (notification.action_url) {
                router.push(
                    notification.action_url,
                );
            }
        },
        [markRead, router],
    );

    const openNotificationRef = useRef(
        openNotification,
    );

    useEffect(() => {
        openNotificationRef.current =
            openNotification;
    }, [openNotification]);

    const hasMore =
        notifications.length < total;

    const value = useMemo(
        () => ({
            notifications,
            attentionNotifications,
            unreadCount,
            attentionUnreadCount,
            total,
            loading,
            loadingMore,
            hasMore,
            connected,
            error,
            refresh,
            loadMore,
            markRead,
            markAllRead,
            archive,
            openNotification,
        }),
        [
            archive,
            attentionNotifications,
            attentionUnreadCount,
            connected,
            error,
            hasMore,
            loading,
            loadingMore,
            loadMore,
            markAllRead,
            markRead,
            notifications,
            openNotification,
            refresh,
            total,
            unreadCount,
        ],
    );

    return (
        <NotificationContext.Provider
            value={value}
        >
            {children}
        </NotificationContext.Provider>
    );
}

export function useNotifications(): NotificationContextValue {
    const context = useContext(
        NotificationContext,
    );

    if (!context) {
        throw new Error(
            "useNotifications must be used inside NotificationProvider",
        );
    }

    return context;
}
