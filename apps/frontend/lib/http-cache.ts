import type { EnhancedStore } from "@reduxjs/toolkit";
import axios, {
    AxiosHeaders,
    type AxiosAdapter,
    type AxiosInstance,
    type AxiosResponse,
    type InternalAxiosRequestConfig,
} from "axios";

import {
    cacheCleared,
    cacheDeduplicated,
    cacheEntryRemoved,
    cacheExpiredEntriesRemoved,
    cacheHit,
    cacheMiss,
    cacheNetworkRequest,
    cacheScopeInvalidated,
    cacheStored,
    cacheTagsInvalidated,
    type HttpCacheEntry,
} from "@/store/features/slices/httpCacheSlice";
import type { RootState } from "@/store";

export type LoanHubCacheMode = "default" | "refresh" | "no-store";

export type LoanHubCacheOptions = {
    mode?: LoanHubCacheMode;
    ttlMs?: number;
    staleWhileRevalidateMs?: number;
    tags?: string[];
};

declare module "axios" {
    interface AxiosRequestConfig<D = any> {
        loanHubCache?: LoanHubCacheOptions;
    }
}

type CachePolicy = {
    ttlMs: number;
    staleWhileRevalidateMs: number;
};

const installedClients = new WeakSet<AxiosInstance>();
const storeUnsubscribers = new WeakMap<object, () => void>();
const inflightRequests = new Map<string, Promise<AxiosResponse>>();

const DEFAULT_POLICY: CachePolicy = {
    ttlMs: 30_000,
    staleWhileRevalidateMs: 0,
};

const REFERENCE_POLICY: CachePolicy = {
    ttlMs: 5 * 60_000,
    staleWhileRevalidateMs: 60_000,
};

const DIRECTORY_POLICY: CachePolicy = {
    ttlMs: 60_000,
    staleWhileRevalidateMs: 15_000,
};

const LIVE_POLICY: CachePolicy = {
    ttlMs: 10_000,
    staleWhileRevalidateMs: 0,
};

const SUMMARY_POLICY: CachePolicy = {
    ttlMs: 20_000,
    staleWhileRevalidateMs: 5_000,
};

const MAX_CACHEABLE_BYTES = 2 * 1024 * 1024;

function normalizedPath(config: InternalAxiosRequestConfig): string {
    try {
        return new URL(
            config.url ?? "",
            config.baseURL ??
                (typeof window !== "undefined"
                    ? window.location.origin
                    : "http://localhost"),
        ).pathname.replace(/^\/api\/v1/, "");
    } catch {
        return (config.url ?? "").split("?")[0] ?? "";
    }
}

function policyForPath(path: string): CachePolicy {
    if (
        /\/(payments|loans|collections|marketplace|accounting|finance)(\/|$)/.test(
            path,
        )
    ) {
        return LIVE_POLICY;
    }

    if (
        /\/(dashboard|analytics|summary|overview|workspace)(\/|$)/.test(path) ||
        path.startsWith("/reports")
    ) {
        return SUMMARY_POLICY;
    }

    if (
        /\/(branches|companies|employees|staff|clients|borrowers|candidates|assets)(\/|$)/.test(
            path,
        )
    ) {
        return DIRECTORY_POLICY;
    }

    if (
        /\/(plans|products|departments|positions|shifts|leave\/types|settings|config)(\/|$)/.test(
            path,
        )
    ) {
        return REFERENCE_POLICY;
    }

    return DEFAULT_POLICY;
}

function isExplicitlyUncacheable(
    config: InternalAxiosRequestConfig,
    path: string,
): boolean {
    const headers = AxiosHeaders.from(config.headers);
    const requestCacheControl = String(
        headers.get("Cache-Control") ?? "",
    ).toLowerCase();
    const loanHubHeader = String(
        headers.get("X-LoanHub-Cache") ?? "",
    ).toLowerCase();

    if (
        config.loanHubCache?.mode === "no-store" ||
        requestCacheControl.includes("no-store") ||
        loanHubHeader === "bypass"
    ) {
        return true;
    }

    if (
        config.responseType &&
        !["json", "text"].includes(config.responseType)
    ) {
        return true;
    }

    return [
        "/auth/",
        "/notifications",
        "/chat/",
        "/system-errors",
        "/ws",
        "/health",
        "/files/",
        "/payroll",
        "/financial-profile",
        "/banking",
        "/credentials",
        "/secrets",
        "/download",
        "/receipt",
        "/pdf",
        "/export",
    ].some((fragment) => path.includes(fragment));
}

