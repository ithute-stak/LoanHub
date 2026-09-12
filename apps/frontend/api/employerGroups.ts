import { api } from "@/lib/api";
import type { EmployerGroup } from "@/types/employerGroup";

export async function listEmployerGroups(search?: string): Promise<EmployerGroup[]> {
  return (
    await api.get<EmployerGroup[]>("/employer-groups", {
      params: search?.trim() ? { search: search.trim() } : undefined,
    })
  ).data;
}
