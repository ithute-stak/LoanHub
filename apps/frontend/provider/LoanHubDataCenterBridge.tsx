"use client";

/** Opt-in only. No persisted data and no financial APIs are replaced.
 * This bridge refuses to install Redux projections until the server certifies
 * a complete, cursor-bound, replayable snapshot for the current membership.
 */
import {useEffect} from "react";
import {api} from "@/lib/api";
import {DB_COMMIT_EVENT_NAME} from "@/lib/realtime-commit";
import {useTenant} from "@/provider/tenantProvider";
import {useRealtime} from "@/provider/realtimeProvider";
import {store} from "@/store";
import {useAppDispatch, useAppSelector} from "@/store/hooks";
import {
    dataCenterActions,
    type DirectoryProjection,
    type DirectoryScope,
} from "@/store/slices/dataCenterSlice";
import {createUuid} from "@/lib/uuid";

// Explicitly disabled in current production builds unless a separately
// tested image is built with this opt-in flag and the server capture is on.
export const LOANHUB_DATA_CENTER_ENABLED =
    process.env.NEXT_PUBLIC_LOANHUB_DATA_CENTER_ENABLED === "true";

type Preview = {
    contract?: string;
    ready?: boolean;
    complete_data_center_snapshot?: boolean;
    replay_supported?: boolean;
    generation?: string;
    cursor?: number;
    scope?: DirectoryScope;
    buckets?: DirectoryProjection["buckets"];
};
type Replay = {
    contract?: string;
    company_id?: string;
    payloads_included?: boolean;
    generation?: string;
    from_cursor?: number;
    next_cursor?: number;
    high_watermark?: number;
    has_more?: boolean;
    events?: Array<{cursor: number; resource: string; entity_id: string; branch_id: string | null; action: string}>;
};

const MAX_REPLAY_PAGES = 40;