function requestScope(
    state: RootState,
    config: InternalAxiosRequestConfig,
): string {
    const headers = AxiosHeaders.from(config.headers);
    const userId = state.auth.user?.id ?? "anonymous";
    const companyId = String(
        headers.get("X-Company-ID") ?? "platform",
    );
    const role = String(
        headers.get("X-Active-Role") ?? state.auth.user?.role ?? "anonymous",
    );

    return `${userId}:${companyId}:${role}`;
}

function requestKey(
    state: RootState,
    config: InternalAxiosRequestConfig,
): { key: string; scope: string; requestUrl: string } {
    const scope = requestScope(state, config);
    const requestUrl = axios.getUri(config);
    return {
        key: `http:${scope}|${requestUrl}`,
        scope,
        requestUrl,
    };
}

function resourceTagsFromPath(path: string): string[] {
    const segments = path
        .split("/")
        .map((segment) => segment.trim().toLowerCase())
        .filter(Boolean)
        .filter((segment) => !/^[0-9a-f-]{16,}$/i.test(segment));

    const tags = new Set<string>();
    if (segments[0]) {
        tags.add(segments[0]);
    }
    if (segments[0] && segments[1]) {
        tags.add(`${segments[0]}:${segments[1]}`);
    }

    if (
        segments.some((segment) =>
            ["dashboard", "summary", "overview", "analytics", "reports"].includes(
                segment,
            ),
        )
    ) {
        tags.add("summary");
    }

    return [...tags];
}

type AxiosResponseHeaderBag = AxiosResponse["headers"];

function responseHeadersToAxiosHeaders(
    headers: AxiosResponseHeaderBag,
): AxiosHeaders {
    if (headers instanceof AxiosHeaders) {
        return new AxiosHeaders(headers);
    }

    const normalized = new AxiosHeaders();

    for (const [name, value] of Object.entries(headers)) {
        if (value === undefined) {
            continue;
        }
        normalized.set(name, value);
    }

    return normalized;
}

function headersToRecord(
    headers: AxiosResponseHeaderBag,
): Record<string, string> {
    const result: Record<string, string> = {};
    const normalized = responseHeadersToAxiosHeaders(headers).toJSON();

    for (const [key, value] of Object.entries(normalized)) {
        if (value === null || value === undefined) {
            continue;
        }
        result[key] = Array.isArray(value) ? value.join(", ") : String(value);
    }

    return result;
}

function cloneCacheData<T>(data: T): T {
    if (data === null || data === undefined || typeof data !== "object") {
        return data;
    }

    if (typeof structuredClone === "function") {
        try {
            return structuredClone(data);
        } catch {
            // API cache entries are expected to be JSON. Fall through to the
            // JSON clone for browsers with partial structured-clone support.
        }
    }

    return JSON.parse(JSON.stringify(data)) as T;
}

function cacheableResponse(response: AxiosResponse): boolean {
    if (response.status < 200 || response.status >= 300) {
        return false;
    }

    const headers = responseHeadersToAxiosHeaders(response.headers);
    const responseCacheControl = String(
        headers.get("Cache-Control") ?? "",
    ).toLowerCase();
    const contentType = String(
        headers.get("Content-Type") ?? "application/json",
    ).toLowerCase();

    if (
        responseCacheControl.includes("no-store") ||
        !contentType.includes("json")
    ) {
        return false;
    }

    try {
        return JSON.stringify(response.data).length <= MAX_CACHEABLE_BYTES;
    } catch {
        return false;
    }
}

function responseFromEntry(
    entry: HttpCacheEntry,
    config: InternalAxiosRequestConfig,
    cacheStatus: "HIT" | "STALE",
): AxiosResponse {
    const headers = AxiosHeaders.from(entry.headers);
    headers.set("X-LoanHub-Client-Cache", cacheStatus);

    return {
        data: cloneCacheData(entry.data),
        status: entry.status,
        statusText: entry.statusText,
        headers,
        config,
    };
}

export function invalidateLoanHubClientCache(
    store: EnhancedStore<RootState>,
    options?: { scope?: string; tags?: string[] },
): void {
    if (options?.tags?.length) {
        store.dispatch(
            cacheTagsInvalidated({
                scope: options.scope,
                tags: options.tags,
            }),
        );
        return;
    }

    if (options?.scope) {
        store.dispatch(cacheScopeInvalidated({ scope: options.scope }));
        return;
    }

    store.dispatch(cacheCleared());
}

