import {
    createSlice,
    type PayloadAction,
} from "@reduxjs/toolkit";

export type HttpCacheEntry = {
    key: string;
    scope: string;
    url: string;
    resourceTags: string[];
    data: unknown;
    status: number;
    statusText: string;
    headers: Record<string, string>;
    storedAt: number;
    expiresAt: number;
    staleUntil: number;
    lastAccessedAt: number;
};

type HttpCacheState = {
    entries: Record<string, HttpCacheEntry>;
    hits: number;
    misses: number;
    deduplicated: number;
    networkRequests: number;
    invalidations: number;
};

const MAX_CACHE_ENTRIES = 250;

const initialState: HttpCacheState = {
    entries: {},
    hits: 0,
    misses: 0,
    deduplicated: 0,
    networkRequests: 0,
    invalidations: 0,
};

function evictLeastRecentlyUsed(state: HttpCacheState): void {
    const entries = Object.values(state.entries);
    if (entries.length <= MAX_CACHE_ENTRIES) {
        return;
    }

    entries
        .sort((left, right) => left.lastAccessedAt - right.lastAccessedAt)
        .slice(0, entries.length - MAX_CACHE_ENTRIES)
        .forEach((entry) => {
            delete state.entries[entry.key];
        });
}

const httpCacheSlice = createSlice({
    name: "httpCache",
    initialState,
    reducers: {
        cacheStored(state, action: PayloadAction<HttpCacheEntry>) {
            state.entries[action.payload.key] = action.payload;
            evictLeastRecentlyUsed(state);
        },
        cacheHit(
            state,
            action: PayloadAction<{ key: string; accessedAt: number }>,
        ) {
            state.hits += 1;
            const entry = state.entries[action.payload.key];
            if (entry) {
                entry.lastAccessedAt = action.payload.accessedAt;
            }
        },
        cacheMiss(state) {
            state.misses += 1;
        },
        cacheDeduplicated(state) {
            state.deduplicated += 1;
        },
        cacheNetworkRequest(state) {
            state.networkRequests += 1;
        },
        cacheEntryRemoved(state, action: PayloadAction<string>) {
            delete state.entries[action.payload];
        },
        cacheExpiredEntriesRemoved(
            state,
            action: PayloadAction<{ now: number }>,
        ) {
            for (const [key, entry] of Object.entries(state.entries)) {
                if (entry.staleUntil <= action.payload.now) {
                    delete state.entries[key];
                }
            }
        },
        cacheScopeInvalidated(
            state,
            action: PayloadAction<{ scope: string }>,
        ) {
            let removed = 0;
            for (const [key, entry] of Object.entries(state.entries)) {
                if (entry.scope === action.payload.scope) {
                    delete state.entries[key];
                    removed += 1;
                }
            }
            if (removed > 0) {
                state.invalidations += 1;
            }
        },
        cacheTagsInvalidated(
            state,
            action: PayloadAction<{
                scope?: string;
                tags: string[];
            }>,
        ) {
            const requestedTags = new Set(action.payload.tags);
            let removed = 0;

            for (const [key, entry] of Object.entries(state.entries)) {
                if (
                    action.payload.scope &&
                    entry.scope !== action.payload.scope
                ) {
                    continue;
                }

                if (
                    entry.resourceTags.some((tag) => requestedTags.has(tag))
                ) {
                    delete state.entries[key];
                    removed += 1;
                }
            }

            if (removed > 0) {
                state.invalidations += 1;
            }
        },
        cacheCleared(state) {
            state.entries = {};
            state.invalidations += 1;
        },
    },
});

export const {
    cacheStored,
    cacheHit,
    cacheMiss,
    cacheDeduplicated,
    cacheNetworkRequest,
    cacheEntryRemoved,
    cacheExpiredEntriesRemoved,
    cacheScopeInvalidated,
    cacheTagsInvalidated,
    cacheCleared,
} = httpCacheSlice.actions;

export default httpCacheSlice.reducer;
