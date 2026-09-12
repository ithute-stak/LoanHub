"use client";

import type { Editor } from "@tiptap/react";
import {
    AlignCenter,
    AlignJustify,
    AlignLeft,
    AlignRight,
    Bold,
    BookOpen,
    CaseSensitive,
    CheckSquare2,
    ChevronDown,
    Columns3,
    FileText,
    Highlighter,
    ImagePlus,
    IndentDecrease,
    IndentIncrease,
    Italic,
    Link2,
    List,
    MapPin,
    ListOrdered,
    Minus,
    Pilcrow,
    Quote,
    Redo2,
    RemoveFormatting,
    Rows3,
    ScissorsLineDashed,
    Signature,
    Stamp,
    Subscript,
    Superscript,
    Table2,
    Trash2,
    Underline as UnderlineIcon,
    Undo2,
} from "lucide-react";
import { useRef, useState } from "react";

import {
    SIGNATURE_FIELD_MIME,
    createSignatureFieldAttrs,
} from "@/components/documents/editor/document-editor-extensions";
import { NativeSelect } from "@/components/ui/native-select";
import type {
    DocumentOrientation,
    DocumentPageSize,
    DocumentStyleKey,
    SignatureFieldType,
    WorkspaceDocument,
} from "@/types/workspaceDocuments";
import { toast } from "@/utils/toast";

export type DocumentSettingsChange = Partial<{
    page_size: DocumentPageSize;
    orientation: DocumentOrientation;
    margin_top_mm: number;
    margin_right_mm: number;
    margin_bottom_mm: number;
    margin_left_mm: number;
    style_key: DocumentStyleKey;
    default_font_family: string;
    default_font_size_pt: number;
    default_line_height_percent: number;
}>;

type RibbonTab = "home" | "insert" | "layout" | "design";

const FONTS = [
    "Arial",
    "Aptos",
    "Calibri",
    "Cambria",
    "Georgia",
    "Helvetica",
    "Times New Roman",
    "Trebuchet MS",
    "Verdana",
    "Courier New",
];

const FONT_SIZES = [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48, 60, 72];

const WORD_STYLES = [
    { key: "normal", label: "Normal", preview: "AaBbCc", kind: "paragraph" },
    { key: "no_spacing", label: "No Spacing", preview: "AaBbCc", kind: "paragraph" },
    { key: "title", label: "Title", preview: "Title", kind: "h1" },
    { key: "subtitle", label: "Subtitle", preview: "Subtitle", kind: "paragraph" },
    { key: "heading_1", label: "Heading 1", preview: "Heading 1", kind: "h1" },
    { key: "heading_2", label: "Heading 2", preview: "Heading 2", kind: "h2" },
    { key: "heading_3", label: "Heading 3", preview: "Heading 3", kind: "h3" },
    { key: "quote", label: "Quote", preview: "Quote", kind: "quote" },
    { key: "intense_quote", label: "Intense Quote", preview: "Intense", kind: "quote" },
] as const;

const THEMES: Array<{
    key: DocumentStyleKey;
    label: string;
    description: string;
    accent: string;
    heading: string;
}> = [
    { key: "modern_blue", label: "Modern Blue", description: "LoanHub professional", accent: "#1268B3", heading: "#0F2742" },
    { key: "classic_word", label: "Classic Word", description: "Familiar business style", accent: "#2F5597", heading: "#1F3864" },
    { key: "executive_navy", label: "Executive Navy", description: "Boardroom and reports", accent: "#163A5F", heading: "#102A43" },
    { key: "elegant_green", label: "Elegant Green", description: "Warm formal identity", accent: "#167D66", heading: "#0E5546" },
    { key: "legal_monochrome", label: "Legal Monochrome", description: "Contracts and policies", accent: "#343A40", heading: "#111827" },
    { key: "warm_professional", label: "Warm Professional", description: "Human and inviting", accent: "#A4552A", heading: "#67351F" },
    { key: "minimal_clean", label: "Minimal Clean", description: "Simple and spacious", accent: "#64748B", heading: "#1E293B" },
];

