"use client";

import Link from "next/link";
import {useEffect, useMemo, useState, type ReactNode} from "react";
import {
    Banknote,
    ChevronLeft,
    ChevronRight,
    Eye,
    FileSignature,
    FileText,
    FilterX,
    HandCoins,
    Maximize2,
    PanelLeftClose,
    PanelLeftOpen,
    Phone,
    RotateCcw,
    SlidersHorizontal,
} from "lucide-react";

import {branchApi} from "@/api/branch";
import {Badge} from "@/components/ui/badge";
import {Button} from "@/components/ui/button";
import {Card, CardContent, CardDescription, CardHeader, CardTitle} from "@/components/ui/card";
import {Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle} from "@/components/ui/dialog";
import {Input} from "@/components/ui/input";
import {Label} from "@/components/ui/label";
import {Progress} from "@/components/ui/progress";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "@/components/ui/select";
import {SuggestionSearch, fuzzySearchScore} from "@/components/ui/suggestion-search";
import { StickyFilterBar } from "@/components/ui/sticky-filter-bar";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
import {formatDate, formatMoney, titleCase} from "@/lib/format";
import {interestMethodLabel} from "@/lib/interest-methods";
import type {Branch} from "@/types/branch";
import type {CompanyClient} from "@/types/companyClient";
import type {Loan} from "@/types/loan";
import type {ContractTemplateStyle, LoanContract} from "@/types/origination";

const CONTRACT_STYLE_OPTIONS: Array<{value: ContractTemplateStyle; label: string}> = [
    {value: "loanhub_standard", label: "LoanHub standard"},
    {value: "filizwa_style", label: "Filizwa style"},
];

const PAGE_SIZES = [15, 30, 50, 100] as const;

type YesNoFilter = "all" | "yes" | "no";
type LoanContractFilter = "all" | "missing" | "generated" | "signed" | "unsigned";
type SignatureFilter = "all" | "none" | "borrower_only" | "company_only" | "both";
type DueWindow = "all" | "overdue" | "today" | "next_7" | "next_14" | "next_30" | "later" | "none";
type PaydayWindow = "all" | "today" | "next_7" | "next_14" | "next_30" | "none";
type BalanceFilter = "all" | "outstanding" | "settled";
type LinkedFilter = "all" | "linked" | "not_linked";
type SortOption =
    | "latest"
    | "oldest"
    | "due_soonest"
    | "due_latest"
    | "balance_high"
    | "balance_low"
    | "principal_high"
    | "principal_low"
    | "installment_high"
    | "installment_low"
    | "progress_high"
    | "progress_low";

type PortfolioFilters = {
    status: string;
    contract: LoanContractFilter;
    signatures: SignatureFilter;
    contractStyle: "all" | ContractTemplateStyle;
    channel: string;
    repaymentType: string;
    calculationMethod: string;
    riskLevel: string;
    overdue: YesNoFilter;
    balanceState: BalanceFilter;
    approval: "all" | "approved" | "not_approved";
    disbursement: "all" | "disbursed" | "not_disbursed";
    branchId: string;
    employment: string;
    employer: string;
    district: string;
    town: string;
    bankAccount: YesNoFilter;
    salaryAccount: YesNoFilter;
    paydayWindow: PaydayWindow;
    topUp: YesNoFilter;
    requestLink: LinkedFilter;
    offerLink: LinkedFilter;
    dueWindow: DueWindow;
    firstDueFrom: string;
    firstDueTo: string;
    maturityFrom: string;
    maturityTo: string;
    approvedFrom: string;
    approvedTo: string;
    disbursedFrom: string;
    disbursedTo: string;
    principalMin: string;
    principalMax: string;
    installmentMin: string;
    installmentMax: string;
    balanceMin: string;
    balanceMax: string;
    totalRepayableMin: string;
    totalRepayableMax: string;
    paidMin: string;
    paidMax: string;
    interestRateMin: string;
    interestRateMax: string;
    repaymentPeriodMin: string;
    repaymentPeriodMax: string;
    progressMin: string;
    progressMax: string;
    sortBy: SortOption;
};

type PortfolioRow = {
    loan: Loan;
    client?: CompanyClient;
    contract?: LoanContract;
    branch?: Branch;
    searchText: string;
    progress: number;
    nextDueDate: string | null;
    nextDueAmount: number | null;
};

const DEFAULT_FILTERS: PortfolioFilters = {
    status: "all",
    contract: "all",
    signatures: "all",
    contractStyle: "all",
    channel: "all",
    repaymentType: "all",
    calculationMethod: "all",
    riskLevel: "all",
    overdue: "all",
    balanceState: "all",
    approval: "all",
    disbursement: "all",
    branchId: "all",
    employment: "all",
    employer: "all",
    district: "all",
    town: "all",
    bankAccount: "all",
    salaryAccount: "all",
    paydayWindow: "all",
    topUp: "all",
    requestLink: "all",
    offerLink: "all",
    dueWindow: "all",
    firstDueFrom: "",
    firstDueTo: "",
    maturityFrom: "",
    maturityTo: "",
    approvedFrom: "",
    approvedTo: "",
    disbursedFrom: "",
    disbursedTo: "",
    principalMin: "",
    principalMax: "",
    installmentMin: "",
    installmentMax: "",
    balanceMin: "",
    balanceMax: "",
    totalRepayableMin: "",
    totalRepayableMax: "",
    paidMin: "",
    paidMax: "",
    interestRateMin: "",
    interestRateMax: "",
    repaymentPeriodMin: "",
    repaymentPeriodMax: "",
    progressMin: "",
    progressMax: "",
    sortBy: "latest",
};

function installmentOutstanding(installment: Loan["installments"][number]) {
    return Math.max(0, Number(installment.total_due) - Number(installment.paid_amount));
}

function contractStyle(contract: LoanContract | undefined): ContractTemplateStyle | null {
    if (!contract) return null;
    const value = String(contract.template_style ?? contract.terms_snapshot?.["contract_template_style"] ?? "").toLowerCase();
    return value === "filizwa" || value === "filizwa_style" || value === "filizwa-style"
        ? "filizwa_style"
        : "loanhub_standard";
}

function contractStyleLabel(contract: LoanContract | undefined) {
    return contractStyle(contract) === "filizwa_style" ? "Filizwa style" : "LoanHub standard";
}

function uniqueStrings(values: Array<string | null | undefined>) {
    return Array.from(new Set(values.filter((value): value is string => Boolean(value?.trim()))))
        .sort((left, right) => left.localeCompare(right));
}

function isoDay(value: string | null | undefined) {
    return value ? value.slice(0, 10) : "";
}

function parseDate(value: string) {
    const [year, month, day] = value.split("-").map(Number);
    return new Date(year, month - 1, day);
}

