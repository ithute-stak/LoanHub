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
import { useTenant } from "@/provider/tenantProvider";
import { useAppSelector } from "@/store/hooks";

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

    const generated = window.crypto.randomUUID();
    window.sessionStorage.setItem(key, generated);
    return generated;
}

function websocketUrl(
    clientId: string,
): string {
    const configured =
        process.env.NEXT_PUBLIC_API_URL ??
        "http://localhost:8000/api/v1";

    const base = new URL(
        configured,
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

export function RealtimeProvider({
    children,
}: {
    children: ReactNode;
}) {
    const userId = useAppSelector(
        (state) => state.auth.user?.id ?? null,
    );
    const accessToken = useAppSelector(
        (state) => state.auth.accessToken,
    );
    const authInitialized = useAppSelector(
        (state) => state.auth.initialized,
    );
    const { activeCompanyId } = useTenant();

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
            accessToken,
        ].join(":");
        let generation = 0;

        function scheduleReconnect() {
            if (disposedRef.current) {
                return;
            }

            const attempt =
                reconnectAttemptRef.current++;
            const delay = Math.min(
                30_000,
                1_000 * 2 ** attempt,
            );

            reconnectTimerRef.current =
                window.setTimeout(
                    () => void connect(),
                    delay,
                );
        }

        async function connect() {
            if (disposedRef.current) {
                return;
            }

            if (
                socketKeyRef.current === socketKey &&
                socketRef.current &&
                [
                    WebSocket.CONNECTING,
                    WebSocket.OPEN,
                ].includes(
                    socketRef.current.readyState,
                )
            ) {
                return;
            }

            const currentGeneration = ++generation;
            clearReconnectTimer();
            closeCurrentSocket();

            try {
                // Creates a short-lived HttpOnly cookie scoped to /api/v1/ws.
                // The access token never appears in the WebSocket URL.
                await prepareWebSocketSession(
                    activeCompanyId,
                );
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

            if (
                disposedRef.current ||
                currentGeneration !== generation
            ) {
                return;
            }

            const socket = new WebSocket(
                websocketUrl(clientId),
                ["loanhub.v1"],
            );

            socketRef.current = socket;
            socketKeyRef.current = socketKey;

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
        authInitialized,
        clearReconnectTimer,
        closeCurrentSocket,
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
