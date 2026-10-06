import { api } from "@/lib/api";

export type FolioIntegrityIssue =
  | "missing_folio"
  | "invalid_format"
  | "component_mismatch"
  | "duplicate_folio"
  | "duplicate_sequence";

export type FolioBookRow = {
  loan_id: string;
  folio_number: string | null;
  folio_company_code: string;
  folio_group_code: string;
  folio_sequence: number;
  loan_reference: string;
  borrower_id: string;
  borrower_name: string;
  borrower_identity: string | null;
  employer_group_name: string | null;
  employer_group_code: string | null;
  employer_name: string | null;
  branch_id: string | null;
  branch_name: string | null;
  principal_amount: number;
  amount_paid: number;
  balance: number;
  status: string;
  origination_channel: string | null;
  created_at: string | null;
  approved_at: string | null;
  disbursed_at: string | null;
  integrity_issues: FolioIntegrityIssue[];
};

export type FolioSequenceBook = {
  group_code: string;
  group_name: string | null;
  company_code: string;
  loan_count: number;
  first_sequence: number | null;
  last_sequence: number | null;
  next_sequence: number;
  next_folio_number: string;
  gap_count: number;
  gaps: number[];
  gaps_truncated: boolean;
};

export type FolioBookPayload = {
  summary: {
    total_loans: number;
    visible_loans?: number;
    sequence_book_count: number;
    missing_folio_count: number;
    invalid_format_count: number;
    component_mismatch_count: number;
    duplicate_folio_count: number;
    duplicate_sequence_count: number;
    gap_count: number;
    integrity_ok: boolean;
  };
  sequence_books: FolioSequenceBook[];
  total: number;
  skip: number;
  limit: number;
  rows: FolioBookRow[];
};

export type FolioBookQuery = {
  search?: string;
  group_code?: string;
  status?: string;
  branch_id?: string;
  skip?: number;
  limit?: number;
};

export type BorrowerFolioHistory = {
  borrower_id: string;
  borrower_name: string;
  loan_count: number;
  folios: FolioBookRow[];
};

export type FolioIntegrity = {
  healthy: boolean;
  loan_count: number;
  missing_folio_count: number;
  malformed_folio_count: number;
  duplicate_folio_count: number;
  gap_count: number;
  groups: Array<{
    company_code: string;
    group_code: string;
    loan_count: number;
    first_sequence: number | null;
    last_sequence: number | null;
    next_sequence: number;
    next_folio: string;
    gap_count: number;
    gaps: number[];
  }>;
};

function queryParams(query: FolioBookQuery = {}) {
  return Object.fromEntries(
    Object.entries(query).filter(([, value]) => value !== undefined && value !== null && value !== ""),
  );
}

export async function getFolioBook(query: FolioBookQuery = {}): Promise<FolioBookPayload> {
  return (await api.get<FolioBookPayload>("/folio-book", { params: queryParams(query) })).data;
}

export async function lookupFolio(folioNumber: string): Promise<FolioBookRow> {
  return (
    await api.get<FolioBookRow>(
      `/folio-book/lookup/${encodeURIComponent(folioNumber.trim().toUpperCase())}`,
    )
  ).data;
}

export async function getBorrowerFolioHistory(borrowerId: string): Promise<BorrowerFolioHistory> {
  return (
    await api.get<BorrowerFolioHistory>(
      `/folio-book/borrowers/${encodeURIComponent(borrowerId)}`,
    )
  ).data;
}

export async function getFolioIntegrity(): Promise<FolioIntegrity> {
  return (await api.get<FolioIntegrity>("/folio-book/integrity")).data;
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
}

export async function downloadFolioBookCsv(query: FolioBookQuery | string = {}): Promise<void> {
  const normalized = typeof query === "string" ? { group_code: query } : query;
  const response = await api.get<Blob>("/folio-book/export.csv", {
    params: queryParams(normalized),
    responseType: "blob",
  });
  const groupCode = normalized.group_code;
  downloadBlob(
    response.data,
    groupCode ? `LoanHub-Folio-Book-${groupCode}.csv` : "LoanHub-Folio-Book.csv",
  );
}
