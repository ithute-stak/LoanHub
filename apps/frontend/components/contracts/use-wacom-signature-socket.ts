"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  validateWacomPreviewStrokes,
  type WacomPreviewStrokes,
} from "./wacom-stroke-preview";

export type WacomSocketStatus =
  | "idle" | "connecting" | "authorizing" | "capturing"
  | "complete" | "cancelled" | "error";

export type AuthorizedWacomPreview = Readonly<{
  /** Issued by LoanHub after workstation proof and consent. Never put in a URL. */
  ticket: string;
  /** A non-secret unique session/contract-hash/field binding for UI reset. */
  sessionKey: string;
  /** Approved field identifier supplied by LoanHub, not derived from an arbitrary DOM id. */
  fieldId: string;
  /** The backend-approved connector endpoint. Must be local loopback. */
  endpoint: string;
  /** Server-provided, never exceed 30 seconds. */
  expiresAt: number;
}>;

const MAX_FRAME_BYTES = 256 * 1024;

function isSafeEndpoint(endpoint: string): boolean {
  try {
    const url = new URL(endpoint);
    return (
      url.protocol === "ws:" &&
      url.hostname === "127.0.0.1" &&
      url.port === "8765" &&
      url.pathname === "/v1/preview/stream" &&
      url.search === "" &&
      url.hash === "" &&
      url.username === "" &&
      url.password === ""
    );
  } catch {
    return false;
  }
}

export function useWacomSignatureSocket(sessionKey: string) {
  const socket = useRef<WebSocket | null>(null);
  const expiryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [status, setStatus] = useState<WacomSocketStatus>("idle");
  const [strokes, setStrokes] = useState<WacomPreviewStrokes | null>(null);
  const activeKey = useRef(sessionKey);

  const close = useCallback((notify = true) => {
    if (expiryTimer.current !== null) clearTimeout(expiryTimer.current);
    expiryTimer.current = null;
    const current = socket.current;
    socket.current = null;
    if (current) {
      if (notify && current.readyState === WebSocket.OPEN)
        current.send(JSON.stringify({ type: "cancel" }));
      current.close(1000, "preview closed");
    }
    setStrokes(null);
    setStatus("cancelled");
  }, []);

  useEffect(() => {
    activeKey.current = sessionKey;
    setStrokes(null);
    setStatus("idle");
    return () => {
      const current = socket.current;
      socket.current = null;
      current?.close(1000, "session changed");
      if (expiryTimer.current !== null) clearTimeout(expiryTimer.current);
      expiryTimer.current = null;
    };
  }, [sessionKey]);

  const start = useCallback((approval: AuthorizedWacomPreview) => {
    // Focus alone must never call start: it requires a separate explicit
    // user action and a backend-authorized, consented, short-lived ticket.
    if (!sessionKey || approval.sessionKey !== sessionKey ||
        !approval.fieldId || !isSafeEndpoint(approval.endpoint) ||
        !approval.ticket || approval.ticket.length > 3500 ||
        !Number.isFinite(approval.expiresAt) ||
        approval.expiresAt <= Date.now() ||
        approval.expiresAt - Date.now() > 30_000 ||
        socket.current !== null) {
      setStatus("error");
      return false;
    }
    setStrokes(null);
    setStatus("connecting");
    const connection = new WebSocket(approval.endpoint);
    socket.current = connection;
    const expectedKey = approval.sessionKey;
    // Local transport disconnects no later than the ticket deadline.
    expiryTimer.current = setTimeout(() => {
      if (socket.current === connection) close();
    }, Math.max(1, approval.expiresAt - Date.now()));
    connection.onopen = () => {
      if (socket.current !== connection || activeKey.current !== expectedKey) return;
      setStatus("authorizing");
      // Token is sent in the first WebSocket DATA frame, never in URL,
      // subprotocol, logs or browser persistent storage.
      connection.send(JSON.stringify({
        type: "authorize_preview",
        preview_ticket: approval.ticket,
        field_id: approval.fieldId,
      }));
    };
    connection.onmessage = (event: MessageEvent) => {
      if (socket.current !== connection || activeKey.current !== expectedKey) return;
      if (typeof event.data !== "string" || event.data.length > MAX_FRAME_BYTES) {
        close(); setStatus("error"); return;
      }
      let message: unknown;
      try { message = JSON.parse(event.data); } catch { close(); setStatus("error"); return; }
      if (!message || typeof message !== "object" || !("type" in message)) {
        close(); setStatus("error"); return;
      }
      const frame = message as Record<string, unknown>;
      if (frame.session_key !== expectedKey || frame.field_id !== approval.fieldId) {
        close(); setStatus("error"); return;
      }
      if (frame.type === "authorized") {
        setStatus("capturing");
      } else if (frame.type === "preview_strokes") {
        const valid = validateWacomPreviewStrokes(frame.strokes);
        if (!valid) { close(); setStatus("error"); return; }
        setStatus("capturing");
        setStrokes(valid);
      } else if (frame.type === "complete") {
        // A preview complete event is NOT a legally executed signature.
        if (expiryTimer.current !== null) clearTimeout(expiryTimer.current);
        expiryTimer.current = null;
        socket.current = null;
        connection.close(1000, "preview complete");
        setStatus("complete");
      } else if (frame.type === "revoked" || frame.type === "expired") {
        close();
      } else {
        close(); setStatus("error");
      }
    };
    connection.onerror = () => {
      if (socket.current === connection) { close(false); setStatus("error"); }
    };
    connection.onclose = () => {
      if (socket.current === connection) { close(false); setStatus("error"); }
    };
    return true;
  }, [sessionKey, close]);

  return { status, strokes, start, cancel: close };
}
