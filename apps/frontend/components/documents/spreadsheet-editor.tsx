"use client";

import Link from "next/link";
import {
    useCallback,
    useEffect,
    useMemo,
    useRef,
    useState,
    type CSSProperties,
} from "react";
import {
    AlignCenter,
    AlignLeft,
    AlignRight,
    Bold,
    ChevronLeft,
    ChevronRight,
    Download,
    FileSpreadsheet,
    Italic,
    Loader2,
    Maximize2,
    Minimize2,
    Plus,
    Redo2,
    RefreshCcw,
    Save,
    Sheet,
    Trash2,
    Underline,
    Undo2,
    UploadCloud,
} from "lucide-react";

import { getWorkspaceDocument } from "@/api/workspaceDocuments";
import {
    downloadWorkspaceSpreadsheet,
    publishWorkspaceSpreadsheet,
    refreshWorkspaceSpreadsheetData,
    saveWorkspaceSpreadsheet,
} from "@/api/workspaceSpreadsheets";
import type { WorkspaceDocument } from "@/types/workspaceDocuments";
import type {
    SpreadsheetCell,
    SpreadsheetCellStyle,
    SpreadsheetExportFormat,
    SpreadsheetSheet,
    SpreadsheetWorkbook,
} from "@/types/workspaceSpreadsheets";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

const PAGE_ROWS = 60;
const PAGE_COLUMNS = 24;
const MAX_ROWS = 5000;
const MAX_COLUMNS = 200;
const DEFAULT_COLUMN_WIDTH = 14;
const DEFAULT_ROW_HEIGHT = 30;
const DATABASE_TEMPLATES = new Set([
    "spreadsheet_loan_portfolio",
    "spreadsheet_cashbook",
    "spreadsheet_collections",
]);

type CellPosition = { column: number; row: number };
type Bounds = { minRow: number; maxRow: number; minColumn: number; maxColumn: number };
type ResizeState = {
    kind: "column" | "row";
    index: number;
    start: number;
    initial: number;
};

function columnName(index: number): string {
    let value = index;
    let output = "";
    while (value > 0) {
        const remainder = (value - 1) % 26;
        output = String.fromCharCode(65 + remainder) + output;
        value = Math.floor((value - 1) / 26);
    }
    return output;
}

function columnIndex(name: string): number {
    return name
        .toUpperCase()
        .split("")
        .reduce((total, character) => total * 26 + character.charCodeAt(0) - 64, 0);
}

function parseReference(reference: string): CellPosition {
    const match = /^([A-Z]+)(\d+)$/i.exec(reference.trim());
    return match
        ? { column: columnIndex(match[1]), row: Number(match[2]) }
        : { column: 1, row: 1 };
}

function referenceFor(position: CellPosition): string {
    return `${columnName(position.column)}${position.row}`;
}

function selectedBounds(startReference: string, endReference: string): Bounds {
    const start = parseReference(startReference);
    const end = parseReference(endReference);
    return {
        minRow: Math.min(start.row, end.row),
        maxRow: Math.max(start.row, end.row),
        minColumn: Math.min(start.column, end.column),
        maxColumn: Math.max(start.column, end.column),
    };
}

function referencesInRange(startReference: string, endReference: string): string[] {
    const bounds = selectedBounds(startReference, endReference);
    const references: string[] = [];
    for (let row = bounds.minRow; row <= bounds.maxRow; row += 1) {
        for (let column = bounds.minColumn; column <= bounds.maxColumn; column += 1) {
            references.push(`${columnName(column)}${row}`);
        }
    }
    return references;
}

function rangeLabel(startReference: string, endReference: string): string {
    if (startReference === endReference) return startReference;
    const bounds = selectedBounds(startReference, endReference);
    return `${referenceFor({ column: bounds.minColumn, row: bounds.minRow })}:${referenceFor({ column: bounds.maxColumn, row: bounds.maxRow })}`;
}

function rawValue(cell: SpreadsheetCell | undefined): string {
    if (!cell) return "";
    if (cell.formula) return cell.formula;
    return cell.value === null || cell.value === undefined ? "" : String(cell.value);
}

function parsedCell(value: string, existing?: SpreadsheetCell): SpreadsheetCell {
    if (value.startsWith("=")) {
        return { value, formula: value, style: existing?.style };
    }
    const trimmed = value.trim();
    let parsed: string | number | boolean | null = value;
    if (!trimmed) parsed = null;
    else if (/^-?(?:\d+\.?\d*|\.\d+)$/.test(trimmed)) parsed = Number(trimmed);
    else if (/^(true|false)$/i.test(trimmed)) parsed = trimmed.toLowerCase() === "true";
    return { value: parsed, style: existing?.style };
}

function normaliseClientWorkbook(value: unknown): SpreadsheetWorkbook {
    const candidate = value as SpreadsheetWorkbook | undefined;
    if (candidate?.sheets?.length) return candidate;
    return {
        format_version: 1,
        active_sheet: "Sheet1",
        sheets: [
            {
                id: "sheet-1",
                name: "Sheet1",
                row_count: 40,
                column_count: 12,
                cells: {},
                column_widths: {},
                row_heights: {},
                merges: [],
                freeze_panes: null,
            },
        ],
    };
}

function styleForCell(style?: SpreadsheetCellStyle): CSSProperties {
    return {
        fontWeight: style?.bold ? 700 : undefined,
        fontStyle: style?.italic ? "italic" : undefined,
        textDecoration: style?.underline ? "underline" : undefined,
        textAlign:
            style?.horizontal === "center" || style?.horizontal === "right"
                ? style.horizontal
                : "left",
        color: style?.font_color || undefined,
        backgroundColor: style?.fill_color || undefined,
        whiteSpace: style?.wrap ? "normal" : "nowrap",
        overflow: "hidden",
        textOverflow: style?.wrap ? undefined : "ellipsis",
    };
}

function rangeNumbers(sheet: SpreadsheetSheet, token: string, seen: Set<string>): number[] {
    const [start, end] = token.toUpperCase().split(":");
    if (!end) return [numericCell(sheet, start, new Set(seen))];
    return referencesInRange(start, end).map((reference) =>
        numericCell(sheet, reference, new Set(seen)),
    );
}

