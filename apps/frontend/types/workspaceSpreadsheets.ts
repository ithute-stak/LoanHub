import type { ManagedFile } from "@/types/files";
import type { DocumentVisibility, WorkspaceDocument } from "@/types/workspaceDocuments";

export type SpreadsheetTemplate = "blank" | "loan_portfolio" | "cashbook" | "collections" | "budget";
export type SpreadsheetExportFormat = "xlsx" | "csv";

export type SpreadsheetCellStyle = {
    bold?: boolean;
    italic?: boolean;
    underline?: boolean;
    font_size?: number;
    font_color?: string;
    fill_color?: string;
    horizontal?: "left" | "center" | "right" | "general";
    vertical?: "top" | "center" | "bottom";
    wrap?: boolean;
    number_format?: string;
    border?: Record<string, { style?: string; color?: string | null }>;
};

export type SpreadsheetCell = {
    value: string | number | boolean | null;
    formula?: string;
    style?: SpreadsheetCellStyle;
    value_type?: string;
};

export type SpreadsheetSheet = {
    id: string;
    name: string;
    row_count: number;
    column_count: number;
    cells: Record<string, SpreadsheetCell>;
    column_widths: Record<string, number>;
    row_heights: Record<string, number>;
    merges: string[];
    freeze_panes: string | null;
};

export type SpreadsheetWorkbook = {
    format_version: number;
    active_sheet: string;
    sheets: SpreadsheetSheet[];
    source_filename?: string;
};

export type CreateWorkspaceSpreadsheetPayload = {
    title: string;
    template: SpreadsheetTemplate;
    visibility: DocumentVisibility;
    is_confidential?: boolean;
};

export type SaveWorkspaceSpreadsheetPayload = {
    workbook: SpreadsheetWorkbook;
    title?: string;
    expected_version?: number;
    create_revision?: boolean;
};

export type PublishWorkspaceSpreadsheetPayload = {
    format: SpreadsheetExportFormat;
    visibility?: DocumentVisibility;
    file_name?: string;
    is_confidential?: boolean;
};

export type WorkspaceSpreadsheetDocument = WorkspaceDocument & {
    content_json: SpreadsheetWorkbook;
};

export type PublishedWorkspaceSpreadsheet = ManagedFile;

export function isSpreadsheetDocument(document: Pick<WorkspaceDocument, "template_key">): boolean {
    return String(document.template_key || "").startsWith("spreadsheet_");
}
