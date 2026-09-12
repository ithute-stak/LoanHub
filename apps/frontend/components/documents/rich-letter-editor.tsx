"use client";

import { Color, FontFamily, FontSize, TextStyle } from "@tiptap/extension-text-style";
import Highlight from "@tiptap/extension-highlight";
import Image from "@tiptap/extension-image";
import Placeholder from "@tiptap/extension-placeholder";
import { TableKit } from "@tiptap/extension-table";
import TextAlign from "@tiptap/extension-text-align";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
    ArrowLeft,
    BookOpen,
    Check,
    Clock3,
    Download,
    FileDown,
    ImagePlus,
    FileText,
    History,
    Loader2,
    LockKeyhole,
    MapPin,
    Maximize2,
    Minimize2,
    MoreVertical,
    PenLine,
    Printer,
    Save,
    Share2,
    ShieldCheck,
    Stamp,
    Trash2,
    UsersRound,
    ZoomIn,
    ZoomOut,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
    applyWorkspaceDocumentSignature,
    deleteWorkspaceDocumentAsset,
    downloadWorkspaceDocument,
    getDocumentBrandLogoObjectUrl,
    getDocumentSignatureObjectUrl,
    getWorkspaceAssetObjectUrl,
    getWorkspaceDocument,
    listWorkspaceDocumentAssets,
    listWorkspaceDocumentRevisions,
    listWorkspaceDocumentSignatures,
    openWorkspaceDocumentPrintView,
    publishWorkspaceDocument,
    revokeWorkspaceDocumentSignature,
    updateWorkspaceDocument,
    uploadWorkspaceLogo,
    uploadWorkspaceSignature,
} from "@/api/workspaceDocuments";
import { DocumentSharingDialog } from "@/components/documents/document-sharing-dialog";
import {
    DocumentBlockFormatting,
    PageBreak,
    SIGNATURE_FIELD_MIME,
    SignatureField,
    SignaturePreviewContext,
    SubscriptMark,
    SuperscriptMark,
    createSignatureFieldAttrs,
} from "@/components/documents/editor/document-editor-extensions";
import { DocumentAddressOverlay } from "@/components/documents/editor/document-address-overlay";
import {
    DocumentRibbon,
    type DocumentSettingsChange,
} from "@/components/documents/editor/document-ribbon";
import { ExternalFileShareDialog } from "@/components/files/file-share-dialogs";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { createUuid } from "@/lib/uuid";
import type { ManagedFile } from "@/types/files";
import type {
    DocumentAddressBlock,
    DocumentCoverPage,
    DocumentExportFormat,
    DocumentSignatureMethod,
    DocumentStatus,
    DocumentVisibility,
    SignatureFieldType,
    WorkspaceDocument,
    WorkspaceDocumentAsset,
    WorkspaceDocumentRevision,
    WorkspaceDocumentSignature,
} from "@/types/workspaceDocuments";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

const extensions = [
    StarterKit.configure({
        link: { openOnClick: false, autolink: true, defaultProtocol: "https" },
    }),
    TextStyle,
    FontSize,
    FontFamily,
    Color,
    Highlight.configure({ multicolor: true }),
    TextAlign.configure({ types: ["heading", "paragraph"] }),
    Image.configure({ allowBase64: true, inline: false }),
    Placeholder.configure({ placeholder: "Start writing your document..." }),
    TableKit.configure({ table: { resizable: true } }),
    DocumentBlockFormatting,
    SubscriptMark,
    SuperscriptMark,
    SignatureField,
    PageBreak,
];

type SaveState = "loading" | "saved" | "unsaved" | "saving" | "error";

type EditorMode = "company" | "borrower" | "superadmin" | "platform";

const THEME_CSS: Record<
    WorkspaceDocument["style_key"],
    { accent: string; heading: string; soft: string; ink: string }
> = {
    modern_blue: { accent: "#1268B3", heading: "#0F2742", soft: "#EDF6FF", ink: "#172033" },
    classic_word: { accent: "#2F5597", heading: "#1F3864", soft: "#EAF0F8", ink: "#1F1F1F" },
    executive_navy: { accent: "#163A5F", heading: "#102A43", soft: "#E9F0F6", ink: "#243B53" },
    elegant_green: { accent: "#167D66", heading: "#0E5546", soft: "#E9F8F3", ink: "#1E3A34" },
    legal_monochrome: { accent: "#343A40", heading: "#111827", soft: "#F3F4F6", ink: "#111827" },
    warm_professional: { accent: "#A4552A", heading: "#67351F", soft: "#FFF4EC", ink: "#3F3028" },
    minimal_clean: { accent: "#64748B", heading: "#1E293B", soft: "#F8FAFC", ink: "#1E293B" },
};