function numericCell(sheet: SpreadsheetSheet, reference: string, seen = new Set<string>()): number {
    if (seen.has(reference)) return 0;
    seen.add(reference);
    const cell = sheet.cells[reference];
    if (!cell) return 0;
    if (!cell.formula) return Number(cell.value) || 0;
    const evaluated = evaluateFormula(sheet, cell.formula, seen);
    return typeof evaluated === "number" && Number.isFinite(evaluated) ? evaluated : 0;
}

function operandValue(sheet: SpreadsheetSheet, token: string, seen: Set<string>): number {
    const clean = token.trim().toUpperCase();
    if (/^[A-Z]+\d+$/.test(clean)) return numericCell(sheet, clean, new Set(seen));
    return Number(clean) || 0;
}

function evaluateFormula(
    sheet: SpreadsheetSheet,
    formula: string,
    seen = new Set<string>(),
): number | string {
    const expression = formula.replace(/^=/, "").trim();
    const aggregate = /^(SUM|AVERAGE|MIN|MAX|COUNT)\(([^)]+)\)$/i.exec(expression);
    if (aggregate) {
        const numbers = aggregate[2]
            .split(",")
            .flatMap((token) => rangeNumbers(sheet, token.trim(), seen));
        switch (aggregate[1].toUpperCase()) {
            case "SUM":
                return numbers.reduce((total, value) => total + value, 0);
            case "AVERAGE":
                return numbers.length
                    ? numbers.reduce((total, value) => total + value, 0) / numbers.length
                    : 0;
            case "MIN":
                return numbers.length ? Math.min(...numbers) : 0;
            case "MAX":
                return numbers.length ? Math.max(...numbers) : 0;
            default:
                return numbers.filter(Number.isFinite).length;
        }
    }

    const ifMatch = /^IF\(([^=<>]+)=([^,]+),([^,]+),(.+)\)$/i.exec(expression);
    if (ifMatch) {
        const left = operandValue(sheet, ifMatch[1], seen);
        const right = operandValue(sheet, ifMatch[2], seen);
        return evaluateFormula(sheet, `=${left === right ? ifMatch[3] : ifMatch[4]}`, seen);
    }

    const binary = /^([A-Z]+\d+|-?\d+(?:\.\d+)?)\s*([+\-*/])\s*([A-Z]+\d+|-?\d+(?:\.\d+)?)$/i.exec(
        expression,
    );
    if (binary) {
        const left = operandValue(sheet, binary[1], seen);
        const right = operandValue(sheet, binary[3], seen);
        if (binary[2] === "+") return left + right;
        if (binary[2] === "-") return left - right;
        if (binary[2] === "*") return left * right;
        return right === 0 ? 0 : left / right;
    }

    if (/^[A-Z]+\d+$/i.test(expression)) {
        return numericCell(sheet, expression.toUpperCase(), seen);
    }
    const literal = Number(expression);
    return Number.isFinite(literal) ? literal : formula;
}

function formatDisplay(
    value: string | number | boolean | null | undefined,
    style?: SpreadsheetCellStyle,
): string {
    if (value === null || value === undefined) return "";
    if (typeof value !== "number") return String(value);
    if (style?.number_format?.includes("%")) return `${(value * 100).toFixed(2)}%`;
    if (style?.number_format?.includes("M ")) {
        return `M ${value.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        })}`;
    }
    if (style?.number_format?.includes("#,##0.00")) {
        return value.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }
    return String(value);
}

function displayValue(sheet: SpreadsheetSheet, cell: SpreadsheetCell | undefined): string {
    if (!cell) return "";
    if (cell.formula) return formatDisplay(evaluateFormula(sheet, cell.formula), cell.style);
    return formatDisplay(cell.value, cell.style);
}

