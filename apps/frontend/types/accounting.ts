export type AccountingAccount = {
    id: string;
    scope_key: string;
    scope_type: string;
    company_id: string | null;
    branch_id: string | null;
    parent_id: string | null;
    code: string;
    name: string;
    account_type: string;
    normal_balance: string;
    description: string | null;
    is_system: boolean;
    is_active: boolean;
    created_at: string;
};

export type JournalLine = {
    id: string;
    account_id: string;
    description: string | null;
    debit: number;
    credit: number;
    account: AccountingAccount;
};

export type JournalEntry = {
    id: string;
    scope_key: string;
    scope_type: string;
    company_id: string | null;
    branch_id: string | null;
    entry_number: string;
    entry_date: string;
    description: string;
    reference_type: string | null;
    reference_id: string | null;
    status: string;
    total_debit: number;
    total_credit: number;
    posted_at: string | null;
    created_at: string;
    lines: JournalLine[];
};

export type TrialBalance = {
    from_date: string | null;
    to_date: string | null;
    lines: Array<{
        account_id: string;
        code: string;
        name: string;
        account_type: string;
        debit: number;
        credit: number;
        balance: number;
    }>;
    total_debit: number;
    total_credit: number;
};

export type FinancialStatement = {
    statement: string;
    from_date: string | null;
    to_date: string;
    sections: Record<string, Array<{ code: string; name: string; amount: number }>>;
    totals: Record<string, number>;
};
