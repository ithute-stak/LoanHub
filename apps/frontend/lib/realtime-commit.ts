const RECENT_REQUEST_TTL_MS = 60_000;
const localMutationRequestIds = new Map<string, number>();

function prune(now = Date.now()): void {
    for (const [requestId, expiresAt] of localMutationRequestIds) {
        if (expiresAt <= now) {
            localMutationRequestIds.delete(requestId);
        }
    }
}

export function rememberLocalMutationRequest(requestId: string): void {
    prune();
    localMutationRequestIds.set(requestId, Date.now() + RECENT_REQUEST_TTL_MS);
}

export function isLocalMutationRequest(requestId: unknown): boolean {
    if (!requestId) return false;
    prune();
    return localMutationRequestIds.has(String(requestId));
}

export type DbCommitBatchDetail = {
    events: Array<Record<string, unknown>>;
    count: number;
    latest: Record<string, unknown> | null;
    hasRemoteChanges: boolean;
};

export const DB_COMMIT_EVENT_NAME = "loanhub:db-commit";
