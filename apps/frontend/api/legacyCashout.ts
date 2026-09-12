import { api } from "@/lib/api";
import type { LegacyCashoutCapture, LegacyCashoutCaptureInput } from "@/types/legacyCashout";

const ROOT = "/legacy-cashout-register";

export async function listLegacyCashoutCaptures(): Promise<LegacyCashoutCapture[]> {
  const response = await api.get<LegacyCashoutCapture[]>(ROOT);
  return response.data;
}

export async function createLegacyCashoutCapture(
  payload: LegacyCashoutCaptureInput,
): Promise<LegacyCashoutCapture> {
  const response = await api.post<LegacyCashoutCapture>(ROOT, payload);
  return response.data;
}

export async function updateLegacyCashoutCapture(
  id: string,
  payload: LegacyCashoutCaptureInput,
): Promise<LegacyCashoutCapture> {
  const response = await api.put<LegacyCashoutCapture>(ROOT + "/" + id, payload);
  return response.data;
}

export async function reviewLegacyCashoutCapture(
  id: string,
  payload: { approve_for_posting: boolean; verified_against_cashout_book: boolean; notes?: string | null },
): Promise<LegacyCashoutCapture> {
  const response = await api.post<LegacyCashoutCapture>(ROOT + "/" + id + "/review", payload);
  return response.data;
}

export async function postLegacyCashoutCapture(id: string): Promise<LegacyCashoutCapture> {
  const response = await api.post<LegacyCashoutCapture>(ROOT + "/" + id + "/post");
  return response.data;
}
