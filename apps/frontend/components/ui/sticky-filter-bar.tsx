"use client";

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type AriaRole,
  type CSSProperties,
  type ReactNode,
} from "react";

import { useWorkspaceFullscreen } from "@/components/accessibility/workspace-mode";
import { cn } from "@/lib/utils";

type FloatingGeometry = {
  height: number;
  left: number;
  width: number;
};

type StickyFilterBarProps = {
  children: ReactNode;
  className?: string;
  /** Offset used below the normal LoanHub shell header. */
  topOffset?: number;
  /** Offset used while the workspace is in full-screen mode. */
  fullscreenTopOffset?: number;
  /** Minimum space kept between the floating toolbar and viewport edges. */
  viewportInset?: number;
  ariaLabel?: string;
  landmarkRole?: AriaRole;
};

/**
 * Keeps search, filters and other result controls available while their data
 * scrolls. CSS sticky positioning is the no-JavaScript fallback. Once the
 * toolbar is about to leave the viewport, it changes to a measured fixed
 * surface so ancestor overflow and short header containers cannot clip it.
 */
export function StickyFilterBar({
  children,
  className,
  topOffset = 64,
  fullscreenTopOffset = 64,
  viewportInset = 8,
  ariaLabel = "Search and filters",
  landmarkRole = "search",
}: StickyFilterBarProps) {
  const fullscreenWorkspace = useWorkspaceFullscreen();
  const sentinelRef = useRef<HTMLDivElement>(null);
  const anchorRef = useRef<HTMLDivElement>(null);
  const barRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef<number | null>(null);
  const [floating, setFloating] = useState(false);
  const [geometry, setGeometry] = useState<FloatingGeometry>({
    height: 0,
    left: viewportInset,
    width: 0,
  });
  const activeTopOffset = fullscreenWorkspace
    ? fullscreenTopOffset
    : topOffset;

  const measure = useCallback(() => {
    if (typeof window === "undefined") return;

    const anchor = anchorRef.current;
    const bar = barRef.current;
    if (!anchor || !bar) return;

    const anchorRect = anchor.getBoundingClientRect();
    const barRect = bar.getBoundingClientRect();
    const left = Math.max(viewportInset, anchorRect.left);
    const availableWidth = Math.max(
      0,
      window.innerWidth - left - viewportInset,
    );
    const width = Math.min(anchorRect.width || barRect.width, availableWidth);
    const next = {
      height: Math.ceil(barRect.height),
      left: Math.round(left),
      width: Math.round(width),
    };

    setGeometry((current) =>
      current.height === next.height &&
      current.left === next.left &&
      current.width === next.width
        ? current
        : next,
    );
  }, [viewportInset]);

  const scheduleMeasure = useCallback(() => {
    if (typeof window === "undefined") return;
    if (frameRef.current !== null) window.cancelAnimationFrame(frameRef.current);
    frameRef.current = window.requestAnimationFrame(() => {
      frameRef.current = null;
      measure();
    });
  }, [measure]);

  useLayoutEffect(() => {
    measure();
  }, [floating, measure]);

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel || typeof IntersectionObserver === "undefined") {
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) =>
        setFloating(
          !entry.isIntersecting &&
            entry.boundingClientRect.top <= activeTopOffset,
        ),
      {
        root: null,
        threshold: 0,
        rootMargin: `-${activeTopOffset + 1}px 0px 0px 0px`,
      },
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [activeTopOffset]);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const anchor = anchorRef.current;
    const bar = barRef.current;
    const resizeObserver =
      typeof ResizeObserver === "undefined"
        ? null
        : new ResizeObserver(scheduleMeasure);

    if (anchor) resizeObserver?.observe(anchor);
    if (bar) resizeObserver?.observe(bar);
    window.addEventListener("resize", scheduleMeasure);
    window.addEventListener("scroll", scheduleMeasure, true);

    return () => {
      resizeObserver?.disconnect();
      window.removeEventListener("resize", scheduleMeasure);
      window.removeEventListener("scroll", scheduleMeasure, true);
      if (frameRef.current !== null) {
        window.cancelAnimationFrame(frameRef.current);
        frameRef.current = null;
      }
    };
  }, [scheduleMeasure]);

  const style = {
    "--loanhub-sticky-filter-top": `${activeTopOffset}px`,
    ...(floating
      ? {
          left: `${geometry.left}px`,
          width: geometry.width ? `${geometry.width}px` : undefined,
        }
      : {}),
  } as CSSProperties;

  return (
    <>
      <div
        ref={sentinelRef}
        aria-hidden="true"
        className="pointer-events-none h-px w-full"
      />
      <div
        ref={anchorRef}
        aria-hidden="true"
        className="pointer-events-none h-0 w-full"
      />
      {floating && geometry.height > 0 ? (
        <div
          aria-hidden="true"
          className="pointer-events-none w-full"
          style={{ height: geometry.height }}
        />
      ) : null}
      <div
        ref={barRef}
        role={landmarkRole}
        aria-label={ariaLabel}
        data-loanhub-sticky-toolbar="true"
        data-floating={floating ? "true" : "false"}
        style={style}
        className={cn(
          floating ? "fixed" : "sticky",
          "top-[calc(var(--loanhub-sticky-filter-top)_+_env(safe-area-inset-top))] z-40",
          "transition-[border-radius,box-shadow,background-color,border-color] duration-200",
          "data-[floating=true]:border-border/80 data-[floating=true]:bg-background/95",
          "data-[floating=true]:shadow-[0_18px_45px_-24px_hsl(var(--foreground)/0.45)]",
          "data-[floating=true]:backdrop-blur-xl",
          className,
        )}
      >
        {children}
      </div>
    </>
  );
}
