import type { ManagedFile } from "@/types/files";

export type ChatUser = {
    id: string;
    display_name: string;
    email: string | null;
    phone: string;
    role: string;
    company_name: string | null;
    branch_name: string | null;
    is_online: boolean;
    last_seen_at: string | null;
};

export type ChatParticipant = {
    user: ChatUser;
    is_admin: boolean;
    last_read_at: string | null;
};

export type ChatMessage = {
    id: string;
    conversation_id: string;
    sender: ChatUser | null;
    message_type: "text" | "file" | "voice" | string;
    body: string | null;
    reply_to_message_id: string | null;
    client_message_id: string;
    attachments: ManagedFile[];
    edited_at: string | null;
    deleted_at: string | null;
    created_at: string;
};

export type ChatConversation = {
    id: string;
    reference: string;
    title: string;
    conversation_type: string;
    is_group: boolean;
    company_id: string | null;
    branch_id: string | null;
    context_type: string | null;
    context_id: string | null;
    participants: ChatParticipant[];
    last_message: ChatMessage | null;
    unread_count: number;
    last_message_at: string | null;
    created_at: string;
};

export type CreateConversationPayload = {
    participant_ids: string[];
    title?: string;
    conversation_type?: string;
    context_type?: string;
    context_id?: string;
};