export function installReduxHttpCache(
    client: AxiosInstance,
    store: EnhancedStore<RootState>,
): void {
    if (installedClients.has(client)) {
        return;
    }
    installedClients.add(client);

    const networkAdapter: AxiosAdapter = axios.getAdapter(
        client.defaults.adapter,
    );

    async function fetchAndStore(
        config: InternalAxiosRequestConfig,
        cacheIdentity: {
            key: string;
            scope: string;
            requestUrl: string;
        },
        policy: CachePolicy,
        path: string,
    ): Promise<AxiosResponse> {
        store.dispatch(cacheNetworkRequest());
        const response = await networkAdapter(config);
        const responseHeaders = responseHeadersToAxiosHeaders(response.headers);
        responseHeaders.set("X-LoanHub-Client-Cache", "MISS");
        response.headers = responseHeaders;

        if (cacheableResponse(response)) {
            const now = Date.now();
            const explicitTags = config.loanHubCache?.tags ?? [];
            store.dispatch(
                cacheStored({
                    key: cacheIdentity.key,
                    scope: cacheIdentity.scope,
                    url: cacheIdentity.requestUrl,
                    resourceTags: [
                        ...new Set([
                            ...resourceTagsFromPath(path),
                            ...explicitTags,
                        ]),
                    ],
                    data: cloneCacheData(response.data),
                    status: response.status,
                    statusText: response.statusText,
                    headers: headersToRecord(response.headers),
                    storedAt: now,
                    expiresAt: now + policy.ttlMs,
                    staleUntil:
                        now + policy.ttlMs + policy.staleWhileRevalidateMs,
                    lastAccessedAt: now,
                }),
            );
        }

        return response;
    }

    client.defaults.adapter = async (
        config: InternalAxiosRequestConfig,
    ): Promise<AxiosResponse> => {
        const method = (config.method ?? "get").toLowerCase();
        const path = normalizedPath(config);

        if (
            method !== "get" ||
            isExplicitlyUncacheable(config, path)
        ) {
            return networkAdapter(config);
        }

        const state = store.getState();
        const identity = requestKey(state, config);
        const configured = policyForPath(path);
        const policy: CachePolicy = {
            ttlMs: config.loanHubCache?.ttlMs ?? configured.ttlMs,
            staleWhileRevalidateMs:
                config.loanHubCache?.staleWhileRevalidateMs ??
                configured.staleWhileRevalidateMs,
        };
        const now = Date.now();

        store.dispatch(cacheExpiredEntriesRemoved({ now }));
        const entry = store.getState().httpCache.entries[identity.key];
        const forceRefresh = config.loanHubCache?.mode === "refresh";

        if (!forceRefresh && entry && entry.expiresAt > now) {
            store.dispatch(cacheHit({ key: identity.key, accessedAt: now }));
            return responseFromEntry(entry, config, "HIT");
        }

        if (
            !forceRefresh &&
            entry &&
            entry.staleUntil > now &&
            policy.staleWhileRevalidateMs > 0
        ) {
            store.dispatch(cacheHit({ key: identity.key, accessedAt: now }));
            if (!inflightRequests.has(identity.key)) {
                const backgroundConfig = {
                    ...config,
                    signal: undefined,
                } as InternalAxiosRequestConfig;
                const backgroundRequest = fetchAndStore(
                    backgroundConfig,
                    identity,
                    policy,
                    path,
                ).finally(() => {
                    inflightRequests.delete(identity.key);
                });
                inflightRequests.set(identity.key, backgroundRequest);
                void backgroundRequest.catch(() => undefined);
            }
            return responseFromEntry(entry, config, "STALE");
        }

        if (entry) {
            store.dispatch(cacheEntryRemoved(identity.key));
        }
        store.dispatch(cacheMiss());

        const inflight = inflightRequests.get(identity.key);
        if (inflight) {
            store.dispatch(cacheDeduplicated());
            return inflight;
        }

        const request = fetchAndStore(
            config,
            identity,
            policy,
            path,
        ).finally(() => {
            inflightRequests.delete(identity.key);
        });
        inflightRequests.set(identity.key, request);
        return request;
    };

    client.interceptors.response.use((response) => {
        const method = (response.config.method ?? "get").toLowerCase();
        if (method === "get" || response.status >= 400) {
            return response;
        }

        const path = normalizedPath(
            response.config as InternalAxiosRequestConfig,
        );
        if (path.startsWith("/auth/")) {
            store.dispatch(cacheCleared());
            return response;
        }

        const scope = requestScope(
            store.getState(),
            response.config as InternalAxiosRequestConfig,
        );
        store.dispatch(cacheScopeInvalidated({ scope }));
        return response;
    });

    let previousUserId = store.getState().auth.user?.id ?? null;
    if (!storeUnsubscribers.has(store)) {
        const unsubscribe = store.subscribe(() => {
            const nextUserId = store.getState().auth.user?.id ?? null;
            if (nextUserId !== previousUserId) {
                previousUserId = nextUserId;
                store.dispatch(cacheCleared());
            }
        });
        storeUnsubscribers.set(store, unsubscribe);
    }
}
