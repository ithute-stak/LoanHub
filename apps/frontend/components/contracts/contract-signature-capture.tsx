"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";

type Point = { x: number; y: number; at: number; pressure: number };
type Stroke = Point[];

type Props = {
  contractId: string;
  disabled?: boolean;
  onCapture?: (capture: { contractId: string; strokes: Stroke[]; imageDataUrl: string; inputMethod: "pointer" }) => void;
};

const WIDTH = 640;
const HEIGHT = 240;
const MAX_POINTS = 10000;

/**
 * Browser stroke capture only. Wacom STU devices normally need a vendor SDK
 * and a trusted localhost bridge; browser pointer events alone do not provide
 * direct STU USB access or proof of signer identity.
 *
 * This component does NOT submit a borrower signature or unlock a contract.
 * Wire onCapture only to an authenticated, document-hash-bound backend session
 * after the signing evidence endpoint and device integration are completed.
 */
export function ContractSignatureCapture({ contractId, disabled = false, onCapture }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const drawing = useRef(false);
  const strokes = useRef<Stroke[]>([]);
  const active = useRef<Stroke | null>(null);
  const [pointCount, setPointCount] = useState(0);
  const [preview, setPreview] = useState<string | null>(null);

  const paint = useCallback(() => {
    const ctx = canvas.current?.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, WIDTH, HEIGHT);
    ctx.lineWidth = 2.2;
    ctx.strokeStyle = "#111827";
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    for (const stroke of [...strokes.current, ...(active.current ? [active.current] : [])]) {
      if (!stroke.length) continue;
      ctx.beginPath();
      ctx.moveTo(stroke[0].x, stroke[0].y);
      if (stroke.length === 1) {
        ctx.lineTo(stroke[0].x + 0.1, stroke[0].y + 0.1);
      } else {
        for (const point of stroke.slice(1)) ctx.lineTo(point.x, point.y);
      }
      ctx.stroke();
    }
  }, []);

  useEffect(() => {
    strokes.current = [];
    active.current = null;
    drawing.current = false;
    setPointCount(0);
    setPreview(null);
    paint();
  }, [contractId, paint]);

  const point = (event: React.PointerEvent<HTMLCanvasElement>): Point => {
    const rect = event.currentTarget.getBoundingClientRect();
    return {
      x: Math.min(WIDTH, Math.max(0, (event.clientX - rect.left) * WIDTH / rect.width)),
      y: Math.min(HEIGHT, Math.max(0, (event.clientY - rect.top) * HEIGHT / rect.height)),
      at: Date.now(),
      pressure: event.pressure || 0.5,
    };
  };

  const start = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (disabled || preview || event.button !== 0) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    active.current = [point(event)];
    drawing.current = true;
    paint();
  };

  const move = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawing.current || !active.current || disabled) return;
    event.preventDefault();
    const total = strokes.current.reduce((count, stroke) => count + stroke.length, 0);
    if (total + active.current.length >= MAX_POINTS) return;
    active.current.push(point(event));
    setPointCount(total + active.current.length);
    paint();
  };

  const end = () => {
    if (!drawing.current) return;
    drawing.current = false;
    if (active.current?.length) strokes.current.push(active.current);
    active.current = null;
    setPointCount(strokes.current.reduce((n, stroke) => n + stroke.length, 0));
    paint();
  };

  const clear = () => {
    strokes.current = [];
    active.current = null;
    drawing.current = false;
    setPreview(null);
    setPointCount(0);
    paint();
  };

  const capture = () => {
    if (disabled || !strokes.current.length || !canvas.current) return;
    const imageDataUrl = canvas.current.toDataURL("image/png");
    setPreview(imageDataUrl);
    onCapture?.({
      contractId,
      strokes: strokes.current.map((stroke) => stroke.map((p) => ({ ...p }))),
      imageDataUrl,
      inputMethod: "pointer",
    });
  };

  return (
    <section className="space-y-3 rounded-2xl border bg-background p-4" aria-label="Browser signature capture">
      <div>
        <h3 className="font-bold">Signature pad capture — preview</h3>
        <p className="text-sm text-muted-foreground">
          Test handwriting with a mouse or touchscreen. Direct Wacom STU USB capture requires
          the vendor SDK connector. This preview is not legally submitted and does not sign the contract.
        </p>
      </div>
      <canvas
        ref={canvas}
        width={WIDTH}
        height={HEIGHT}
        aria-label="Handwritten signature area"
        className="w-full rounded-lg border bg-white"
        style={{ touchAction: "none", aspectRatio: `${WIDTH} / ${HEIGHT}` }}
        onPointerDown={start}
        onPointerMove={move}
        onPointerUp={end}
        onPointerCancel={end}
        onLostPointerCapture={end}
      />
      <p className="text-xs text-muted-foreground">{pointCount} captured points. Do not use for formal authorization yet.</p>
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" onClick={clear} disabled={disabled}>Clear</Button>
        <Button type="button" onClick={capture} disabled={disabled || pointCount === 0}>Preview capture</Button>
      </div>
      {preview ? <p role="status" className="text-sm font-medium">Captured locally for preview only. No signature has been submitted to LoanHub.</p> : null}
    </section>
  );
}
