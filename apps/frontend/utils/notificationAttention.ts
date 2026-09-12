import type {
    AppNotification,
    NotificationType,
} from "@/types/notification";

const ATTENTION_NOTIFICATION_TYPES: ReadonlySet<NotificationType> =
    new Set([
        "loan_request",
        "access_request",
        "offer",
        "payment",
        "subscription",
    ]);

const ATTENTION_PRIORITIES = new Set([
    "critical",
    "high",
    "urgent",
]);

/**
 * Notifications shown in the header bell must be unread and either belong to
 * a core financial/access workflow or carry an explicit high-priority flag.
 * The full notification centre remains the complete event history.
 */
export function isAttentionNotification(
    notification: AppNotification,
): boolean {
    if (
        notification.is_archived ||
        notification.is_read
    ) {
        return false;
    }

    const priority = notification.priority
        .trim()
        .toLowerCase();

    return (
        ATTENTION_PRIORITIES.has(priority) ||
        ATTENTION_NOTIFICATION_TYPES.has(
            notification.notification_type,
        )
    );
}
