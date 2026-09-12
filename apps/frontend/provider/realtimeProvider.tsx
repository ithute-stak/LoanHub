"use client";

import {
    createContext,
    type ReactNode,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useRef,
    useState,
} from "react";

import { prepareWebSocketSession } from "@/api/auth";
import { resolveApiBaseUrl } from "@/lib/api";
import { createUuid } from "@/lib/uuid";
import { useTenant } from "@/provider/tenantProvider";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { cacheScopeInvalidated } from "@/store/features/slices/httpCacheSlice";

export type RealtimePayload = Record<string, unknown>;
export type RealtimeListener = (payload: RealtimePayload) => void;

type RealtimeContextValue = {
    connected: boolean;
    send: (payload: string | RealtimePayload) => boolean;
    subscribe: (listener: RealtimeListener) => () => void;
};

const RealtimeContext = createContext<RealtimeContextValue | null>(null);

function getClientId(): string {
    const key = "loanhub.realtime.client-id";
    const existing = window.sessionStorage.getItem(key);

    if (existing) {
        return existing;
    }

    const generated = createUuid();
    window.sessionStorage.setItem(key, generated);
    return generated;
}

function websocketUrl(
    clientId: string,
): string {
    const base = new URL(
        resolveApiBaseUrl(),
        window.location.origin,
    ).toString();

    const url = new URL(
        `${base.replace(/\/$/, "")}/ws`,
    );

    url.protocol =
        url.protocol === "https:"
            ? "wss:"
            : "ws:";

    url.searchParams.set("client_id", clientId);

    return url.toString();
}

function websocketProtocols(
    websocketToken: string,
): string[] {
    // JWTs use the RFC 4648 base64url alphabet and are valid WebSocket
    // subprotocol tokens. Reject unexpected characters instead of silently
    // falling back to a credential-bearing URL.
    if (!/^[A-Za-z0-9._~-]+$/.test(websocketToken)) {
        throw new Error("Invalid WebSocket session token");
    }

    return [
        "loanhub.v1",
        `loanhub.jwt.${websocketToken}`,
    ];
}

