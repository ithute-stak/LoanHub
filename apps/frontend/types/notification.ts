export type NotificationType =
    | "loan_request"
    | "access_request"
    | "offer"
    | "payment"
    | "subscription"
    | "system";

export type AppNotification = {
    id: string;
    user_id: string;
    actor_user_id: string | null;
    company_id: string | null;
    branch_id: string | null;
    title: string;
    message: string;
    notification_type: NotificationType;
    event_type: string;
    action: string;
    entity_type: string | null;
    entity_id: string | null;
    action_url: string | null;
    icon: string | null;
    priority: string;
    data: Record<string, unknown>;
    is_read: boolean;
    read_at: string | null;
    is_archived: boolean;
    archived_at: string | null;
    created_at: string;
    updated_at: string;
};

export type NotificationListResponse = {
    items: AppNotification[];
    total: number;
    unread_count: number;
    page: number;
    page_size: number;
};
