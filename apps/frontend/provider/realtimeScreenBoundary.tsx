"use client";

import { Fragment, type ReactNode, useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";

import {
    DB_COMMIT_EVENT_NAME,
    type DbCommitBatchDetail,
} from "@/lib/realtime-commit";
import { shouldRefreshRouteForCommit } from "@/lib/realtime-resources";

function userIsEditing(): boolean {
    const active = document.activeElement;
    if (!(active instanceof HTMLElement)) return false;

    if (active.isContentEditable) return true;
    return ["INPUT", "TEXTAREA", "SELECT"].includes(active.tagName);
}

/**
 * Guarantees that standalone client pages which own their own local fetch/state
 * also catch up after any committed database change.
 *
 * Shared AppData resources refresh in-place. This boundary is the universal
 * fallback for screens that have not yet moved their loaders into shared state.
 * To avoid destroying an in-progress edit, a remount is deferred while
 * an editable control has focus and applied as soon as the user leaves it.
 */
export function RealtimeScreenBoundary({ children }: { children: ReactNode }) {
    const pathname = usePathname();
    const [revision, setRevision] = useState(0);
    const pendingRef = useRef(false);

    useEffect(() => {
        function applyPending() {
            if (!pendingRef.current || userIsEditing()) return;
            pendingRef.current = false;
            setRevision((current) => current + 1);
        }

        function onCommit(event: Event) {
            const detail = (event as CustomEvent<DbCommitBatchDetail>).detail;
            if (!detail?.count || !shouldRefreshRouteForCommit(pathname, detail)) return;

            if (userIsEditing()) {
                pendingRef.current = true;
                return;
            }

            setRevision((current) => current + 1);
        }

        window.addEventListener(DB_COMMIT_EVENT_NAME, onCommit);
        const onFocusOut = () => window.setTimeout(applyPending, 0);
        document.addEventListener("focusout", onFocusOut);

        return () => {
            window.removeEventListener(DB_COMMIT_EVENT_NAME, onCommit);
            document.removeEventListener("focusout", onFocusOut);
        };
    }, [pathname]);

    return <Fragment key={revision}>{children}</Fragment>;
}