export function RichLetterEditor({
    documentId,
    basePath,
    mode,
}: {
    documentId: string;
    basePath: string;
    mode: EditorMode;
}) {
    const router = useRouter();
    const [documentRecord, setDocumentRecord] = useState<WorkspaceDocument | null>(null);
    const [title, setTitle] = useState("");
    const [saveState, setSaveState] = useState<SaveState>("loading");
    const [shareOpen, setShareOpen] = useState(false);
    const [publishedFile, setPublishedFile] = useState<ManagedFile | null>(null);
    const [publishing, setPublishing] = useState<DocumentExportFormat | null>(null);
    const [revisions, setRevisions] = useState<WorkspaceDocumentRevision[]>([]);
    const [historyOpen, setHistoryOpen] = useState(false);
    const [fullscreenOpen, setFullscreenOpen] = useState(false);
    const [zoom, setZoom] = useState(90);
    const [brandingOpen, setBrandingOpen] = useState(false);
    const [signatureVaultOpen, setSignatureVaultOpen] = useState(false);
    const [coverOpen, setCoverOpen] = useState(false);
    const [addressesOpen, setAddressesOpen] = useState(false);
    const [logoAssets, setLogoAssets] = useState<WorkspaceDocumentAsset[]>([]);
    const [signatureAssets, setSignatureAssets] = useState<WorkspaceDocumentAsset[]>([]);
    const [brandLogoUrl, setBrandLogoUrl] = useState<string | null>(null);
    const [signatures, setSignatures] = useState<WorkspaceDocumentSignature[]>([]);
    const [signatureImageUrls, setSignatureImageUrls] = useState<Record<string, string>>({});
    const [assetBusy, setAssetBusy] = useState(false);
    const [signing, setSigning] = useState(false);
    const [signTarget, setSignTarget] = useState<{ fieldId: string; fieldType: SignatureFieldType; label: string } | null>(null);
    const [signMethod, setSignMethod] = useState<DocumentSignatureMethod>("stored_signature");
    const [signAssetId, setSignAssetId] = useState("");
    const [signConsent, setSignConsent] = useState("I confirm that I intend this electronic action to serve as my signature on this document.");
    const saveTimer = useRef<number | null>(null);
    const versionRef = useRef(1);
    const titleRef = useRef("");
    const savingRef = useRef(false);
    const queuedSaveRef = useRef(false);
    const initializedRef = useRef(false);
    const canEditRef = useRef(false);

    const editor = useEditor({
        extensions,
        content: "",
        immediatelyRender: false,
        editorProps: {
            attributes: {
                class: "document-editor-content min-h-[820px] outline-none",
                spellcheck: "true",
                "aria-label": "Document body editor",
            },
        },
        onUpdate: () => scheduleAutosave(),
    });

    const refreshBrandLogo = useCallback(async () => {
        try {
            const nextUrl = await getDocumentBrandLogoObjectUrl(documentId);
            setBrandLogoUrl((previous) => {
                if (previous) URL.revokeObjectURL(previous);
                return nextUrl;
            });
        } catch {
            setBrandLogoUrl((previous) => {
                if (previous) URL.revokeObjectURL(previous);
                return null;
            });
        }
    }, [documentId]);

    const refreshAssets = useCallback(async () => {
        try {
            const [logos, signaturesList] = await Promise.all([
                listWorkspaceDocumentAssets("logo"),
                listWorkspaceDocumentAssets("signature"),
            ]);
            setLogoAssets(logos);
            setSignatureAssets(signaturesList);
            setSignAssetId((current) => current || signaturesList.find((asset) => asset.is_default)?.id || signaturesList[0]?.id || "");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not load document assets."));
        }
    }, []);

    const refreshSignatures = useCallback(async () => {
        try {
            const rows = await listWorkspaceDocumentSignatures(documentId);
            const assetIds = Array.from(new Set(rows.map((row) => row.asset_id).filter((value): value is string => Boolean(value))));
            const urls: Record<string, string> = {};
            await Promise.all(assetIds.map(async (assetId) => {
                try {
                    urls[assetId] = await getDocumentSignatureObjectUrl(documentId, assetId);
                } catch {
                    // A revoked or inaccessible asset remains represented by the audit metadata.
                }
            }));
            setSignatureImageUrls((previous) => {
                Object.values(previous).forEach((url) => URL.revokeObjectURL(url));
                return urls;
            });
            setSignatures(rows);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not load document signatures."));
        }
    }, [documentId]);

    const load = useCallback(async () => {
        initializedRef.current = false;
        setSaveState("loading");
        try {
            const record = await getWorkspaceDocument(documentId);
            setDocumentRecord(record);
            setTitle(record.title);
            titleRef.current = record.title;
            versionRef.current = record.version;
            canEditRef.current = record.can_edit;
            setSaveState("saved");
            void refreshBrandLogo();
            void refreshSignatures();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not open the document."));
            router.replace(basePath);
        }
    }, [basePath, documentId, refreshBrandLogo, refreshSignatures, router]);

    useEffect(() => {
        void load();
    }, [load]);

    useEffect(() => {
        if (!editor || !documentRecord || initializedRef.current) return;

        const activeEditor = editor;
        const record = documentRecord;
        let cancelled = false;

        // Older Filizwa-style documents may already have the placeholder header
        // stored in both content_html and content_json. The real Document Studio
        // header now owns branding, so discard the legacy table before hydrating.
        const jsonText = JSON.stringify(record.content_json ?? {});
        const hasLegacyPlaceholderHeader =
            jsonText.includes("[LEFT LOGO]") &&
            jsonText.includes("[COMPANY NAME]") &&
            jsonText.includes("[RIGHT LOGO]");
        const normalizedHtml = stripLegacyFilizwaPlaceholderHeader(record.content_html || "");

        // Tiptap's React-backed node views can call ReactDOM.flushSync while
        // setContent() runs. Defer hydration until React has completed the current
        // lifecycle stack. Keeping this dependency list at two entries also avoids
        // Fast Refresh's changing-hook-input-size warning.
        queueMicrotask(() => {
            if (cancelled || activeEditor.isDestroyed || initializedRef.current) return;

            const jsonContent = record.content_json as { content?: unknown[] } | null;
            const content = hasLegacyPlaceholderHeader
                ? normalizedHtml
                : jsonContent?.content?.length
                    ? record.content_json
                    : normalizedHtml;

            activeEditor.commands.setContent(content, { emitUpdate: false });
            activeEditor.setEditable(record.can_edit);
            initializedRef.current = true;
        });

        return () => {
            cancelled = true;
        };
    }, [documentRecord, editor]);

    useEffect(
        () => () => {
            if (saveTimer.current) window.clearTimeout(saveTimer.current);
            if (brandLogoUrl) URL.revokeObjectURL(brandLogoUrl);
            Object.values(signatureImageUrls).forEach((url) => URL.revokeObjectURL(url));
        },
        [brandLogoUrl, signatureImageUrls],
    );

    const statistics = useMemo(() => {
        if (!editor) return { words: 0, characters: 0, paragraphs: 0, fields: 0 };
        const text = editor.getText({ blockSeparator: "\n" });
        const words = text.trim() ? text.trim().split(/\s+/).length : 0;
        const paragraphs = editor.getJSON().content?.length ?? 0;
        let fields = 0;
        editor.state.doc.descendants((node) => {
            if (node.type.name === "signatureField") fields += 1;
        });
        return { words, characters: text.length, paragraphs, fields };
    }, [editor, saveState, documentRecord?.version]);

    const signaturePreviewEntries = useMemo(() => {
        return Object.fromEntries(
            signatures.map((row) => [
                row.field_id,
                {
                    signerName: row.signer_name,
                    signedAt: row.signed_at,
                    method: row.method,
                    verificationCode: row.verification_code,
                    imageUrl: row.asset_id ? signatureImageUrls[row.asset_id] : undefined,
                },
            ]),
        );
    }, [signatureImageUrls, signatures]);

    function scheduleAutosave() {
        if (!canEditRef.current || !initializedRef.current) return;
        setSaveState("unsaved");
        if (saveTimer.current) window.clearTimeout(saveTimer.current);
        saveTimer.current = window.setTimeout(() => void save(false), 1000);
    }

    async function save(createRevision: boolean): Promise<boolean> {
        if (!editor || !documentRecord?.can_edit) return true;
        if (saveTimer.current) {
            window.clearTimeout(saveTimer.current);
            saveTimer.current = null;
        }
        if (savingRef.current) {
            queuedSaveRef.current = true;
            return false;
        }
        savingRef.current = true;
        setSaveState("saving");
        try {
            const updated = await updateWorkspaceDocument(documentId, {
                title: titleRef.current,
                content_json: editor.getJSON() as Record<string, unknown>,
                content_html: editor.getHTML(),
                expected_version: versionRef.current,
                create_revision: createRevision,
            });
            versionRef.current = updated.version;
            setDocumentRecord(updated);
            setSaveState("saved");
            if (createRevision) {
                toast.success("Document saved with a revision checkpoint");
                void refreshRevisions();
            }
            return true;
        } catch (error: unknown) {
            setSaveState("error");
            const message = getErrorMessage(error, "Document could not be saved.");
            toast.error(message);
            if (message.toLowerCase().includes("another user")) {
                initializedRef.current = false;
                await load();
            }
            return false;
        } finally {
            savingRef.current = false;
            if (queuedSaveRef.current) {
                queuedSaveRef.current = false;
                void save(false);
            }
        }
    }

    async function refreshRevisions() {
        try {
            setRevisions(await listWorkspaceDocumentRevisions(documentId));
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not load revision history."));
        }
    }

    function updateTitle(value: string) {
        setTitle(value);
        titleRef.current = value;
        scheduleAutosave();
    }

    async function changeSettings(
        payload: DocumentSettingsChange &
            Partial<{
                visibility: DocumentVisibility;
                status: DocumentStatus;
                include_brand_header: boolean;
                include_footer: boolean;
                is_confidential: boolean;
                brand_logo_asset_id: string | null;
                clear_brand_logo_asset: boolean;
                cover_page_enabled: boolean;
                cover_page: DocumentCoverPage;
                address_blocks: DocumentAddressBlock[];
            }>,
        options: { revision?: boolean; notify?: boolean } = {},
    ) {
        if (!documentRecord) return;
        if (saveState === "unsaved") {
            const saved = await save(false);
            if (!saved) return;
        }
        try {
            const updated = await updateWorkspaceDocument(documentRecord.id, {
                ...payload,
                expected_version: versionRef.current,
                create_revision: options.revision ?? true,
            });
            versionRef.current = updated.version;
            setDocumentRecord(updated);
            setSaveState("saved");
            if (options.notify ?? true) toast.success("Document settings updated");
            if (options.revision ?? true) void refreshRevisions();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not update document settings."));
        }
    }

    async function handleLogoUpload(file: File, label: string) {
        setAssetBusy(true);
        try {
            await uploadWorkspaceLogo(file, label || "My document logo", true);
            await refreshAssets();
            await changeSettings({ clear_brand_logo_asset: true }, { revision: false, notify: false });
            await refreshBrandLogo();
            toast.success("Logo uploaded and set as your default document logo");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not upload the logo."));
        } finally {
            setAssetBusy(false);
        }
    }

    async function selectBrandLogo(assetId: string | null) {
        try {
            if (assetId) {
                await changeSettings({ brand_logo_asset_id: assetId }, { revision: false, notify: false });
            } else {
                await changeSettings({ clear_brand_logo_asset: true }, { revision: false, notify: false });
            }
            await refreshBrandLogo();
            toast.success(assetId ? "Document logo selected" : "Document now follows your default logo");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not change the document logo."));
        }
    }

    async function handleSignatureUpload(file: File, label: string) {
        setAssetBusy(true);
        try {
            const asset = await uploadWorkspaceSignature(file, label || "My signature", true);
            await refreshAssets();
            setSignAssetId(asset.id);
            toast.success("Signature image processed and stored in your private signature vault");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not process the signature image."));
        } finally {
            setAssetBusy(false);
        }
    }

    async function removeAsset(asset: WorkspaceDocumentAsset) {
        try {
            await deleteWorkspaceDocumentAsset(asset.id);
            await refreshAssets();
            if (asset.kind === "logo") await refreshBrandLogo();
            toast.success(`${asset.kind === "logo" ? "Logo" : "Signature"} removed`);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not remove the asset."));
        }
    }

    function openSignDialog(fieldId: string, fieldType: SignatureFieldType, label: string) {
        setSignTarget({ fieldId, fieldType, label });
        setSignMethod("stored_signature");
        setSignConsent("I confirm that I intend this electronic action to serve as my signature on this document.");
        void refreshAssets();
    }

    async function applySignature() {
        if (!signTarget) return;
        if (saveState !== "saved") {
            const saved = await save(true);
            if (!saved) return;
        }
        if (signMethod === "stored_signature" && !signAssetId) {
            toast.error("Upload or select a stored signature first.");
            return;
        }
        setSigning(true);
        try {
            await applyWorkspaceDocumentSignature(documentId, {
                field_id: signTarget.fieldId,
                method: signMethod,
                asset_id: signMethod === "stored_signature" ? signAssetId : null,
                consent_text: signConsent,
            });
            setSignTarget(null);
            await Promise.all([load(), refreshSignatures()]);
            toast.success(signMethod === "electronic" ? "Electronic signature applied" : "Stored signature applied");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not sign this field."));
        } finally {
            setSigning(false);
        }
    }

    async function revokeSignature(fieldId: string) {
        try {
            await revokeWorkspaceDocumentSignature(documentId, fieldId);
            await Promise.all([load(), refreshSignatures()]);
            toast.success("Signature revoked and recorded in the audit trail");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not revoke the signature."));
        }
    }

    function updateAddressBlocksLocally(blocks: DocumentAddressBlock[]) {
        setDocumentRecord((current) => current ? { ...current, address_blocks: blocks } : current);
    }

    async function commitAddressBlocks(blocks: DocumentAddressBlock[]) {
        await changeSettings({ address_blocks: blocks }, { revision: false, notify: false });
    }

    async function saveAddressBlocks(blocks: DocumentAddressBlock[]) {
        await changeSettings({ address_blocks: blocks }, { revision: true, notify: true });
        setAddressesOpen(false);
    }

    async function saveCoverPage(enabled: boolean, cover: DocumentCoverPage) {
        await changeSettings({ cover_page_enabled: enabled, cover_page: cover }, { revision: true, notify: true });
        setCoverOpen(false);
    }

    function insertSignatureField(type: SignatureFieldType) {
        if (!editor || !documentRecord?.can_edit) return;
        editor
            .chain()
            .focus()
            .insertContent({ type: "signatureField", attrs: createSignatureFieldAttrs(type) })
            .run();
    }

    function handleDrop(event: React.DragEvent<HTMLDivElement>) {
        if (!editor || !documentRecord?.can_edit) return;
        const raw = event.dataTransfer.getData(SIGNATURE_FIELD_MIME);
        if (!raw) return;
        event.preventDefault();
        event.stopPropagation();
        try {
            const attrs = JSON.parse(raw) as Record<string, unknown>;
            const position = editor.view.posAtCoords({ left: event.clientX, top: event.clientY });
            editor
                .chain()
                .focus()
                .insertContentAt(position?.pos ?? editor.state.selection.anchor, {
                    type: "signatureField",
                    attrs,
                })
                .run();
            toast.success("Signature field added. Drag it again to reposition it.");
        } catch {
            toast.error("The signature field could not be added.");
        }
    }

    async function exportFile(format: DocumentExportFormat) {
        if (!documentRecord) return;
        const saved = await save(false);
        if (!saved && documentRecord.can_edit) return;
        try {
            await downloadWorkspaceDocument(documentRecord.id, format, titleRef.current);
            toast.success(`${format.toUpperCase()} download started`);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, `Could not export ${format.toUpperCase()}.`));
        }
    }

    async function publish(format: DocumentExportFormat) {
        if (!documentRecord) return;
        const saved = await save(true);
        if (!saved && documentRecord.can_edit) return;
        setPublishing(format);
        try {
            const file = await publishWorkspaceDocument(documentRecord.id, {
                format,
                visibility: documentRecord.company_id ? "company" : "private",
                is_confidential: documentRecord.is_confidential,
            });
            setPublishedFile(file);
            toast.success(`${format.toUpperCase()} saved to the document library`);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not publish the document."));
        } finally {
            setPublishing(null);
        }
    }

    async function printDocument() {
        if (!documentRecord) return;
        const saved = await save(false);
        if (!saved && documentRecord.can_edit) return;
        try {
            await openWorkspaceDocumentPrintView(documentRecord.id);
            toast.success("Print-ready PDF opened in a new tab");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not open the print view."));
        }
    }

    if (!editor || !documentRecord || saveState === "loading") {
        return (
            <div className="flex min-h-[60vh] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
        );
    }

    // Capture stable non-null references before creating the nested renderer.
    // TypeScript intentionally does not keep React-state narrowing inside a
    // closure because the state value may change before that closure runs.
    const activeDocument = documentRecord;
    const activeEditor = editor;

    const theme = THEME_CSS[activeDocument.style_key];
    const pageWidth = activeDocument.page_size === "LETTER" ? 215.9 : 210;
    const pageHeight = activeDocument.page_size === "LETTER" ? 279.4 : 297;
    const width = activeDocument.orientation === "landscape" ? pageHeight : pageWidth;
    const minHeight = activeDocument.orientation === "landscape" ? pageWidth : pageHeight;

    function renderStudio(fullscreen: boolean) {
        return (
            <main className={`document-studio-shell ${fullscreen ? "document-studio-fullscreen" : ""}`}>
                <section className="document-editor-commandbar">
                    <div className="flex min-w-0 flex-1 items-center gap-2">
                        <Button asChild variant="ghost" size="icon">
                            <Link href={basePath} aria-label="Back to documents">
                                <ArrowLeft />
                            </Link>
                        </Button>
                        <div className="min-w-0 flex-1">
                            <Input
                                value={title}
                                onChange={(event) => updateTitle(event.target.value)}
                                disabled={!activeDocument.can_edit}
                                className="h-9 border-0 bg-transparent px-1 text-lg font-black shadow-none focus-visible:ring-0"
                            />
                            <p className="truncate px-1 text-[11px] text-muted-foreground">
                                {activeDocument.reference} · {activeDocument.owner_display_name}
                            </p>
                        </div>
                    </div>
                    <div className="flex flex-wrap items-center justify-end gap-2">
                        <SaveIndicator state={saveState} version={versionRef.current} />
                        <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() => {
                                setHistoryOpen((current) => !current);
                                if (!historyOpen) void refreshRevisions();
                            }}
                        >
                            <History /> History
                        </Button>
                        {activeDocument.can_manage && (
                            <Button type="button" variant="outline" size="sm" onClick={() => setShareOpen(true)}>
                                <UsersRound /> Share
                            </Button>
                        )}
                        <Button type="button" variant="outline" size="sm" onClick={() => void exportFile("docx")}>
                            <Download /> Word
                        </Button>
                        <Button type="button" variant="outline" size="sm" onClick={() => void exportFile("pdf")}>
                            <FileDown /> PDF
                        </Button>
                        <Button type="button" variant="outline" size="sm" onClick={() => void printDocument()}>
                            <Printer /> Print
                        </Button>
                        {activeDocument.can_edit && (
                            <Button type="button" size="sm" onClick={() => void save(true)}>
                                <Save /> Save
                            </Button>
                        )}
                        <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() => setFullscreenOpen(!fullscreen)}
                            aria-label={fullscreen ? "Exit full screen editor" : "Open full screen editor"}
                            title={fullscreen ? "Exit full screen" : "Open full screen"}
                        >
                            {fullscreen ? <Minimize2 /> : <Maximize2 />}
                            <span className="hidden 2xl:inline">{fullscreen ? "Exit full screen" : "Full screen"}</span>
                        </Button>
                    </div>
                </section>

                <DocumentRibbon
                    editor={activeEditor}
                    disabled={!activeDocument.can_edit}
                    document={activeDocument}
                    onSettingsChange={(payload) => void changeSettings(payload)}
                    onInsertSignature={insertSignatureField}
                    onOpenBranding={() => { void refreshAssets(); setBrandingOpen(true); }}
                    onOpenCoverPage={() => setCoverOpen(true)}
                    onOpenAddresses={() => setAddressesOpen(true)}
                    onOpenSignatureVault={() => { void refreshAssets(); setSignatureVaultOpen(true); }}
                />

                <section className="document-editor-main-grid">
                    <div className="document-editor-canvas-wrap">
                        <div className="document-editor-zoom-controls">
                            <ZoomOut className="h-4 w-4" />
                            <input
                                type="range"
                                min={50}
                                max={140}
                                step={5}
                                value={zoom}
                                onChange={(event) => setZoom(Number(event.target.value))}
                                aria-label="Document zoom"
                            />
                            <span>{zoom}%</span>
                            <ZoomIn className="h-4 w-4" />
                        </div>
                        <div
                            className="document-paper-transform"
                            style={{ transform: `scale(${zoom / 100})`, transformOrigin: "top center" }}
                        >
                            {activeDocument.cover_page_enabled && (
                                <DocumentCoverPreview
                                    document={activeDocument}
                                    logoUrl={brandLogoUrl}
                                    widthMm={width}
                                    heightMm={minHeight}
                                    theme={theme}
                                />
                            )}
                            <div
                                className={`document-paper document-theme-${activeDocument.style_key}`}
                                style={
                                    {
                                        width: `${width}mm`,
                                        minHeight: `${minHeight}mm`,
                                        padding: `${activeDocument.margin_top_mm}mm ${activeDocument.margin_right_mm}mm ${activeDocument.margin_bottom_mm}mm ${activeDocument.margin_left_mm}mm`,
                                        fontFamily: activeDocument.default_font_family,
                                        fontSize: `${activeDocument.default_font_size_pt}pt`,
                                        lineHeight: activeDocument.default_line_height_percent / 100,
                                        "--document-accent": theme.accent,
                                        "--document-heading": theme.heading,
                                        "--document-soft": theme.soft,
                                        "--document-ink": theme.ink,
                                    } as React.CSSProperties
                                }
                                onDragOver={(event) => {
                                    if (event.dataTransfer.types.includes(SIGNATURE_FIELD_MIME)) {
                                        event.preventDefault();
                                        event.dataTransfer.dropEffect = "copy";
                                    }
                                }}
                                onDrop={handleDrop}
                            >
                                {activeDocument.include_brand_header && (
                                    <header className="document-letter-header">
                                        <div className="document-header-logo document-header-logo-left">
                                            <img src="/loanhub-horizontal-logo.png" alt="LoanHub" />
                                        </div>

                                        <div className="document-company-header-info">
                                            <p className="document-company-name">{activeDocument.company_header.name}</p>
                                            {(activeDocument.company_header.registration_number || activeDocument.company_header.license_number) && (
                                                <p>
                                                    {activeDocument.company_header.registration_number && `Registration: ${activeDocument.company_header.registration_number}`}
                                                    {activeDocument.company_header.registration_number && activeDocument.company_header.license_number && " · "}
                                                    {activeDocument.company_header.license_number && `Licence: ${activeDocument.company_header.license_number}`}
                                                </p>
                                            )}
                                            {(activeDocument.company_header.phone || activeDocument.company_header.email || activeDocument.company_header.website) && (
                                                <p>
                                                    {[activeDocument.company_header.phone, activeDocument.company_header.email, activeDocument.company_header.website]
                                                        .filter(Boolean)
                                                        .join(" · ")}
                                                </p>
                                            )}
                                            {(activeDocument.company_header.address || activeDocument.company_header.district) && (
                                                <p>
                                                    {[activeDocument.company_header.address, activeDocument.company_header.district]
                                                        .filter(Boolean)
                                                        .join(" · ")}
                                                </p>
                                            )}
                                        </div>

                                        <div className="document-header-logo document-header-logo-right">
                                            {brandLogoUrl && (
                                                <img className="document-writer-logo" src={brandLogoUrl} alt={`${activeDocument.company_header.name} logo`} />
                                            )}
                                        </div>
                                    </header>
                                )}
                                <DocumentAddressOverlay
                                    blocks={activeDocument.address_blocks}
                                    pageWidthMm={width}
                                    pageHeightMm={minHeight}
                                    editable={activeDocument.can_edit}
                                    onChange={updateAddressBlocksLocally}
                                    onCommit={(blocks) => void commitAddressBlocks(blocks)}
                                />
                                <SignaturePreviewContext.Provider
                                    value={{
                                        signatures: signaturePreviewEntries,
                                        canSign: activeDocument.status !== "archived" && (activeDocument.can_edit || activeDocument.can_manage),
                                        canRevoke: activeDocument.can_manage && activeDocument.status !== "archived",
                                        onSign: openSignDialog,
                                        onRevoke: (fieldId) => void revokeSignature(fieldId),
                                    }}
                                >
                                    <EditorContent editor={activeEditor} />
                                </SignaturePreviewContext.Provider>
                                {activeDocument.include_footer && (
                                    <footer className="document-letter-footer">
                                        <span>
                                            {activeDocument.is_confidential ? "CONFIDENTIAL · " : ""}
                                            {activeDocument.reference}
                                        </span>
                                        <span>LoanHub Document Studio</span>
                                    </footer>
                                )}
                            </div>
                        </div>
                    </div>

                    <aside className="document-inspector">
                        {historyOpen && (
                            <section className="document-inspector-card">
                                <div className="flex items-center justify-between gap-3">
                                    <h2><Clock3 /> Revision history</h2>
                                    <button type="button" onClick={() => setHistoryOpen(false)}>Close</button>
                                </div>
                                <div className="mt-3 max-h-56 space-y-2 overflow-auto">
                                    {revisions.map((revision) => (
                                        <div key={revision.id} className="rounded-xl border bg-muted/20 p-3">
                                            <div className="flex items-center justify-between gap-3">
                                                <strong>Version {revision.version}</strong>
                                                <span>{new Date(revision.created_at).toLocaleString()}</span>
                                            </div>
                                            <p>{revision.title}</p>
                                        </div>
                                    ))}
                                    {revisions.length === 0 && <p className="text-xs text-muted-foreground">No revision checkpoints yet.</p>}
                                </div>
                            </section>
                        )}

                        <section className="document-inspector-card">
                            <h2><FileText /> Document</h2>
                            <div className="mt-4 space-y-4 text-sm">
                                <label className="block">
                                    <span className="document-setting-label">Visibility</span>
                                    <NativeSelect
                                        value={activeDocument.visibility}
                                        disabled={!activeDocument.can_manage}
                                        onChange={(event) => void changeSettings({ visibility: event.target.value as DocumentVisibility })}
                                        className="h-10 w-full rounded-xl border bg-background px-3"
                                    >
                                        <option value="private">Private</option>
                                        {activeDocument.company_id && <option value="company">Company</option>}
                                        {(mode === "superadmin" || mode === "platform") && <option value="platform">Platform team</option>}
                                    </NativeSelect>
                                </label>
                                <label className="block">
                                    <span className="document-setting-label">Status</span>
                                    <NativeSelect
                                        value={activeDocument.status}
                                        disabled={!activeDocument.can_manage}
                                        onChange={(event) => void changeSettings({ status: event.target.value as DocumentStatus })}
                                        className="h-10 w-full rounded-xl border bg-background px-3"
                                    >
                                        <option value="draft">Draft</option>
                                        <option value="final">Final</option>
                                        <option value="archived">Archived</option>
                                    </NativeSelect>
                                </label>
                                <ToggleSetting label="Brand header" checked={activeDocument.include_brand_header} disabled={!activeDocument.can_edit} onChange={(value) => void changeSettings({ include_brand_header: value })} />
                                <ToggleSetting label="Page footer" checked={activeDocument.include_footer} disabled={!activeDocument.can_edit} onChange={(value) => void changeSettings({ include_footer: value })} />
                                <ToggleSetting label="Confidential" checked={activeDocument.is_confidential} disabled={!activeDocument.can_manage} onChange={(value) => void changeSettings({ is_confidential: value })} />
                            </div>
                        </section>

                        <section className="document-inspector-card">
                            <h2><Stamp /> Document tools</h2>
                            <div className="mt-3 grid gap-2">
                                <Button type="button" variant="outline" size="sm" disabled={!activeDocument.can_manage} onClick={() => { void refreshAssets(); setBrandingOpen(true); }}><ImagePlus /> Branding</Button>
                                <Button type="button" variant="outline" size="sm" onClick={() => setCoverOpen(true)} disabled={!activeDocument.can_edit}><BookOpen /> Cover page</Button>
                                <Button type="button" variant="outline" size="sm" onClick={() => setAddressesOpen(true)} disabled={!activeDocument.can_edit}><MapPin /> Addresses ({activeDocument.address_blocks.length})</Button>
                                <Button type="button" variant="outline" size="sm" onClick={() => { void refreshAssets(); setSignatureVaultOpen(true); }}><PenLine /> Signature vault ({signatureAssets.length})</Button>
                            </div>
                        </section>

                        <section className="document-inspector-card">
                            <h2><ShieldCheck /> Document statistics</h2>
                            <div className="document-stat-grid">
                                <Stat value={statistics.words} label="Words" />
                                <Stat value={statistics.characters} label="Characters" />
                                <Stat value={statistics.paragraphs} label="Blocks" />
                                <Stat value={statistics.fields} label="Signature fields" />
                            </div>
                        </section>

                        <section className="document-inspector-card">
                            <h2><Share2 /> Publish to library</h2>
                            <p className="mt-1 text-xs leading-5 text-muted-foreground">
                                Create a controlled Word or PDF copy, then share it through chat or a secure external link.
                            </p>
                            <div className="mt-4 grid gap-2">
                                <Button type="button" variant="outline" onClick={() => void publish("docx")} disabled={Boolean(publishing)}>
                                    {publishing === "docx" ? <Loader2 className="animate-spin" /> : <FileText />} Save Word to library
                                </Button>
                                <Button type="button" variant="outline" onClick={() => void publish("pdf")} disabled={Boolean(publishing)}>
                                    {publishing === "pdf" ? <Loader2 className="animate-spin" /> : <FileDown />} Save PDF to library
                                </Button>
                            </div>
                        </section>

                        {!activeDocument.can_edit && (
                            <section className="rounded-3xl border border-amber-300 bg-amber-50 p-5 text-amber-900 dark:bg-amber-950/20 dark:text-amber-200">
                                <p className="flex items-center gap-2 font-black"><LockKeyhole className="h-4 w-4" /> View-only document</p>
                                <p className="mt-1 text-xs leading-5">You can read, print and export this document, but cannot change it.</p>
                            </section>
                        )}
                    </aside>
                </section>
            </main>
        );
    }

    return (
        <>
            {!fullscreenOpen && renderStudio(false)}
            <Dialog open={fullscreenOpen} onOpenChange={setFullscreenOpen}>
                <DialogContent
                    showCloseButton={false}
                    className="!left-0 !top-0 !flex !h-dvh !max-h-dvh !w-screen !max-w-none !translate-x-0 !translate-y-0 !flex-col !gap-0 !overflow-hidden !rounded-none !border-0 !bg-background !p-0"
                >
                    <DialogTitle className="sr-only">Full screen LoanHub document editor</DialogTitle>
                    <DialogDescription className="sr-only">Edit the current document using the full browser window.</DialogDescription>
                    {renderStudio(true)}
                </DialogContent>
            </Dialog>

            <DocumentSharingDialog document={activeDocument} open={shareOpen} onOpenChange={setShareOpen} />
            <ExternalFileShareDialog
                file={publishedFile}
                open={Boolean(publishedFile)}
                onOpenChange={(open) => !open && setPublishedFile(null)}
                settingsPath={mode === "company" ? "/company/settings" : basePath}
            />
            <BrandingDialog
                open={brandingOpen}
                onOpenChange={setBrandingOpen}
                assets={logoAssets}
                activeAssetId={activeDocument.brand_logo_asset_id}
                busy={assetBusy}
                onUpload={handleLogoUpload}
                onSelect={selectBrandLogo}
                onDelete={removeAsset}
            />
            <SignatureVaultDialog
                open={signatureVaultOpen}
                onOpenChange={setSignatureVaultOpen}
                assets={signatureAssets}
                busy={assetBusy}
                onUpload={handleSignatureUpload}
                onDelete={removeAsset}
            />
            <SignDocumentDialog
                target={signTarget}
                onOpenChange={(open) => !open && setSignTarget(null)}
                assets={signatureAssets}
                method={signMethod}
                onMethodChange={setSignMethod}
                assetId={signAssetId}
                onAssetChange={setSignAssetId}
                consent={signConsent}
                onConsentChange={setSignConsent}
                signing={signing}
                onSubmit={() => void applySignature()}
                onOpenVault={() => { setSignTarget(null); void refreshAssets(); setSignatureVaultOpen(true); }}
            />
            <AddressBlocksDialog
                open={addressesOpen}
                onOpenChange={setAddressesOpen}
                blocks={activeDocument.address_blocks}
                onSave={(blocks) => void saveAddressBlocks(blocks)}
            />
            <CoverPageDialog
                open={coverOpen}
                onOpenChange={setCoverOpen}
                enabled={activeDocument.cover_page_enabled}
                cover={activeDocument.cover_page}
                onSave={(enabled, cover) => void saveCoverPage(enabled, cover)}
            />
        </>
    );
}


