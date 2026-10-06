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


export type FinancialBooksPack = {
    book_pack: string;
    accounting_basis: string;
    company_id: string;
    branch_id: string | null;
    period: { from_date: string; to_date: string };
    book_index: Array<{ order: number; book: string; purpose: string }>;
    books_of_original_entry: Array<Record<string, unknown>>;
    source_book_traceability: Record<string, unknown>;
    general_ledger: Array<{
        account_id: string;
        account_code: string;
        account_name: string;
        account_type: string;
        normal_balance: string;
        opening_balance: number;
        period_debit: number;
        period_credit: number;
        closing_balance: number;
        lines: Array<Record<string, unknown>>;
    }>;
    trial_balance: {
        total_debit: number;
        total_credit: number;
        difference: number;
        lines: TrialBalance["lines"];
    };
    income_statement: FinancialStatement;
    statement_of_financial_position: FinancialStatement;
    statement_of_changes_in_equity: Record<string, unknown>;
    statement_of_cash_flows: Record<string, unknown>;
    receipts_and_payments: Record<string, unknown>;
    financial_ratios: {
        profitability?: Record<string, number | null>;
        liquidity?: Record<string, number | null>;
        efficiency?: Record<string, number | null>;
        capital_structure?: Record<string, number | null>;
        [key: string]: unknown;
    };
    accounting_controls: {
        error_diagnostics: Record<string, unknown>;
        incomplete_records: Record<string, unknown>;
        modern_practice_readiness: Record<string, unknown>;
    };
    preparation_note: string;
};
