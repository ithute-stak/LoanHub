import { api } from "@/lib/api";
import type {
    PlatformStaffAccount,
    PlatformStaffAccountCreatePayload,
    PlatformStaffAccountPayload,
} from "@/types/platformStaff";

export async function listPlatformStaff(): Promise<PlatformStaffAccount[]> {
    return (await api.get<PlatformStaffAccount[]>("/platform-staff")).data;
}

export async function createPlatformStaff(payload: PlatformStaffAccountCreatePayload): Promise<PlatformStaffAccount> {
    return (await api.post<PlatformStaffAccount>("/platform-staff", payload)).data;
}

export async function updatePlatformStaff(id: string, payload: PlatformStaffAccountPayload): Promise<PlatformStaffAccount> {
    return (await api.put<PlatformStaffAccount>(`/platform-staff/${id}`, payload)).data;
}

export async function updatePlatformStaffStatus(id: string, isActive: boolean): Promise<PlatformStaffAccount> {
    return (await api.patch<PlatformStaffAccount>(`/platform-staff/${id}/status`, null, {
        params: { is_active: isActive },
    })).data;
}