const SIGNATURE_FIELDS: Array<{
    type: SignatureFieldType;
    label: string;
    description: string;
    icon: typeof Signature;
}> = [
    { type: "signature", label: "Signature", description: "Full handwritten or electronic signature", icon: Signature },
    { type: "initials", label: "Initials", description: "Short initials field", icon: ScissorsLineDashed },
    { type: "date", label: "Date signed", description: "Date completed by the signer", icon: FileText },
    { type: "name", label: "Full name", description: "Printed signer name", icon: CaseSensitive },
    { type: "title", label: "Title / capacity", description: "Role or legal capacity", icon: Pilcrow },
    { type: "text", label: "Text field", description: "General fillable text", icon: CaseSensitive },
    { type: "checkbox", label: "Checkbox", description: "Consent or confirmation", icon: CheckSquare2 },
];

function ToolbarButton({
    active,
    disabled,
    title,
    onClick,
    children,
}: {
    active?: boolean;
    disabled?: boolean;
    title: string;
    onClick: () => void;
    children: React.ReactNode;
}) {
    return (
        <button
            type="button"
            title={title}
            aria-label={title}
            disabled={disabled}
            onClick={onClick}
            className={`document-ribbon-button ${active ? "is-active" : ""}`}
        >
            {children}
        </button>
    );
}

function RibbonGroup({
    label,
    children,
    className = "",
}: {
    label: string;
    children: React.ReactNode;
    className?: string;
}) {
    return (
        <div className={`document-ribbon-group ${className}`}>
            <div className="document-ribbon-group-content">{children}</div>
            <span className="document-ribbon-group-label">{label}</span>
        </div>
    );
}

function applyWordStyle(editor: Editor, styleKey: (typeof WORD_STYLES)[number]["key"]) {
    const clearBlockAttributes = {
        paragraphStyle: styleKey,
        lineHeight: null,
        marginTop: null,
        marginBottom: null,
        textIndent: null,
        letterSpacing: null,
    };
    const chain = editor.chain().focus().unsetAllMarks();

    switch (styleKey) {
        case "title":
            chain
                .setHeading({ level: 1 })
                .updateAttributes("heading", {
                    ...clearBlockAttributes,
                    lineHeight: "1.1",
                    marginTop: "0",
                    marginBottom: "12pt",
                    letterSpacing: "-0.02em",
                })
                .setFontFamily("Arial")
                .setFontSize("30pt")
                .setColor("#0F2742")
                .setTextAlign("center")
                .run();
            return;
        case "subtitle":
            chain
                .setParagraph()
                .updateAttributes("paragraph", {
                    ...clearBlockAttributes,
                    lineHeight: "1.25",
                    marginBottom: "14pt",
                })
                .setFontSize("14pt")
                .setColor("#64748B")
                .setTextAlign("center")
                .run();
            return;
        case "heading_1":
        case "heading_2":
        case "heading_3": {
            const level = Number(styleKey.slice(-1)) as 1 | 2 | 3;
            const size = { 1: "20pt", 2: "15pt", 3: "12pt" }[level];
            chain
                .setHeading({ level })
                .updateAttributes("heading", {
                    ...clearBlockAttributes,
                    lineHeight: "1.2",
                    marginTop: level === 1 ? "16pt" : "12pt",
                    marginBottom: level === 1 ? "8pt" : "6pt",
                })
                .setFontFamily("Arial")
                .setFontSize(size)
                .setColor("#0F2742")
                .setTextAlign("left")
                .run();
            return;
        }
        case "quote":
            chain
                .setParagraph()
                .toggleBlockquote()
                .setFontFamily("Georgia")
                .setFontSize("11pt")
                .setColor("#475569")
                .run();
            return;
        case "intense_quote":
            chain
                .setParagraph()
                .toggleBlockquote()
                .setFontFamily("Georgia")
                .setFontSize("12pt")
                .setColor("#1268B3")
                .toggleItalic()
                .run();
            return;
        case "no_spacing":
            chain
                .setParagraph()
                .updateAttributes("paragraph", {
                    ...clearBlockAttributes,
                    lineHeight: "1",
                    marginTop: "0",
                    marginBottom: "0",
                })
                .setFontFamily("Arial")
                .setFontSize("11pt")
                .setColor("#172033")
                .setTextAlign("left")
                .run();
            return;
        default:
            chain
                .setParagraph()
                .updateAttributes("paragraph", {
                    ...clearBlockAttributes,
                    lineHeight: "1.15",
                    marginTop: "0",
                    marginBottom: "8pt",
                })
                .setFontFamily("Arial")
                .setFontSize("11pt")
                .setColor("#172033")
                .setTextAlign("left")
                .run();
    }
}

