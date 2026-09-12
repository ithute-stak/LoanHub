import { api } from "@/lib/api";
import type {
    AppNotification,
    NotificationListResponse,
} from "@/types/notification";

export async function listNotifications(params?: {
    page?: number;
    page_size?: number;
    unread_only?: boolean;
    include_archived?: boolean;
    event_type?: string;
    attention_only?: boolean;
}): Promise<NotificationListResponse> {
    const response = await api.get<NotificationListResponse>(
        "/notifications",
        { params },
    );
    return response.data;
}

export async function markNotificationRead(
    notificationId: string,
): Promise<AppNotification> {
    const response = await api.patch<AppNotification>(
        `/notifications/${notificationId}/read`,
    );
    return response.data;
}

export async function markAllNotificationsRead(): Promise<void> {
    await api.patch("/notifications/read-all");
}

export async function archiveNotification(
    notificationId: string,
): Promise<AppNotification> {
    const response = await api.patch<AppNotification>(
        `/notifications/${notificationId}/archive`,
    );
    return response.data;
}
