"use client";

import { Grip, MapPin } from "lucide-react";
import { useRef, useState } from "react";

import type { DocumentAddressBlock } from "@/types/workspaceDocuments";

type DragState = {
    id: string;
    offsetXmm: number;
    offsetYmm: number;
} | null;

export function DocumentAddressOverlay({
    blocks,
    pageWidthMm,
    pageHeightMm,
    editable,
    onChange,
    onCommit,
}: {
    blocks: DocumentAddressBlock[];
    pageWidthMm: number;
    pageHeightMm: number;
    editable: boolean;
    onChange: (blocks: DocumentAddressBlock[]) => void;
    onCommit?: (blocks: DocumentAddressBlock[]) => void;
}) {
    const rootRef = useRef<HTMLDivElement | null>(null);
    const [drag, setDrag] = useState<DragState>(null);

    function pointToMm(clientX: number, clientY: number) {
        const rect = rootRef.current?.getBoundingClientRect();
        if (!rect || !rect.width || !rect.height) return null;
        return {
            x: ((clientX - rect.left) / rect.width) * pageWidthMm,
            y: ((clientY - rect.top) / rect.height) * pageHeightMm,
        };
    }

    function beginDrag(event: React.PointerEvent, block: DocumentAddressBlock) {
        if (!editable) return;
        const point = pointToMm(event.clientX, event.clientY);
        if (!point) return;
        event.preventDefault();
        event.stopPropagation();
        setDrag({
            id: block.id,
            offsetXmm: point.x - block.x_mm,
            offsetYmm: point.y - block.y_mm,
        });
        event.currentTarget.setPointerCapture?.(event.pointerId);
    }

    function moveDrag(event: React.PointerEvent) {
        if (!drag || !editable) return;
        const point = pointToMm(event.clientX, event.clientY);
        if (!point) return;
        const next = blocks.map((block) => {
            if (block.id !== drag.id) return block;
            const maxX = Math.max(0, pageWidthMm - Math.min(block.width_mm, pageWidthMm));
            const x = Math.max(0, Math.min(maxX, point.x - drag.offsetXmm));
            const y = Math.max(0, Math.min(pageHeightMm - 12, point.y - drag.offsetYmm));
            return {
                ...block,
                x_mm: Number(x.toFixed(1)),
                y_mm: Number(y.toFixed(1)),
            };
        });
        onChange(next);
    }

    function endDrag() {
        if (drag) onCommit?.(blocks);
        setDrag(null);
    }

    return (
        <div
            ref={rootRef}
            className="document-address-overlay"
            onPointerMove={moveDrag}
            onPointerUp={endDrag}
            onPointerCancel={endDrag}
            aria-label="Document address positioning layer"
        >
            {blocks.map((block) => (
                <div
                    key={block.id}
                    className={`document-address-block ${editable ? "is-editable" : ""} ${drag?.id === block.id ? "is-dragging" : ""}`}
                    style={{
                        left: `${block.x_mm}mm`,
                        top: `${block.y_mm}mm`,
                        width: `${block.width_mm}mm`,
                        fontSize: `${block.font_size_pt}pt`,
                        textAlign: block.alignment,
                    }}
                    onPointerDown={(event) => beginDrag(event, block)}
                    title={editable ? "Drag to position this address on the page" : block.label}
                >
                    {editable && (
                        <span className="document-address-grip" aria-hidden="true">
                            <Grip />
                        </span>
                    )}
                    {block.show_label && (
                        <strong className="document-address-label">
                            <MapPin /> {block.label}
                        </strong>
                    )}
                    <div className="document-address-text">
                        {block.content.split("\n").map((line, index) => (
                            <span key={`${block.id}-${index}`}>{line || "\u00a0"}</span>
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
}