function todayStart() {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

function addDays(value: Date, days: number) {
    const next = new Date(value);
    next.setDate(next.getDate() + days);
    return next;
}

function sameDay(left: Date, right: Date) {
    return left.getFullYear() === right.getFullYear()
        && left.getMonth() === right.getMonth()
        && left.getDate() === right.getDate();
}

function numberFilter(value: number, minimum: string, maximum: string) {
    const min = minimum.trim() === "" ? null : Number(minimum);
    const max = maximum.trim() === "" ? null : Number(maximum);
    if (min !== null && Number.isFinite(min) && value < min) return false;
    if (max !== null && Number.isFinite(max) && value > max) return false;
    return true;
}

function dateRangeFilter(value: string | null | undefined, from: string, to: string) {
    if (!from && !to) return true;
    if (!value) return false;
    const day = isoDay(value);
    if (from && day < from) return false;
    if (to && day > to) return false;
    return true;
}

function dueWindowMatches(value: string | null, filter: DueWindow) {
    if (filter === "all") return true;
    if (filter === "none") return !value;
    if (!value) return false;

    const due = parseDate(value);
    const today = todayStart();
    if (filter === "overdue") return due < today;
    if (filter === "today") return sameDay(due, today);
    if (filter === "next_7") return due >= today && due <= addDays(today, 7);
    if (filter === "next_14") return due >= today && due <= addDays(today, 14);
    if (filter === "next_30") return due >= today && due <= addDays(today, 30);
    return due > addDays(today, 30);
}

function paydayWindowMatches(value: string | null | undefined, filter: PaydayWindow) {
    if (filter === "all") return true;
    if (filter === "none") return !value;
    if (!value) return false;

    const payday = parseDate(value);
    const today = todayStart();
    if (filter === "today") return sameDay(payday, today);
    if (filter === "next_7") return payday >= today && payday <= addDays(today, 7);
    if (filter === "next_14") return payday >= today && payday <= addDays(today, 14);
    return payday >= today && payday <= addDays(today, 30);
}

function signatureState(contract: LoanContract | undefined): Exclude<SignatureFilter, "all"> {
    if (!contract?.borrower_signed_at && !contract?.company_signed_at) return "none";
    if (contract.borrower_signed_at && contract.company_signed_at) return "both";
    if (contract.borrower_signed_at) return "borrower_only";
    return "company_only";
}

function rowSortDate(row: PortfolioRow) {
    return row.loan.disbursed_at
        ?? row.loan.approved_at
        ?? row.loan.maturity_date
        ?? row.loan.first_payment_due
        ?? row.loan.loan_reference;
}

function compareOptionalDate(left: string | null, right: string | null) {
    if (!left && !right) return 0;
    if (!left) return 1;
    if (!right) return -1;
    return left.localeCompare(right);
}

function sortRows(left: PortfolioRow, right: PortfolioRow, sortBy: SortOption) {
    switch (sortBy) {
        case "oldest": return rowSortDate(left).localeCompare(rowSortDate(right));
        case "due_soonest": return compareOptionalDate(left.nextDueDate, right.nextDueDate);
        case "due_latest": return compareOptionalDate(right.nextDueDate, left.nextDueDate);
        case "balance_high": return Number(right.loan.balance) - Number(left.loan.balance);
        case "balance_low": return Number(left.loan.balance) - Number(right.loan.balance);
        case "principal_high": return Number(right.loan.principal_amount) - Number(left.loan.principal_amount);
        case "principal_low": return Number(left.loan.principal_amount) - Number(right.loan.principal_amount);
        case "installment_high": return Number(right.loan.installment_amount) - Number(left.loan.installment_amount);
        case "installment_low": return Number(left.loan.installment_amount) - Number(right.loan.installment_amount);
        case "progress_high": return right.progress - left.progress;
        case "progress_low": return left.progress - right.progress;
        case "latest":
        default: return rowSortDate(right).localeCompare(rowSortDate(left));
    }
}

function FilterField({label, children}: {label: string; children: ReactNode}) {
    return <div className="space-y-1.5"><Label className="text-xs font-bold">{label}</Label>{children}</div>;
}

function RangeInputs({
    label,
    minimum,
    maximum,
    onMinimumChange,
    onMaximumChange,
    type = "number",
}: {
    label: string;
    minimum: string;
    maximum: string;
    onMinimumChange: (value: string) => void;
    onMaximumChange: (value: string) => void;
    type?: "number" | "date";
}) {
    return <FilterField label={label}>
        <div className="grid grid-cols-2 gap-2">
            <Input type={type} value={minimum} placeholder="Min / from" onChange={(event) => onMinimumChange(event.target.value)} />
            <Input type={type} value={maximum} placeholder="Max / to" onChange={(event) => onMaximumChange(event.target.value)} />
        </div>
    </FilterField>;
}

export function LoanPortfolioWorkspace({
    loans,
    clients,
    contracts,
    canDisburse,
    signedContractRequired,
    onOpenSchedule,
    onOpenDocuments,
    onOpenDisbursement,
    onStartCall,
}: {
    loans: Loan[];
    clients: CompanyClient[];
    contracts: LoanContract[];
    canDisburse: boolean;
    signedContractRequired: boolean;
    onOpenSchedule: (loan: Loan) => void;
    onOpenDocuments: (loan: Loan) => void;
    onOpenDisbursement: (loan: Loan) => void;
    onStartCall: (loan: Loan) => void;
}) {
    const [search, setSearch] = useState("");
    const [expanded, setExpanded] = useState(false);
    const [filtersCollapsed, setFiltersCollapsed] = useState(false);
    const [filters, setFilters] = useState<PortfolioFilters>(DEFAULT_FILTERS);
    const [page, setPage] = useState(1);
    const [pageSize, setPageSize] = useState<number>(15);
    const [branches, setBranches] = useState<Branch[]>([]);

    useEffect(() => {
        let cancelled = false;
        void branchApi.getAll()
            .then((response) => {
                if (!cancelled) setBranches(response.data);
            })
            .catch(() => {
                if (!cancelled) setBranches([]);
            });
        return () => { cancelled = true; };
    }, []);

    const clientByBorrower = useMemo(
        () => new Map(clients.map((client) => [client.borrower_id, client])),
        [clients],
    );
    const contractByLoan = useMemo(
        () => new Map(contracts.map((contract) => [contract.loan_id, contract])),
        [contracts],
    );
    const branchById = useMemo(
        () => new Map(branches.map((branch) => [branch.id, branch])),
        [branches],
    );

    const rows = useMemo<PortfolioRow[]>(() => loans.map((loan) => {
        const client = clientByBorrower.get(loan.borrower_id);
        const contract = contractByLoan.get(loan.id);
        const branch = branchById.get(loan.branch_id ?? client?.branch_id ?? "");
        const nextInstallment = [...loan.installments]
            .filter((installment) => ["pending", "partially_paid", "overdue"].includes(installment.status))
            .sort((left, right) => left.due_date.localeCompare(right.due_date) || left.installment_number - right.installment_number)[0];
        const nextDueDate = nextInstallment?.due_date ?? (Number(loan.balance) > 0 ? loan.first_payment_due : null);
        const nextDueAmount = nextInstallment ? installmentOutstanding(nextInstallment) : (Number(loan.balance) > 0 ? Number(loan.installment_amount) : null);
        const progress = Number(loan.total_repayable) > 0
            ? (Number(loan.amount_paid) / Number(loan.total_repayable)) * 100
            : 0;
        const searchText = [
            loan.id,
            loan.loan_reference,
            loan.borrower_id,
            loan.loan_request_id,
            loan.loan_offer_id,
            loan.status,
            loan.origination_channel,
            loan.repayment_type,
            loan.calculation_method,
            loan.risk_level,
            loan.branch_id,
            branch?.name,
            branch?.district,
            client?.full_name,
            client?.account_reference,
            client?.national_id,
            client?.passport_number,
            client?.phone,
            client?.email,
            client?.employment_status,
            client?.employer_name,
            client?.job_title,
            client?.district,
            client?.town_or_village,
            client?.physical_address,
            client?.bank_name,
            client?.bank_account_last4,
            client?.masked_bank_account,
            contract?.contract_number,
            contract?.status,
        ].filter(Boolean).join(" ");
        return {loan, client, contract, branch, searchText, progress, nextDueDate, nextDueAmount};
    }), [branchById, clientByBorrower, contractByLoan, loans]);

    const suggestions = useMemo(() => rows.map(({loan, client, nextDueDate}) => ({
        value: loan.loan_reference,
        label: client?.full_name ? `${client.full_name} · ${loan.loan_reference}` : loan.loan_reference,
        description: [titleCase(loan.status), formatMoney(loan.balance), nextDueDate ? `Due ${formatDate(nextDueDate)}` : null].filter(Boolean).join(" · "),
        keywords: [loan.id, loan.borrower_id, client?.phone ?? "", client?.national_id ?? "", client?.employer_name ?? ""],
    })), [rows]);

    const optionSets = useMemo(() => ({
        statuses: uniqueStrings(rows.map(({loan}) => loan.status)),
        channels: uniqueStrings(rows.map(({loan}) => loan.origination_channel)),
        repaymentTypes: uniqueStrings(rows.map(({loan}) => loan.repayment_type)),
        calculationMethods: uniqueStrings(rows.map(({loan}) => String(loan.calculation_method))),
        riskLevels: uniqueStrings(rows.map(({loan}) => loan.risk_level)),
        branchIds: uniqueStrings(rows.flatMap(({loan, client}) => [loan.branch_id, client?.branch_id])),
        employment: uniqueStrings(rows.map(({client}) => client?.employment_status)),
        employers: uniqueStrings(rows.map(({client}) => client?.employer_name)),
        districts: uniqueStrings(rows.flatMap(({client, branch}) => [client?.district, branch?.district])),
        towns: uniqueStrings(rows.flatMap(({client, branch}) => [client?.town_or_village, branch?.town])),
    }), [rows]);

    const filteredRows = useMemo(() => {
        const query = search.trim();
        const scored = rows.map((row, index) => ({
            row,
            index,
            score: query ? fuzzySearchScore(query, row.searchText) : 0,
        })).filter((item) => !query || Number.isFinite(item.score));

        if (query) scored.sort((left, right) => left.score - right.score || left.index - right.index);

        return scored
            .map(({row}) => row)
            .filter((row) => {
                const {loan, client, contract, branch, progress, nextDueDate} = row;
                const style = contractStyle(contract);
                const hasBalance = Number(loan.balance) > 0;
                const approved = Boolean(loan.approved_at);
                const disbursed = Boolean(loan.disbursed_at);
                const isTopUp = Boolean(loan.is_top_up);
                const requestLinked = Boolean(loan.loan_request_id);
                const offerLinked = Boolean(loan.loan_offer_id);

                if (filters.status !== "all" && loan.status !== filters.status) return false;
                if (filters.channel !== "all" && loan.origination_channel !== filters.channel) return false;
                if (filters.repaymentType !== "all" && loan.repayment_type !== filters.repaymentType) return false;
                if (filters.calculationMethod !== "all" && String(loan.calculation_method) !== filters.calculationMethod) return false;
                if (filters.riskLevel !== "all" && loan.risk_level !== filters.riskLevel) return false;
                if (filters.branchId !== "all" && (loan.branch_id ?? client?.branch_id ?? "") !== filters.branchId) return false;
                if (filters.employment !== "all" && (client?.employment_status ?? "") !== filters.employment) return false;
                if (filters.employer !== "all" && (client?.employer_name ?? "") !== filters.employer) return false;
                if (filters.district !== "all" && ![client?.district, branch?.district].includes(filters.district)) return false;
                if (filters.town !== "all" && ![client?.town_or_village, branch?.town].includes(filters.town)) return false;
                if (filters.overdue === "yes" && !loan.is_overdue) return false;
                if (filters.overdue === "no" && loan.is_overdue) return false;
                if (filters.balanceState === "outstanding" && !hasBalance) return false;
                if (filters.balanceState === "settled" && hasBalance) return false;
                if (filters.approval === "approved" && !approved) return false;
                if (filters.approval === "not_approved" && approved) return false;
                if (filters.disbursement === "disbursed" && !disbursed) return false;
                if (filters.disbursement === "not_disbursed" && disbursed) return false;
                if (filters.topUp === "yes" && !isTopUp) return false;
                if (filters.topUp === "no" && isTopUp) return false;
                if (filters.requestLink === "linked" && !requestLinked) return false;
                if (filters.requestLink === "not_linked" && requestLinked) return false;
                if (filters.offerLink === "linked" && !offerLinked) return false;
                if (filters.offerLink === "not_linked" && offerLinked) return false;
                if (filters.bankAccount === "yes" && !client?.has_bank_account) return false;
                if (filters.bankAccount === "no" && client?.has_bank_account) return false;
                if (filters.salaryAccount === "yes" && !client?.salary_account) return false;
                if (filters.salaryAccount === "no" && client?.salary_account) return false;
                if (!paydayWindowMatches(client?.next_salary_pay_date, filters.paydayWindow)) return false;
                if (!dueWindowMatches(nextDueDate, filters.dueWindow)) return false;

                if (filters.contract === "missing" && contract) return false;
                if (filters.contract === "generated" && !contract) return false;
                if (filters.contract === "signed" && contract?.status !== "signed") return false;
                if (filters.contract === "unsigned" && (!contract || contract.status === "signed")) return false;
                if (filters.signatures !== "all" && signatureState(contract) !== filters.signatures) return false;
                if (filters.contractStyle !== "all" && style !== filters.contractStyle) return false;

                if (!dateRangeFilter(loan.first_payment_due, filters.firstDueFrom, filters.firstDueTo)) return false;
                if (!dateRangeFilter(loan.maturity_date, filters.maturityFrom, filters.maturityTo)) return false;
                if (!dateRangeFilter(loan.approved_at, filters.approvedFrom, filters.approvedTo)) return false;
                if (!dateRangeFilter(loan.disbursed_at, filters.disbursedFrom, filters.disbursedTo)) return false;

                if (!numberFilter(Number(loan.principal_amount), filters.principalMin, filters.principalMax)) return false;
                if (!numberFilter(Number(loan.installment_amount), filters.installmentMin, filters.installmentMax)) return false;
                if (!numberFilter(Number(loan.balance), filters.balanceMin, filters.balanceMax)) return false;
                if (!numberFilter(Number(loan.total_repayable), filters.totalRepayableMin, filters.totalRepayableMax)) return false;
                if (!numberFilter(Number(loan.amount_paid), filters.paidMin, filters.paidMax)) return false;
                if (!numberFilter(Number(loan.interest_rate), filters.interestRateMin, filters.interestRateMax)) return false;
                if (!numberFilter(Number(loan.repayment_period), filters.repaymentPeriodMin, filters.repaymentPeriodMax)) return false;
                if (!numberFilter(progress, filters.progressMin, filters.progressMax)) return false;

                return true;
            })
            .sort((left, right) => sortRows(left, right, filters.sortBy));
    }, [filters, rows, search]);

    const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize));
    const safePage = Math.min(page, totalPages);
    const pageStart = (safePage - 1) * pageSize;
    const pageRows = filteredRows.slice(pageStart, pageStart + pageSize);

    useEffect(() => {
        setPage(1);
    }, [filters, pageSize, search]);

    useEffect(() => {
        if (page > totalPages) setPage(totalPages);
    }, [page, totalPages]);

    const filteredOutstanding = useMemo(
        () => filteredRows.reduce((sum, row) => sum + Number(row.loan.balance || 0), 0),
        [filteredRows],
    );
    const dueSoonCount = useMemo(
        () => filteredRows.filter((row) => dueWindowMatches(row.nextDueDate, "next_7")).length,
        [filteredRows],
    );
    const overdueCount = useMemo(
        () => filteredRows.filter((row) => row.loan.is_overdue).length,
        [filteredRows],
    );
    const missingContractCount = useMemo(
        () => filteredRows.filter((row) => !row.contract).length,
        [filteredRows],
    );
    const activeFilterCount = useMemo(() => {
        let count = search.trim() ? 1 : 0;
        (Object.keys(DEFAULT_FILTERS) as Array<keyof PortfolioFilters>).forEach((key) => {
            if (filters[key] !== DEFAULT_FILTERS[key]) count += 1;
        });
        return count;
    }, [filters, search]);

    function updateFilter<K extends keyof PortfolioFilters>(key: K, value: PortfolioFilters[K]) {
        setFilters((current) => ({...current, [key]: value}));
    }

    function resetFilters() {
        setSearch("");
        setFilters(DEFAULT_FILTERS);
        setPage(1);
    }

    function applyQuickFilter(kind: "active" | "overdue" | "due7" | "missing_contract" | "outstanding" | "ready") {
        setFilters({...DEFAULT_FILTERS});
        if (kind === "active") setFilters((current) => ({...current, status: "active"}));
        if (kind === "overdue") setFilters((current) => ({...current, overdue: "yes"}));
        if (kind === "due7") setFilters((current) => ({...current, dueWindow: "next_7"}));
        if (kind === "missing_contract") setFilters((current) => ({...current, contract: "missing"}));
        if (kind === "outstanding") setFilters((current) => ({...current, balanceState: "outstanding"}));
        if (kind === "ready") setFilters((current) => ({...current, status: "approved", contract: signedContractRequired ? "signed" : "all", disbursement: "not_disbursed"}));
        setPage(1);
    }

    const searchControl = <SuggestionSearch
        value={search}
        onValueChange={setSearch}
        suggestions={suggestions}
        minimumCharacters={1}
        maxSuggestions={12}
        placeholder="Loan, borrower, ID, phone, employer, branch, contract..."
        suggestionLabel="Company loans"
        emptyMessage="No loan matches that text."
        wrapperClassName="w-full"
    />;

    return <>
        <Card className="loanhub-panel overflow-visible rounded-2xl border shadow-sm">
            <StickyFilterBar
                ariaLabel="Company loan portfolio search and quick filters"
                className="rounded-t-2xl data-[floating=true]:rounded-2xl data-[floating=true]:border"
            >
            <CardHeader className="rounded-[inherit] border-b bg-gradient-to-r from-muted/30 via-background to-background px-5 py-5 sm:px-6">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
                    <div className="min-w-0">
                        <div className="flex items-center gap-3">
                            <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                                <Banknote className="size-5"/>
                            </div>
                            <div className="min-w-0">
                                <CardTitle className="text-lg font-black tracking-tight">Company loan portfolio</CardTitle>
                                <CardDescription className="mt-1">
                                    Search the portfolio or open the full workspace for advanced filtering and loan management.
                                </CardDescription>
                            </div>
                        </div>
                        <div className="mt-4 flex flex-wrap gap-2">
                            <Badge variant="secondary" className="rounded-full px-3">{filteredRows.length} matching</Badge>
                            <Badge variant="outline" className="rounded-full px-3">Outstanding {formatMoney(filteredOutstanding)}</Badge>
                            <Badge variant="outline" className="rounded-full px-3">Due 7 days {dueSoonCount}</Badge>
                            <Badge variant={overdueCount > 0 ? "destructive" : "outline"} className="rounded-full px-3">Overdue {overdueCount}</Badge>
                        </div>
                    </div>
                    <div className="flex w-full flex-col gap-2 sm:flex-row xl:w-auto xl:min-w-[38rem]">
                        {searchControl}
                        <Button className="shrink-0 rounded-xl" onClick={() => setExpanded(true)}>
                            <Maximize2 className="size-4"/>Workspace
                        </Button>
                    </div>
                </div>
            </CardHeader>
            </StickyFilterBar>
            <CardContent className="overflow-hidden rounded-b-2xl p-0">
                <LoanTable
                    rows={filteredRows}
                    canDisburse={canDisburse}
                    signedContractRequired={signedContractRequired}
                    onOpenSchedule={onOpenSchedule}
                    onOpenDocuments={onOpenDocuments}
                    onOpenDisbursement={onOpenDisbursement}
                    onStartCall={onStartCall}
                    compact
                />
            </CardContent>
        </Card>

        <Dialog open={expanded} onOpenChange={setExpanded}>
            <DialogContent className="flex h-[97vh] max-h-[97vh] w-[98vw] max-w-[98vw] flex-col gap-0 overflow-hidden rounded-2xl border bg-background p-0 shadow-2xl sm:max-w-[98vw]">
                <DialogHeader className="shrink-0 border-b bg-background/95 px-5 py-4 pr-14 backdrop-blur sm:px-6">
                    <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
                        <div className="min-w-0">
                            <div className="flex items-center gap-3">
                                <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                                    <Banknote className="size-5"/>
                                </div>
                                <div className="min-w-0">
                                    <DialogTitle className="text-xl font-black tracking-tight">Company loan portfolio</DialogTitle>
                                    <DialogDescription className="mt-0.5">
                                        Search, filter and manage the full company loan book from one workspace.
                                    </DialogDescription>
                                </div>
                            </div>
                            <div className="mt-3 flex flex-wrap gap-2">
                                <Badge variant="secondary" className="rounded-full px-3">{filteredRows.length} loans</Badge>
                                <Badge variant="outline" className="rounded-full px-3">Outstanding {formatMoney(filteredOutstanding)}</Badge>
                                <Badge variant="outline" className="rounded-full px-3">Due soon {dueSoonCount}</Badge>
                                <Badge variant={overdueCount > 0 ? "destructive" : "outline"} className="rounded-full px-3">{overdueCount} overdue</Badge>
                                <Badge variant="outline" className="rounded-full px-3">{missingContractCount} missing contracts</Badge>
                            </div>
                        </div>

                        <div className="w-full space-y-2 xl:w-[42rem]">
                            {searchControl}
                            <div className="flex flex-wrap items-center gap-2">
                                <Button size="sm" variant="secondary" className="rounded-lg" onClick={() => applyQuickFilter("active")}>Active</Button>
                                <Button size="sm" variant="outline" className="rounded-lg" onClick={() => applyQuickFilter("overdue")}>Overdue</Button>
                                <Button size="sm" variant="outline" className="rounded-lg" onClick={() => applyQuickFilter("due7")}>Due 7 days</Button>
                                <Button size="sm" variant="outline" className="rounded-lg" onClick={() => applyQuickFilter("missing_contract")}>Missing contract</Button>
                                <Button size="sm" variant="outline" className="rounded-lg" onClick={() => applyQuickFilter("ready")}>Ready to pay out</Button>
                                <Button size="sm" variant="ghost" className="ml-auto rounded-lg" onClick={resetFilters}>
                                    <FilterX className="size-3.5"/>Clear all
                                </Button>
                            </div>
                        </div>
                    </div>
                </DialogHeader>

                <div className={`grid min-h-0 flex-1 grid-rows-[minmax(220px,38vh)_minmax(0,1fr)] transition-[grid-template-columns] duration-300 ease-out lg:grid-rows-1 ${
                    filtersCollapsed
                        ? "lg:grid-cols-[64px_minmax(0,1fr)]"
                        : "lg:grid-cols-[320px_minmax(0,1fr)]"
                }`}>
                    <aside className="flex min-h-0 flex-col border-b bg-muted/15 lg:border-b-0 lg:border-r">
                        <div className={`flex h-14 shrink-0 items-center border-b ${filtersCollapsed ? "justify-center px-2" : "justify-between px-3"}`}>
                            {!filtersCollapsed ? <div className="flex min-w-0 items-center gap-2">
                                <SlidersHorizontal className="size-4 shrink-0 text-primary"/>
                                <p className="truncate text-sm font-black">All loan filters</p>
                                {activeFilterCount > 0 ? <Badge className="h-5 min-w-5 justify-center rounded-full px-1.5 text-[10px]">{activeFilterCount}</Badge> : null}
                            </div> : null}
                            <Button
                                size="icon"
                                variant="ghost"
                                className="hidden size-9 shrink-0 rounded-xl lg:inline-flex"
                                onClick={() => setFiltersCollapsed((current) => !current)}
                                title={filtersCollapsed ? "Expand filters" : "Collapse filters"}
                            >
                                {filtersCollapsed ? <PanelLeftOpen className="size-4"/> : <PanelLeftClose className="size-4"/>}
                            </Button>
                            <Button size="sm" variant="ghost" className="lg:hidden" onClick={resetFilters}>
                                Reset
                            </Button>
                        </div>

                        {filtersCollapsed ? <div className="hidden min-h-0 flex-1 flex-col items-center gap-2 py-3 lg:flex">
                            <Button size="icon" variant="ghost" className="relative rounded-xl" onClick={() => setFiltersCollapsed(false)} title="Open filters">
                                <SlidersHorizontal className="size-5"/>
                                {activeFilterCount > 0 ? <span className="absolute -right-1 -top-1 flex size-5 items-center justify-center rounded-full bg-primary text-[10px] font-black text-primary-foreground">{activeFilterCount}</span> : null}
                            </Button>
                            <div className="my-1 h-px w-8 bg-border"/>
                            <Button size="icon" variant="ghost" className="rounded-xl" onClick={() => applyQuickFilter("active")} title="Active loans">
                                <Banknote className="size-4"/>
                            </Button>
                            <Button size="icon" variant="ghost" className="rounded-xl" onClick={resetFilters} title="Reset all filters">
                                <RotateCcw className="size-4"/>
                            </Button>
                        </div> : <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-3">
                            <div className="space-y-3">
                            <FilterSection title="Lifecycle & contract">
                                <FilterField label="Loan status"><FilterSelect value={filters.status} allLabel="All statuses" options={optionSets.statuses} onValueChange={(value) => updateFilter("status", value)} /></FilterField>
                                <FilterField label="Contract state"><Select value={filters.contract} onValueChange={(value) => updateFilter("contract", value as LoanContractFilter)}><SelectTrigger><SelectValue/></SelectTrigger><SelectContent><SelectItem value="all">All contracts</SelectItem><SelectItem value="missing">Not generated</SelectItem><SelectItem value="generated">Generated</SelectItem><SelectItem value="signed">Fully signed</SelectItem><SelectItem value="unsigned">Generated, not fully signed</SelectItem></SelectContent></Select></FilterField>
                                <FilterField label="Signature state"><Select value={filters.signatures} onValueChange={(value) => updateFilter("signatures", value as SignatureFilter)}><SelectTrigger><SelectValue/></SelectTrigger><SelectContent><SelectItem value="all">Any signatures</SelectItem><SelectItem value="none">No signatures</SelectItem><SelectItem value="borrower_only">Borrower only</SelectItem><SelectItem value="company_only">Company only</SelectItem><SelectItem value="both">Both signed</SelectItem></SelectContent></Select></FilterField>
                                <FilterField label="Contract style"><Select value={filters.contractStyle} onValueChange={(value) => updateFilter("contractStyle", value as PortfolioFilters["contractStyle"])}><SelectTrigger><SelectValue/></SelectTrigger><SelectContent><SelectItem value="all">Any style</SelectItem>{CONTRACT_STYLE_OPTIONS.map((option) => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}</SelectContent></Select></FilterField>
                                <FilterField label="Approval"><Select value={filters.approval} onValueChange={(value) => updateFilter("approval", value as PortfolioFilters["approval"])}><SelectTrigger><SelectValue/></SelectTrigger><SelectContent><SelectItem value="all">Any approval state</SelectItem><SelectItem value="approved">Approved</SelectItem><SelectItem value="not_approved">Not approved</SelectItem></SelectContent></Select></FilterField>
                                <FilterField label="Disbursement"><Select value={filters.disbursement} onValueChange={(value) => updateFilter("disbursement", value as PortfolioFilters["disbursement"])}><SelectTrigger><SelectValue/></SelectTrigger><SelectContent><SelectItem value="all">Any disbursement state</SelectItem><SelectItem value="disbursed">Disbursed</SelectItem><SelectItem value="not_disbursed">Not disbursed</SelectItem></SelectContent></Select></FilterField>
                            </FilterSection>

                            <FilterSection title="Source, repayment & risk">
                                <FilterField label="Origination channel"><FilterSelect value={filters.channel} allLabel="All channels" options={optionSets.channels} onValueChange={(value) => updateFilter("channel", value)} /></FilterField>
                                <FilterField label="Repayment type"><FilterSelect value={filters.repaymentType} allLabel="All repayment types" options={optionSets.repaymentTypes} onValueChange={(value) => updateFilter("repaymentType", value)} /></FilterField>
                                <FilterField label="Interest method"><FilterSelect value={filters.calculationMethod} allLabel="All interest methods" options={optionSets.calculationMethods} labelFor={interestMethodLabel} onValueChange={(value) => updateFilter("calculationMethod", value)} /></FilterField>
                                <FilterField label="Risk level"><FilterSelect value={filters.riskLevel} allLabel="All risk levels" options={optionSets.riskLevels} onValueChange={(value) => updateFilter("riskLevel", value)} /></FilterField>
                                <FilterField label="Top-up loan"><YesNoSelect value={filters.topUp} allLabel="All loans" yesLabel="Top-up only" noLabel="Not top-up" onValueChange={(value) => updateFilter("topUp", value)} /></FilterField>
                                <FilterField label="Loan request link"><LinkedSelect value={filters.requestLink} onValueChange={(value) => updateFilter("requestLink", value)} /></FilterField>
                                <FilterField label="Accepted offer link"><LinkedSelect value={filters.offerLink} onValueChange={(value) => updateFilter("offerLink", value)} /></FilterField>
                            </FilterSection>

                            <FilterSection title="Collections & due dates">
                                <FilterField label="Overdue state"><YesNoSelect value={filters.overdue} allLabel="All loans" yesLabel="Overdue only" noLabel="Not overdue" onValueChange={(value) => updateFilter("overdue", value)} /></FilterField>
                                <FilterField label="Outstanding balance"><Select value={filters.balanceState} onValueChange={(value) => updateFilter("balanceState", value as BalanceFilter)}><SelectTrigger><SelectValue/></SelectTrigger><SelectContent><SelectItem value="all">All balances</SelectItem><SelectItem value="outstanding">Outstanding only</SelectItem><SelectItem value="settled">Settled / zero balance</SelectItem></SelectContent></Select></FilterField>
                                <FilterField label="Next installment due"><Select value={filters.dueWindow} onValueChange={(value) => updateFilter("dueWindow", value as DueWindow)}><SelectTrigger><SelectValue/></SelectTrigger><SelectContent><SelectItem value="all">Any due date</SelectItem><SelectItem value="overdue">Past due</SelectItem><SelectItem value="today">Due today</SelectItem><SelectItem value="next_7">Next 7 days</SelectItem><SelectItem value="next_14">Next 14 days</SelectItem><SelectItem value="next_30">Next 30 days</SelectItem><SelectItem value="later">After 30 days</SelectItem><SelectItem value="none">No upcoming installment</SelectItem></SelectContent></Select></FilterField>
                                <RangeInputs label="First payment due" type="date" minimum={filters.firstDueFrom} maximum={filters.firstDueTo} onMinimumChange={(value) => updateFilter("firstDueFrom", value)} onMaximumChange={(value) => updateFilter("firstDueTo", value)} />
                                <RangeInputs label="Maturity date" type="date" minimum={filters.maturityFrom} maximum={filters.maturityTo} onMinimumChange={(value) => updateFilter("maturityFrom", value)} onMaximumChange={(value) => updateFilter("maturityTo", value)} />
                                <RangeInputs label="Approved date" type="date" minimum={filters.approvedFrom} maximum={filters.approvedTo} onMinimumChange={(value) => updateFilter("approvedFrom", value)} onMaximumChange={(value) => updateFilter("approvedTo", value)} />
                                <RangeInputs label="Disbursed date" type="date" minimum={filters.disbursedFrom} maximum={filters.disbursedTo} onMinimumChange={(value) => updateFilter("disbursedFrom", value)} onMaximumChange={(value) => updateFilter("disbursedTo", value)} />
                            </FilterSection>

                            <FilterSection title="Borrower & company">
                                <FilterField label="Branch"><Select value={filters.branchId} onValueChange={(value) => updateFilter("branchId", value)}><SelectTrigger><SelectValue/></SelectTrigger><SelectContent><SelectItem value="all">All branches</SelectItem>{optionSets.branchIds.map((branchId) => { const branch = branchById.get(branchId); return <SelectItem key={branchId} value={branchId}>{branch ? `${branch.name} · ${branch.district}` : branchId}</SelectItem>; })}</SelectContent></Select></FilterField>
                                <FilterField label="Employment"><FilterSelect value={filters.employment} allLabel="All employment" options={optionSets.employment} onValueChange={(value) => updateFilter("employment", value)} /></FilterField>
                                <FilterField label="Employer"><FilterSelect value={filters.employer} allLabel="All employers" options={optionSets.employers} rawLabels onValueChange={(value) => updateFilter("employer", value)} /></FilterField>
                                <FilterField label="District"><FilterSelect value={filters.district} allLabel="All districts" options={optionSets.districts} rawLabels onValueChange={(value) => updateFilter("district", value)} /></FilterField>
                                <FilterField label="Town / village"><FilterSelect value={filters.town} allLabel="All towns" options={optionSets.towns} rawLabels onValueChange={(value) => updateFilter("town", value)} /></FilterField>
                                <FilterField label="Bank account"><YesNoSelect value={filters.bankAccount} allLabel="Any bank state" yesLabel="Has bank account" noLabel="No bank account" onValueChange={(value) => updateFilter("bankAccount", value)} /></FilterField>
                                <FilterField label="Salary account"><YesNoSelect value={filters.salaryAccount} allLabel="Any salary account" yesLabel="Salary account" noLabel="Not salary account" onValueChange={(value) => updateFilter("salaryAccount", value)} /></FilterField>
                                <FilterField label="Next salary/pay date"><Select value={filters.paydayWindow} onValueChange={(value) => updateFilter("paydayWindow", value as PaydayWindow)}><SelectTrigger><SelectValue/></SelectTrigger><SelectContent><SelectItem value="all">Any pay date</SelectItem><SelectItem value="today">Today</SelectItem><SelectItem value="next_7">Next 7 days</SelectItem><SelectItem value="next_14">Next 14 days</SelectItem><SelectItem value="next_30">Next 30 days</SelectItem><SelectItem value="none">Not recorded</SelectItem></SelectContent></Select></FilterField>
                            </FilterSection>

                            <FilterSection title="Amounts & progress">
                                <RangeInputs label="Principal" minimum={filters.principalMin} maximum={filters.principalMax} onMinimumChange={(value) => updateFilter("principalMin", value)} onMaximumChange={(value) => updateFilter("principalMax", value)} />
                                <RangeInputs label="Installment" minimum={filters.installmentMin} maximum={filters.installmentMax} onMinimumChange={(value) => updateFilter("installmentMin", value)} onMaximumChange={(value) => updateFilter("installmentMax", value)} />
                                <RangeInputs label="Outstanding balance" minimum={filters.balanceMin} maximum={filters.balanceMax} onMinimumChange={(value) => updateFilter("balanceMin", value)} onMaximumChange={(value) => updateFilter("balanceMax", value)} />
                                <RangeInputs label="Total repayable" minimum={filters.totalRepayableMin} maximum={filters.totalRepayableMax} onMinimumChange={(value) => updateFilter("totalRepayableMin", value)} onMaximumChange={(value) => updateFilter("totalRepayableMax", value)} />
                                <RangeInputs label="Amount paid" minimum={filters.paidMin} maximum={filters.paidMax} onMinimumChange={(value) => updateFilter("paidMin", value)} onMaximumChange={(value) => updateFilter("paidMax", value)} />
                                <RangeInputs label="Interest rate %" minimum={filters.interestRateMin} maximum={filters.interestRateMax} onMinimumChange={(value) => updateFilter("interestRateMin", value)} onMaximumChange={(value) => updateFilter("interestRateMax", value)} />
                                <RangeInputs label="Repayment period" minimum={filters.repaymentPeriodMin} maximum={filters.repaymentPeriodMax} onMinimumChange={(value) => updateFilter("repaymentPeriodMin", value)} onMaximumChange={(value) => updateFilter("repaymentPeriodMax", value)} />
                                <RangeInputs label="Progress %" minimum={filters.progressMin} maximum={filters.progressMax} onMinimumChange={(value) => updateFilter("progressMin", value)} onMaximumChange={(value) => updateFilter("progressMax", value)} />
                                <FilterField label="Sort"><Select value={filters.sortBy} onValueChange={(value) => updateFilter("sortBy", value as SortOption)}><SelectTrigger><SelectValue/></SelectTrigger><SelectContent><SelectItem value="latest">Latest first</SelectItem><SelectItem value="oldest">Oldest first</SelectItem><SelectItem value="due_soonest">Due soonest</SelectItem><SelectItem value="due_latest">Due latest</SelectItem><SelectItem value="balance_high">Highest balance</SelectItem><SelectItem value="balance_low">Lowest balance</SelectItem><SelectItem value="principal_high">Highest principal</SelectItem><SelectItem value="principal_low">Lowest principal</SelectItem><SelectItem value="installment_high">Highest installment</SelectItem><SelectItem value="installment_low">Lowest installment</SelectItem><SelectItem value="progress_high">Highest progress</SelectItem><SelectItem value="progress_low">Lowest progress</SelectItem></SelectContent></Select></FilterField>
                            </FilterSection>
                            </div>

                        </div>}
                    </aside>

                    <section className="flex min-h-0 min-w-0 flex-col bg-background">
                        <div className="flex min-h-14 shrink-0 flex-wrap items-center justify-between gap-3 border-b px-4 py-2.5 sm:px-5">
                            <div className="min-w-0">
                                <p className="text-sm font-bold">{filteredRows.length} matching loans</p>
                                <p className="truncate text-xs text-muted-foreground">
                                    Filtered loan records with borrower, source, due-date, contract and balance context.
                                </p>
                            </div>
                            <div className="flex items-center gap-2">
                                <Label className="hidden text-xs text-muted-foreground sm:block">Rows per page</Label>
                                <Select value={String(pageSize)} onValueChange={(value) => setPageSize(Number(value))}>
                                    <SelectTrigger className="h-9 w-[84px] rounded-xl"><SelectValue/></SelectTrigger>
                                    <SelectContent>{PAGE_SIZES.map((size) => <SelectItem key={size} value={String(size)}>{size}</SelectItem>)}</SelectContent>
                                </Select>
                            </div>
                        </div>

                        <div className="min-h-0 min-w-0 flex-1 overflow-hidden">
                            <LoanTable
                                rows={pageRows}
                                canDisburse={canDisburse}
                                signedContractRequired={signedContractRequired}
                                onOpenSchedule={onOpenSchedule}
                                onOpenDocuments={onOpenDocuments}
                                onOpenDisbursement={onOpenDisbursement}
                                onStartCall={onStartCall}
                            />
                        </div>

                        <div className="flex min-h-14 shrink-0 flex-col justify-center gap-3 border-t bg-background/95 px-4 py-2 backdrop-blur sm:flex-row sm:items-center sm:justify-between sm:px-5">
                            <p className="text-xs text-muted-foreground sm:text-sm">
                                Showing <span className="font-bold text-foreground">{filteredRows.length === 0 ? 0 : pageStart + 1}</span>–<span className="font-bold text-foreground">{Math.min(pageStart + pageSize, filteredRows.length)}</span> of <span className="font-bold text-foreground">{filteredRows.length}</span>
                            </p>
                            <div className="flex items-center gap-2">
                                <Button size="sm" variant="outline" className="h-9 rounded-xl" disabled={safePage <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>
                                    <ChevronLeft className="size-4"/>Previous
                                </Button>
                                <div className="flex h-9 min-w-[82px] items-center justify-center rounded-xl border bg-muted/30 px-3 text-xs font-bold">
                                    {safePage} / {totalPages}
                                </div>
                                <Button size="sm" variant="outline" className="h-9 rounded-xl" disabled={safePage >= totalPages} onClick={() => setPage((current) => Math.min(totalPages, current + 1))}>
                                    Next<ChevronRight className="size-4"/>
                                </Button>
                            </div>
                        </div>
                    </section>
                </div>
            </DialogContent>
        </Dialog>
    </>;
}

function FilterSection({title, children}: {title: string; children: ReactNode}) {
    return <section className="overflow-hidden rounded-xl border bg-background shadow-sm">
        <div className="border-b bg-muted/30 px-3 py-2.5">
            <p className="text-[10px] font-black uppercase tracking-[0.14em] text-muted-foreground">{title}</p>
        </div>
        <div className="space-y-3 p-3">{children}</div>
    </section>;
}

function FilterSelect({
    value,
    allLabel,
    options,
    labelFor,
    rawLabels = false,
    onValueChange,
}: {
    value: string;
    allLabel: string;
    options: string[];
    labelFor?: (value: string) => string;
    rawLabels?: boolean;
    onValueChange: (value: string) => void;
}) {
    return <Select value={value} onValueChange={onValueChange}>
        <SelectTrigger><SelectValue/></SelectTrigger>
        <SelectContent>
            <SelectItem value="all">{allLabel}</SelectItem>
            {options.map((option) => <SelectItem key={option} value={option}>{labelFor ? labelFor(option) : rawLabels ? option : titleCase(option)}</SelectItem>)}
        </SelectContent>
    </Select>;
}

function YesNoSelect({value, allLabel, yesLabel, noLabel, onValueChange}: {
    value: YesNoFilter;
    allLabel: string;
    yesLabel: string;
    noLabel: string;
    onValueChange: (value: YesNoFilter) => void;
}) {
    return <Select value={value} onValueChange={(next) => onValueChange(next as YesNoFilter)}>
        <SelectTrigger><SelectValue/></SelectTrigger>
        <SelectContent><SelectItem value="all">{allLabel}</SelectItem><SelectItem value="yes">{yesLabel}</SelectItem><SelectItem value="no">{noLabel}</SelectItem></SelectContent>
    </Select>;
}

function LinkedSelect({value, onValueChange}: {value: LinkedFilter; onValueChange: (value: LinkedFilter) => void}) {
    return <Select value={value} onValueChange={(next) => onValueChange(next as LinkedFilter)}>
        <SelectTrigger><SelectValue/></SelectTrigger>
        <SelectContent><SelectItem value="all">Any linkage</SelectItem><SelectItem value="linked">Linked</SelectItem><SelectItem value="not_linked">Not linked</SelectItem></SelectContent>
    </Select>;
}

function LoanTable({
    rows,
    canDisburse,
    signedContractRequired,
    onOpenSchedule,
    onOpenDocuments,
    onOpenDisbursement,
    onStartCall,
    compact = false,
}: {
    rows: PortfolioRow[];
    canDisburse: boolean;
    signedContractRequired: boolean;
    onOpenSchedule: (loan: Loan) => void;
    onOpenDocuments: (loan: Loan) => void;
    onOpenDisbursement: (loan: Loan) => void;
    onStartCall: (loan: Loan) => void;
    compact?: boolean;
}) {
    return <div className={compact
        ? "min-w-0 overflow-x-auto [&_[data-slot=table-container]]:overflow-visible"
        : "h-full min-h-0 min-w-0 overflow-auto [&_[data-slot=table-container]]:overflow-visible"
    }>
        <Table className={compact ? "min-w-[1040px]" : "min-w-[1340px] table-fixed"}>
            <TableHeader className={compact ? "bg-muted/20" : "sticky top-0 z-20 bg-background/95 shadow-[0_1px_0_hsl(var(--border))] backdrop-blur"}>
                <TableRow className="hover:bg-transparent">
                    <TableHead className={compact ? "min-w-[15rem] pl-4" : "w-[190px] pl-4"}>Loan</TableHead>
                    {!compact ? <TableHead className="w-[170px]">Borrower</TableHead> : null}
                    {!compact ? <TableHead className="w-[135px]">Branch / channel</TableHead> : null}
                    <TableHead className={compact ? "text-right" : "w-[100px] text-right"}>Principal</TableHead>
                    <TableHead className={compact ? "text-right" : "w-[100px] text-right"}>Instalment</TableHead>
                    <TableHead className={compact ? "text-right" : "w-[100px] text-right"}>Balance</TableHead>
                    <TableHead className={compact ? "" : "w-[120px]"}>Next due</TableHead>
                    <TableHead className={compact ? "min-w-[8rem]" : "w-[120px]"}>Progress</TableHead>
                    <TableHead className={compact ? "" : "w-[95px]"}>Status</TableHead>
                    <TableHead className={compact ? "" : "w-[105px]"}>Contract</TableHead>
                    <TableHead className={compact ? "pr-4 text-right" : "w-[125px] pr-4 text-right"}>Actions</TableHead>
                </TableRow>
            </TableHeader>
            <TableBody>
                {rows.length === 0 ? <TableRow>
                    <TableCell colSpan={compact ? 9 : 11} className="h-72 whitespace-normal text-center">
                        <div className="mx-auto flex max-w-sm flex-col items-center justify-center py-10">
                            <div className="mb-3 flex size-12 items-center justify-center rounded-2xl bg-muted">
                                <SlidersHorizontal className="size-5 text-muted-foreground"/>
                            </div>
                            <p className="font-bold">No loans found</p>
                            <p className="mt-1 text-sm text-muted-foreground">Adjust the search or filters to see more loan records.</p>
                        </div>
                    </TableCell>
                </TableRow> : rows.map((row) => {
                    const {loan, client, contract, branch, progress, nextDueDate, nextDueAmount} = row;
                    const canPay = Number(loan.balance) > 0 && ["active", "defaulted"].includes(loan.status);
                    const canPayout = canDisburse && loan.status === "approved" && (!signedContractRequired || contract?.status === "signed");
                    const blockedPayout = canDisburse && loan.status === "approved" && signedContractRequired && contract?.status !== "signed";
                    const safeProgress = Math.max(0, Math.min(100, progress));

                    return <TableRow key={loan.id} className="group hover:bg-muted/35">
                        <TableCell className="pl-4">
                            <div className="min-w-0">
                                <div className="flex items-center gap-1.5">
                                    <p className="max-w-[180px] truncate font-mono text-[11px] font-black text-primary" title={loan.loan_reference}>{loan.loan_reference}</p>
                                    {loan.is_top_up ? <Badge variant="secondary" className="h-5 rounded-full px-1.5 text-[9px]">TOP-UP</Badge> : null}
                                </div>
                                {compact ? <>
                                    <p className="mt-1 max-w-[220px] truncate text-xs font-semibold">{client?.full_name ?? "Borrower"}</p>
                                    <p className="mt-0.5 max-w-[220px] truncate text-[10px] text-muted-foreground">{titleCase(loan.origination_channel)} · {interestMethodLabel(loan.calculation_method)}</p>
                                </> : <p className="mt-1 max-w-[180px] truncate text-[10px] text-muted-foreground" title={loan.id}>{loan.id}</p>}
                            </div>
                        </TableCell>

                        {!compact ? <TableCell>
                            <div className="min-w-0">
                                <p className="max-w-[160px] truncate text-xs font-bold" title={client?.full_name}>{client?.full_name ?? "Borrower"}</p>
                                <p className="mt-1 truncate text-[10px] text-muted-foreground">{client?.phone ?? "No phone"}</p>
                                <p className="mt-0.5 max-w-[160px] truncate text-[10px] text-muted-foreground" title={client?.employer_name ?? undefined}>{titleCase(client?.employment_status ?? "unrecorded")}{client?.employer_name ? ` · ${client.employer_name}` : ""}</p>
                            </div>
                        </TableCell> : null}

                        {!compact ? <TableCell>
                            <p className="max-w-[125px] truncate text-xs font-semibold" title={branch?.name}>{branch?.name ?? "Unassigned"}</p>
                            <p className="mt-1 max-w-[125px] truncate text-[10px] text-muted-foreground">{titleCase(loan.origination_channel)}</p>
                            <p className="mt-0.5 max-w-[125px] truncate text-[10px] text-muted-foreground">{titleCase(loan.repayment_type)} · {interestMethodLabel(loan.calculation_method)}</p>
                        </TableCell> : null}

                        <TableCell className="text-right text-xs tabular-nums">{formatMoney(loan.principal_amount)}</TableCell>
                        <TableCell className="text-right text-xs font-black tabular-nums">{formatMoney(loan.installment_amount)}</TableCell>
                        <TableCell className="text-right text-xs font-black tabular-nums">{formatMoney(loan.balance)}</TableCell>

                        <TableCell>{nextDueDate ? <div>
                            <p className="text-xs font-semibold">{formatDate(nextDueDate)}</p>
                            <p className="mt-1 text-[10px] text-muted-foreground">{nextDueAmount !== null ? formatMoney(nextDueAmount) : "Scheduled"}</p>
                        </div> : <span className="text-[10px] text-muted-foreground">None upcoming</span>}</TableCell>

                        <TableCell>
                            <div className="w-full min-w-[88px]">
                                <div className="mb-1 flex items-center justify-between gap-2">
                                    <span className="text-[10px] font-bold tabular-nums">{safeProgress.toFixed(0)}%</span>
                                </div>
                                <Progress className="h-1.5" value={safeProgress}/>
                            </div>
                        </TableCell>

                        <TableCell>
                            <div className="flex flex-col items-start gap-1">
                                <Badge variant={loan.status === "active" || loan.status === "completed" ? "default" : "secondary"} className="h-5 rounded-full px-2 text-[9px] font-bold">{titleCase(loan.status)}</Badge>
                                {loan.is_overdue ? <Badge variant="destructive" className="h-5 rounded-full px-2 text-[9px]">Overdue</Badge> : <span className="text-[9px] text-muted-foreground">{titleCase(loan.risk_level)} risk</span>}
                            </div>
                        </TableCell>

                        <TableCell>{contract ? <div className="min-w-0">
                            <Badge variant={contract.status === "signed" ? "default" : "secondary"} className="h-5 rounded-full px-2 text-[9px]">{titleCase(contract.status)}</Badge>
                            {!compact ? <>
                                <p className="mt-1 max-w-[95px] truncate text-[9px] text-muted-foreground" title={contract.contract_number}>{contract.contract_number}</p>
                                <p className="mt-0.5 max-w-[95px] truncate text-[9px] text-muted-foreground">{contractStyleLabel(contract)}</p>
                            </> : null}
                        </div> : <Badge variant="outline" className="rounded-full text-[9px] text-muted-foreground">Missing</Badge>}</TableCell>

                        <TableCell className="pr-4">
                            <div className="flex justify-end gap-1">
                                <Button size="icon-sm" variant="ghost" className="rounded-lg" onClick={() => onOpenSchedule(loan)} title="View payment schedule" aria-label={`View schedule for ${loan.loan_reference}`}>
                                    <Eye className="size-4"/>
                                </Button>
                                <Button size="icon-sm" variant="ghost" className="rounded-lg" onClick={() => onOpenDocuments(loan)} title="Open loan documents" aria-label={`Open documents for ${loan.loan_reference}`}>
                                    <FileText className="size-4"/>
                                </Button>
                                <Button size="icon-sm" variant="ghost" className="rounded-lg" onClick={() => onStartCall(loan)} title="Call borrower" aria-label={`Call borrower for ${loan.loan_reference}`}>
                                    <Phone className="size-4"/>
                                </Button>
                                {canPay ? <Button size="icon-sm" className="rounded-lg" asChild>
                                    <Link href={`/company/cashier?loan=${encodeURIComponent(loan.loan_reference)}`} title="Receive loan payment" aria-label={`Receive payment for ${loan.loan_reference}`}>
                                        <HandCoins className="size-4"/>
                                    </Link>
                                </Button> : null}
                                {canPayout ? <Button size="icon-sm" className="rounded-lg" onClick={() => onOpenDisbursement(loan)} title="Disburse loan" aria-label={`Disburse ${loan.loan_reference}`}>
                                    <Banknote className="size-4"/>
                                </Button> : null}
                                {blockedPayout ? <Button size="icon-sm" variant="outline" className="rounded-lg" disabled title="Generate and fully sign the contract before disbursement" aria-label={`Contract must be signed before disbursing ${loan.loan_reference}`}>
                                    <FileSignature className="size-4"/>
                                </Button> : null}
                            </div>
                        </TableCell>
                    </TableRow>;
                })}
            </TableBody>
        </Table>
    </div>;
}
