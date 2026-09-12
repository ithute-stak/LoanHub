import { api } from "@/lib/api";
import type {
    ChatConversation,
    ChatMessage,
    ChatUser,
    CreateConversationPayload,
} from "@/types/chat";

export async function listChatDirectory(search?: string): Promise<ChatUser[]> {
    const response = await api.get<ChatUser[]>("/chat/directory", {
        params: { search },
    });
    return response.data;
}

export async function listChatConversations(): Promise<ChatConversation[]> {
    const response = await api.get<ChatConversation[]>("/chat/conversations");
    return response.data;
}

export async function getChatUnreadCount(): Promise<number> {
    const response = await api.get<{ unread_count: number }>("/chat/unread-count");
    return response.data.unread_count;
}

export async function createChatConversation(
    payload: CreateConversationPayload,
): Promise<ChatConversation> {
    const response = await api.post<ChatConversation>("/chat/conversations", payload);
    return response.data;
}

export async function listChatMessages(
    conversationId: string,
    params?: { before?: string; limit?: number },
): Promise<ChatMessage[]> {
    const response = await api.get<ChatMessage[]>(
        `/chat/conversations/${conversationId}/messages`,
        { params },
    );
    return response.data;
}

export async function sendChatMessage(
    conversationId: string,
    payload: {
        body: string;
        client_message_id: string;
        reply_to_message_id?: string | null;
    },
): Promise<ChatMessage> {
    const response = await api.post<ChatMessage>(
        `/chat/conversations/${conversationId}/messages`,
        payload,
    );
    return response.data;
}

export async function sendChatFile(
    conversationId: string,
    payload: { file: File; body?: string; clientMessageId: string },
): Promise<ChatMessage> {
    const form = new FormData();
    form.append("file", payload.file);
    form.append("client_message_id", payload.clientMessageId);
    if (payload.body) form.append("body", payload.body);

    const response = await api.post<ChatMessage>(
        `/chat/conversations/${conversationId}/files`,
        form,
    );
    return response.data;
}

export async function markChatConversationRead(conversationId: string): Promise<void> {
    await api.patch(`/chat/conversations/${conversationId}/read`);
}


export async function shareManagedFileInChat(
    conversationId: string,
    fileId: string,
    payload: { body?: string; client_message_id: string },
): Promise<ChatMessage> {
    const response = await api.post<ChatMessage>(
        `/chat/conversations/${conversationId}/share-file/${fileId}`,
        payload,
    );
    return response.data;
}
