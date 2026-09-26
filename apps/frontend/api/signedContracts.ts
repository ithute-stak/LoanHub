import { api } from "@/lib/api";

export type SignedContractIntakeStatus = "filed" | "review" | "duplicate" | "rejected";

export type SignedContractIntakeResult = {
  file_id?: string | null;
  original_name: string;
  status: SignedContractIntakeStatus;
  client_account_id?: string | null;
  client_name?: string | null;
  evidence_types: string[];
  extraction_method?: string | null;
  detail: string;
};

export type SignedContractReviewItem = {
  file_id: string;
  reference: string;
  original_name: string;
  size_bytes: number;
  mime_type: string;
  description?: string | null;
  uploaded_at: string;
};

export async function uploadSignedContracts(files: File[]): Promise<SignedContractIntakeResult[]> {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  return (await api.post<SignedContractIntakeResult[]>("/signed-contracts/intake", form)).data;
}

export async function listSignedContractReviewQueue(): Promise<SignedContractReviewItem[]> {
  return (await api.get<SignedContractReviewItem[]>("/signed-contracts/review")).data;
}

export async function assignSignedContract(
  fileId: string,
  clientAccountId: string,
): Promise<{ file_id: string; client_account_id: string; client_name: string; status: "filed" }> {
  return (
    await api.post(`/signed-contracts/review/${fileId}/assign`, {
      client_account_id: clientAccountId,
    })
  ).data;
}

export async function openManagedFile(fileId: string): Promise<void> {
  const response = await api.get<Blob>(`/files/${fileId}/content`, { responseType: "blob" });
  const url = URL.createObjectURL(response.data);
  window.open(url, "_blank", "noopener,noreferrer");
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