export function SpreadsheetEditor({
    documentId,
    basePath,
}: {
    documentId: string;
    basePath: string;
}) {
    const [workspaceDocument, setWorkspaceDocument] = useState<WorkspaceDocument | null>(null);
    const [workbook, setWorkbook] = useState<SpreadsheetWorkbook | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [publishing, setPublishing] = useState(false);
    const [refreshing, setRefreshing] = useState(false);
    const [dirty, setDirty] = useState(false);
    const [selectedCell, setSelectedCell] = useState("A1");
    const [selectionEnd, setSelectionEnd] = useState("A1");
    const [rowPage, setRowPage] = useState(0);
    const [columnPage, setColumnPage] = useState(0);
    const [fullscreen, setFullscreen] = useState(false);
    const [editingCell, setEditingCell] = useState<string | null>(null);
    const [undoStack, setUndoStack] = useState<SpreadsheetWorkbook[]>([]);
    const [redoStack, setRedoStack] = useState<SpreadsheetWorkbook[]>([]);
    const resizeRef = useRef<ResizeState | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const value = await getWorkspaceDocument(documentId);
            setWorkspaceDocument(value);
            setWorkbook(normaliseClientWorkbook(value.content_json));
            setSelectedCell("A1");
            setSelectionEnd("A1");
            setRowPage(0);
            setColumnPage(0);
            setDirty(false);
            setUndoStack([]);
            setRedoStack([]);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not open the spreadsheet."));
        } finally {
            setLoading(false);
        }
    }, [documentId]);

    useEffect(() => {
        void load();
    }, [load]);

    const activeSheet = useMemo(() => {
        if (!workbook) return null;
        return (
            workbook.sheets.find((sheet) => sheet.name === workbook.active_sheet) ??
            workbook.sheets[0] ??
            null
        );
    }, [workbook]);

    const selectedReferences = useMemo(
        () => referencesInRange(selectedCell, selectionEnd),
        [selectedCell, selectionEnd],
    );
    const selected = activeSheet?.cells[selectedCell];

    function currentSheet(draft: SpreadsheetWorkbook): SpreadsheetSheet {
        return draft.sheets.find((sheet) => sheet.name === draft.active_sheet) ?? draft.sheets[0];
    }

    function pushHistory(current: SpreadsheetWorkbook) {
        setUndoStack((history) => [...history.slice(-49), structuredClone(current)]);
        setRedoStack([]);
    }

    function updateWorkbook(
        mutator: (draft: SpreadsheetWorkbook) => void,
        recordHistory = true,
    ) {
        setWorkbook((current) => {
            if (!current) return current;
            if (recordHistory) pushHistory(current);
            const next = structuredClone(current);
            mutator(next);
            return next;
        });
        setDirty(true);
    }

    const undo = useCallback(() => {
        setUndoStack((history) => {
            if (!history.length) return history;
            const previous = history[history.length - 1];
            setWorkbook((current) => {
                if (current) {
                    setRedoStack((future) => [structuredClone(current), ...future].slice(0, 50));
                }
                return structuredClone(previous);
            });
            setDirty(true);
            return history.slice(0, -1);
        });
    }, []);

    const redo = useCallback(() => {
        setRedoStack((future) => {
            if (!future.length) return future;
            const next = future[0];
            setWorkbook((current) => {
                if (current) {
                    setUndoStack((history) => [
                        ...history.slice(-49),
                        structuredClone(current),
                    ]);
                }
                return structuredClone(next);
            });
            setDirty(true);
            return future.slice(1);
        });
    }, []);

    function setCell(reference: string, value: string) {
        updateWorkbook((draft) => {
            const sheet = currentSheet(draft);
            const existing = sheet.cells[reference];
            const next = parsedCell(value, existing);
            if (next.value === null && !next.formula && !Object.keys(next.style || {}).length) {
                delete sheet.cells[reference];
            } else {
                sheet.cells[reference] = next;
            }
        });
    }

    function clearSelection() {
        updateWorkbook((draft) => {
            const sheet = currentSheet(draft);
            selectedReferences.forEach((reference) => delete sheet.cells[reference]);
        });
    }

    function updateSelectedStyle(patch: Partial<SpreadsheetCellStyle>) {
        updateWorkbook((draft) => {
            const sheet = currentSheet(draft);
            selectedReferences.forEach((reference) => {
                const cell = sheet.cells[reference] ?? { value: null };
                cell.style = { ...(cell.style || {}), ...patch };
                sheet.cells[reference] = cell;
            });
        });
    }

    function pasteMatrix(startReference: string, text: string) {
        const start = parseReference(startReference);
        const matrix = text
            .replace(/\r/g, "")
            .split("\n")
            .filter((row, index, all) => row !== "" || index < all.length - 1)
            .map((row) => row.split("\t"));
        if (!matrix.length) return;
        updateWorkbook((draft) => {
            const sheet = currentSheet(draft);
            matrix.forEach((rowValues, rowOffset) => {
                rowValues.forEach((value, columnOffset) => {
                    const row = start.row + rowOffset;
                    const column = start.column + columnOffset;
                    if (row > MAX_ROWS || column > MAX_COLUMNS) return;
                    const reference = `${columnName(column)}${row}`;
                    sheet.cells[reference] = parsedCell(value, sheet.cells[reference]);
                    sheet.row_count = Math.max(sheet.row_count, row);
                    sheet.column_count = Math.max(sheet.column_count, column);
                });
            });
        });
    }

    function mergeSelection() {
        const label = rangeLabel(selectedCell, selectionEnd);
        if (!label.includes(":")) return;
        updateWorkbook((draft) => {
            const sheet = currentSheet(draft);
            if (!sheet.merges.includes(label)) sheet.merges.push(label);
            referencesInRange(selectedCell, selectionEnd)
                .slice(1)
                .forEach((reference) => delete sheet.cells[reference]);
        });
    }

    function unmergeSelection() {
        const selectedRange = selectedBounds(selectedCell, selectionEnd);
        updateWorkbook((draft) => {
            const sheet = currentSheet(draft);
            sheet.merges = sheet.merges.filter((mergeRange) => {
                const [start, end] = mergeRange.split(":");
                if (!end) return true;
                const merged = selectedBounds(start, end);
                return (
                    merged.maxRow < selectedRange.minRow ||
                    merged.minRow > selectedRange.maxRow ||
                    merged.maxColumn < selectedRange.minColumn ||
                    merged.minColumn > selectedRange.maxColumn
                );
            });
        });
    }

    function insertFunction(name: "SUM" | "AVERAGE" | "MIN" | "MAX" | "COUNT") {
        const current = parseReference(selectedCell);
        const source =
            selectedCell === selectionEnd
                ? `${columnName(current.column)}1:${columnName(current.column)}${Math.max(1, current.row - 1)}`
                : rangeLabel(selectedCell, selectionEnd);
        setCell(selectedCell, `=${name}(${source})`);
    }

    function autoFitColumn(column: number) {
        if (!activeSheet) return;
        const name = columnName(column);
        let longest = name.length;
        Object.entries(activeSheet.cells).forEach(([reference, cell]) => {
            if (parseReference(reference).column === column) {
                longest = Math.max(longest, displayValue(activeSheet, cell).length);
            }
        });
        updateWorkbook((draft) => {
            currentSheet(draft).column_widths[name] = Math.max(8, Math.min(60, longest + 2));
        });
    }

    function autoFitRow(row: number) {
        if (!activeSheet) return;
        let lines = 1;
        Object.entries(activeSheet.cells).forEach(([reference, cell]) => {
            if (parseReference(reference).row === row) {
                lines = Math.max(lines, displayValue(activeSheet, cell).split("\n").length);
            }
        });
        updateWorkbook((draft) => {
            currentSheet(draft).row_heights[String(row)] = Math.min(
                120,
                Math.max(DEFAULT_ROW_HEIGHT, lines * 22),
            );
        });
    }

    const save = useCallback(async (): Promise<boolean> => {
        if (!workspaceDocument || !workbook || !workspaceDocument.can_edit) return false;
        if (!dirty) return true;
        if (saving) return false;
        setSaving(true);
        try {
            const updated = await saveWorkspaceSpreadsheet(workspaceDocument.id, {
                workbook,
                title: workspaceDocument.title,
                expected_version: workspaceDocument.version,
                create_revision: true,
            });
            setWorkspaceDocument(updated);
            setWorkbook(normaliseClientWorkbook(updated.content_json));
            setDirty(false);
            setUndoStack([]);
            setRedoStack([]);
            toast.success(`Saved version ${updated.version}.`);
            return true;
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not save the spreadsheet."));
            return false;
        } finally {
            setSaving(false);
        }
    }, [dirty, saving, workbook, workspaceDocument]);

    useEffect(() => {
        function handleKey(event: KeyboardEvent) {
            const command = event.ctrlKey || event.metaKey;
            if (command && event.key.toLowerCase() === "s") {
                event.preventDefault();
                void save();
            } else if (command && event.key.toLowerCase() === "z" && !event.shiftKey) {
                event.preventDefault();
                undo();
            } else if (
                command &&
                (event.key.toLowerCase() === "y" ||
                    (event.key.toLowerCase() === "z" && event.shiftKey))
            ) {
                event.preventDefault();
                redo();
            } else if (
                event.key === "Delete" &&
                workspaceDocument?.can_edit &&
                editingCell === null
            ) {
                event.preventDefault();
                clearSelection();
            } else if (event.key === "Escape" && fullscreen) {
                setFullscreen(false);
            }
        }
        window.addEventListener("keydown", handleKey);
        return () => window.removeEventListener("keydown", handleKey);
    }, [editingCell, fullscreen, redo, save, undo, workspaceDocument]);

    useEffect(() => {
        if (!dirty) return;
        const handler = (event: BeforeUnloadEvent) => event.preventDefault();
        window.addEventListener("beforeunload", handler);
        return () => window.removeEventListener("beforeunload", handler);
    }, [dirty]);

    useEffect(() => {
        function onMove(event: MouseEvent) {
            const resize = resizeRef.current;
            if (!resize || !workspaceDocument?.can_edit) return;
            const delta =
                (resize.kind === "column" ? event.clientX : event.clientY) - resize.start;
            if (resize.kind === "column") {
                const width = Math.max(4, Math.min(100, resize.initial + delta / 8));
                updateWorkbook((draft) => {
                    currentSheet(draft).column_widths[columnName(resize.index)] = Number(
                        width.toFixed(1),
                    );
                }, false);
            } else {
                const height = Math.max(18, Math.min(200, resize.initial + delta));
                updateWorkbook((draft) => {
                    currentSheet(draft).row_heights[String(resize.index)] = Number(
                        height.toFixed(1),
                    );
                }, false);
            }
        }
        function onUp() {
            resizeRef.current = null;
        }
        window.addEventListener("mousemove", onMove);
        window.addEventListener("mouseup", onUp);
        return () => {
            window.removeEventListener("mousemove", onMove);
            window.removeEventListener("mouseup", onUp);
        };
    }, [workspaceDocument]);

    async function refreshDatabaseData() {
        if (!workspaceDocument || refreshing) return;
        if (dirty) {
            toast.error("Save or discard your current edits before refreshing LoanHub data.");
            return;
        }
        setRefreshing(true);
        try {
            const updated = await refreshWorkspaceSpreadsheetData(workspaceDocument.id);
            setWorkspaceDocument(updated);
            setWorkbook(normaliseClientWorkbook(updated.content_json));
            setUndoStack([]);
            setRedoStack([]);
            setDirty(false);
            toast.success("Workbook refreshed from the current LoanHub database.");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not refresh LoanHub data."));
        } finally {
            setRefreshing(false);
        }
    }

    async function download(format: SpreadsheetExportFormat) {
        if (!workspaceDocument) return;
        if (dirty && workspaceDocument.can_edit && !(await save())) return;
        try {
            await downloadWorkspaceSpreadsheet(
                workspaceDocument.id,
                format,
                workspaceDocument.title,
            );
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, `Could not export ${format.toUpperCase()}.`));
        }
    }

    async function publish() {
        if (!workspaceDocument || publishing) return;
        if (dirty && workspaceDocument.can_edit && !(await save())) return;
        setPublishing(true);
        try {
            await publishWorkspaceSpreadsheet(workspaceDocument.id, {
                format: "xlsx",
                visibility: workspaceDocument.company_id
                    ? "company"
                    : workspaceDocument.visibility,
                is_confidential: workspaceDocument.is_confidential,
            });
            toast.success("Excel workbook published to the managed document library.");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not publish the workbook."));
        } finally {
            setPublishing(false);
        }
    }

    function addSheet() {
        if (!workbook || workbook.sheets.length >= 30) return;
        let nextName = "";
        updateWorkbook((draft) => {
            let number = draft.sheets.length + 1;
            nextName = `Sheet${number}`;
            while (draft.sheets.some((sheet) => sheet.name === nextName)) {
                number += 1;
                nextName = `Sheet${number}`;
            }
            draft.sheets.push({
                id: `sheet-${Date.now()}`,
                name: nextName,
                row_count: 40,
                column_count: 12,
                cells: {},
                column_widths: {},
                row_heights: {},
                merges: [],
                freeze_panes: null,
            });
            draft.active_sheet = nextName;
        });
        setRowPage(0);
        setColumnPage(0);
        setSelectedCell("A1");
        setSelectionEnd("A1");
    }

    function renameSheet() {
        if (!activeSheet || !workbook) return;
        const requested = window.prompt("Sheet name", activeSheet.name)?.trim();
        if (!requested || requested === activeSheet.name) return;
        const cleaned = requested.replace(/[\\/*?:\[\]]/g, " ").trim().slice(0, 31);
        if (
            !cleaned ||
            workbook.sheets.some((sheet) => sheet.name.toLowerCase() === cleaned.toLowerCase())
        ) {
            toast.error("Use a unique Excel-compatible sheet name.");
            return;
        }
        updateWorkbook((draft) => {
            const sheet = currentSheet(draft);
            sheet.name = cleaned;
            draft.active_sheet = cleaned;
        });
    }

    function deleteSheet() {
        if (!activeSheet || !workbook || workbook.sheets.length <= 1) return;
        if (!window.confirm(`Delete ${activeSheet.name}?`)) return;
        updateWorkbook((draft) => {
            const index = draft.sheets.findIndex(
                (sheet) => sheet.name === draft.active_sheet,
            );
            draft.sheets.splice(index, 1);
            draft.active_sheet = draft.sheets[Math.max(0, index - 1)].name;
        });
        setRowPage(0);
        setColumnPage(0);
        setSelectedCell("A1");
        setSelectionEnd("A1");
    }

    if (loading) {
        return (
            <div className="flex min-h-[60vh] items-center justify-center">
                <Loader2 className="h-7 w-7 animate-spin text-primary" />
            </div>
        );
    }
    if (!workspaceDocument || !workbook || !activeSheet) {
        return (
            <div className="rounded-3xl border bg-card p-8 text-center text-sm text-muted-foreground">
                Spreadsheet unavailable.
            </div>
        );
    }

    const rowStart = rowPage * PAGE_ROWS + 1;
    const rowEnd = Math.min(activeSheet.row_count, rowStart + PAGE_ROWS - 1);
    const columnStart = columnPage * PAGE_COLUMNS + 1;
    const columnEnd = Math.min(
        activeSheet.column_count,
        columnStart + PAGE_COLUMNS - 1,
    );
    const rows = Array.from(
        { length: Math.max(0, rowEnd - rowStart + 1) },
        (_, index) => rowStart + index,
    );
    const columns = Array.from(
        { length: Math.max(0, columnEnd - columnStart + 1) },
        (_, index) => columnStart + index,
    );
    const selectedRange = selectedBounds(selectedCell, selectionEnd);

    return (
        <main
            className={
                fullscreen
                    ? "fixed inset-0 z-[100] flex h-dvh w-screen flex-col overflow-hidden bg-background"
                    : "flex min-h-[620px] w-full max-w-none flex-col overflow-hidden rounded-2xl border bg-background shadow-sm"
            }
            data-spreadsheet-fullscreen={fullscreen ? "true" : "false"}
        >
            <header className="shrink-0 border-b bg-card">
                <div className="flex flex-wrap items-center gap-2 px-2 py-2 sm:px-3 md:px-4">
                    <Link
                        href={basePath}
                        className="inline-flex h-9 items-center gap-1.5 rounded-lg border px-2 text-xs font-black hover:border-primary hover:text-primary sm:px-3"
                    >
                        <ChevronLeft className="h-4 w-4" />
                        <span className="hidden sm:inline">Documents</span>
                    </Link>
                    <div className="flex min-w-[180px] flex-1 items-center gap-2">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-700 dark:text-emerald-400">
                            <FileSpreadsheet className="h-5 w-5" />
                        </div>
                        <input
                            value={workspaceDocument.title}
                            disabled={!workspaceDocument.can_edit}
                            onChange={(event) => {
                                const title = event.target.value;
                                setWorkspaceDocument((current) =>
                                    current ? { ...current, title } : current,
                                );
                                setDirty(true);
                            }}
                            className="min-w-24 flex-1 bg-transparent text-sm font-black outline-none md:text-base"
                            aria-label="Workbook title"
                        />
                        <span className="hidden rounded-full bg-muted px-2 py-1 text-[11px] font-bold text-muted-foreground sm:inline">
                            v{workspaceDocument.version}
                        </span>
                    </div>
                    {DATABASE_TEMPLATES.has(workspaceDocument.template_key) && (
                        <button
                            type="button"
                            disabled={!workspaceDocument.can_edit || refreshing || dirty}
                            onClick={() => void refreshDatabaseData()}
                            className="inline-flex h-9 items-center gap-1.5 rounded-lg border px-2 text-xs font-black hover:border-primary hover:text-primary disabled:opacity-40"
                            title="Replace workbook data with the latest LoanHub records"
                        >
                            <RefreshCcw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
                            <span className="hidden xl:inline">Refresh LoanHub data</span>
                        </button>
                    )}
                    <button
                        type="button"
                        disabled={!workspaceDocument.can_edit || !dirty || saving}
                        onClick={() => void save()}
                        className="inline-flex h-9 items-center gap-2 rounded-lg bg-primary px-3 text-xs font-black text-primary-foreground disabled:opacity-50"
                    >
                        {saving ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <Save className="h-4 w-4" />
                        )}
                        <span className="hidden sm:inline">Save</span>
                    </button>
                    <button
                        type="button"
                        onClick={() => void download("xlsx")}
                        className="inline-flex h-9 items-center gap-2 rounded-lg border px-2 text-xs font-black hover:border-emerald-500 hover:text-emerald-700 sm:px-3"
                    >
                        <Download className="h-4 w-4" />
                        <span className="hidden sm:inline">XLSX</span>
                    </button>
                    <button
                        type="button"
                        onClick={() => void publish()}
                        disabled={publishing}
                        className="hidden h-9 items-center gap-2 rounded-lg border px-3 text-xs font-black hover:border-primary hover:text-primary md:inline-flex"
                    >
                        {publishing ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <UploadCloud className="h-4 w-4" />
                        )}
                        Publish
                    </button>
                    <button
                        type="button"
                        onClick={() => setFullscreen((value) => !value)}
                        className="inline-flex h-9 items-center gap-2 rounded-lg border px-2 text-xs font-black hover:border-primary hover:text-primary sm:px-3"
                    >
                        {fullscreen ? (
                            <Minimize2 className="h-4 w-4" />
                        ) : (
                            <Maximize2 className="h-4 w-4" />
                        )}
                        <span className="hidden xl:inline">
                            {fullscreen ? "Exit full screen" : "Full screen"}
                        </span>
                    </button>
                </div>

                <div className="flex items-center gap-1 overflow-x-auto border-t px-2 py-1.5 [scrollbar-width:thin] sm:px-3 md:px-4">
                    <button
                        type="button"
                        disabled={!undoStack.length}
                        onClick={undo}
                        className="rounded-md p-2 hover:bg-muted disabled:opacity-30"
                        title="Undo"
                    >
                        <Undo2 className="h-4 w-4" />
                    </button>
                    <button
                        type="button"
                        disabled={!redoStack.length}
                        onClick={redo}
                        className="rounded-md p-2 hover:bg-muted disabled:opacity-30"
                        title="Redo"
                    >
                        <Redo2 className="h-4 w-4" />
                    </button>
                    <span className="mx-1 h-6 w-px shrink-0 bg-border" />
                    <button
                        type="button"
                        disabled={!workspaceDocument.can_edit}
                        onClick={() => updateSelectedStyle({ bold: !selected?.style?.bold })}
                        className={`rounded-md p-2 ${
                            selected?.style?.bold
                                ? "bg-primary text-primary-foreground"
                                : "hover:bg-muted"
                        }`}
                        title="Bold"
                    >
                        <Bold className="h-4 w-4" />
                    </button>
                    <button
                        type="button"
                        disabled={!workspaceDocument.can_edit}
                        onClick={() => updateSelectedStyle({ italic: !selected?.style?.italic })}
                        className={`rounded-md p-2 ${
                            selected?.style?.italic
                                ? "bg-primary text-primary-foreground"
                                : "hover:bg-muted"
                        }`}
                        title="Italic"
                    >
                        <Italic className="h-4 w-4" />
                    </button>
                    <button
                        type="button"
                        disabled={!workspaceDocument.can_edit}
                        onClick={() =>
                            updateSelectedStyle({ underline: !selected?.style?.underline })
                        }
                        className={`rounded-md p-2 ${
                            selected?.style?.underline
                                ? "bg-primary text-primary-foreground"
                                : "hover:bg-muted"
                        }`}
                        title="Underline"
                    >
                        <Underline className="h-4 w-4" />
                    </button>
                    <button
                        type="button"
                        disabled={!workspaceDocument.can_edit}
                        onClick={() => updateSelectedStyle({ wrap: !selected?.style?.wrap })}
                        className={`rounded-md px-2 py-1.5 text-xs font-black ${
                            selected?.style?.wrap
                                ? "bg-primary text-primary-foreground"
                                : "hover:bg-muted"
                        }`}
                    >
                        Wrap
                    </button>
                    <button
                        type="button"
                        disabled={!workspaceDocument.can_edit}
                        onClick={() => updateSelectedStyle({ horizontal: "left" })}
                        className="rounded-md p-2 hover:bg-muted"
                        title="Align left"
                    >
                        <AlignLeft className="h-4 w-4" />
                    </button>
                    <button
                        type="button"
                        disabled={!workspaceDocument.can_edit}
                        onClick={() => updateSelectedStyle({ horizontal: "center" })}
                        className="rounded-md p-2 hover:bg-muted"
                        title="Align center"
                    >
                        <AlignCenter className="h-4 w-4" />
                    </button>
                    <button
                        type="button"
                        disabled={!workspaceDocument.can_edit}
                        onClick={() => updateSelectedStyle({ horizontal: "right" })}
                        className="rounded-md p-2 hover:bg-muted"
                        title="Align right"
                    >
                        <AlignRight className="h-4 w-4" />
                    </button>
                    <label className="flex h-8 items-center gap-1 rounded-md border px-2 text-[10px] font-black">
                        Text
                        <input
                            type="color"
                            value={selected?.style?.font_color || "#111827"}
                            disabled={!workspaceDocument.can_edit}
                            onChange={(event) =>
                                updateSelectedStyle({ font_color: event.target.value })
                            }
                            className="h-5 w-5 cursor-pointer border-0 bg-transparent p-0"
                        />
                    </label>
                    <label className="flex h-8 items-center gap-1 rounded-md border px-2 text-[10px] font-black">
                        Fill
                        <input
                            type="color"
                            value={selected?.style?.fill_color || "#ffffff"}
                            disabled={!workspaceDocument.can_edit}
                            onChange={(event) =>
                                updateSelectedStyle({ fill_color: event.target.value })
                            }
                            className="h-5 w-5 cursor-pointer border-0 bg-transparent p-0"
                        />
                    </label>
                    <button
                        type="button"
                        disabled={!workspaceDocument.can_edit || selectedCell === selectionEnd}
                        onClick={mergeSelection}
                        className="rounded-md px-2 py-1.5 text-xs font-black hover:bg-muted disabled:opacity-30"
                    >
                        Merge
                    </button>
                    <button
                        type="button"
                        disabled={!workspaceDocument.can_edit}
                        onClick={unmergeSelection}
                        className="rounded-md px-2 py-1.5 text-xs font-black hover:bg-muted"
                    >
                        Unmerge
                    </button>
                    <button
                        type="button"
                        disabled={!workspaceDocument.can_edit}
                        onClick={() =>
                            updateWorkbook((draft) => {
                                currentSheet(draft).freeze_panes =
                                    selectedCell === "A1" ? null : selectedCell;
                            })
                        }
                        className="rounded-md px-2 py-1.5 text-xs font-black hover:bg-muted"
                    >
                        Freeze panes
                    </button>
                    <button
                        type="button"
                        disabled={!workspaceDocument.can_edit}
                        onClick={() => updateSelectedStyle({ number_format: "#,##0.00" })}
                        className="rounded-md px-2 py-1.5 text-xs font-black hover:bg-muted"
                    >
                        1,234.00
                    </button>
                    <button
                        type="button"
                        disabled={!workspaceDocument.can_edit}
                        onClick={() => updateSelectedStyle({ number_format: "0.00%" })}
                        className="rounded-md px-2 py-1.5 text-xs font-black hover:bg-muted"
                    >
                        %
                    </button>
                    <button
                        type="button"
                        disabled={!workspaceDocument.can_edit}
                        onClick={() => updateSelectedStyle({ number_format: "M #,##0.00" })}
                        className="rounded-md px-2 py-1.5 text-xs font-black hover:bg-muted"
                    >
                        M
                    </button>
                    <select
                        disabled={!workspaceDocument.can_edit}
                        defaultValue=""
                        onChange={(event) => {
                            const value = event.target.value as
                                | "SUM"
                                | "AVERAGE"
                                | "MIN"
                                | "MAX"
                                | "COUNT"
                                | "";
                            if (value) insertFunction(value);
                            event.currentTarget.value = "";
                        }}
                        className="h-8 rounded-md border bg-background px-2 text-xs font-black"
                    >
                        <option value="">Functions</option>
                        <option value="SUM">SUM</option>
                        <option value="AVERAGE">AVERAGE</option>
                        <option value="MIN">MIN</option>
                        <option value="MAX">MAX</option>
                        <option value="COUNT">COUNT</option>
                    </select>
                    <button
                        type="button"
                        onClick={() => void download("csv")}
                        className="ml-auto shrink-0 rounded-md px-2 py-1.5 text-xs font-black hover:bg-muted"
                    >
                        Export CSV
                    </button>
                </div>

                <div className="flex items-center border-t bg-muted/20">
                    <div className="w-28 shrink-0 border-r px-2 py-2 text-center font-mono text-xs font-black">
                        {rangeLabel(selectedCell, selectionEnd)}
                    </div>
                    <div className="px-3 text-xs font-black text-muted-foreground">fx</div>
                    <input
                        value={rawValue(selected)}
                        disabled={!workspaceDocument.can_edit}
                        onFocus={() => setEditingCell("formula")}
                        onBlur={() => setEditingCell(null)}
                        onChange={(event) => setCell(selectedCell, event.target.value)}
                        className="h-9 min-w-0 flex-1 bg-transparent px-2 font-mono text-xs outline-none"
                        aria-label="Formula bar"
                    />
                </div>
            </header>

            <section className="relative min-h-0 min-w-0 flex-1 overflow-auto bg-muted/15 overscroll-contain">
                <table
                    className="min-w-full border-separate border-spacing-0 text-xs"
                    style={{ width: "max-content" }}
                >
                    <thead className="sticky top-0 z-20 bg-muted">
                        <tr>
                            <th className="sticky left-0 z-30 h-8 w-12 min-w-12 border-b border-r bg-muted" />
                            {columns.map((column) => {
                                const name = columnName(column);
                                const widthUnits =
                                    activeSheet.column_widths[name] || DEFAULT_COLUMN_WIDTH;
                                const widthPx = Math.max(80, widthUnits * 8);
                                return (
                                    <th
                                        key={column}
                                        className="relative h-8 border-b border-r bg-muted px-2 text-center font-black text-muted-foreground"
                                        style={{
                                            width: widthPx,
                                            minWidth: widthPx,
                                            maxWidth: widthPx,
                                        }}
                                    >
                                        {name}
                                        {workspaceDocument.can_edit && (
                                            <span
                                                role="separator"
                                                aria-label={`Resize column ${name}`}
                                                onDoubleClick={() => autoFitColumn(column)}
                                                onMouseDown={(event) => {
                                                    event.preventDefault();
                                                    pushHistory(workbook);
                                                    resizeRef.current = {
                                                        kind: "column",
                                                        index: column,
                                                        start: event.clientX,
                                                        initial: widthUnits,
                                                    };
                                                }}
                                                className="absolute -right-1 top-0 z-40 h-full w-2 cursor-col-resize select-none"
                                            />
                                        )}
                                    </th>
                                );
                            })}
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((row) => {
                            const rowHeight =
                                activeSheet.row_heights[String(row)] || DEFAULT_ROW_HEIGHT;
                            return (
                                <tr key={row} style={{ height: rowHeight }}>
                                    <th
                                        className="sticky left-0 z-10 relative w-12 min-w-12 border-b border-r bg-muted px-2 text-right font-mono text-[11px] text-muted-foreground"
                                        style={{ height: rowHeight }}
                                    >
                                        {row}
                                        {workspaceDocument.can_edit && (
                                            <span
                                                role="separator"
                                                aria-label={`Resize row ${row}`}
                                                onDoubleClick={() => autoFitRow(row)}
                                                onMouseDown={(event) => {
                                                    event.preventDefault();
                                                    pushHistory(workbook);
                                                    resizeRef.current = {
                                                        kind: "row",
                                                        index: row,
                                                        start: event.clientY,
                                                        initial: rowHeight,
                                                    };
                                                }}
                                                className="absolute -bottom-1 left-0 z-40 h-2 w-full cursor-row-resize select-none"
                                            />
                                        )}
                                    </th>
                                    {columns.map((column) => {
                                        const name = columnName(column);
                                        const reference = `${name}${row}`;
                                        const cell = activeSheet.cells[reference];
                                        const widthUnits =
                                            activeSheet.column_widths[name] ||
                                            DEFAULT_COLUMN_WIDTH;
                                        const widthPx = Math.max(80, widthUnits * 8);
                                        const isSelected =
                                            row >= selectedRange.minRow &&
                                            row <= selectedRange.maxRow &&
                                            column >= selectedRange.minColumn &&
                                            column <= selectedRange.maxColumn;
                                        const mergeRange = activeSheet.merges.find((item) => {
                                            const [start, end] = item.split(":");
                                            return end
                                                ? referencesInRange(start, end).includes(reference)
                                                : false;
                                        });

                                        if (mergeRange) {
                                            const [mergeStart, mergeEnd] = mergeRange.split(":");
                                            if (reference !== mergeStart) return null;
                                            const merged = selectedBounds(mergeStart, mergeEnd);
                                            return (
                                                <td
                                                    key={reference}
                                                    colSpan={
                                                        merged.maxColumn - merged.minColumn + 1
                                                    }
                                                    rowSpan={merged.maxRow - merged.minRow + 1}
                                                    className={`border-b border-r bg-background p-0 ${
                                                        isSelected
                                                            ? "outline outline-2 -outline-offset-2 outline-emerald-500"
                                                            : ""
                                                    }`}
                                                    style={{ minWidth: widthPx }}
                                                >
                                                    <CellInput
                                                        reference={reference}
                                                        cell={cell}
                                                        sheet={activeSheet}
                                                        canEdit={workspaceDocument.can_edit}
                                                        editing={editingCell === reference}
                                                        onSelect={() => {
                                                            setSelectedCell(reference);
                                                            setSelectionEnd(reference);
                                                        }}
                                                        onEditing={setEditingCell}
                                                        onChange={setCell}
                                                        onPaste={pasteMatrix}
                                                    />
                                                </td>
                                            );
                                        }

                                        return (
                                            <td
                                                key={reference}
                                                className={`border-b border-r bg-background p-0 ${
                                                    isSelected
                                                        ? "outline outline-2 -outline-offset-2 outline-emerald-500"
                                                        : ""
                                                }`}
                                                style={{
                                                    width: widthPx,
                                                    minWidth: widthPx,
                                                    maxWidth: widthPx,
                                                    height: rowHeight,
                                                }}
                                            >
                                                <CellInput
                                                    reference={reference}
                                                    cell={cell}
                                                    sheet={activeSheet}
                                                    canEdit={workspaceDocument.can_edit}
                                                    editing={editingCell === reference}
                                                    onMouseSelect={(shift) => {
                                                        if (shift) setSelectionEnd(reference);
                                                        else {
                                                            setSelectedCell(reference);
                                                            setSelectionEnd(reference);
                                                        }
                                                    }}
                                                    onSelect={() => {
                                                        if (
                                                            selectedCell !== reference &&
                                                            selectionEnd !== reference
                                                        ) {
                                                            setSelectedCell(reference);
                                                            setSelectionEnd(reference);
                                                        }
                                                    }}
                                                    onEditing={setEditingCell}
                                                    onChange={setCell}
                                                    onPaste={pasteMatrix}
                                                />
                                            </td>
                                        );
                                    })}
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </section>

            <footer className="shrink-0 border-t bg-card">
                <div className="flex flex-wrap items-center gap-2 px-2 py-1.5 sm:px-3">
                    <div className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
                        {workbook.sheets.map((sheet) => (
                            <button
                                key={sheet.id}
                                type="button"
                                onDoubleClick={() =>
                                    sheet.name === workbook.active_sheet && renameSheet()
                                }
                                onClick={() => {
                                    setWorkbook((current) =>
                                        current
                                            ? { ...current, active_sheet: sheet.name }
                                            : current,
                                    );
                                    setRowPage(0);
                                    setColumnPage(0);
                                    setSelectedCell("A1");
                                    setSelectionEnd("A1");
                                }}
                                className={`inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg px-3 text-xs font-black ${
                                    sheet.name === workbook.active_sheet
                                        ? "bg-emerald-600 text-white"
                                        : "bg-muted hover:bg-muted/80"
                                }`}
                            >
                                <Sheet className="h-3.5 w-3.5" /> {sheet.name}
                            </button>
                        ))}
                        {workspaceDocument.can_edit && (
                            <button
                                type="button"
                                onClick={addSheet}
                                className="rounded-lg p-2 hover:bg-muted"
                                title="Add sheet"
                            >
                                <Plus className="h-4 w-4" />
                            </button>
                        )}
                    </div>
                    {workspaceDocument.can_edit && workbook.sheets.length > 1 && (
                        <button
                            type="button"
                            onClick={deleteSheet}
                            className="rounded-lg p-2 text-destructive hover:bg-destructive/10"
                            title="Delete active sheet"
                        >
                            <Trash2 className="h-4 w-4" />
                        </button>
                    )}
                </div>
                <div className="flex flex-wrap items-center justify-between gap-2 border-t px-2 py-1.5 text-[11px] text-muted-foreground sm:px-3">
                    <div className="flex items-center gap-2">
                        <button
                            type="button"
                            disabled={rowPage === 0}
                            onClick={() => setRowPage((value) => Math.max(0, value - 1))}
                            className="rounded-md border p-1 disabled:opacity-40"
                        >
                            <ChevronLeft className="h-3.5 w-3.5" />
                        </button>
                        <span>
                            Rows {rowStart}–{rowEnd} of {activeSheet.row_count}
                        </span>
                        <button
                            type="button"
                            disabled={rowEnd >= activeSheet.row_count}
                            onClick={() => setRowPage((value) => value + 1)}
                            className="rounded-md border p-1 disabled:opacity-40"
                        >
                            <ChevronRight className="h-3.5 w-3.5" />
                        </button>
                        {workspaceDocument.can_edit && activeSheet.row_count < MAX_ROWS && (
                            <button
                                type="button"
                                onClick={() =>
                                    updateWorkbook((draft) => {
                                        const sheet = currentSheet(draft);
                                        sheet.row_count = Math.min(
                                            MAX_ROWS,
                                            sheet.row_count + 25,
                                        );
                                    })
                                }
                                className="rounded-md border px-2 py-1 font-black"
                            >
                                +25 rows
                            </button>
                        )}
                    </div>
                    <div className="hidden items-center gap-2 sm:flex">
                        <button
                            type="button"
                            disabled={columnPage === 0}
                            onClick={() =>
                                setColumnPage((value) => Math.max(0, value - 1))
                            }
                            className="rounded-md border p-1 disabled:opacity-40"
                        >
                            <ChevronLeft className="h-3.5 w-3.5" />
                        </button>
                        <span>
                            Columns {columnName(columnStart)}–{columnName(columnEnd)} of{" "}
                            {activeSheet.column_count}
                        </span>
                        <button
                            type="button"
                            disabled={columnEnd >= activeSheet.column_count}
                            onClick={() => setColumnPage((value) => value + 1)}
                            className="rounded-md border p-1 disabled:opacity-40"
                        >
                            <ChevronRight className="h-3.5 w-3.5" />
                        </button>
                        {workspaceDocument.can_edit &&
                            activeSheet.column_count < MAX_COLUMNS && (
                                <button
                                    type="button"
                                    onClick={() =>
                                        updateWorkbook((draft) => {
                                            const sheet = currentSheet(draft);
                                            sheet.column_count = Math.min(
                                                MAX_COLUMNS,
                                                sheet.column_count + 5,
                                            );
                                        })
                                    }
                                    className="rounded-md border px-2 py-1 font-black"
                                >
                                    +5 cols
                                </button>
                            )}
                    </div>
                    <span
                        className={
                            dirty
                                ? "font-black text-amber-600"
                                : "font-semibold text-emerald-600"
                        }
                    >
                        {dirty ? "Unsaved changes" : "All changes saved"}
                    </span>
                </div>
            </footer>
        </main>
    );
}

function CellInput({
    reference,
    cell,
    sheet,
    canEdit,
    editing,
    onSelect,
    onMouseSelect,
    onEditing,
    onChange,
    onPaste,
}: {
    reference: string;
    cell: SpreadsheetCell | undefined;
    sheet: SpreadsheetSheet;
    canEdit: boolean;
    editing: boolean;
    onSelect: () => void;
    onMouseSelect?: (shift: boolean) => void;
    onEditing: (reference: string | null) => void;
    onChange: (reference: string, value: string) => void;
    onPaste: (reference: string, text: string) => void;
}) {
    return (
        <input
            value={editing ? rawValue(cell) : displayValue(sheet, cell)}
            readOnly={!canEdit}
            onMouseDown={(event) => {
                if (onMouseSelect) {
                    if (event.shiftKey) event.preventDefault();
                    onMouseSelect(event.shiftKey);
                }
            }}
            onFocus={() => {
                onSelect();
                onEditing(reference);
            }}
            onBlur={() => onEditing(null)}
            onChange={(event) => onChange(reference, event.target.value)}
            onPaste={(event) => {
                const text = event.clipboardData.getData("text/plain");
                if (text.includes("\t") || text.includes("\n")) {
                    event.preventDefault();
                    onPaste(reference, text);
                }
            }}
            style={styleForCell(cell?.style)}
            className="h-full min-h-8 w-full bg-transparent px-2 outline-none"
            aria-label={`Cell ${reference}`}
        />
    );
}
