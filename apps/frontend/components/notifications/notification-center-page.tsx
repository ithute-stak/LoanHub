"use client";


import { Input } from "@/components/ui/input";
import { SuggestionSearch } from "@/components/ui/suggestion-search";
import { NativeSelect } from "@/components/ui/native-select";
import {
    Archive,
    Bell,
    CheckCheck,
    RefreshCcw,
    Search,
    Loader2,
} from "lucide-react";
import {
    format,
    formatDistanceToNow,
} from "date-fns";
import {
    useMemo,
    useState,
} from "react";

import {
    NotificationIcon,
} from "@/components/notifications/notification-icon";
import {
    useNotifications,
} from "@/provider/notificationProvider";

export function NotificationCenterPage() {
    const {
        notifications,
        unreadCount,
        total,
        loading,
        loadingMore,
        hasMore,
        connected,
        refresh,
        loadMore,
        markAllRead,
        archive,
        openNotification,
    } = useNotifications();

    const [search, setSearch] =
        useState("");
    const [filter, setFilter] =
        useState<"all" | "unread" | "high">(
            "all",
        );

    const filtered = useMemo(() => {
        const token = search
            .trim()
            .toLowerCase();

        return notifications.filter(
            (notification) => {
                const matchesFilter =
                    filter === "all" ||
                    (filter === "unread" &&
                        !notification.is_read) ||
                    (filter === "high" &&
                        [
                            "high",
                            "critical",
                        ].includes(
                            notification.priority,
                        ));

                const matchesSearch =
                    !token ||
                    notification.title
                        .toLowerCase()
                        .includes(token) ||
                    notification.message
                        .toLowerCase()
                        .includes(token) ||
                    notification.event_type
                        .toLowerCase()
                        .includes(token);

                return (
                    matchesFilter &&
                    matchesSearch
                );
            },
        );
    }, [filter, notifications, search]);

    return (
        <main className="space-y-6">
            <section className="rounded-3xl border bg-card p-6 shadow-sm md:p-8">
                <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
                    <div>
                        <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[0.16em] text-primary">
                            <span
                                className={`h-2.5 w-2.5 rounded-full ${
                                    connected
                                        ? "bg-green-500"
                                        : "bg-amber-500"
                                }`}
                            />
                            Live event centre
                        </div>

                        <h1 className="mt-3 text-3xl font-black tracking-tight">
                            Notifications
                        </h1>

                        <p className="mt-2 text-sm text-muted-foreground">
                            {unreadCount} unread from {total}{" "}
                            notification events.
                        </p>
                    </div>

                    <div className="flex flex-wrap gap-2">
                        <button
                            type="button"
                            onClick={() =>
                                void markAllRead()
                            }
                            disabled={unreadCount === 0}
                            className="inline-flex h-11 items-center gap-2 rounded-xl border bg-background px-4 text-sm font-black disabled:opacity-50"
                        >
                            <CheckCheck className="h-4 w-4" />
                            Mark all read
                        </button>

                        <button
                            type="button"
                            onClick={() => void refresh()}
                            disabled={loading}
                            className="inline-flex h-11 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground disabled:opacity-50"
                        >
                            <RefreshCcw
                                className={`h-4 w-4 ${
                                    loading
                                        ? "animate-spin"
                                        : ""
                                }`}
                            />
                            Refresh
                        </button>
                    </div>
                </div>
            </section>

            <section className="overflow-hidden rounded-3xl border bg-card shadow-sm">
                <div className="grid gap-3 border-b p-4 sm:grid-cols-[1fr_auto] sm:p-5">
                    <SuggestionSearch
                        value={search}
                        onValueChange={setSearch}
                        suggestions={notifications.map((notification) => ({
                            value: notification.title,
                            label: notification.title,
                            description: notification.message,
                            keywords: [
                                notification.id,
                                notification.notification_type,
                                notification.event_type,
                                notification.priority,
                                notification.entity_type ?? "",
                            ],
                        }))}
                        placeholder="Type a title, message, event or priority..."
                        suggestionLabel="Notifications"
                        emptyMessage="No notification matches that text."
                    />

                    <NativeSelect
                        value={filter}
                        onChange={(event) =>
                            setFilter(
                                event.target.value as
                                    | "all"
                                    | "unread"
                                    | "high",
                            )
                        }
                        className="h-11 rounded-xl border bg-background px-3 text-sm font-bold"
                    >
                        <option value="all">
                            All notifications
                        </option>
                        <option value="unread">
                            Unread only
                        </option>
                        <option value="high">
                            High priority
                        </option>
                    </NativeSelect>
                </div>

                <div>
                    {filtered.length === 0 ? (
                        <div className="flex min-h-72 flex-col items-center justify-center p-8 text-center">
                            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
                                <Bell className="h-7 w-7 text-muted-foreground" />
                            </div>
                            <h2 className="mt-4 font-black">
                                No matching notifications
                            </h2>
                            <p className="mt-1 text-sm text-muted-foreground">
                                New relevant events will appear
                                here automatically.
                            </p>
                        </div>
                    ) : (
                        filtered.map((notification) => (
                            <article
                                key={notification.id}
                                className={`flex gap-4 border-b p-4 transition hover:bg-muted/40 sm:p-5 ${
                                    notification.is_read
                                        ? "bg-background"
                                        : "bg-primary/[0.04]"
                                }`}
                            >
                                <button
                                    type="button"
                                    onClick={() =>
                                        void openNotification(
                                            notification,
                                        )
                                    }
                                    className="flex min-w-0 flex-1 gap-4 text-left"
                                >
                                    <NotificationIcon
                                        icon={notification.icon}
                                        priority={
                                            notification.priority
                                        }
                                    />

                                    <span className="min-w-0 flex-1">
                                        <span className="flex flex-wrap items-center gap-2">
                                            <span className="font-black">
                                                {notification.title}
                                            </span>
                                            {!notification.is_read && (
                                                <span className="rounded-full bg-primary px-2 py-0.5 text-[10px] font-black text-primary-foreground">
                                                    New
                                                </span>
                                            )}
                                            <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-bold text-muted-foreground">
                                                {
                                                    notification.event_type
                                                }
                                            </span>
                                        </span>

                                        <span className="mt-1.5 block text-sm leading-6 text-muted-foreground">
                                            {notification.message}
                                        </span>

                                        <span className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs font-semibold text-muted-foreground">
                                            <span>
                                                {formatDistanceToNow(
                                                    new Date(
                                                        notification.created_at,
                                                    ),
                                                    {
                                                        addSuffix: true,
                                                    },
                                                )}
                                            </span>
                                            <span>
                                                {format(
                                                    new Date(
                                                        notification.created_at,
                                                    ),
                                                    "dd MMM yyyy, HH:mm",
                                                )}
                                            </span>
                                        </span>
                                    </span>
                                </button>

                                <button
                                    type="button"
                                    onClick={() =>
                                        void archive(
                                            notification.id,
                                        )
                                    }
                                    aria-label="Archive notification"
                                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground"
                                >
                                    <Archive className="h-4 w-4" />
                                </button>
                            </article>
                        ))
                    )}
                </div>

                {hasMore && (
                    <div className="flex items-center justify-center border-t p-4">
                        <button
                            type="button"
                            onClick={() => void loadMore()}
                            disabled={loadingMore}
                            className="inline-flex h-11 items-center gap-2 rounded-xl border bg-background px-5 text-sm font-black transition hover:border-primary hover:text-primary disabled:opacity-50"
                        >
                            {loadingMore && (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            )}
                            {loadingMore
                                ? "Loading notifications..."
                                : `Load more (${notifications.length} of ${total})`}
                        </button>
                    </div>
                )}
            </section>
        </main>
    );
}