export function RealtimeProvider({
    children,
}: {
    children: ReactNode;
}) {
    const dispatch = useAppDispatch();
    const userId = useAppSelector(
        (state) => state.auth.user?.id ?? null,
    );
    const userRole = useAppSelector(
        (state) => state.auth.user?.role ?? null,
    );
    const accessToken = useAppSelector(
        (state) => state.auth.accessToken,
    );
    const authInitialized = useAppSelector(
        (state) => state.auth.initialized,
    );
    const { activeCompanyId, activeMembership } = useTenant();
    const activeRole = activeMembership?.role ?? userRole ?? "anonymous";

    const [connected, setConnected] =
        useState(false);

    const socketRef = useRef<WebSocket | null>(null);
    const socketKeyRef = useRef<string | null>(null);
    const reconnectTimerRef = useRef<number | null>(null);
    const reconnectAttemptRef = useRef(0);
    const listenersRef = useRef(
        new Set<RealtimeListener>(),
    );
    const disposedRef = useRef(false);

    const clearReconnectTimer = useCallback(() => {
        if (reconnectTimerRef.current !== null) {
            window.clearTimeout(
                reconnectTimerRef.current,
            );
            reconnectTimerRef.current = null;
        }
    }, []);

    const closeCurrentSocket = useCallback(() => {
        clearReconnectTimer();

        const socket = socketRef.current;
        socketRef.current = null;
        socketKeyRef.current = null;

        if (
            socket &&
            socket.readyState !== WebSocket.CLOSED
        ) {
            socket.onclose = null;
            socket.onerror = null;
            socket.onmessage = null;
            socket.onopen = null;
            socket.close(1000, "Scope changed");
        }

        setConnected(false);
    }, [clearReconnectTimer]);

    useEffect(() => {
        if (
            !authInitialized ||
            !userId ||
            !accessToken
        ) {
            disposedRef.current = true;
            closeCurrentSocket();
            return;
        }

        disposedRef.current = false;
        const clientId = getClientId();
        const socketKey = [
            userId,
            activeCompanyId ?? "platform",
            activeRole,
            accessToken,
        ].join(":");
        let generation = 0;

        function scheduleReconnect() {
            if (disposedRef.current) {
                return;
            }

            const attempt =
                reconnectAttemptRef.current++;
            const baseDelay = Math.min(
                60_000,
                1_000 * 2 ** attempt,
            );
            const jitter = Math.floor(
                Math.random() * Math.min(1_000, baseDelay * 0.2),
            );

            reconnectTimerRef.current =
                window.setTimeout(
                    () => void connect(),
                    baseDelay + jitter,
                );
        }

        async function connect() {
            if (disposedRef.current) {
                return;
            }

            if (
                socketKeyRef.current === socketKey &&
                socketRef.current &&
                (socketRef.current.readyState ===
                    WebSocket.CONNECTING ||
                    socketRef.current.readyState ===
                        WebSocket.OPEN)
            ) {
                return;
            }

            const currentGeneration = ++generation;
            clearReconnectTimer();
            closeCurrentSocket();

            try {
                // Creates a client-bound, short-lived WebSocket token. It is
                // sent as a subprotocol, never in the URL or application logs.
                // The HttpOnly cookie remains a same-origin fallback.
                const session = await prepareWebSocketSession(
                    activeCompanyId,
                    clientId,
                );

                if (
                    disposedRef.current ||
                    currentGeneration !== generation
                ) {
                    return;
                }

                const socket = new WebSocket(
                    websocketUrl(clientId),
                    session.websocket_token
                        ? websocketProtocols(session.websocket_token)
                        : ["loanhub.v1"],
                );

                socketRef.current = socket;
                socketKeyRef.current = socketKey;
            } catch {
                if (
                    disposedRef.current ||
                    currentGeneration !== generation
                ) {
                    return;
                }

                setConnected(false);
                scheduleReconnect();
                return;
            }

            const socket = socketRef.current;
            if (!socket) {
                setConnected(false);
                scheduleReconnect();
                return;
            }

            socket.onopen = () => {
                if (
                    socketRef.current !== socket ||
                    disposedRef.current
                ) {
                    socket.close();
                    return;
                }

                reconnectAttemptRef.current = 0;
                setConnected(true);
            };

            socket.onmessage = (event) => {
                if (event.data === "pong") {
                    return;
                }

                let payload: RealtimePayload;

                try {
                    payload = JSON.parse(
                        String(event.data),
                    ) as RealtimePayload;
                } catch {
                    return;
                }

                if (String(payload.type ?? "") === "DB_EVENT") {
                    dispatch(
                        cacheScopeInvalidated({
                            scope: [
                                userId,
                                activeCompanyId ?? "platform",
                                activeRole,
                            ].join(":"),
                        }),
                    );
                }

                for (
                    const listener of
                    listenersRef.current
                ) {
                    try {
                        listener(payload);
                    } catch {
                        // One consumer must not break other realtime consumers.
                    }
                }
            };

            socket.onerror = () => {
                if (socketRef.current === socket) {
                    setConnected(false);
                }
            };

            socket.onclose = () => {
                if (socketRef.current === socket) {
                    socketRef.current = null;
                    socketKeyRef.current = null;
                    setConnected(false);
                }

                if (disposedRef.current) {
                    return;
                }

                scheduleReconnect();
            };
        }

        void connect();

        const heartbeat = window.setInterval(() => {
            if (
                socketRef.current?.readyState ===
                WebSocket.OPEN
            ) {
                socketRef.current.send("ping");
            }
        }, 25_000);

        return () => {
            disposedRef.current = true;
            generation += 1;
            window.clearInterval(heartbeat);
            closeCurrentSocket();
        };
    }, [
        accessToken,
        activeCompanyId,
        activeRole,
        authInitialized,
        clearReconnectTimer,
        closeCurrentSocket,
        dispatch,
        userId,
    ]);

    const subscribe = useCallback(
        (listener: RealtimeListener) => {
            listenersRef.current.add(listener);

            return () => {
                listenersRef.current.delete(listener);
            };
        },
        [],
    );

    const send = useCallback(
        (payload: string | RealtimePayload) => {
            const socket = socketRef.current;

            if (
                !socket ||
                socket.readyState !== WebSocket.OPEN
            ) {
                return false;
            }

            socket.send(
                typeof payload === "string"
                    ? payload
                    : JSON.stringify(payload),
            );

            return true;
        },
        [],
    );

    const value = useMemo<RealtimeContextValue>(
        () => ({
            connected,
            send,
            subscribe,
        }),
        [connected, send, subscribe],
    );

    return (
        <RealtimeContext.Provider value={value}>
            {children}
        </RealtimeContext.Provider>
    );
}

export function useRealtime(): RealtimeContextValue {
    const context = useContext(RealtimeContext);

    if (!context) {
        throw new Error(
            "useRealtime must be used inside RealtimeProvider",
        );
    }

    return context;
}
