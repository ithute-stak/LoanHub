"use client";

import { useEffect, useRef, useState } from "react";

const REFRESH_THRESHOLD_PX = 72;
const MAX_INDICATOR_PULL_PX = 44;
const IGNORE_PULL_SELECTOR = [
    "input",
    "textarea",
    "select",
    "button",
    "a",
    "[contenteditable='true']",
    "[role='textbox']",
    "[role='dialog']",
    "[data-disable-pull-refresh]",
].join(",");

type ScrollContainer = Element | null;

function isMobileTouchDevice(): boolean {
    if (typeof window === "undefined") return false;
    const coarseMobile = window.matchMedia("(max-width: 1023.98px) and (pointer: coarse)").matches;
    return coarseMobile || (window.innerWidth <= 1024 && navigator.maxTouchPoints > 0);
}

function findScrollableContainer(target: EventTarget | null): ScrollContainer {
    let node = target instanceof Element ? target : null;

    while (node && node !== document.body && node !== document.documentElement) {
        const style = window.getComputedStyle(node);
        const overflowY = style.overflowY;
        const canScroll = /(auto|scroll|overlay)/.test(overflowY)
            && node.scrollHeight > node.clientHeight + 1;
        if (canScroll) return node;
        node = node.parentElement;
    }

    return document.scrollingElement;
}

function scrollTopOf(container: ScrollContainer): number {
    if (!container || container === document.documentElement || container === document.body) {
        return window.scrollY
            || document.documentElement.scrollTop
            || document.body.scrollTop
            || 0;
    }
    return container.scrollTop;
}

function shouldIgnoreTarget(target: EventTarget | null): boolean {
    return target instanceof Element && Boolean(target.closest(IGNORE_PULL_SELECTOR));
}

export default function MobilePullToRefresh() {
    const [indicatorPull, setIndicatorPull] = useState(0);
    const [readyToRefresh, setReadyToRefresh] = useState(false);
    const [refreshing, setRefreshing] = useState(false);

    const startX = useRef(0);
    const startY = useRef(0);
    const eligible = useRef(false);
    const scrollContainer = useRef<ScrollContainer>(null);
    const readyRef = useRef(false);
    const refreshingRef = useRef(false);

    useEffect(() => {
        refreshingRef.current = refreshing;
    }, [refreshing]);

    useEffect(() => {
        const resetGesture = () => {
            eligible.current = false;
            scrollContainer.current = null;
            readyRef.current = false;
            setReadyToRefresh(false);
            if (!refreshingRef.current) setIndicatorPull(0);
        };

        const onTouchStart = (event: TouchEvent) => {
            if (refreshingRef.current || !isMobileTouchDevice() || event.touches.length !== 1) {
                resetGesture();
                return;
            }
            if (shouldIgnoreTarget(event.target)) {
                resetGesture();
                return;
            }

            const container = findScrollableContainer(event.target);
            if (scrollTopOf(container) > 1) {
                resetGesture();
                return;
            }

            const touch = event.touches[0];
            startX.current = touch.clientX;
            startY.current = touch.clientY;
            scrollContainer.current = container;
            eligible.current = true;
            readyRef.current = false;
            setReadyToRefresh(false);
        };

        const onTouchMove = (event: TouchEvent) => {
            if (!eligible.current || refreshingRef.current || event.touches.length !== 1) return;

            const touch = event.touches[0];
            const deltaX = touch.clientX - startX.current;
            const deltaY = touch.clientY - startY.current;

            if (deltaY <= 0 || Math.abs(deltaX) > Math.abs(deltaY)) {
                resetGesture();
                return;
            }
            if (scrollTopOf(scrollContainer.current) > 1) {
                resetGesture();
                return;
            }
            if (deltaY < 6) return;

            // Once a downward pull is clearly intentional, keep the browser from
            // invoking its own pull-to-refresh so LoanHub has one predictable refresh path.
            event.preventDefault();

            const visualPull = Math.min(MAX_INDICATOR_PULL_PX, deltaY * 0.5);
            const armed = deltaY >= REFRESH_THRESHOLD_PX;
            readyRef.current = armed;
            setIndicatorPull(visualPull);
            setReadyToRefresh(armed);
        };

        const onTouchEnd = () => {
            if (!eligible.current || refreshingRef.current) {
                resetGesture();
                return;
            }

            const shouldRefresh = readyRef.current;
            eligible.current = false;
            scrollContainer.current = null;
            readyRef.current = false;
            setReadyToRefresh(false);

            if (!shouldRefresh) {
                setIndicatorPull(0);
                return;
            }

            refreshingRef.current = true;
            setRefreshing(true);
            setIndicatorPull(MAX_INDICATOR_PULL_PX);
            window.dispatchEvent(new CustomEvent("loanhub:pull-refresh", {
                detail: { path: window.location.pathname },
            }));

            // A full reload refreshes server components and every client-side data
            // provider, including screens whose data is loaded outside router.refresh().
            window.setTimeout(() => window.location.reload(), 120);
        };

        const onTouchCancel = () => resetGesture();

        document.addEventListener("touchstart", onTouchStart, { passive: true });
        document.addEventListener("touchmove", onTouchMove, { passive: false });
        document.addEventListener("touchend", onTouchEnd, { passive: true });
        document.addEventListener("touchcancel", onTouchCancel, { passive: true });

        return () => {
            document.removeEventListener("touchstart", onTouchStart);
            document.removeEventListener("touchmove", onTouchMove);
            document.removeEventListener("touchend", onTouchEnd);
            document.removeEventListener("touchcancel", onTouchCancel);
        };
    }, []);

    const visible = refreshing || indicatorPull > 0;
    const label = refreshing
        ? "Refreshing data…"
        : readyToRefresh
            ? "Release to refresh"
            : "Pull to refresh";

    return (
        <div
            aria-live="polite"
            aria-atomic="true"
            data-loanhub-pull-refresh
            className={`pointer-events-none fixed left-1/2 z-[100] -translate-x-1/2 rounded-full border bg-background/95 px-3 py-1.5 text-xs font-bold text-foreground shadow-lg backdrop-blur transition-[opacity,transform] duration-150 ${visible ? "opacity-100" : "opacity-0"}`}
            style={{
                top: "calc(env(safe-area-inset-top, 0px) + 0.5rem)",
                transform: `translate(-50%, ${Math.max(0, indicatorPull - 12)}px)`,
            }}
        >
            {label}
        </div>
    );
}
