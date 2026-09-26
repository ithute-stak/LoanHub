import { api } from "@/lib/api";

export type FolioBookRow = {
  loan_id: string;
  folio_number: string;
  company_code: string;
  group_code: string;
  sequence: number;
  loan_reference: string;
  borrower_id: string;
  borrower_name: string;
  employer_name: string | null;
  branch_id: string | null;
  branch_name: string | null;
  principal_amount: number;
  balance: number;
  status: string;
  approved_at: string | null;
  disbursed_at: string | null;
  maturity_date: string | null;
  is_overdue: boolean;
};

export type FolioSequenceGroup = {
  company_code: string;
  group_code: string;
  loan_count: number;
  first_sequence: number | null;
  last_sequence: number | null;
  next_sequence: number;
  next_folio: string;
  gap_count: number;
  gaps: number[];
};

export type FolioIntegrity = {
  healthy: boolean;
  loan_count: number;
  missing_folio_count: number;
  missing_loan_ids: string[];
  malformed_folio_count: number;
  malformed_folios: string[];
  duplicate_folio_count: number;
  duplicate_folios: Record<string, string[]>;
  gap_count: number;
  groups: FolioSequenceGroup[];
};

export type FolioBookResponse = {
  total: number;
  skip: number;
  limit: number;
  rows: FolioBookRow[];
  integrity: FolioIntegrity;
};

export async function getFolioBook(params?: {
  search?: string;
  group_code?: string;
  status?: string;
  skip?: number;
  limit?: number;
}): Promise<FolioBookResponse> {
  return (await api.get<FolioBookResponse>("/folio-book", { params })).data;
}

export async function lookupFolio(folioNumber: string): Promise<FolioBookRow> {
  return (await api.get<FolioBookRow>(`/folio-book/lookup/${encodeURIComponent(folioNumber.trim().toUpperCase())}`)).data;
}

export async function getFolioIntegrity(): Promise<FolioIntegrity> {
  return (await api.get<FolioIntegrity>("/folio-book/integrity")).data;
}

export async function downloadFolioBookCsv(groupCode?: string): Promise<void> {
  const response = await api.get<Blob>("/folio-book/export.csv", {
    params: groupCode ? { group_code: groupCode } : undefined,
    responseType: "blob",
  });
  const url = URL.createObjectURL(response.data);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = groupCode ? `loanhub-folio-book-${groupCode}.csv` : "loanhub-folio-book.csv";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 5_000);
}
