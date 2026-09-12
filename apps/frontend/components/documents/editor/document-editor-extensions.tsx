"use client";

import { Extension, Mark, Node, mergeAttributes } from "@tiptap/core";
import { createContext, useContext } from "react";
import {
    NodeViewWrapper,
    ReactNodeViewRenderer,
    type NodeViewProps,
} from "@tiptap/react";
import {
    CalendarDays,
    CheckSquare2,
    GripVertical,
    PenLine,
    TextCursorInput,
    Trash2,
    UserRound,
} from "lucide-react";

import { createUuid } from "@/lib/uuid";
import type { SignatureFieldType } from "@/types/workspaceDocuments";

export const SIGNATURE_FIELD_MIME = "application/x-loanhub-signature-field";


export type SignaturePreviewEntry = {
    signerName: string;
    signedAt: string;
    method: "stored_signature" | "electronic";
    verificationCode: string;
    imageUrl?: string;
};

export type SignaturePreviewContextValue = {
    signatures: Record<string, SignaturePreviewEntry>;
    canSign: boolean;
    canRevoke: boolean;
    onSign?: (fieldId: string, fieldType: SignatureFieldType, label: string) => void;
    onRevoke?: (fieldId: string) => void;
};

export const SignaturePreviewContext = createContext<SignaturePreviewContextValue>({
    signatures: {},
    canSign: false,
    canRevoke: false,
});

export const PageBreak = Node.create({
    name: "pageBreak",
    group: "block",
    atom: true,
    selectable: true,
    parseHTML() {
        return [{ tag: "div[data-page-break]" }];
    },
    renderHTML({ HTMLAttributes }) {
        return [
            "div",
            mergeAttributes(HTMLAttributes, {
                "data-page-break": "true",
                class: "document-page-break",
            }),
        ];
    },
});

export const DocumentBlockFormatting = Extension.create({
    name: "documentBlockFormatting",
    addGlobalAttributes() {
        return [
            {
                types: ["paragraph", "heading"],
                attributes: {
                    paragraphStyle: {
                        default: null,
                        parseHTML: (element) => element.getAttribute("data-paragraph-style"),
                        renderHTML: (attributes) =>
                            attributes.paragraphStyle
                                ? { "data-paragraph-style": attributes.paragraphStyle }
                                : {},
                    },
                    lineHeight: {
                        default: null,
                        parseHTML: (element) => element.style.lineHeight || null,
                        renderHTML: (attributes) =>
                            attributes.lineHeight
                                ? { style: `line-height:${attributes.lineHeight}` }
                                : {},
                    },
                    marginTop: {
                        default: null,
                        parseHTML: (element) => element.style.marginTop || null,
                        renderHTML: (attributes) =>
                            attributes.marginTop
                                ? { style: `margin-top:${attributes.marginTop}` }
                                : {},
                    },
                    marginBottom: {
                        default: null,
                        parseHTML: (element) => element.style.marginBottom || null,
                        renderHTML: (attributes) =>
                            attributes.marginBottom
                                ? { style: `margin-bottom:${attributes.marginBottom}` }
                                : {},
                    },
                    textIndent: {
                        default: null,
                        parseHTML: (element) => element.style.textIndent || null,
                        renderHTML: (attributes) =>
                            attributes.textIndent
                                ? { style: `text-indent:${attributes.textIndent}` }
                                : {},
                    },
                    letterSpacing: {
                        default: null,
                        parseHTML: (element) => element.style.letterSpacing || null,
                        renderHTML: (attributes) =>
                            attributes.letterSpacing
                                ? { style: `letter-spacing:${attributes.letterSpacing}` }
                                : {},
                    },
                },
            },
        ];
    },
});

export const SubscriptMark = Mark.create({
    name: "subscript",
    excludes: "superscript",
    parseHTML() {
        return [{ tag: "sub" }];
    },
    renderHTML({ HTMLAttributes }) {
        return ["sub", mergeAttributes(HTMLAttributes), 0];
    },
});

export const SuperscriptMark = Mark.create({
    name: "superscript",
    excludes: "subscript",
    parseHTML() {
        return [{ tag: "sup" }];
    },
    renderHTML({ HTMLAttributes }) {
        return ["sup", mergeAttributes(HTMLAttributes), 0];
    },
});