function AssetPreview({ asset, className = "" }: { asset: WorkspaceDocumentAsset; className?: string }) {
    const [url, setUrl] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        let objectUrl: string | null = null;
        void getWorkspaceAssetObjectUrl(asset.id)
            .then((next) => {
                objectUrl = next;
                if (!cancelled) setUrl(next);
            })
            .catch(() => setUrl(null));
        return () => {
            cancelled = true;
            if (objectUrl) URL.revokeObjectURL(objectUrl);
        };
    }, [asset.id]);

    return (
        <div className={`document-asset-preview ${className}`}>
            {url ? <img src={url} alt={asset.label} /> : <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />}
        </div>
    );
}

function BrandingDialog({
    open,
    onOpenChange,
    assets,
    activeAssetId,
    busy,
    onUpload,
    onSelect,
    onDelete,
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    assets: WorkspaceDocumentAsset[];
    activeAssetId: string | null;
    busy: boolean;
    onUpload: (file: File, label: string) => Promise<void>;
    onSelect: (assetId: string | null) => Promise<void>;
    onDelete: (asset: WorkspaceDocumentAsset) => Promise<void>;
}) {
    const inputRef = useRef<HTMLInputElement | null>(null);
    const [label, setLabel] = useState("My organisation logo");

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-3xl">
                <DialogTitle>Document branding</DialogTitle>
                <DialogDescription>
                    Upload a transparent PNG, JPG or WebP logo. The newest upload becomes your default document logo and replaces the title/reference text in the page header wherever a document follows your default branding.
                </DialogDescription>
                <div className="grid gap-5 md:grid-cols-[280px_1fr]">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">Upload logo</CardTitle>
                            <CardDescription>LoanHub normalises the image to a clean PNG for PDF, Word and print output.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            <Label htmlFor="document-logo-label">Logo label</Label>
                            <Input id="document-logo-label" value={label} onChange={(event) => setLabel(event.target.value)} />
                            <input
                                ref={inputRef}
                                hidden
                                type="file"
                                accept="image/png,image/jpeg,image/webp"
                                onChange={(event) => {
                                    const file = event.target.files?.[0];
                                    if (file) void onUpload(file, label);
                                    event.currentTarget.value = "";
                                }}
                            />
                            <Button className="w-full" type="button" disabled={busy} onClick={() => inputRef.current?.click()}>
                                {busy ? <Loader2 className="animate-spin" /> : <ImagePlus />} Upload and use everywhere
                            </Button>
                            <Button className="w-full" type="button" variant="outline" onClick={() => void onSelect(null)}>
                                Follow my default logo
                            </Button>
                        </CardContent>
                    </Card>
                    <ScrollArea className="h-[360px] pr-3">
                        <div className="grid gap-3 sm:grid-cols-2">
                            {assets.map((asset) => (
                                <Card key={asset.id} className={activeAssetId === asset.id ? "ring-2 ring-primary" : ""}>
                                    <CardContent className="p-3">
                                        <AssetPreview asset={asset} className="h-24" />
                                        <div className="mt-3 flex items-start justify-between gap-2">
                                            <div className="min-w-0">
                                                <p className="truncate text-sm font-black">{asset.label}</p>
                                                <p className="text-xs text-muted-foreground">{asset.width_px}×{asset.height_px}{asset.is_default ? " · Default" : ""}</p>
                                            </div>
                                            <Button type="button" variant="ghost" size="icon" onClick={() => void onDelete(asset)} title="Remove logo">
                                                <Trash2 />
                                            </Button>
                                        </div>
                                        <Button className="mt-2 w-full" type="button" size="sm" variant={activeAssetId === asset.id ? "secondary" : "outline"} onClick={() => void onSelect(asset.id)}>
                                            {activeAssetId === asset.id ? "In use" : "Use this logo"}
                                        </Button>
                                    </CardContent>
                                </Card>
                            ))}
                            {assets.length === 0 && (
                                <div className="col-span-full rounded-2xl border border-dashed p-8 text-center text-sm text-muted-foreground">
                                    No uploaded logos yet.
                                </div>
                            )}
                        </div>
                    </ScrollArea>
                </div>
            </DialogContent>
        </Dialog>
    );
}

