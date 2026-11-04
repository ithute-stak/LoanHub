"use client";

import { useEffect, useRef } from "react";

// Presentation only: MUST receive points through a separately authenticated,
// contract-hash-bound channel. This component never fetches from localhost,
// accepts operator-entered device claims, stores a signature, or signs PDFs.
export type WacomPreviewPoint = Readonly<{
  x: number;
  y: number;
  at: number;
  pressure: number;
}>;
export type WacomPreviewStrokes = ReadonlyArray<ReadonlyArray<WacomPreviewPoint>>;

const WIDTH = 640;
const HEIGHT = 240;
const MAX_POINTS = 10000;
const MAX_STROKES = 300;
const MAX_DURATION_MS = 120000;

export function validateWacomPreviewStrokes(input: unknown): WacomPreviewStrokes | null {
  if (!Array.isArray(input) || input.length === 0 || input.length > MAX_STROKES) return null;
  let count = 0;
  let lastTime = -1;
  for (const stroke of input) {
    if (!Array.isArray(stroke) || stroke.length === 0) return null;
    for (const point of stroke) {
      count += 1;
      if (count > MAX_POINTS || !point || typeof point !== "object") return null;
      if (typeof point.x !== "number" || !Number.isFinite(point.x) || point.x < 0 || point.x > WIDTH ||
          typeof point.y !== "number" || !Number.isFinite(point.y) || point.y < 0 || point.y > HEIGHT ||
          typeof point.pressure !== "number" || !Number.isFinite(point.pressure) ||
          point.pressure < 0 || point.pressure > 1 ||
          typeof point.at !== "number" || !Number.isInteger(point.at) ||
          point.at < 0 || point.at > MAX_DURATION_MS || point.at < lastTime) return null;
      lastTime = point.at;
    }
  }
  return count >= 2 ? input as WacomPreviewStrokes : null;
}

export function WacomStrokePreview({
  strokes,
  sessionKey,
  active = false,
}: {
  strokes: unknown;
  /** Unique contract-hash-bound session key; do not reuse across contracts. */
  sessionKey: string;
  /** True only after backend+workstation auth (NOT provided by this component). */
  active?: boolean;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const ctx = canvas.current?.getContext("2d");
    if (!ctx) return;
    // Any session key change, invalid data, or authorization removal clears
    // the preview. No canvas data URL or browser storage is created.
    ctx.clearRect(0, 0, WIDTH, HEIGHT);
    if (!active || !sessionKey) return;
    const checked = validateWacomPreviewStrokes(strokes);
    if (!checked) return;
    ctx.strokeStyle = "#111827";
    ctx.lineWidth = 2.2;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    for (const stroke of checked) {
      ctx.beginPath();
      ctx.moveTo(stroke[0].x, stroke[0].y);
      if (stroke.length === 1) {
        ctx.lineTo(stroke[0].x + 0.1, stroke[0].y + 0.1);
      } else {
        for (const point of stroke.slice(1)) ctx.lineTo(point.x, point.y);
      }
      ctx.stroke();
    }
    return () => { ctx.clearRect(0, 0, WIDTH, HEIGHT); };
  }, [strokes, sessionKey, active]);

  return (
    <section aria-label="Wacom handwriting preview" className="space-y-2 rounded-2xl border p-3">
      <p className="text-sm font-semibold">Wacom STU-540 — temporary preview</p>
      <p className="text-xs text-muted-foreground">
        Test preview only. This does not verify borrower identity, record consent, or sign a contract.
      </p>
      <canvas
        ref={canvas}
        width={WIDTH}
        height={HEIGHT}
        aria-label="Temporary handwriting preview, not a signed contract"
        className="w-full rounded-lg border bg-white"
        style={{ aspectRatio: `${WIDTH} / ${HEIGHT}` }}
      />
    </section>
  );
}
