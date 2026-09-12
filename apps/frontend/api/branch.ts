import type {
    Branch,
    BranchCreatePayload,
    BranchUpdatePayload,
} from "@/types/branch";

import {
    api,
} from "@/lib/api";

export const branchApi = {
    getAll: () =>
        api.get<Branch[]>(
            "/branches/",
        ),

    getByCompany: (
        companyId: string,
    ) =>
        api.get<Branch[]>(
            `/branches/company/${companyId}`,
        ),

    getOne: (
        branchId: string,
    ) =>
        api.get<Branch>(
            `/branches/${branchId}`,
        ),

    create: (
        payload: BranchCreatePayload,
    ) =>
        api.post<Branch>(
            "/branches/",
            payload,
        ),

    update: (
        branchId: string,
        payload: BranchUpdatePayload,
    ) =>
        api.put<Branch>(
            `/branches/${branchId}`,
            payload,
        ),

    activate: (
        branchId: string,
    ) =>
        api.patch(
            `/branches/${branchId}/activate`,
        ),

    deactivate: (
        branchId: string,
    ) =>
        api.patch(
            `/branches/${branchId}/deactivate`,
        ),

    delete: (
        branchId: string,
    ) =>
        api.delete(
            `/branches/${branchId}`,
        ),
};