function SignatureVaultDialog({
    open,
    onOpenChange,
    assets,
    busy,
    onUpload,
    onDelete,
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    assets: WorkspaceDocumentAsset[];
    busy: boolean;
    onUpload: (file: File, label: string) => Promise<void>;
    onDelete: (asset: WorkspaceDocumentAsset) => Promise<void>;
}) {
    const inputRef = useRef<HTMLInputElement | null>(null);
    const [label, setLabel] = useState("My signature");

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-3xl">
                <DialogTitle>Private signature vault</DialogTitle>
                <DialogDescription>
                    Upload a photograph or scan of your signature. FastAPI removes the paper background, crops the ink and stores a reusable PNG. This processing does not perform biometric identity verification.
                </DialogDescription>
                <div className="grid gap-5 md:grid-cols-[280px_1fr]">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">Add signature image</CardTitle>
                            <CardDescription>For best results, sign dark ink on clean white paper and photograph it in good light.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            <Label htmlFor="signature-label">Signature label</Label>
                            <Input id="signature-label" value={label} onChange={(event) => setLabel(event.target.value)} />
                            <input
                                ref={inputRef}
                                hidden
                                type="file"
                                accept="image/png,image/jpeg,image/webp"
                                onChange={(event) => {
                                    const file = event.target.files?.[0];
                                    if (file) void onUpload(file, label);
                                    event.currentTarget.value = "";
                                }}
                            />
                            <Button className="w-full" type="button" disabled={busy} onClick={() => inputRef.current?.click()}>
                                {busy ? <Loader2 className="animate-spin" /> : <PenLine />} Process signature image
                            </Button>
                        </CardContent>
                    </Card>
                    <ScrollArea className="h-[360px] pr-3">
                        <div className="grid gap-3 sm:grid-cols-2">
                            {assets.map((asset) => (
                                <Card key={asset.id}>
                                    <CardContent className="p-3">
                                        <AssetPreview asset={asset} className="h-24 document-signature-asset-preview" />
                                        <div className="mt-3 flex items-start justify-between gap-2">
                                            <div>
                                                <p className="text-sm font-black">{asset.label}</p>
                                                <p className="text-xs text-muted-foreground">{asset.is_default ? "Default signature" : "Stored signature"}</p>
                                            </div>
                                            <Button type="button" variant="ghost" size="icon" onClick={() => void onDelete(asset)} title="Remove signature">
                                                <Trash2 />
                                            </Button>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                            {assets.length === 0 && <div className="col-span-full rounded-2xl border border-dashed p-8 text-center text-sm text-muted-foreground">No stored signatures yet.</div>}
                        </div>
                    </ScrollArea>
                </div>
            </DialogContent>
        </Dialog>
    );
}

function SignDocumentDialog({
    target,
    onOpenChange,
    assets,
    method,
    onMethodChange,
    assetId,
    onAssetChange,
    consent,
    onConsentChange,
    signing,
    onSubmit,
    onOpenVault,
}: {
    target: { fieldId: string; fieldType: SignatureFieldType; label: string } | null;
    onOpenChange: (open: boolean) => void;
    assets: WorkspaceDocumentAsset[];
    method: DocumentSignatureMethod;
    onMethodChange: (method: DocumentSignatureMethod) => void;
    assetId: string;
    onAssetChange: (assetId: string) => void;
    consent: string;
    onConsentChange: (value: string) => void;
    signing: boolean;
    onSubmit: () => void;
    onOpenVault: () => void;
}) {
    const [accepted, setAccepted] = useState(false);
    useEffect(() => setAccepted(false), [target?.fieldId]);

    return (
        <Dialog open={Boolean(target)} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-2xl">
                <DialogTitle>Sign {target?.label || "document field"}</DialogTitle>
                <DialogDescription>
                    Choose a stored signature image or create an electronic signature backed by your authenticated LoanHub account and an audit record.
                </DialogDescription>
                <div className="grid grid-cols-2 gap-2">
                    <Button type="button" variant={method === "stored_signature" ? "default" : "outline"} onClick={() => onMethodChange("stored_signature")}><PenLine /> Stored signature</Button>
                    <Button type="button" variant={method === "electronic" ? "default" : "outline"} onClick={() => onMethodChange("electronic")}><Stamp /> Electronic signature</Button>
                </div>
                {method === "stored_signature" ? (
                    <div className="space-y-3">
                        <div className="grid gap-3 sm:grid-cols-2">
                            {assets.map((asset) => (
                                <button key={asset.id} type="button" className={`document-signature-choice ${assetId === asset.id ? "is-active" : ""}`} onClick={() => onAssetChange(asset.id)}>
                                    <AssetPreview asset={asset} className="h-20" />
                                    <strong>{asset.label}</strong>
                                    <small>{asset.is_default ? "Default" : "Stored"}</small>
                                </button>
                            ))}
                        </div>
                        {assets.length === 0 && <Button type="button" variant="outline" onClick={onOpenVault}><PenLine /> Upload a signature first</Button>}
                    </div>
                ) : (
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">Authenticated electronic signature</CardTitle>
                            <CardDescription>Your name, timestamp, document version/hash and a verification code are stored with this signature.</CardDescription>
                        </CardHeader>
                    </Card>
                )}
                <div className="space-y-2">
                    <Label htmlFor="signature-consent">Signature intent</Label>
                    <Textarea id="signature-consent" value={consent} onChange={(event) => onConsentChange(event.target.value)} rows={3} />
                    <label className="flex items-start gap-3 rounded-xl border p-3 text-sm">
                        <Checkbox checked={accepted} onCheckedChange={(value) => setAccepted(value === true)} />
                        <span>I have reviewed this document and intentionally apply this signature to the selected field.</span>
                    </label>
                </div>
                <div className="flex justify-end gap-2">
                    <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
                    <Button type="button" disabled={signing || !accepted || consent.trim().length < 10 || (method === "stored_signature" && !assetId)} onClick={onSubmit}>
                        {signing ? <Loader2 className="animate-spin" /> : <Stamp />} Apply signature
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
}

function AddressBlocksDialog({
    open,
    onOpenChange,
    blocks,
    onSave,
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    blocks: DocumentAddressBlock[];
    onSave: (blocks: DocumentAddressBlock[]) => void;
}) {
    const [draft, setDraft] = useState<DocumentAddressBlock[]>(blocks);
    useEffect(() => { if (open) setDraft(blocks); }, [blocks, open]);

    function addBlock() {
        setDraft((current) => [
            ...current,
            {
                id: createUuid(), label: `Address ${current.length + 1}`, content: "",
                x_mm: 22, y_mm: 48 + current.length * 30, width_mm: 72,
                font_size_pt: 9, alignment: "left", show_label: true, first_page_only: true,
            },
        ]);
    }

    function update(id: string, values: Partial<DocumentAddressBlock>) {
        setDraft((current) => current.map((item) => item.id === id ? { ...item, ...values } : item));
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-4xl">
                <DialogTitle>Positioned address blocks</DialogTitle>
                <DialogDescription>
                    Add as many sender, recipient, department or legal addresses as needed. Set precise coordinates here, then drag each address directly on the document page to fine-tune its X/Y position.
                </DialogDescription>
                <ScrollArea className="max-h-[65vh] pr-3">
                    <div className="space-y-3">
                        {draft.map((block, index) => (
                            <Card key={block.id}>
                                <CardHeader className="pb-3">
                                    <div className="flex items-center justify-between gap-3">
                                        <CardTitle className="text-base">Address {index + 1}</CardTitle>
                                        <Button type="button" size="icon" variant="ghost" onClick={() => setDraft((current) => current.filter((item) => item.id !== block.id))}><Trash2 /></Button>
                                    </div>
                                </CardHeader>
                                <CardContent className="grid gap-3 md:grid-cols-2">
                                    <label><Label>Label</Label><Input value={block.label} onChange={(event) => update(block.id, { label: event.target.value })} /></label>
                                    <label><Label>Alignment</Label><NativeSelect className="h-10 w-full rounded-md border bg-background px-3" value={block.alignment} onChange={(event) => update(block.id, { alignment: event.target.value as DocumentAddressBlock["alignment"] })}><option value="left">Left</option><option value="center">Center</option><option value="right">Right</option></NativeSelect></label>
                                    <label className="md:col-span-2"><Label>Address</Label><Textarea rows={4} value={block.content} onChange={(event) => update(block.id, { content: event.target.value })} placeholder={"Recipient name\nCompany\nStreet / village\nDistrict / postal code"} /></label>
                                    <div className="grid grid-cols-3 gap-2 md:col-span-2">
                                        <label><Label>X (mm)</Label><Input type="number" value={block.x_mm} onChange={(event) => update(block.id, { x_mm: Number(event.target.value) })} /></label>
                                        <label><Label>Y (mm)</Label><Input type="number" value={block.y_mm} onChange={(event) => update(block.id, { y_mm: Number(event.target.value) })} /></label>
                                        <label><Label>Width (mm)</Label><Input type="number" value={block.width_mm} onChange={(event) => update(block.id, { width_mm: Number(event.target.value) })} /></label>
                                    </div>
                                    <label className="flex items-center gap-2"><Checkbox checked={block.show_label} onCheckedChange={(value) => update(block.id, { show_label: value === true })} /> Show label</label>
                                    <label className="flex items-center gap-2"><Checkbox checked={block.first_page_only} onCheckedChange={(value) => update(block.id, { first_page_only: value === true })} /> First page only</label>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </ScrollArea>
                <div className="flex flex-wrap justify-between gap-2">
                    <Button type="button" variant="outline" onClick={addBlock}><MapPin /> Add address</Button>
                    <div className="flex gap-2"><Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button><Button type="button" onClick={() => onSave(draft)}>Save addresses</Button></div>
                </div>
            </DialogContent>
        </Dialog>
    );
}

function CoverPageDialog({
    open,
    onOpenChange,
    enabled,
    cover,
    onSave,
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    enabled: boolean;
    cover: DocumentCoverPage;
    onSave: (enabled: boolean, cover: DocumentCoverPage) => void;
}) {
    const [isEnabled, setIsEnabled] = useState(enabled);
    const [draft, setDraft] = useState<DocumentCoverPage>(cover);
    useEffect(() => {
        if (open) { setIsEnabled(enabled); setDraft(cover); }
    }, [cover, enabled, open]);

    function update(values: Partial<DocumentCoverPage>) { setDraft((current) => ({ ...current, ...values })); }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-3xl">
                <DialogTitle>Cover page</DialogTitle>
                <DialogDescription>Add a professional first page for proposals, reports, contracts, CV portfolios and other formal documents.</DialogDescription>
                <label className="flex items-center justify-between rounded-2xl border bg-muted/20 p-4">
                    <span><strong className="block">Include cover page</strong><small className="text-muted-foreground">The body starts on the following page.</small></span>
                    <Checkbox checked={isEnabled} onCheckedChange={(value) => setIsEnabled(value === true)} />
                </label>
                <div className="grid gap-3 md:grid-cols-2">
                    <label className="md:col-span-2"><Label>Title</Label><Input value={draft.title} onChange={(event) => update({ title: event.target.value })} /></label>
                    <label className="md:col-span-2"><Label>Subtitle</Label><Input value={draft.subtitle} onChange={(event) => update({ subtitle: event.target.value })} /></label>
                    <label><Label>Prepared for</Label><Input value={draft.prepared_for} onChange={(event) => update({ prepared_for: event.target.value })} /></label>
                    <label><Label>Prepared by</Label><Input value={draft.prepared_by} onChange={(event) => update({ prepared_by: event.target.value })} /></label>
                    <label><Label>Date</Label><Input value={draft.document_date} onChange={(event) => update({ document_date: event.target.value })} /></label>
                    <label><Label>Version / edition</Label><Input value={draft.version_label} onChange={(event) => update({ version_label: event.target.value })} /></label>
                    <label className="md:col-span-2"><Label>Confidentiality note</Label><Input value={draft.confidentiality_note} onChange={(event) => update({ confidentiality_note: event.target.value })} /></label>
                    <label className="flex items-center gap-2"><Checkbox checked={draft.show_logo} onCheckedChange={(value) => update({ show_logo: value === true })} /> Show logo</label>
                    <label className="flex items-center gap-2"><Checkbox checked={draft.show_reference} onCheckedChange={(value) => update({ show_reference: value === true })} /> Show document reference</label>
                </div>
                <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button><Button type="button" onClick={() => onSave(isEnabled, draft)}>Save cover page</Button></div>
            </DialogContent>
        </Dialog>
    );
}

function DocumentCoverPreview({
    document,
    logoUrl,
    widthMm,
    heightMm,
    theme,
}: {
    document: WorkspaceDocument;
    logoUrl: string | null;
    widthMm: number;
    heightMm: number;
    theme: { accent: string; heading: string; soft: string; ink: string };
}) {
    const cover = document.cover_page;
    return (
        <div
            className={`document-paper document-cover-page document-theme-${document.style_key}`}
            style={{
                width: `${widthMm}mm`, minHeight: `${heightMm}mm`,
                "--document-accent": theme.accent, "--document-heading": theme.heading,
                "--document-soft": theme.soft, "--document-ink": theme.ink,
            } as React.CSSProperties}
        >
            <div className="document-cover-accent" />
            {cover.show_logo && <div className="document-cover-logo">{logoUrl ? <img src={logoUrl} alt="Document logo" /> : <img src="/loanhub-horizontal-logo.png" alt="LoanHub" />}</div>}
            <div className="document-cover-main">
                <span className="document-cover-kicker">LoanHub Document Studio</span>
                <h1>{cover.title || document.title}</h1>
                {cover.subtitle && <p className="document-cover-subtitle">{cover.subtitle}</p>}
                <Separator />
                <dl>
                    {cover.prepared_for && <div><dt>Prepared for</dt><dd>{cover.prepared_for}</dd></div>}
                    {cover.prepared_by && <div><dt>Prepared by</dt><dd>{cover.prepared_by}</dd></div>}
                    {cover.document_date && <div><dt>Date</dt><dd>{cover.document_date}</dd></div>}
                    {cover.version_label && <div><dt>Version</dt><dd>{cover.version_label}</dd></div>}
                </dl>
            </div>
            <div className="document-cover-footer">
                <span>{cover.confidentiality_note || (document.is_confidential ? "CONFIDENTIAL" : "")}</span>
                {cover.show_reference && <span>{document.reference}</span>}
            </div>
        </div>
    );
}

function stripLegacyFilizwaPlaceholderHeader(value: string): string {
    if (
        !value.includes("[LEFT LOGO]") ||
        !value.includes("[COMPANY NAME]") ||
        !value.includes("[RIGHT LOGO]")
    ) {
        return value;
    }

    const parsed = new DOMParser().parseFromString(`<div id="loanhub-document-root">${value}</div>`, "text/html");
    const root = parsed.getElementById("loanhub-document-root");
    if (!root) return value;

    root.querySelectorAll("table").forEach((table) => {
        const text = (table.textContent || "").replace(/\s+/g, " ").trim();
        if (
            text.includes("[LEFT LOGO]") &&
            text.includes("[COMPANY NAME]") &&
            text.includes("[RIGHT LOGO]")
        ) {
            table.remove();
        }
    });

    return root.innerHTML;
}

function SaveIndicator({ state, version }: { state: SaveState; version: number }) {
    const config = {
        saved: { label: `Saved · v${version}`, icon: Check, className: "text-emerald-700" },
        unsaved: { label: "Unsaved changes", icon: MoreVertical, className: "text-amber-700" },
        saving: { label: "Saving...", icon: Loader2, className: "text-primary" },
        error: { label: "Save failed", icon: MoreVertical, className: "text-red-600" },
        loading: { label: "Loading...", icon: Loader2, className: "text-muted-foreground" },
    }[state];
    const Icon = config.icon;
    return (
        <span className={`inline-flex items-center gap-1.5 rounded-full bg-muted px-3 py-1.5 text-xs font-black ${config.className}`}>
            <Icon className={`h-3.5 w-3.5 ${state === "saving" || state === "loading" ? "animate-spin" : ""}`} />
            {config.label}
        </span>
    );
}

function ToggleSetting({
    label,
    checked,
    disabled,
    onChange,
}: {
    label: string;
    checked: boolean;
    disabled?: boolean;
    onChange: (value: boolean) => void;
}) {
    return (
        <label className="flex items-center justify-between gap-3">
            <span className="font-bold">{label}</span>
            <input
                type="checkbox"
                checked={checked}
                disabled={disabled}
                onChange={(event) => onChange(event.target.checked)}
                className="h-4 w-4 accent-primary"
            />
        </label>
    );
}

function Stat({ value, label }: { value: number; label: string }) {
    return (
        <div>
            <strong>{value.toLocaleString()}</strong>
            <span>{label}</span>
        </div>
    );
}