export function LoanHubDataCenterBridge() {
    const dispatch = useAppDispatch();
    const userId = useAppSelector(state => state.auth.user?.id ?? null);
    const authInitialized = useAppSelector(state => state.auth.initialized);
    const {activeCompanyId, activeMembership} = useTenant();
    const {connected} = useRealtime();
    const role = activeMembership?.role ?? null;
    const branch = activeMembership?.branch_id ?? null;

    useEffect(() => {
        if (!LOANHUB_DATA_CENTER_ENABLED || !authInitialized || !connected ||
            !userId || !activeCompanyId ||
            (role !== "company_owner" && role !== "company_admin")) {
            return;
        }

        const sessionId = createUuid();
        const expectedScope: DirectoryScope = {
            userId, companyId: activeCompanyId, role, branchId: null,
        };
        const scopeIsCurrent = (scope: DirectoryScope | undefined): boolean =>
            Boolean(scope &&
                scope.userId === expectedScope.userId &&
                scope.companyId === expectedScope.companyId &&
                scope.role === expectedScope.role &&
                scope.branchId === null);
        const controller = new AbortController();
        let cancelled = false;
        let generation: string | null = null;
        let cursor: number | null = null;
        let running = false;
        let queued = false;
        let timer: number | null = null;

        const revoke = () => {
            dispatch(dataCenterActions.clear(sessionId));
            generation = null;
            cursor = null;
        };

        const bootstrap = async (): Promise<boolean> => {
            const {data} = await api.get<Preview>("/realtime/data-center/snapshot-preview", {
                signal: controller.signal,
                loanHubCache: {mode: "no-store"},
            });
            if (cancelled) return false;
            if (data.contract !== "loanhub.directory-preview.v1" ||
                !data.ready || !data.complete_data_center_snapshot ||
                !data.replay_supported || !data.generation ||
                !scopeIsCurrent(data.scope) ||
                typeof data.cursor !== "number" ||
                !Number.isSafeInteger(data.cursor) || data.cursor < 0 ||
                !data.buckets) {
                revoke();
                return false;
            }

            const projection: DirectoryProjection = {
                scope: expectedScope,
                cursor: data.cursor!,
                ready: true,
                buckets: data.buckets,
            };
            const previous = store.getState().dataCenter;
            if (previous.sessionId === sessionId &&
                previous.cursor !== null &&
                projection.cursor < previous.cursor) {
                revoke();
                return false;
            }
            if (previous.sessionId && previous.sessionId !== sessionId) {
                // Only the old scope's effect may retire its own session.
                return false;
            }
            dispatch(dataCenterActions.install(sessionId, projection));
            // The reducer independently validates the complete six-bucket
            // field allowlists, tenant scope and cursor before marking ready.
            const installed = store.getState().dataCenter;
            if (!installed.ready || installed.sessionId !== sessionId ||
                installed.cursor !== projection.cursor) {
                revoke();
                return false;
            }
            generation = data.generation;
            cursor = projection.cursor;
            return true;
        };

        const catchup = async (): Promise<void> => {
            if (cancelled) return;
            if (!generation || cursor === null) {
                await bootstrap();
                return;
            }
            let after = cursor;
            let hasMore = false;
            try {
                for (let page = 0; page < MAX_REPLAY_PAGES; page++) {
                    const replayResponse: {data: Replay} = await api.get<Replay>("/realtime/data-center/replay", {
                        signal: controller.signal,
                        loanHubCache: {mode: "no-store"},
                        params: {generation, after_cursor: after, limit: 200},
                    });
                    if (cancelled) return;
                    const reply: Replay = replayResponse.data;
                    if (reply.contract !== "loanhub.data-center-replay.v1" ||
                        reply.company_id !== expectedScope.companyId ||
                        reply.payloads_included !== false ||
                        reply.generation !== generation || reply.from_cursor !== after ||
                        typeof reply.has_more !== "boolean" ||
                        !Number.isSafeInteger(reply.from_cursor) ||
                        !Number.isSafeInteger(reply.next_cursor) ||
                        !Number.isSafeInteger(reply.high_watermark) ||
                        reply.high_watermark! < after ||
                        !Array.isArray(reply.events) || reply.events.length > 200) {
                        throw new Error("Invalid replay envelope");
                    }
                    let expected = after + 1;
                    for (const event of reply.events) {
                        if (!Number.isSafeInteger(event.cursor) ||
                            event.cursor !== expected++ ||
                            !["branches", "loanProducts", "staff", "clients", "loans", "payments"].includes(event.resource) ||
                            !["created", "updated", "deleted"].includes(event.action) ||
                            typeof event.entity_id !== "string" || !event.entity_id ||
                            (event.branch_id !== null && typeof event.branch_id !== "string")) {
                            throw new Error("Replay cursor gap or invalid metadata");
                        }
                    }
                    if (reply.next_cursor !== expected - 1 ||
                        reply.next_cursor > reply.high_watermark!) {
                        throw new Error("Replay cursor mismatch");
                    }
                    after = reply.next_cursor;
                    hasMore = Boolean(reply.has_more);
                    if (hasMore !== (after < reply.high_watermark!)) {
                        throw new Error("Replay completeness mismatch");
                    }
                    if (!hasMore) break;
                    if (page === MAX_REPLAY_PAGES - 1) {
                        throw new Error("Replay capacity exceeded");
                    }
                }
                // Rebuild from a consistent authoritative snapshot only when
                // changes were observed; never patch financial rows from events.
                if (after > cursor || !store.getState().dataCenter.ready) {
                    await bootstrap();
                }
            } catch {
                if (cancelled) return;
                revoke();
                // Any gap, generation change, or outage forces a new verified
                // snapshot. Never keep a stale projection marked current.
                try { await bootstrap(); } catch { /* next catchup can retry */ }
            }
        };

        const runSync = async () => {
            if (cancelled) return;
            if (running) {
                queued = true;
                return;
            }
            running = true;
            try { await catchup(); }
            catch { revoke(); }
            finally {
                running = false;
                if (queued && !cancelled) {
                    queued = false;
                    schedule(150);
                }
            }
        };
        function schedule(delay = 150) {
            if (cancelled) return;
            if (timer !== null) window.clearTimeout(timer);
            timer = window.setTimeout(() => {
                timer = null;
                void runSync();
            }, delay);
        }
        const onCommit = () => schedule();
        const onVisibility = () => {
            if (document.visibilityState === "visible") schedule();
        };
        window.addEventListener(DB_COMMIT_EVENT_NAME, onCommit);
        document.addEventListener("visibilitychange", onVisibility);
        const interval = window.setInterval(() => {
            if (document.visibilityState === "visible") schedule();
        }, 60_000);
        schedule(0);

        return () => {
            cancelled = true;
            controller.abort();
            if (timer !== null) window.clearTimeout(timer);
            window.clearInterval(interval);
            window.removeEventListener(DB_COMMIT_EVENT_NAME, onCommit);
            document.removeEventListener("visibilitychange", onVisibility);
            dispatch(dataCenterActions.clear(sessionId));
        };
    }, [activeCompanyId, authInitialized, branch, connected, dispatch, role, userId]);

    return null;
}