const FIELD_DEFAULTS: Record<
    SignatureFieldType,
    { label: string; placeholder: string; height: number }
> = {
    signature: { label: "Signature", placeholder: "Sign here", height: 62 },
    initials: { label: "Initials", placeholder: "Initial here", height: 46 },
    date: { label: "Date signed", placeholder: "DD / MM / YYYY", height: 44 },
    name: { label: "Full name", placeholder: "Type or write full name", height: 44 },
    title: { label: "Title / capacity", placeholder: "Position or capacity", height: 44 },
    text: { label: "Text field", placeholder: "Enter text", height: 48 },
    checkbox: { label: "Checkbox", placeholder: "Select to confirm", height: 42 },
};

export function createSignatureFieldAttrs(
    fieldType: SignatureFieldType,
    overrides: Record<string, unknown> = {},
) {
    const defaults = FIELD_DEFAULTS[fieldType];
    return {
        fieldId: createUuid(),
        fieldType,
        label: defaults.label,
        assignedTo: "Borrower",
        required: true,
        width: 100,
        height: defaults.height,
        placeholder: defaults.placeholder,
        ...overrides,
    };
}

function signatureIcon(type: SignatureFieldType) {
    if (type === "date") return CalendarDays;
    if (type === "checkbox") return CheckSquare2;
    if (type === "name" || type === "title") return UserRound;
    if (type === "text") return TextCursorInput;
    return PenLine;
}

function SignatureFieldNodeView({
    node,
    selected,
    updateAttributes,
    deleteNode,
}: NodeViewProps) {
    const attrs = node.attrs as {
        fieldId: string;
        fieldType: SignatureFieldType;
        label: string;
        assignedTo: string;
        required: boolean;
        width: number;
        height: number;
        placeholder: string;
    };
    const Icon = signatureIcon(attrs.fieldType);
    const signatureContext = useContext(SignaturePreviewContext);
    const signed = signatureContext.signatures[attrs.fieldId];

    return (
        <NodeViewWrapper
            className={`document-signature-node ${selected ? "is-selected" : ""}`}
            style={{ width: `${attrs.width}%`, minHeight: `${attrs.height}px` }}
            data-signature-node-view="true"
        >
            <div className="document-signature-drag" data-drag-handle contentEditable={false}>
                <GripVertical className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1" contentEditable={false}>
                <div className="flex flex-wrap items-center gap-2">
                    <Icon className="h-4 w-4 text-primary" />
                    <span className="font-black">{attrs.label}</span>
                    <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-black uppercase text-primary">
                        {attrs.assignedTo}
                    </span>
                    {attrs.required && (
                        <span className="text-[10px] font-black uppercase text-red-600">Required</span>
                    )}
                </div>
                {signed ? (
                    <div className="document-signature-applied">
                        {signed.imageUrl ? (
                            <img src={signed.imageUrl} alt={`Signature of ${signed.signerName}`} />
                        ) : (
                            <div className="document-electronic-signature">{signed.signerName}</div>
                        )}
                        <div>
                            <strong>Signed by {signed.signerName}</strong>
                            <span>{new Date(signed.signedAt).toLocaleString()} · {signed.verificationCode}</span>
                        </div>
                    </div>
                ) : attrs.fieldType === "checkbox" ? (
                    <div className="mt-3 flex items-center gap-2 text-sm text-slate-500">
                        <span className="flex h-5 w-5 items-center justify-center rounded border-2 border-slate-400" />
                        {attrs.placeholder}
                    </div>
                ) : (
                    <div className="mt-4 border-b border-dashed border-slate-500 pb-1 text-xs text-slate-400">
                        {attrs.placeholder}
                    </div>
                )}
                {!signed && signatureContext.canSign && ["signature", "initials"].includes(attrs.fieldType) && (
                    <button
                        type="button"
                        className="document-sign-field-action"
                        contentEditable={false}
                        onClick={() => signatureContext.onSign?.(attrs.fieldId, attrs.fieldType, attrs.label)}
                    >
                        Apply signature
                    </button>
                )}
                {signed && signatureContext.canRevoke && (
                    <button
                        type="button"
                        className="document-revoke-signature-action"
                        contentEditable={false}
                        onClick={() => signatureContext.onRevoke?.(attrs.fieldId)}
                    >
                        Revoke signature
                    </button>
                )}
            </div>

            {selected && (
                <div className="document-signature-properties" contentEditable={false}>
                    <label>
                        <span>Label</span>
                        <input
                            value={attrs.label}
                            onChange={(event) => updateAttributes({ label: event.target.value })}
                        />
                    </label>
                    <label>
                        <span>Assigned to</span>
                        <select
                            value={attrs.assignedTo}
                            onChange={(event) => updateAttributes({ assignedTo: event.target.value })}
                        >
                            <option>Borrower</option>
                            <option>Lender</option>
                            <option>Witness</option>
                            <option>Approver</option>
                            <option>Recipient</option>
                            <option>Any signer</option>
                        </select>
                    </label>
                    <label>
                        <span>Width</span>
                        <select
                            value={attrs.width}
                            onChange={(event) => updateAttributes({ width: Number(event.target.value) })}
                        >
                            <option value={35}>Small</option>
                            <option value={50}>Half</option>
                            <option value={70}>Wide</option>
                            <option value={100}>Full</option>
                        </select>
                    </label>
                    <label className="document-signature-required">
                        <input
                            type="checkbox"
                            checked={attrs.required}
                            onChange={(event) => updateAttributes({ required: event.target.checked })}
                        />
                        Required
                    </label>
                    <button type="button" onClick={deleteNode} title="Delete field">
                        <Trash2 className="h-4 w-4" />
                    </button>
                </div>
            )}
        </NodeViewWrapper>
    );
}