function insertLink(editor: Editor) {
    const previous = editor.getAttributes("link").href as string | undefined;
    const value = window.prompt("Enter the link URL", previous || "https://");
    if (value === null) return;
    if (!value.trim()) editor.chain().focus().unsetLink().run();
    else editor.chain().focus().extendMarkRange("link").setLink({ href: value.trim() }).run();
}

export function DocumentRibbon({
    editor,
    disabled,
    document,
    onSettingsChange,
    onInsertSignature,
    onOpenBranding,
    onOpenCoverPage,
    onOpenAddresses,
    onOpenSignatureVault,
}: {
    editor: Editor;
    disabled: boolean;
    document: WorkspaceDocument;
    onSettingsChange: (payload: DocumentSettingsChange) => void;
    onInsertSignature: (type: SignatureFieldType) => void;
    onOpenBranding: () => void;
    onOpenCoverPage: () => void;
    onOpenAddresses: () => void;
    onOpenSignatureVault: () => void;
}) {
    const [tab, setTab] = useState<RibbonTab>("home");
    const imageInput = useRef<HTMLInputElement | null>(null);

    function imageSelected(file: File | undefined) {
        if (!file) return;
        if (!file.type.startsWith("image/")) {
            toast.error("Choose an image file.");
            return;
        }
        if (file.size > 2 * 1024 * 1024) {
            toast.error("Document images must be smaller than 2 MB.");
            return;
        }
        const reader = new FileReader();
        reader.onload = () =>
            editor.chain().focus().setImage({ src: String(reader.result), alt: file.name }).run();
        reader.readAsDataURL(file);
    }

    function indent(direction: "in" | "out") {
        const current = String(
            editor.getAttributes(editor.isActive("heading") ? "heading" : "paragraph").textIndent || "0mm",
        );
        const value = Number.parseFloat(current) || 0;
        const next = Math.max(0, Math.min(40, value + (direction === "in" ? 6 : -6)));
        const node = editor.isActive("heading") ? "heading" : "paragraph";
        editor.chain().focus().updateAttributes(node, { textIndent: `${next}mm` }).run();
    }

    return (
        <div className="document-ribbon">
            <div className="document-ribbon-tabs">
                {(["home", "insert", "layout", "design"] as RibbonTab[]).map((item) => (
                    <button
                        key={item}
                        type="button"
                        onClick={() => setTab(item)}
                        className={tab === item ? "is-active" : ""}
                    >
                        {item[0].toUpperCase() + item.slice(1)}
                    </button>
                ))}
            </div>

            <div className="document-ribbon-body">
                {tab === "home" && (
                    <>
                        <RibbonGroup label="History">
                            <div className="grid grid-cols-2 gap-1">
                                <ToolbarButton
                                    title="Undo"
                                    disabled={disabled || !editor.can().chain().focus().undo().run()}
                                    onClick={() => editor.chain().focus().undo().run()}
                                >
                                    <Undo2 />
                                </ToolbarButton>
                                <ToolbarButton
                                    title="Redo"
                                    disabled={disabled || !editor.can().chain().focus().redo().run()}
                                    onClick={() => editor.chain().focus().redo().run()}
                                >
                                    <Redo2 />
                                </ToolbarButton>
                            </div>
                        </RibbonGroup>

                        <RibbonGroup label="Font" className="min-w-[245px]">
                            <div className="grid grid-cols-[1fr_70px] gap-1">
                                <NativeSelect
                                    disabled={disabled}
                                    value={String(editor.getAttributes("textStyle").fontFamily || document.default_font_family)}
                                    onChange={(event) => editor.chain().focus().setFontFamily(event.target.value).run()}
                                    className="h-8 rounded-lg border bg-background px-2 text-xs font-bold"
                                >
                                    {FONTS.map((font) => (
                                        <option key={font}>{font}</option>
                                    ))}
                                </NativeSelect>
                                <NativeSelect
                                    disabled={disabled}
                                    value={String(editor.getAttributes("textStyle").fontSize || `${document.default_font_size_pt}pt`)}
                                    onChange={(event) => editor.chain().focus().setFontSize(event.target.value).run()}
                                    className="h-8 rounded-lg border bg-background px-2 text-xs font-bold"
                                >
                                    {FONT_SIZES.map((size) => (
                                        <option key={size} value={`${size}pt`}>
                                            {size}
                                        </option>
                                    ))}
                                </NativeSelect>
                            </div>
                            <div className="mt-1 flex flex-wrap gap-1">
                                <ToolbarButton title="Bold" disabled={disabled} active={editor.isActive("bold")} onClick={() => editor.chain().focus().toggleBold().run()}><Bold /></ToolbarButton>
                                <ToolbarButton title="Italic" disabled={disabled} active={editor.isActive("italic")} onClick={() => editor.chain().focus().toggleItalic().run()}><Italic /></ToolbarButton>
                                <ToolbarButton title="Underline" disabled={disabled} active={editor.isActive("underline")} onClick={() => editor.chain().focus().toggleUnderline().run()}><UnderlineIcon /></ToolbarButton>
                                <ToolbarButton title="Subscript" disabled={disabled} active={editor.isActive("subscript")} onClick={() => editor.chain().focus().toggleMark("subscript").run()}><Subscript /></ToolbarButton>
                                <ToolbarButton title="Superscript" disabled={disabled} active={editor.isActive("superscript")} onClick={() => editor.chain().focus().toggleMark("superscript").run()}><Superscript /></ToolbarButton>
                                <label title="Text colour" className="document-ribbon-color"><span>A</span><input disabled={disabled} type="color" onChange={(event) => editor.chain().focus().setColor(event.target.value).run()} /></label>
                                <label title="Highlight" className="document-ribbon-color"><Highlighter /><input disabled={disabled} type="color" defaultValue="#fff59d" onChange={(event) => editor.chain().focus().toggleHighlight({ color: event.target.value }).run()} /></label>
                                <ToolbarButton title="Clear formatting" disabled={disabled} onClick={() => editor.chain().focus().unsetAllMarks().clearNodes().run()}><RemoveFormatting /></ToolbarButton>
                            </div>
                        </RibbonGroup>

                        <RibbonGroup label="Paragraph" className="min-w-[220px]">
                            <div className="flex flex-wrap gap-1">
                                <ToolbarButton title="Bullet list" disabled={disabled} active={editor.isActive("bulletList")} onClick={() => editor.chain().focus().toggleBulletList().run()}><List /></ToolbarButton>
                                <ToolbarButton title="Numbered list" disabled={disabled} active={editor.isActive("orderedList")} onClick={() => editor.chain().focus().toggleOrderedList().run()}><ListOrdered /></ToolbarButton>
                                <ToolbarButton title="Decrease indent" disabled={disabled} onClick={() => indent("out")}><IndentDecrease /></ToolbarButton>
                                <ToolbarButton title="Increase indent" disabled={disabled} onClick={() => indent("in")}><IndentIncrease /></ToolbarButton>
                                <ToolbarButton title="Align left" disabled={disabled} active={editor.isActive({ textAlign: "left" })} onClick={() => editor.chain().focus().setTextAlign("left").run()}><AlignLeft /></ToolbarButton>
                                <ToolbarButton title="Align centre" disabled={disabled} active={editor.isActive({ textAlign: "center" })} onClick={() => editor.chain().focus().setTextAlign("center").run()}><AlignCenter /></ToolbarButton>
                                <ToolbarButton title="Align right" disabled={disabled} active={editor.isActive({ textAlign: "right" })} onClick={() => editor.chain().focus().setTextAlign("right").run()}><AlignRight /></ToolbarButton>
                                <ToolbarButton title="Justify" disabled={disabled} active={editor.isActive({ textAlign: "justify" })} onClick={() => editor.chain().focus().setTextAlign("justify").run()}><AlignJustify /></ToolbarButton>
                                <ToolbarButton title="Block quote" disabled={disabled} active={editor.isActive("blockquote")} onClick={() => editor.chain().focus().toggleBlockquote().run()}><Quote /></ToolbarButton>
                                <NativeSelect
                                    disabled={disabled}
                                    value={String(editor.getAttributes(editor.isActive("heading") ? "heading" : "paragraph").lineHeight || `${document.default_line_height_percent / 100}`)}
                                    onChange={(event) => {
                                        const node = editor.isActive("heading") ? "heading" : "paragraph";
                                        editor.chain().focus().updateAttributes(node, { lineHeight: event.target.value }).run();
                                    }}
                                    className="h-8 w-24 rounded-lg border bg-background px-2 text-xs font-bold"
                                    title="Line spacing"
                                >
                                    <option value="1">1.0</option>
                                    <option value="1.15">1.15</option>
                                    <option value="1.5">1.5</option>
                                    <option value="2">2.0</option>
                                    <option value="2.5">2.5</option>
                                </NativeSelect>
                            </div>
                        </RibbonGroup>

                        <RibbonGroup label="Styles" className="min-w-[360px] flex-1">
                            <div className="document-word-styles">
                                {WORD_STYLES.map((style) => (
                                    <button key={style.key} type="button" disabled={disabled} onClick={() => applyWordStyle(editor, style.key)}>
                                        <span className={`style-preview style-${style.key}`}>{style.preview}</span>
                                        <small>{style.label}</small>
                                    </button>
                                ))}
                            </div>
                        </RibbonGroup>
                    </>
                )}

                {tab === "insert" && (
                    <>
                        <RibbonGroup label="Pages">
                            <ToolbarButton title="Insert page break" disabled={disabled} onClick={() => editor.chain().focus().insertContent({ type: "pageBreak" }).run()}><FileText /><span>Page break</span></ToolbarButton>
                            <ToolbarButton title="Horizontal line" disabled={disabled} onClick={() => editor.chain().focus().setHorizontalRule().run()}><Minus /><span>Rule</span></ToolbarButton>
                            <ToolbarButton title="Insert today's date" disabled={disabled} onClick={() => editor.chain().focus().insertContent(new Intl.DateTimeFormat(undefined, { dateStyle: "long" }).format(new Date())).run()}><FileText /><span>Date</span></ToolbarButton>
                        </RibbonGroup>
                        <RibbonGroup label="Tables and media">
                            <ToolbarButton title="Insert table" disabled={disabled} onClick={() => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}><Table2 /><span>Table</span></ToolbarButton>
                            <ToolbarButton title="Insert image" disabled={disabled} onClick={() => imageInput.current?.click()}><ImagePlus /><span>Image</span></ToolbarButton>
                            <input ref={imageInput} hidden type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => imageSelected(event.target.files?.[0])} />
                            <ToolbarButton title="Insert link" disabled={disabled} active={editor.isActive("link")} onClick={() => insertLink(editor)}><Link2 /><span>Link</span></ToolbarButton>
                        </RibbonGroup>
                        {editor.isActive("table") && (
                            <RibbonGroup label="Table tools">
                                <ToolbarButton title="Add row" disabled={disabled} onClick={() => editor.chain().focus().addRowAfter().run()}><Rows3 /><span>Add row</span></ToolbarButton>
                                <ToolbarButton title="Add column" disabled={disabled} onClick={() => editor.chain().focus().addColumnAfter().run()}><Columns3 /><span>Add column</span></ToolbarButton>
                                <ToolbarButton title="Delete table" disabled={disabled} onClick={() => editor.chain().focus().deleteTable().run()}><Trash2 /><span>Delete</span></ToolbarButton>
                            </RibbonGroup>
                        )}
                        <RibbonGroup label="Document objects">
                            <ToolbarButton title="Manage positioned address blocks" disabled={disabled} onClick={onOpenAddresses}><MapPin /><span>Addresses</span></ToolbarButton>
                            <ToolbarButton title="Open reusable signature vault" onClick={onOpenSignatureVault}><Stamp /><span>Signature vault</span></ToolbarButton>
                        </RibbonGroup>
                        <RibbonGroup label="Signature and fillable fields" className="flex-1">
                            <div className="document-signature-palette">
                                {SIGNATURE_FIELDS.map(({ type, label, description, icon: Icon }) => (
                                    <button
                                        key={type}
                                        type="button"
                                        draggable={!disabled}
                                        disabled={disabled}
                                        title={`${description}. Drag onto the page or click to insert.`}
                                        onClick={() => onInsertSignature(type)}
                                        onDragStart={(event) => {
                                            event.dataTransfer.effectAllowed = "copy";
                                            event.dataTransfer.setData(
                                                SIGNATURE_FIELD_MIME,
                                                JSON.stringify(createSignatureFieldAttrs(type)),
                                            );
                                        }}
                                    >
                                        <Icon />
                                        <span><strong>{label}</strong><small>{description}</small></span>
                                    </button>
                                ))}
                            </div>
                        </RibbonGroup>
                    </>
                )}

                {tab === "layout" && (
                    <>
                        <RibbonGroup label="Page setup">
                            <label className="document-ribbon-field"><span>Size</span><NativeSelect value={document.page_size} disabled={disabled} onChange={(event) => onSettingsChange({ page_size: event.target.value as DocumentPageSize })}><option value="A4">A4</option><option value="LETTER">US Letter</option></NativeSelect></label>
                            <label className="document-ribbon-field"><span>Orientation</span><NativeSelect value={document.orientation} disabled={disabled} onChange={(event) => onSettingsChange({ orientation: event.target.value as DocumentOrientation })}><option value="portrait">Portrait</option><option value="landscape">Landscape</option></NativeSelect></label>
                        </RibbonGroup>
                        <RibbonGroup label="Margins" className="min-w-[380px]">
                            <div className="grid grid-cols-4 gap-2">
                                {([
                                    ["Top", "margin_top_mm"],
                                    ["Right", "margin_right_mm"],
                                    ["Bottom", "margin_bottom_mm"],
                                    ["Left", "margin_left_mm"],
                                ] as const).map(([label, key]) => (
                                    <label key={key} className="document-ribbon-field"><span>{label}</span><input type="number" min={8} max={60} disabled={disabled} value={document[key]} onChange={(event) => onSettingsChange({ [key]: Number(event.target.value) } as DocumentSettingsChange)} /></label>
                                ))}
                            </div>
                        </RibbonGroup>
                        <RibbonGroup label="Paragraph defaults">
                            <label className="document-ribbon-field"><span>Font</span><NativeSelect value={document.default_font_family} disabled={disabled} onChange={(event) => onSettingsChange({ default_font_family: event.target.value })}>{FONTS.map((font) => <option key={font}>{font}</option>)}</NativeSelect></label>
                            <label className="document-ribbon-field"><span>Size</span><NativeSelect value={document.default_font_size_pt} disabled={disabled} onChange={(event) => onSettingsChange({ default_font_size_pt: Number(event.target.value) })}>{FONT_SIZES.filter((size) => size <= 36).map((size) => <option key={size} value={size}>{size} pt</option>)}</NativeSelect></label>
                            <label className="document-ribbon-field"><span>Spacing</span><NativeSelect value={document.default_line_height_percent} disabled={disabled} onChange={(event) => onSettingsChange({ default_line_height_percent: Number(event.target.value) })}><option value={100}>Single</option><option value={115}>1.15</option><option value={150}>1.5</option><option value={200}>Double</option></NativeSelect></label>
                        </RibbonGroup>
                    </>
                )}

                {tab === "design" && (
                    <>
                    <RibbonGroup label="Document identity">
                        <ToolbarButton title="Upload or select the writer logo used across documents" disabled={!document.can_manage} onClick={onOpenBranding}><ImagePlus /><span>Brand logo</span></ToolbarButton>
                        <ToolbarButton title="Configure an optional cover page" disabled={disabled} onClick={onOpenCoverPage}><BookOpen /><span>Cover page</span></ToolbarButton>
                    </RibbonGroup>
                    <RibbonGroup label="Document style gallery" className="flex-1">
                        <div className="document-theme-gallery">
                            {THEMES.map((theme) => (
                                <button
                                    key={theme.key}
                                    type="button"
                                    disabled={disabled}
                                    className={document.style_key === theme.key ? "is-active" : ""}
                                    onClick={() => onSettingsChange({ style_key: theme.key })}
                                >
                                    <span className="theme-swatch" style={{ background: theme.accent }}><i style={{ background: theme.heading }} /></span>
                                    <span><strong>{theme.label}</strong><small>{theme.description}</small></span>
                                </button>
                            ))}
                        </div>
                    </RibbonGroup>
                    </>
                )}
            </div>
        </div>
    );
}
