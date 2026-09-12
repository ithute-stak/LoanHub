export type Branch = {
    id: string;
    company_id: string;

    name: string;
    district: string;
    town: string | null;
    address: string | null;

    phone: string | null;
    email: string | null;

    is_active: boolean;
    is_headquarters: boolean;

    created_at?: string;
    updated_at?: string;
};

export type BranchCreatePayload = {
    company_id: string;
    name: string;
    district: string;
    town?: string | null;
    address?: string | null;
    phone?: string | null;
    email?: string | null;
    is_active?: boolean;
    is_headquarters?: boolean;
};

export type BranchUpdatePayload = Partial<
    BranchCreatePayload
>;