export const SignatureField = Node.create({
    name: "signatureField",
    group: "block",
    atom: true,
    selectable: true,
    draggable: true,
    defining: true,

    addAttributes() {
        return {
            fieldId: { default: null },
            fieldType: { default: "signature" },
            label: { default: "Signature" },
            assignedTo: { default: "Borrower" },
            required: { default: true },
            width: { default: 100 },
            height: { default: 62 },
            placeholder: { default: "Sign here" },
        };
    },

    parseHTML() {
        return [
            {
                tag: "div[data-signature-field]",
                getAttrs: (element) => {
                    const htmlElement = element as HTMLElement;
                    return {
                        fieldId: htmlElement.dataset.fieldId,
                        fieldType: htmlElement.dataset.fieldType || "signature",
                        label: htmlElement.dataset.label || "Signature",
                        assignedTo: htmlElement.dataset.assignedTo || "Borrower",
                        required: htmlElement.dataset.required === "true",
                        width: Number(htmlElement.dataset.width || 100),
                        height: Number(htmlElement.dataset.height || 62),
                        placeholder: htmlElement.dataset.placeholder || "Sign here",
                    };
                },
            },
        ];
    },

    renderHTML({ HTMLAttributes }) {
        const fieldType = String(HTMLAttributes.fieldType || "signature") as SignatureFieldType;
        const label = String(HTMLAttributes.label || FIELD_DEFAULTS[fieldType]?.label || "Signature");
        const assignedTo = String(HTMLAttributes.assignedTo || "Borrower");
        const required = Boolean(HTMLAttributes.required);
        const width = Number(HTMLAttributes.width || 100);
        const height = Number(HTMLAttributes.height || 62);
        const placeholder = String(HTMLAttributes.placeholder || "Sign here");
        return [
            "div",
            mergeAttributes({
                "data-signature-field": "true",
                "data-field-id": HTMLAttributes.fieldId,
                "data-field-type": fieldType,
                "data-label": label,
                "data-assigned-to": assignedTo,
                "data-required": required ? "true" : "false",
                "data-width": String(width),
                "data-height": String(height),
                "data-placeholder": placeholder,
                class: "document-signature-export",
                style: `width:${width}%;min-height:${height}px`,
            }),
            [
                "div",
                { class: "document-signature-export-label" },
                `${label} · ${assignedTo}${required ? " · REQUIRED" : ""}`,
            ],
            [
                "div",
                { class: "document-signature-export-line" },
                fieldType === "checkbox" ? `☐ ${placeholder}` : placeholder,
            ],
        ];
    },

    addNodeView() {
        return ReactNodeViewRenderer(SignatureFieldNodeView);
    },
});
