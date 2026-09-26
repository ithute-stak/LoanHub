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

function params(query: FolioBookQuery = {}) {
  return Object.fromEntries(
    Object.entries(query).filter(([, value]) => value !== undefined && value !== null && value !== ""),
  );
}

export async function getFolioBook(query: FolioBookQuery = {}): Promise<FolioBookPayload> {
  return (await api.get<FolioBookPayload>("/folio-book", { params: params(query) })).data;
}

export async function downloadFolioBookCsv(query: FolioBookQuery = {}): Promise<void> {
  const response = await api.get<Blob>("/folio-book/export.csv", {
    params: params(query),
    responseType: "blob",
  });
  const url = URL.createObjectURL(response.data);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "LoanHub-Folio-Book.csv";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
}
