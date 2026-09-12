"use client";

import Link from "next/link";
import {
    Bell,
    CheckCheck,
    Loader2,
    Radio,
} from "lucide-react";
import {
    formatDistanceToNow,
} from "date-fns";

import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover";
import {
    ScrollArea,
} from "@/components/ui/scroll-area";
import {
    NotificationIcon,
} from "@/components/notifications/notification-icon";
import {
    useNotifications,
} from "@/provider/notificationProvider";
import type {
    AppNotification,
} from "@/types/notification";
import type {
    UserRole,
} from "@/types/auth";

function allNotificationsHref(
    role: UserRole | null | undefined,
): string {
    if (role === "superadmin") {
        return "/superadmin/notifications";
    }

    if (role === "borrower") {
        return "/borrower/notifications";
    }

    return "/company/notifications";
}

function NotificationRow({
    notification,
    onOpen,
}: {
    notification: AppNotification;
    onOpen: (
        notification: AppNotification,
    ) => void;
}) {
    return (
        <button
            type="button"
            onClick={() =>
                onOpen(notification)
            }
            className={`flex w-full gap-3 border-b px-4 py-3 text-left transition hover:bg-muted/60 ${
                notification.is_read
                    ? "bg-background"
                    : "bg-primary/[0.055]"
            }`}
        >
            <NotificationIcon
                icon={notification.icon}
                priority={
                    notification.priority
                }
            />

            <span className="min-w-0 flex-1">
                <span className="flex items-start justify-between gap-2">
                    <span className="truncate text-sm font-black">
                        {notification.title}
                    </span>

                    {!notification.is_read && (
                        <span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full bg-primary" />
                    )}
                </span>

                <span className="mt-1 line-clamp-2 block text-xs leading-5 text-muted-foreground">
                    {notification.message}
                </span>

                <span className="mt-1.5 block text-[11px] font-bold text-primary">
                    {formatDistanceToNow(
                        new Date(
                            notification.created_at,
                        ),
                        {
                            addSuffix: true,
                        },
                    )}
                </span>
            </span>
        </button>
    );
}

export function NotificationBell({
    role,
}: {
    role: UserRole | null | undefined;
}) {
    const {
        notifications,
        attentionNotifications,
        attentionUnreadCount,
        loading,
        connected,
        markRead,
        openNotification,
    } = useNotifications();

    const preview = attentionNotifications.slice(
        0,
        10,
    );

    async function markShownRead() {
        await Promise.allSettled(
            preview.map((notification) =>
                markRead(notification.id),
            ),
        );
    }

    return (
        <Popover>
            <PopoverTrigger asChild>
                <button
                    type="button"
                    aria-label={`Important notifications${
                        attentionUnreadCount > 0
                            ? `, ${attentionUnreadCount} requiring attention`
                            : ", none requiring attention"
                    }`}
                    className="relative flex h-10 w-10 items-center justify-center rounded-xl border bg-background transition hover:bg-muted"
                >
                    <Bell className="h-5 w-5" />

                    {attentionUnreadCount > 0 && (
                        <span className="absolute -right-1.5 -top-1.5 flex min-h-5 min-w-5 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-black text-white ring-2 ring-background">
                            {attentionUnreadCount > 99
                                ? "99+"
                                : attentionUnreadCount}
                        </span>
                    )}
                </button>
            </PopoverTrigger>

            <PopoverContent
                align="end"
                className="w-[min(92vw,410px)] overflow-hidden p-0"
            >
                <div className="flex items-center justify-between border-b px-4 py-3">
                    <div>
                        <div className="flex items-center gap-2">
                            <h2 className="font-black">
                                Needs attention
                            </h2>

                            <span
                                className={`h-2 w-2 rounded-full ${
                                    connected
                                        ? "bg-green-500"
                                        : "bg-amber-500"
                                }`}
                                title={
                                    connected
                                        ? "Live updates connected"
                                        : "Live updates reconnecting"
                                }
                            />
                        </div>

                        <p className="mt-0.5 text-xs text-muted-foreground">
                            {attentionUnreadCount} unread action alert{attentionUnreadCount === 1
                                ? ""
                                : "s"}
                        </p>
                    </div>

                    <button
                        type="button"
                        onClick={() =>
                            void markShownRead()
                        }
                        disabled={
                            preview.length === 0
                        }
                        className="inline-flex h-9 items-center gap-2 rounded-lg px-3 text-xs font-black text-primary transition hover:bg-primary/10 disabled:opacity-40"
                    >
                        <CheckCheck className="h-4 w-4" />
                        Mark shown read
                    </button>
                </div>

                <ScrollArea className="h-[430px]">
                    {loading &&
                    notifications.length === 0 ? (
                        <div className="flex h-56 items-center justify-center text-muted-foreground">
                            <Loader2 className="h-6 w-6 animate-spin" />
                        </div>
                    ) : preview.length === 0 ? (
                        <div className="flex h-64 flex-col items-center justify-center px-8 text-center">
                            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-muted">
                                <Bell className="h-6 w-6 text-muted-foreground" />
                            </div>

                            <p className="mt-4 font-black">
                                You are all caught up
                            </p>

                            <p className="mt-1 text-xs leading-5 text-muted-foreground">
                                This bell only shows unread loan,
                                access, offer, payment,
                                subscription, and high-priority
                                alerts.
                            </p>
                        </div>
                    ) : (
                        preview.map(
                            (notification) => (
                                <NotificationRow
                                    key={
                                        notification.id
                                    }
                                    notification={
                                        notification
                                    }
                                    onOpen={(
                                        selected,
                                    ) =>
                                        void openNotification(
                                            selected,
                                        )
                                    }
                                />
                            ),
                        )
                    )}
                </ScrollArea>

                <div className="border-t p-3">
                    <Link
                        href={allNotificationsHref(
                            role,
                        )}
                        className="flex h-10 items-center justify-center gap-2 rounded-xl bg-muted text-sm font-black transition hover:bg-muted/70"
                    >
                        <Radio className="h-4 w-4" />
                        View complete notification history
                    </Link>
                </div>
            </PopoverContent>
        </Popover>
    );
}
