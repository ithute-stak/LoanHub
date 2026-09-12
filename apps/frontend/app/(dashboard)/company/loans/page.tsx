"use client";

import Link from "next/link";
import {useRouter} from "next/navigation";
import {useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode} from "react";
import {
    Banknote,
    Calculator,
    CalendarClock,
    CheckCircle2,
    Download,
    Eye,
    FileClock,
    FileSignature,
    FileText,
    HandCoins,
    PenLine,
    Printer,
    ReceiptText,
    RefreshCcw,
    Search,
    ShieldCheck,
    Sparkles,
    UserSearch,
    WalletCards,
    type LucideIcon,
} from "lucide-react";

import {listCompanyClients} from "@/api/companyClients";
import {expenseManagementApi} from "@/api/expenseManagement";
import {
    calculateLoan,
    disburseLoan,
    adjustInstallmentDueDate,
    getLoan,
    listLoanPaymentSlips,
    listLoans,
    payLoanInstallment,
    openLoanDocumentPdf,
    openLoanPaymentSlipPdf,
} from "@/api/loans";
import {originationApi} from "@/api/origination";
import {
    DEFAULT_PAYMENT_METHOD_OPTIONS,
    EMPTY_PAYMENT_EVIDENCE,
    PaymentMethodFields,
    type PaymentEvidence,
} from "@/components/payments/payment-method-fields";
import {
    InstallmentDueDateFields,
    generateMonthlyInstallmentDueDates,
    installmentDueDatesComplete,
} from "@/components/loans/installment-due-date-fields";
import {EarlySettlementDialog} from "@/components/loans/early-settlement-dialog";
import {LoanPortfolioWorkspace} from "@/components/loans/loan-portfolio-workspace";
import {Alert, AlertDescription, AlertTitle} from "@/components/ui/alert";
import {Badge} from "@/components/ui/badge";
import {Button} from "@/components/ui/button";
import {Card, CardContent, CardDescription, CardHeader, CardTitle} from "@/components/ui/card";
import {CustomDialog} from "@/components/ui/custom-dialog";
import {DialogFooter} from "@/components/ui/dialog";
import {Input} from "@/components/ui/input";
import {Label} from "@/components/ui/label";
import {LoadingButton} from "@/components/ui/loading-button";
import {Textarea} from "@/components/ui/textarea";
import {PageLoader} from "@/components/ui/page-loader";
import {SuggestionSearch} from "@/components/ui/suggestion-search";
import {Progress} from "@/components/ui/progress";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "@/components/ui/select";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
import {Tabs, TabsContent, TabsList, TabsTrigger} from "@/components/ui/tabs";
import {createIdempotencyKey, formatDate, formatMoney, titleCase} from "@/lib/format";
import {INTEREST_METHOD_OPTIONS, interestMethodLabel, interestMethodOption} from "@/lib/interest-methods";
import {useTenant} from "@/provider/tenantProvider";
import {CASHIER_ROLES, DIRECT_APPLICATION_ROLES, FINANCE_ROLES, LENDING_ROLES, hasRole} from "@/types/auth";
import type {CompanyClient} from "@/types/companyClient";
import type {PaymentMethodOption} from "@/types/expenseManagement";
import type {
    InterestMethod,
    Loan,
    LoanCalculation,
    LoanDocumentKind,
    LoanPaymentSlip,
    RepaymentInstallment
} from "@/types/loan";
import type {ContractTemplateStyle, LoanContract, OriginationPolicy} from "@/types/origination";
import {getErrorMessage} from "@/utils/apiError";
import {toast} from "@/utils/toast";

function dateInputValue(value: Date): string {
    return value.toISOString().slice(0, 10);
}

function dayAfterIsoDate(value: string): string {
    const [year, month, day] = value.split("-").map(Number);
    const next = new Date(Date.UTC(year, month - 1, day + 1));
    return next.toISOString().slice(0, 10);
}

function dayBeforeIsoDate(value: string): string {
    const [year, month, day] = value.split("-").map(Number);
    const previous = new Date(Date.UTC(year, month - 1, day - 1));
    return previous.toISOString().slice(0, 10);
}

function installmentOutstanding(item: RepaymentInstallment): number {
    return Math.max(0, Number(item.total_due) - Number(item.paid_amount));
}

const CONTRACT_ELIGIBLE_STATUSES = new Set(["approved"]);

const CONTRACT_TEMPLATE_OPTIONS: Array<{ value: ContractTemplateStyle; label: string }> = [
    {value: "loanhub_standard", label: "LoanHub standard"},
    {value: "filizwa_style", label: "Filizwa style"},
];

function contractTemplateStyle(contract: LoanContract | null | undefined): ContractTemplateStyle {
    const raw = String(
        contract?.template_style ??
        contract?.terms_snapshot?.["contract_template_style"] ??
        "",
    ).trim().toLowerCase();

    return raw === "filizwa_style" || raw === "filizwa" || raw === "filizwa-style"
        ? "filizwa_style"
        : "loanhub_standard";
}

function contractTemplateLabel(style: ContractTemplateStyle): string {
    return style === "filizwa_style" ? "Filizwa style" : "LoanHub standard";
}

type WorkspaceTab = "portfolio" | "contracts" | "calculator";

export default function CompanyLoansPage() {
    const router = useRouter();
    const {activeRole} = useTenant();
    const canManageContracts = hasRole(activeRole, DIRECT_APPLICATION_ROLES);
    const canSearchBorrowers = hasRole(activeRole, LENDING_ROLES);
    const canAdjustDueDates = hasRole(activeRole, LENDING_ROLES);
    const canPayInstallments = hasRole(activeRole, CASHIER_ROLES);
    const canDisburse = hasRole(activeRole, FINANCE_ROLES);
    const canSettleEarly = hasRole(activeRole, FINANCE_ROLES);
    const [loans, setLoans] = useState<Loan[]>([]);
    const [clients, setClients] = useState<CompanyClient[]>([]);
    const [contracts, setContracts] = useState<LoanContract[]>([]);
    const [originationPolicy, setOriginationPolicy] = useState<OriginationPolicy | null>(null);
    const [methods, setMethods] = useState<PaymentMethodOption[]>(DEFAULT_PAYMENT_METHOD_OPTIONS);
    const [loading, setLoading] = useState(true);
    const [tab, setTab] = useState<WorkspaceTab>("portfolio");

    const [selectedLoan, setSelectedLoan] = useState<Loan | null>(null);
    const [scheduleOpen, setScheduleOpen] = useState(false);
    const [settlementLoan, setSettlementLoan] = useState<Loan | null>(null);
    const [editingInstallment, setEditingInstallment] = useState<RepaymentInstallment | null>(null);
    const [extendedDueDate, setExtendedDueDate] = useState("");
    const [extensionNote, setExtensionNote] = useState("");
    const [extensionReference, setExtensionReference] = useState("");
    const [extendingDueDate, setExtendingDueDate] = useState(false);
    const [payingInstallment, setPayingInstallment] = useState<RepaymentInstallment | null>(null);
    const [installmentPaymentAmount, setInstallmentPaymentAmount] = useState("");
    const [installmentPaymentEvidence, setInstallmentPaymentEvidence] = useState<PaymentEvidence>(EMPTY_PAYMENT_EVIDENCE);
    const [postingInstallmentPayment, setPostingInstallmentPayment] = useState(false);
    const [disburseOpen, setDisburseOpen] = useState(false);
    const [disbursing, setDisbursing] = useState(false);
    const [evidence, setEvidence] = useState<PaymentEvidence>(EMPTY_PAYMENT_EVIDENCE);

    const [documentLoan, setDocumentLoan] = useState<Loan | null>(null);
    const [paymentSlips, setPaymentSlips] = useState<LoanPaymentSlip[]>([]);
    const [slipsLoading, setSlipsLoading] = useState(false);
    const [documentWorking, setDocumentWorking] = useState<string | null>(null);

    const [selectedContract, setSelectedContract] = useState<LoanContract | null>(null);
    const [contractWorking, setContractWorking] = useState<string | null>(null);
    const [newContractStyle, setNewContractStyle] = useState<ContractTemplateStyle>("loanhub_standard");
    const [borrowerSignature, setBorrowerSignature] = useState("");
    const [witnessName, setWitnessName] = useState("");
    const [signatureMethod, setSignatureMethod] = useState("wet_ink");

    const [borrowerLookupOpen, setBorrowerLookupOpen] = useState(false);
    const [borrowerQuery, setBorrowerQuery] = useState("");
    const [borrowerResults, setBorrowerResults] = useState<CompanyClient[]>([]);
    const [borrowerSearching, setBorrowerSearching] = useState(false);

    const calculatorStart = useMemo(() => new Date(), []);
    const [principal, setPrincipal] = useState("1000");
    const [rate, setRate] = useState("36");
    const [months, setMonths] = useState("6");
    const [fee, setFee] = useState("0");
    const [interestMethod, setInterestMethod] = useState<InterestMethod>("daily_accrual_reducing");
    const [interestStartDate, setInterestStartDate] = useState(() => dateInputValue(calculatorStart));
    const dueDates = useMemo(
        () => generateMonthlyInstallmentDueDates(interestStartDate, Number(months || 0)),
        [interestStartDate, months],
    );
    const [calculating, setCalculating] = useState(false);
    const [calculation, setCalculation] = useState<LoanCalculation | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [loanRows, contractRows, methodRows, clientRows, policy] = await Promise.all([
                listLoans(),
                canManageContracts ? originationApi.listContracts() : Promise.resolve([]),
                expenseManagementApi.paymentMethods().catch(() => DEFAULT_PAYMENT_METHOD_OPTIONS),
                listCompanyClients().catch(() => []),
                (canManageContracts || canDisburse) ? originationApi.getPolicy().catch(() => null) : Promise.resolve(null),
            ]);
            setLoans(loanRows);
            setContracts(contractRows);
            setMethods(methodRows);
            setClients(clientRows);
            setOriginationPolicy(policy);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Loans and contracts could not be loaded."));
        } finally {
            setLoading(false);
        }
    }, [canDisburse, canManageContracts]);

    useEffect(() => {
        const timer = window.setTimeout(() => void load(), 0);
        const requestedTab = new URLSearchParams(window.location.search).get("tab");
        if (requestedTab === "contracts" && canManageContracts) {
            setTab("contracts");
        } else if (requestedTab === "calculator") {
            setTab("calculator");
        }
        return () => window.clearTimeout(timer);
    }, [canManageContracts, load]);

    useEffect(() => {
        if (!borrowerLookupOpen) return;

        const value = borrowerQuery.trim();
        if (value.length < 2) {
            setBorrowerResults([]);
            setBorrowerSearching(false);
            return;
        }

        let cancelled = false;
        const timer = window.setTimeout(async () => {
            setBorrowerSearching(true);
            try {
                const rows = await listCompanyClients({search: value});
                if (!cancelled) setBorrowerResults(rows);
            } catch {
                if (!cancelled) setBorrowerResults([]);
            } finally {
                if (!cancelled) setBorrowerSearching(false);
            }
        }, 300);

        return () => {
            cancelled = true;
            window.clearTimeout(timer);
        };
    }, [borrowerLookupOpen, borrowerQuery]);

    const contractByLoan = useMemo(
        () => new Map(contracts.map((contract) => [contract.loan_id, contract])),
        [contracts],
    );

    const clientByBorrower = useMemo(
        () => new Map(clients.map((client) => [client.borrower_id, client])),
        [clients],
    );

    const signedContractRequired = originationPolicy?.require_signed_contract ?? true;

    const contractsRequired = useMemo(
        () => canManageContracts ? loans.filter((loan) => CONTRACT_ELIGIBLE_STATUSES.has(loan.status) && !contractByLoan.has(loan.id)) : [],
        [canManageContracts, contractByLoan, loans],
    );

    const activeLoans = useMemo(
        () => loans.filter((item) => item.status === "active" || item.status === "defaulted").length,
        [loans],
    );
    const outstanding = useMemo(
        () => loans.reduce((sum, item) => sum + Number(item.balance || 0), 0),
        [loans],
    );
    const readyToDisburse = useMemo(
        () => loans.filter((item) => {
            if (item.status !== "approved") return false;
            return !signedContractRequired || contractByLoan.get(item.id)?.status === "signed";
        }).length,
        [contractByLoan, loans, signedContractRequired],
    );
    const signedContracts = useMemo(
        () => contracts.filter((item) => item.status === "signed").length,
        [contracts],
    );

    async function runCalculator(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        const installmentCount = Number(months || 0);
        if (!installmentDueDatesComplete(dueDates, installmentCount)) {
            toast.warning("Choose a valid payout/interest start date before calculating.");
            return;
        }
        setCalculating(true);
        try {
            setCalculation(await calculateLoan({
                principal: Number(principal),
                rate_percent: Number(rate),
                months: Number(months),
                processing_fee: Number(fee || 0),
                interest_method: interestMethod,
                interest_start_date: interestStartDate || null,
                due_dates: dueDates,
            }));
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "The interest calculation could not be completed."));
        } finally {
            setCalculating(false);
        }
    }

    function openSchedule(loan: Loan) {
        setSelectedLoan(loan);
        setScheduleOpen(true);
    }

    function openDueDateAdjustment(item: RepaymentInstallment) {
        setScheduleOpen(false);
        setEditingInstallment(item);
        setExtendedDueDate(dayAfterIsoDate(item.due_date));
        setExtensionNote("");
        setExtensionReference("");
    }

    function closeDueDateAdjustment() {
        if (extendingDueDate) return;
        setEditingInstallment(null);
        if (selectedLoan) setScheduleOpen(true);
    }

    async function saveDueDateAdjustment() {
        if (!selectedLoan || !editingInstallment) return;
        if (!extendedDueDate) {
            toast.warning("Choose the agreed new due date.");
            return;
        }
        if (extensionNote.trim().length < 3) {
            toast.warning("Record the agreement or reason for adjusting the due date.");
            return;
        }

        setExtendingDueDate(true);
        try {
            const updated = await adjustInstallmentDueDate(selectedLoan.id, editingInstallment.id, {
                new_due_date: extendedDueDate,
                agreement_note: extensionNote.trim(),
                agreement_reference: extensionReference.trim() || null,
            });
            setSelectedLoan(updated);
            setLoans((rows) => rows.map((loan) => (loan.id === updated.id ? updated : loan)));
            setEditingInstallment(null);
            setScheduleOpen(true);
            toast.success("Installment due date adjusted", {
                description: `Installment ${editingInstallment.installment_number} is now due ${formatDate(extendedDueDate)}.`,
            });
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "The installment due date could not be adjusted."));
        } finally {
            setExtendingDueDate(false);
        }
    }

    function openInstallmentPayment(item: RepaymentInstallment) {
        setScheduleOpen(false);
        setPayingInstallment(item);
        setInstallmentPaymentAmount(installmentOutstanding(item).toFixed(2));
        setInstallmentPaymentEvidence(EMPTY_PAYMENT_EVIDENCE);
    }

    function closeInstallmentPayment() {
        if (postingInstallmentPayment) return;
        setPayingInstallment(null);
        if (selectedLoan) setScheduleOpen(true);
    }

    async function submitInstallmentPayment() {
        if (!selectedLoan || !payingInstallment) return;

        const amount = Number(installmentPaymentAmount);
        const outstanding = installmentOutstanding(payingInstallment);
        if (!Number.isFinite(amount) || amount <= 0) {
            toast.warning("Enter a positive payment amount.");
            return;
        }
        if (amount > outstanding + 0.0001) {
            toast.warning("This action cannot overpay the installment.", {
                description: `The installment has ${formatMoney(outstanding)} remaining. Use the Payment desk for advance payments.`,
            });
            return;
        }
        if (
            installmentPaymentEvidence.payment_method === "lelefapaygate"
            && (!installmentPaymentEvidence.gateway_provider || !installmentPaymentEvidence.gateway_customer_phone.trim())
        ) {
            toast.warning("Choose a LelefaPayGate provider and enter the required customer phone number.");
            return;
        }
        if (
            installmentPaymentEvidence.payment_method !== "cash" &&
            installmentPaymentEvidence.payment_method !== "lelefapaygate" &&
            !installmentPaymentEvidence.proof_reference.trim() &&
            !installmentPaymentEvidence.proof_url.trim()
        ) {
            toast.warning("Enter a proof reference or proof document location for a non-cash payment.");
            return;
        }

        setPostingInstallmentPayment(true);
        try {
            const result = await payLoanInstallment(selectedLoan.id, payingInstallment.id, {
                amount_tendered: amount,
                payment_method: installmentPaymentEvidence.payment_method,
                gateway_provider: installmentPaymentEvidence.gateway_provider || null,
                gateway_customer_phone: installmentPaymentEvidence.gateway_customer_phone.trim() || null,
                proof_reference: installmentPaymentEvidence.proof_reference.trim() || null,
                proof_url: installmentPaymentEvidence.proof_url.trim() || null,
                proof_notes: installmentPaymentEvidence.proof_notes.trim() || null,
                notes: installmentPaymentEvidence.proof_notes.trim() || null,
                idempotency_key: createIdempotencyKey(
                    `installment-payment-${installmentPaymentEvidence.payment_method}-${selectedLoan.id}-${payingInstallment.id}`,
                ),
            });
            const updated = await getLoan(selectedLoan.id);
            setSelectedLoan(updated);
            setLoans((rows) => rows.map((loan) => (loan.id === updated.id ? updated : loan)));
            setPayingInstallment(null);
            setScheduleOpen(true);
            const methodLabel = methods.find((item) => item.value === result.payment_method)?.label ?? titleCase(result.payment_method);
            toast.success("Installment payment recorded", {
                description: `${formatMoney(result.preview?.amount_applied ?? amount)} posted through ${methodLabel}. Receipt ${result.receipt_number ?? result.provider_reference}.`,
            });
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "The installment payment could not be recorded."));
        } finally {
            setPostingInstallmentPayment(false);
        }
    }

    function openDisbursement(loan: Loan) {
        const contract = contractByLoan.get(loan.id);
        const contractFullySigned = contract?.status === "signed";
        if (loan.status !== "approved") {
            toast.warning("Loan is not ready for disbursement", {
                description: "Only an approved, undisbursed loan can be paid out.",
            });
            return;
        }
        if (signedContractRequired && !contractFullySigned) {
            toast.warning("Sign contract first", {
                description: "Fully signed contract required. Record both borrower and company signatures before disbursement.",
            });
            return;
        }
        setSelectedLoan(loan);
        setEvidence(EMPTY_PAYMENT_EVIDENCE);
        setDisburseOpen(true);
    }

    async function disburse() {
        if (!selectedLoan) return;
        const contract = contractByLoan.get(selectedLoan.id);
        const contractFullySigned = contract?.status === "signed";
        if (
            selectedLoan.status !== "approved" ||
            (signedContractRequired && !contractFullySigned)
        ) {
            toast.warning("Disbursement blocked", {
                description: signedContractRequired
                    ? "The loan must remain approved and the contract must be fully signed before payout."
                    : "The loan must remain approved and undisbursed before payout.",
            });
            setDisburseOpen(false);
            return;
        }
        setDisbursing(true);
        try {
            if (evidence.payment_method !== "cash" && evidence.payment_method !== "lelefapaygate" && !evidence.proof_reference.trim() && !evidence.proof_url.trim()) {
                toast.warning("Enter a proof reference or proof document location.");
                return;
            }
            const result = await disburseLoan(selectedLoan.id, {
                payment_method: evidence.payment_method,
                proof_reference: evidence.proof_reference.trim() || null,
                proof_url: evidence.proof_url.trim() || null,
                proof_notes: evidence.proof_notes.trim() || null,
                notes: evidence.proof_notes.trim() || null,
                idempotency_key: createIdempotencyKey(`disbursement-${evidence.payment_method}-${selectedLoan.id}`),
            });
            const methodLabel = methods.find((item) => item.value === result.payment_method)?.label ?? titleCase(result.payment_method);
            toast.success("Loan disbursement completed", {
                description: `${formatMoney(selectedLoan.principal_amount)} was recorded through ${methodLabel} under ${result.provider_reference}.`,
            });
            setDisburseOpen(false);
            setSelectedLoan(null);
            await load();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "The loan was not disbursed."));
        } finally {
            setDisbursing(false);
        }
    }

    async function openDocuments(loan: Loan) {
        const currentContract = contractByLoan.get(loan.id);
        setNewContractStyle(contractTemplateStyle(currentContract));
        setDocumentLoan(loan);
        setPaymentSlips([]);
        setSlipsLoading(true);
        try {
            setPaymentSlips(await listLoanPaymentSlips(loan.id));
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Payment slips could not be loaded."));
        } finally {
            setSlipsLoading(false);
        }
    }

    async function printLoanDocument(loan: Loan, kind: LoanDocumentKind) {
        const popup = window.open("", "_blank", "width=1100,height=850");
        setDocumentWorking(kind);
        try {
            await openLoanDocumentPdf(loan.id, loan.loan_reference, kind, popup, loan.company_id);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "The PDF could not be generated."));
        } finally {
            setDocumentWorking(null);
        }
    }

    async function printPaymentSlip(loan: Loan, slip: LoanPaymentSlip) {
        const popup = window.open("", "_blank", "width=900,height=850");
        setDocumentWorking(slip.id);
        try {
            await openLoanPaymentSlipPdf(loan.id, slip, popup, loan.company_id);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "The payment slip could not be opened."));
        } finally {
            setDocumentWorking(null);
        }
    }

    function selectContract(contract: LoanContract) {
        setSelectedContract(contract);
        setBorrowerSignature(contract.borrower_signature_name ?? "");
        setWitnessName(contract.witness_name ?? "");
    }

    function replaceContract(updated: LoanContract) {
        setContracts((current) => {
            const exists = current.some((item) => item.id === updated.id);
            return exists
                ? current.map((item) => item.id === updated.id ? updated : item)
                : [updated, ...current];
        });
        setSelectedContract(updated);
    }

    async function generateContract(loan: Loan) {
        setContractWorking(loan.id);
        try {
            const created = await originationApi.generateContract(loan.id, null, newContractStyle);
            replaceContract(created);
            toast.success("Contract generated", {description: `${created.contract_number} · ${contractTemplateLabel(contractTemplateStyle(created))}`});
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "The contract could not be generated."));
        } finally {
            setContractWorking(null);
        }
    }

    async function printContract(contract: LoanContract) {
        const popup = window.open("", "_blank", "width=1100,height=850");
        setContractWorking(contract.id);
        try {
            await originationApi.openContractForPrinting(contract, popup);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "The contract PDF could not be opened."));
        } finally {
            setContractWorking(null);
        }
    }

    async function borrowerSign(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!selectedContract || borrowerSignature.trim().length < 2) return;
        setContractWorking(selectedContract.id);
        try {
            const updated = await originationApi.borrowerSign(selectedContract.id, {
                signature_name: borrowerSignature.trim(),
                signature_method: signatureMethod,
                witness_name: witnessName.trim() || null,
            });
            replaceContract(updated);
            toast.success("Borrower signature recorded");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Borrower signature could not be recorded."));
        } finally {
            setContractWorking(null);
        }
    }

    async function companySign() {
        if (!selectedContract) return;
        setContractWorking(selectedContract.id);
        try {
            const updated = await originationApi.companySign(selectedContract.id, signatureMethod);
            replaceContract(updated);
            toast.success(updated.status === "signed" ? "Contract fully signed and locked" : "Company signature recorded");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Company signature could not be recorded."));
        } finally {
            setContractWorking(null);
        }
    }

    async function regenerateContractPdf() {
        if (!selectedContract || selectedContract.status === "signed") return;
        setContractWorking(selectedContract.id);
        try {
            const updated = await originationApi.regenerateContractPdf(selectedContract.id);
            replaceContract(updated);
            toast.success("Contract PDF regenerated", {description: `Version ${updated.version}`});
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "The contract PDF could not be regenerated."));
        } finally {
            setContractWorking(null);
        }
    }

    async function regenerateDocumentCentreContract(contract: LoanContract) {
        const locked = Boolean(
            contract.borrower_signed_at ||
            contract.company_signed_at ||
            contract.status === "signed",
        );

        if (locked) {
            toast.warning("Contract style is locked", {
                description: "A contract style cannot change after either party has signed the PDF.",
            });
            return;
        }

        setContractWorking(contract.id);
        try {
            const updated = await originationApi.regenerateContractPdf(contract.id, newContractStyle);
            replaceContract(updated);
            setNewContractStyle(contractTemplateStyle(updated));
            toast.success("Contract style applied", {
                description: `Version ${updated.version} · ${contractTemplateLabel(contractTemplateStyle(updated))}`,
            });
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "The contract PDF could not be regenerated."));
        } finally {
            setContractWorking(null);
        }
    }

    async function searchBorrowers(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        const value = borrowerQuery.trim();
        if (value.length < 2) {
            toast.warning("Enter at least two characters of the borrower name.");
            return;
        }
        setBorrowerSearching(true);
        try {
            setBorrowerResults(await listCompanyClients({search: value}));
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Borrowers could not be searched."));
        } finally {
            setBorrowerSearching(false);
        }
    }

    const nextInstallmentForExtension = selectedLoan && editingInstallment
        ? selectedLoan.installments
        .filter((item) => item.installment_number > editingInstallment.installment_number)
        .sort((left, right) => left.installment_number - right.installment_number)[0] ?? null
        : null;

    const currentPayableInstallment = selectedLoan
        ? selectedLoan.installments
        .filter((item) => ["pending", "partially_paid", "overdue"].includes(item.status))
        .sort((left, right) => left.installment_number - right.installment_number)[0] ?? null
        : null;

    if (loading) return <PageLoader rows={8}/>;

    return (
        <main className="loanhub-page space-y-6">
            <section className="loanhub-hero flex flex-col justify-between gap-5 p-5 sm:p-6 lg:flex-row lg:items-end">
                <div>
                    <p className="text-xs font-black uppercase tracking-[0.24em] text-primary">Loans and contracts</p>
                    <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">One workspace for lending and
                        documents</h1>
                    <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
                        Manage loans, contracts, schedules, payment slips and borrower documents from one page. Every
                        printable document is generated by FastAPI from the current database record.
                    </p>
                </div>
                <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                    {canSearchBorrowers ?
                        <Button variant="outline" onClick={() => setBorrowerLookupOpen(true)}><UserSearch
                            className="h-4 w-4"/>Find borrower</Button> : null}
                    <Button variant="outline" onClick={() => void load()}><RefreshCcw
                        className="h-4 w-4"/>Refresh</Button>
                    <Button asChild><Link href="/company/cashier"><Banknote className="h-4 w-4"/>Payment
                        desk</Link></Button>
                </div>
            </section>

            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <Metric icon={HandCoins} label="Active loans" value={String(activeLoans)}
                        hint="Accepting scheduled repayments"/>
                <Metric icon={ShieldCheck} label="Ready to pay out" value={String(readyToDisburse)}
                        hint={signedContractRequired ? "Approved loans with a fully signed contract" : "Approved loans awaiting disbursement"}/>
                <Metric icon={ReceiptText} label="Outstanding portfolio" value={formatMoney(outstanding)}
                        hint="Balance expected from borrowers"/>
                <Metric icon={FileSignature} label={canManageContracts ? "Signed contracts" : "FastAPI PDFs"}
                        value={canManageContracts ? `${signedContracts}/${contracts.length}` : "3 types"}
                        hint={canManageContracts ? `${contractsRequired.length} loans need a contract` : "Loan info, schedule and payment history"}/>
            </div>

            <Tabs value={tab} onValueChange={(value) => setTab(value as WorkspaceTab)} className="space-y-5">
                <TabsList className="flex h-auto w-full max-w-3xl overflow-x-auto rounded-2xl p-1">
                    <TabsTrigger value="portfolio" className="min-w-40 flex-1 rounded-xl py-2.5">Loan
                        portfolio</TabsTrigger>
                    {canManageContracts ? <TabsTrigger value="contracts"
                                                       className="min-w-40 flex-1 rounded-xl py-2.5">Contracts</TabsTrigger> : null}
                    <TabsTrigger value="calculator" className="min-w-40 flex-1 rounded-xl py-2.5">Interest
                        calculator</TabsTrigger>
                </TabsList>

                <TabsContent value="portfolio" className="space-y-5">
                    <LoanPortfolioWorkspace
                        loans={loans}
                        clients={clients}
                        contracts={contracts}
                        canDisburse={canDisburse}
                        signedContractRequired={signedContractRequired}
                        onOpenSchedule={openSchedule}
                        onOpenDocuments={(loan) => void openDocuments(loan)}
                        onOpenDisbursement={openDisbursement}
                        onStartCall={(loan) => router.push(`/company/calls?borrower=${encodeURIComponent(loan.borrower_id)}&loan=${encodeURIComponent(loan.id)}`)}
                    />
                </TabsContent>

                {canManageContracts ? <TabsContent value="contracts" className="space-y-5">
                    {contractsRequired.length > 0 ?
                        <Card className="rounded-3xl border-amber-500/30 bg-amber-500/5"><CardHeader><CardTitle>Contracts
                            required</CardTitle><CardDescription>These loans are eligible for an agreement but do not
                            yet have one.</CardDescription></CardHeader><CardContent
                            className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{contractsRequired.map((loan) => <div
                            key={loan.id} className="rounded-3xl border bg-card p-5"><p
                            className="font-mono text-xs font-black text-primary">{loan.loan_reference}</p><p
                            className="mt-2 text-2xl font-black">{formatMoney(loan.principal_amount)}</p><p
                            className="text-sm text-muted-foreground">{loan.repayment_period} instalments
                            · {formatMoney(loan.installment_amount)}</p><LoadingButton className="mt-4 w-full"
                                                                                       loading={contractWorking === loan.id}
                                                                                       loadingText="Generating…"
                                                                                       disabled={contractWorking !== null && contractWorking !== loan.id}
                                                                                       onClick={() => void generateContract(loan)}><FileSignature
                            className="h-4 w-4"/>Generate contract</LoadingButton></div>)}</CardContent></Card> : null}

                    <Card className="overflow-hidden rounded-3xl">
                        <CardHeader className="border-b bg-muted/20"><CardTitle>Contract
                            register</CardTitle><CardDescription>Generate, review, sign, print and lock borrower credit
                            agreements without leaving the loan workspace.</CardDescription></CardHeader>
                        <CardContent className="p-0">
                            <div className="overflow-x-auto">
                                <Table><TableHeader><TableRow><TableHead>Contract</TableHead><TableHead>Loan</TableHead><TableHead>Status</TableHead><TableHead>Borrower
                                    signed</TableHead><TableHead>Company signed</TableHead><TableHead
                                    className="text-right">Actions</TableHead></TableRow></TableHeader><TableBody>{contracts.length === 0 ?
                                    <TableRow><TableCell colSpan={6} className="h-40 text-center text-muted-foreground">No
                                        contracts generated.</TableCell></TableRow> : contracts.map((contract) =>
                                        <TableRow key={contract.id}><TableCell><p
                                            className="font-mono text-xs font-black">{contract.contract_number}</p><p
                                            className="text-xs text-muted-foreground">Version {contract.version}</p>
                                        </TableCell><TableCell
                                            className="font-mono text-xs">{String(contract.terms_snapshot.loan_reference ?? contract.loan_id)}</TableCell><TableCell><Badge
                                            variant={contract.status === "signed" ? "default" : "secondary"}>{titleCase(contract.status)}</Badge></TableCell><TableCell>{contract.borrower_signed_at ? formatDate(contract.borrower_signed_at) : "Pending"}</TableCell><TableCell>{contract.company_signed_at ? formatDate(contract.company_signed_at) : "Pending"}</TableCell><TableCell>
                                            <div className="flex min-w-max justify-end gap-2"><LoadingButton size="sm"
                                                                                                             variant="outline"
                                                                                                             loading={contractWorking === contract.id}
                                                                                                             loadingText="Opening…"
                                                                                                             onClick={() => void printContract(contract)}><Printer
                                                className="h-4 w-4"/>Print</LoadingButton><Button size="sm"
                                                                                                  onClick={() => selectContract(contract)}><PenLine
                                                className="h-4 w-4"/>Manage</Button></div>
                                        </TableCell></TableRow>)}</TableBody></Table></div>
                        </CardContent>
                    </Card>
                </TabsContent> : null}

                <TabsContent value="calculator">
                    <div className="grid gap-6 xl:grid-cols-[440px_minmax(0,1fr)]">
                        <Card className="loanhub-panel h-fit">
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2"><Calculator
                                    className="h-5 w-5 text-primary"/>Interest and instalment calculator</CardTitle>
                                <CardDescription>FastAPI uses this same calculation engine for products, offers,
                                    affordability, approved loans, repayment schedules, contracts and printable
                                    PDFs.</CardDescription>
                            </CardHeader>
                            <CardContent>
                                <form onSubmit={runCalculator} className="space-y-4">
                                    <Field label="Interest method">
                                        <Select value={interestMethod}
                                                onValueChange={(value) => setInterestMethod(value as InterestMethod)}>
                                            <SelectTrigger><SelectValue/></SelectTrigger>
                                            <SelectContent>{INTEREST_METHOD_OPTIONS.map((method) => <SelectItem
                                                key={method.value}
                                                value={method.value}>{method.label}</SelectItem>)}</SelectContent>
                                        </Select>
                                        <p className="text-xs leading-5 text-muted-foreground">{interestMethodOption(interestMethod).description}</p>
                                    </Field>
                                    <Field label="Principal amount"><Input type="number" min="0.01" step="0.01" required
                                                                           value={principal}
                                                                           onChange={(event) => setPrincipal(event.target.value)}/></Field>
                                    <div className="grid grid-cols-2 gap-4">
                                        <Field label={interestMethodOption(interestMethod).rateLabel}><Input
                                            type="number" min="0" step="0.0001" required value={rate}
                                            onChange={(event) => setRate(event.target.value)}/></Field>
                                        <Field label="Months"><Input type="number" min="1" max="120" required
                                                                     value={months}
                                                                     onChange={(event) => setMonths(event.target.value)}/></Field>
                                    </div>
                                    <Field label="Processing fee"><Input type="number" min="0" step="0.01" value={fee}
                                                                         onChange={(event) => setFee(event.target.value)}/></Field>
                                    <Field label="Interest/payout start"><Input type="date" required
                                                                                value={interestStartDate}
                                                                                onChange={(event) => setInterestStartDate(event.target.value)}/></Field>
                                    <InstallmentDueDateFields
                                        count={Number(months || 0)}
                                        value={dueDates}
                                        readOnly
                                        statusLabel="Auto-calculated"
                                        description="LoanHub automatically creates the monthly due dates from the payout/interest start date. The first installment is one calendar month later. Offer and approval workflows can still change individual dates before the loan is finalized."
                                    />
                                    <LoadingButton type="submit" className="h-12 w-full" loading={calculating}
                                                   loadingText="Calculating..."><Calculator className="h-4 w-4"/>Calculate
                                        repayment schedule</LoadingButton>
                                </form>
                            </CardContent>
                        </Card>
                        <Card className="loanhub-panel">
                            <CardHeader><CardTitle>Calculation result</CardTitle><CardDescription>The schedule shows how
                                every instalment is divided into principal, interest and
                                fees.</CardDescription></CardHeader>
                            <CardContent>{!calculation ? <div
                                className="flex min-h-72 flex-col items-center justify-center text-center text-muted-foreground">
                                <Calculator className="mb-3 h-10 w-10"/><p>Run a calculation to see the complete FastAPI
                                schedule.</p></div> : <div className="space-y-5">
                                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Value label="Principal"
                                                                                                 value={formatMoney(calculation.principal)}/><Value
                                    label="Total interest" value={formatMoney(calculation.total_interest)}/><Value
                                    label="Total repayable" value={formatMoney(calculation.total_repayable)}/><Value
                                    label="First instalment" value={formatMoney(calculation.monthly_installment)}
                                    emphasis/></div>
                                <Alert><CalendarClock
                                    className="h-4 w-4"/><AlertTitle>{calculation.method_label}</AlertTitle><AlertDescription>{calculation.rate_basis}.
                                    Period {formatDate(calculation.interest_start_date)} to {formatDate(calculation.maturity_date)}.</AlertDescription></Alert>
                                <div className="overflow-x-auto rounded-2xl border">
                                    <Table><TableHeader><TableRow><TableHead>#</TableHead><TableHead>Period</TableHead><TableHead>Opening</TableHead><TableHead>Principal</TableHead><TableHead>Interest</TableHead><TableHead>Fee</TableHead><TableHead>Total</TableHead><TableHead>Closing</TableHead></TableRow></TableHeader><TableBody>{calculation.schedule.map((row) =>
                                        <TableRow key={row.installment_number}><TableCell
                                            className="font-black">{row.installment_number}</TableCell><TableCell
                                            className="min-w-40">
                                            <p>{formatDate(row.period_start)} → {formatDate(row.due_date)}</p>{row.interest_segments.length > 0 ?
                                            <p className="mt-1 text-xs text-muted-foreground">{row.interest_segments.map((segment) => `${segment.days}/${segment.days_in_month} days`).join(" + ")}</p> : null}
                                        </TableCell><TableCell>{formatMoney(row.opening_balance)}</TableCell><TableCell>{formatMoney(row.principal_due)}</TableCell><TableCell
                                            className="font-black">{formatMoney(row.interest_due)}</TableCell><TableCell>{formatMoney(row.fee_due)}</TableCell><TableCell
                                            className="font-black text-primary">{formatMoney(row.total_due)}</TableCell><TableCell>{formatMoney(row.closing_balance)}</TableCell></TableRow>)}</TableBody></Table>
                                </div>
                            </div>}</CardContent>
                        </Card>
                    </div>
                </TabsContent>
            </Tabs>

            <CustomDialog open={Boolean(documentLoan)} onOpenChange={(open) => !open && setDocumentLoan(null)}
                          title={documentLoan ? `Document centre · ${documentLoan.loan_reference}` : "Loan document centre"}
                          description="Every printable item below is generated or served by loanhub."
                          contentClassName="sm:max-w-6xl">
                {documentLoan ? <div className="space-y-6 p-5 sm:p-8">
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><Value label="Principal"
                                                                                     value={formatMoney(documentLoan.principal_amount)}/><Value
                        label="Paid" value={formatMoney(documentLoan.amount_paid)}/><Value label="Outstanding"
                                                                                           value={formatMoney(documentLoan.balance)}
                                                                                           emphasis/><Value
                        label="Status" value={titleCase(documentLoan.status)}/></div>

                    <section><h3 className="text-base font-black">FastAPI loan PDFs</h3><p
                        className="mt-1 text-sm text-muted-foreground">These are created directly from the current loan,
                        borrower, company, schedule and payment records.</p>
                        <div className="mt-4 grid gap-3 sm:grid-cols-3"><DocumentCard icon={FileText}
                                                                                      title="Loan information"
                                                                                      description="Complete borrower and loan statement."
                                                                                      loading={documentWorking === "loan-information"}
                                                                                      onClick={() => void printLoanDocument(documentLoan, "loan-information")}/><DocumentCard
                            icon={CalendarClock} title="Repayment schedule"
                            description="A4 instalment schedule with totals."
                            loading={documentWorking === "repayment-schedule"}
                            onClick={() => void printLoanDocument(documentLoan, "repayment-schedule")}/><DocumentCard
                            icon={FileClock} title="Payment history"
                            description="All disbursement and repayment activity."
                            loading={documentWorking === "payment-history"}
                            onClick={() => void printLoanDocument(documentLoan, "payment-history")}/></div>
                    </section>

                    <section className="rounded-3xl border bg-muted/20 p-5">
                        <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-start">
                            <div className="max-w-2xl">
                                <h3 className="font-black">Credit agreement</h3>
                                <p className="mt-1 text-sm text-muted-foreground">
                                    FastAPI uses the LoanHub system logo on the left and the active company document
                                    logo on the right.
                                </p>
                                <p className="mt-2 text-xs text-muted-foreground">
                                    Choose the LoanHub standard layout or the compact Filizwa-style presentation before
                                    either party signs.
                                </p>
                            </div>

                            {canManageContracts ? (() => {
                                const contract = contractByLoan.get(documentLoan.id);

                                if (contract) {
                                    const locked = Boolean(
                                        contract.borrower_signed_at ||
                                        contract.company_signed_at ||
                                        contract.status === "signed",
                                    );
                                    const currentStyle = contractTemplateStyle(contract);

                                    return (
                                        <div className="w-full space-y-3 lg:w-80">
                                            <div className="space-y-2">
                                                <div className="flex items-center justify-between gap-2">
                                                    <Label>Contract PDF style</Label>
                                                    <Badge
                                                        variant="outline">{contractTemplateLabel(currentStyle)}</Badge>
                                                </div>

                                                <Select
                                                    value={newContractStyle}
                                                    onValueChange={(value) => setNewContractStyle(value as ContractTemplateStyle)}
                                                    disabled={locked}
                                                >
                                                    <SelectTrigger>
                                                        <SelectValue/>
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {CONTRACT_TEMPLATE_OPTIONS.map((option) => (
                                                            <SelectItem key={option.value} value={option.value}>
                                                                {option.label}
                                                            </SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>

                                                <p className="text-xs text-muted-foreground">
                                                    {locked
                                                        ? "Style locked because a signature has already been recorded."
                                                        : "Apply the selected layout before collecting signatures."}
                                                </p>
                                            </div>

                                            <div className="flex flex-wrap gap-2">
                                                <LoadingButton
                                                    variant="outline"
                                                    loading={contractWorking === contract.id}
                                                    onClick={() => void printContract(contract)}
                                                >
                                                    <Printer className="h-4 w-4"/>
                                                    Print contract
                                                </LoadingButton>

                                                {!locked ? (
                                                    <LoadingButton
                                                        variant="outline"
                                                        loading={contractWorking === contract.id}
                                                        onClick={() => void regenerateDocumentCentreContract(contract)}
                                                    >
                                                        <RefreshCcw className="h-4 w-4"/>
                                                        Apply style
                                                    </LoadingButton>
                                                ) : null}

                                                <Button onClick={() => selectContract(contract)}>
                                                    <PenLine className="h-4 w-4"/>
                                                    Manage contract
                                                </Button>
                                            </div>
                                        </div>
                                    );
                                }

                                if (CONTRACT_ELIGIBLE_STATUSES.has(documentLoan.status)) {
                                    return (
                                        <div className="w-full space-y-3 lg:w-80">
                                            <div className="space-y-2">
                                                <Label>Contract PDF style</Label>
                                                <Select
                                                    value={newContractStyle}
                                                    onValueChange={(value) => setNewContractStyle(value as ContractTemplateStyle)}
                                                >
                                                    <SelectTrigger>
                                                        <SelectValue/>
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {CONTRACT_TEMPLATE_OPTIONS.map((option) => (
                                                            <SelectItem key={option.value} value={option.value}>
                                                                {option.label}
                                                            </SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                                <p className="text-xs text-muted-foreground">
                                                    The chosen presentation is stored with the agreement.
                                                </p>
                                            </div>

                                            <LoadingButton
                                                className="w-full"
                                                loading={contractWorking === documentLoan.id}
                                                onClick={() => void generateContract(documentLoan)}
                                            >
                                                <FileSignature className="h-4 w-4"/>
                                                Generate contract
                                            </LoadingButton>
                                        </div>
                                    );
                                }

                                return <Badge variant="secondary">Available after approval</Badge>;
                            })() : <Badge variant="secondary">Origination role required</Badge>}
                        </div>
                    </section>

                    <section>
                        <div className="flex items-center justify-between gap-4">
                            <div><h3 className="font-black">Payment and disbursement slips</h3><p
                                className="mt-1 text-sm text-muted-foreground">Thermal-size PDFs with receipt numbers
                                and verification codes.</p></div>
                            <Badge variant="secondary">{paymentSlips.length} slips</Badge></div>
                        <div className="mt-4 overflow-hidden rounded-2xl border">{slipsLoading ?
                            <div className="p-8 text-center text-sm text-muted-foreground">Loading FastAPI payment
                                slips…</div> : paymentSlips.length === 0 ?
                                <div className="p-8 text-center text-sm text-muted-foreground">No successful payment or
                                    disbursement slip is recorded for this loan.</div> :
                                <div className="overflow-x-auto">
                                    <Table><TableHeader><TableRow><TableHead>Slip</TableHead><TableHead>Date</TableHead><TableHead>Type</TableHead><TableHead>Method</TableHead><TableHead>Amount</TableHead><TableHead
                                        className="text-right">Action</TableHead></TableRow></TableHeader><TableBody>{paymentSlips.map((slip) =>
                                        <TableRow key={slip.id}><TableCell><p
                                            className="font-mono text-xs font-black">{slip.receipt_number}</p><p
                                            className="text-xs text-muted-foreground">Verify {slip.verification_code}</p>
                                        </TableCell><TableCell>{slip.completed_at ? formatDate(slip.completed_at) : "Not recorded"}</TableCell><TableCell>{titleCase(slip.payment_purpose)}</TableCell><TableCell>{titleCase(slip.payment_method)}</TableCell><TableCell
                                            className="font-black">{formatMoney(slip.amount)}</TableCell><TableCell
                                            className="text-right"><LoadingButton size="sm" variant="outline"
                                                                                  loading={documentWorking === slip.id}
                                                                                  onClick={() => void printPaymentSlip(documentLoan, slip)}><Printer
                                            className="h-4 w-4"/>Print
                                            slip</LoadingButton></TableCell></TableRow>)}</TableBody></Table>
                                </div>}</div>
                    </section>
                    <DialogFooter className="mx-0 mb-0"><Button variant="outline"
                                                                onClick={() => setDocumentLoan(null)}>Close</Button></DialogFooter>
                </div> : null}
            </CustomDialog>

            <CustomDialog open={Boolean(selectedContract)}
                          onOpenChange={(open) => !open && !contractWorking && setSelectedContract(null)}
                          title={selectedContract?.contract_number ?? "Loan contract"}
                          description={selectedContract ? `Status: ${titleCase(selectedContract.status)} · Version ${selectedContract.version}` : undefined}
                          contentClassName="sm:max-w-3xl">
                {selectedContract ? <form onSubmit={borrowerSign} className="space-y-6 p-5 sm:p-8"><Alert><ShieldCheck
                    className="h-4 w-4"/><AlertTitle>Signing control</AlertTitle><AlertDescription>Review the
                    FastAPI-generated PDF before recording signatures. The final document is locked when both parties
                    have signed.</AlertDescription></Alert>
                    <div className="grid gap-5 sm:grid-cols-2">
                        <div className="space-y-2"><Label>Signature method</Label><Select value={signatureMethod}
                                                                                          onValueChange={setSignatureMethod}><SelectTrigger><SelectValue/></SelectTrigger><SelectContent><SelectItem
                            value="wet_ink">Wet ink</SelectItem><SelectItem
                            value="electronic">Electronic</SelectItem><SelectItem
                            value="otp">OTP</SelectItem></SelectContent></Select></div>
                        <div className="space-y-2"><Label>Witness name</Label><Input value={witnessName}
                                                                                     onChange={(event) => setWitnessName(event.target.value)}/>
                        </div>
                        <div className="space-y-2 sm:col-span-2"><Label>Borrower signature name</Label><Input
                            value={borrowerSignature} onChange={(event) => setBorrowerSignature(event.target.value)}
                            disabled={Boolean(selectedContract.borrower_signed_at)}/></div>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2"><Value label="Borrower"
                                                                      value={selectedContract.borrower_signed_at ? `Signed ${formatDate(selectedContract.borrower_signed_at)}` : "Pending signature"}/><Value
                        label="Company"
                        value={selectedContract.company_signed_at ? `Signed ${formatDate(selectedContract.company_signed_at)}` : "Pending signature"}/>
                    </div>
                    <DialogFooter className="flex-wrap"><LoadingButton type="button" variant="outline"
                                                                       loading={contractWorking === selectedContract.id}
                                                                       onClick={() => void printContract(selectedContract)}><Download
                        className="h-4 w-4"/>Open PDF</LoadingButton>{selectedContract.status !== "signed" ?
                        <LoadingButton type="button" variant="outline" loading={contractWorking === selectedContract.id}
                                       onClick={() => void regenerateContractPdf()}><RefreshCcw className="h-4 w-4"/>Regenerate
                            PDF</LoadingButton> : null}{!selectedContract.borrower_signed_at ?
                        <LoadingButton type="submit" loading={contractWorking === selectedContract.id}>Borrower
                            signed</LoadingButton> : null}{!selectedContract.company_signed_at ?
                        <LoadingButton type="button" loading={contractWorking === selectedContract.id}
                                       onClick={() => void companySign()}>Company signed</LoadingButton> : null}
                    </DialogFooter></form> : null}
            </CustomDialog>

            <CustomDialog open={borrowerLookupOpen} onOpenChange={setBorrowerLookupOpen} title="Find borrower documents"
                          description="Search by name, then open a linked loan’s document centre."
                          contentClassName="sm:max-w-3xl">
                <div className="space-y-5 p-5 sm:p-8">
                    <form onSubmit={searchBorrowers} className="flex flex-col gap-3 sm:flex-row"><SuggestionSearch
                        value={borrowerQuery}
                        onValueChange={setBorrowerQuery}
                        suggestions={borrowerResults.map((borrower) => ({
                            value: borrower.full_name,
                            label: borrower.full_name,
                            description: `${borrower.account_reference} · ${borrower.phone}`,
                            keywords: [borrower.user_id, borrower.borrower_id, borrower.email ?? "", borrower.national_id ?? ""],
                        }))}
                        placeholder="Type the borrower name..."
                        suggestionLabel="Borrowers"
                        emptyMessage="No borrower suggestion yet. Type at least two letters and search."
                        wrapperClassName="flex-1"
                    /><LoadingButton loading={borrowerSearching} loadingText="Searching…"><UserSearch
                        className="h-4 w-4"/>Search</LoadingButton></form>
                    <div className="space-y-3">{borrowerResults.map((borrower) => {
                        const borrowerLoans = loans.filter((loan) => loan.borrower_id === borrower.borrower_id);
                        return <div key={borrower.id} className="rounded-3xl border p-5">
                            <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                                <div><p className="font-black">{borrower.full_name}</p><p
                                    className="mt-1 text-sm text-muted-foreground">{borrower.phone}{borrower.email ? ` · ${borrower.email}` : ""}</p>
                                    <p className="mt-2 break-all font-mono text-xs text-primary">User
                                        ID: {borrower.user_id}</p></div>
                                <Badge variant="secondary">{borrowerLoans.length} loans</Badge></div>
                            <div className="mt-4 grid gap-2">{borrowerLoans.length === 0 ?
                                <p className="rounded-2xl bg-muted/40 p-4 text-sm text-muted-foreground">No loan is
                                    linked to this borrower in the active company.</p> : borrowerLoans.map((loan) =>
                                    <button type="button" key={loan.id}
                                            className="flex flex-col justify-between gap-3 rounded-2xl border p-4 text-left transition hover:border-primary/50 hover:bg-primary/5 sm:flex-row sm:items-center"
                                            onClick={() => {
                                                setBorrowerLookupOpen(false);
                                                void openDocuments(loan);
                                            }}>
                                        <div><p
                                            className="font-mono text-xs font-black text-primary">{loan.loan_reference}</p>
                                            <p className="mt-1 text-sm font-bold">{formatMoney(loan.principal_amount)} · {titleCase(loan.status)}</p>
                                        </div>
                                        <span className="text-sm font-black text-primary">Open documents</span>
                                    </button>)}</div>
                        </div>;
                    })}{borrowerResults.length === 0 && !borrowerSearching ? <div
                        className="rounded-2xl border border-dashed p-8 text-center text-sm text-muted-foreground">Search
                        for a borrower to see their user ID and linked loans.</div> : null}</div>
                    <DialogFooter className="mx-0 mb-0"><Button variant="outline"
                                                                onClick={() => setBorrowerLookupOpen(false)}>Close</Button></DialogFooter>
                </div>
            </CustomDialog>

            <CustomDialog
                open={scheduleOpen}
                onOpenChange={setScheduleOpen}
                title="Repayment schedule"
                description={selectedLoan ? `${selectedLoan.loan_reference} · Payments are allocated to the oldest unpaid instalment first.` : undefined}
                contentClassName="sm:max-w-5xl"
            >
                <div className="space-y-5 p-5 sm:p-8">
                    {selectedLoan ? (
                        <>
                            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                                <Value label="Method" value={interestMethodLabel(selectedLoan.calculation_method)}/>
                                <Value label="Principal" value={formatMoney(selectedLoan.principal_amount)}/>
                                <Value label="Paid" value={formatMoney(selectedLoan.amount_paid)}/>
                                <Value label="Outstanding" value={formatMoney(selectedLoan.balance)} emphasis/>
                                <Value
                                    label="Progress"
                                    value={`${Math.min(100, Math.max(0, Number(selectedLoan.total_repayable) > 0 ? (Number(selectedLoan.amount_paid) / Number(selectedLoan.total_repayable)) * 100 : 0)).toFixed(1)}%`}
                                />
                            </div>

                            {selectedLoan.is_top_up ? (
                                <Alert>
                                    <Sparkles className="h-4 w-4"/>
                                    <AlertTitle>Top-up replacement loan</AlertTitle>
                                    <AlertDescription>
                                        This loan
                                        settled {formatMoney(selectedLoan.top_up_settlement_amount ?? 0)} internally and
                                        issued {formatMoney(selectedLoan.top_up_cash_amount ?? selectedLoan.principal_amount)} to
                                        the borrower.
                                    </AlertDescription>
                                </Alert>
                            ) : null}

                            <div className="overflow-x-auto rounded-2xl border">
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>#</TableHead>
                                            <TableHead>Due</TableHead>
                                            <TableHead>Principal</TableHead>
                                            <TableHead>Interest</TableHead>
                                            <TableHead>Fee</TableHead>
                                            <TableHead>Total</TableHead>
                                            <TableHead>Paid</TableHead>
                                            <TableHead>Status</TableHead>
                                            <TableHead className="text-right">Action</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {selectedLoan.installments.map((item) => {
                                            const editableLoan = ["approved", "active", "defaulted"].includes(selectedLoan.status);
                                            const repaymentLoan = ["active", "defaulted"].includes(selectedLoan.status);
                                            const lockedInstallment = ["paid", "waived"].includes(item.status);
                                            const canAdjustDate = canAdjustDueDates && editableLoan && !lockedInstallment;
                                            const showPaymentAction = !lockedInstallment;
                                            const isCurrentPayable = currentPayableInstallment?.id === item.id;
                                            const canPayNow = canPayInstallments && repaymentLoan && isCurrentPayable;
                                            const paymentActionTitle = !canPayInstallments
                                                ? "Your active role cannot record installment payments"
                                                : !repaymentLoan
                                                    ? "The loan must be active or defaulted before installment payments can be recorded"
                                                    : isCurrentPayable
                                                        ? "Record a payment for this installment"
                                                        : `Installment ${currentPayableInstallment?.installment_number ?? "earlier"} must be cleared first`;

                                            return (
                                                <TableRow key={item.id}>
                                                    <TableCell
                                                        className="font-black">{item.installment_number}</TableCell>
                                                    <TableCell
                                                        className="whitespace-nowrap">{formatDate(item.due_date)}</TableCell>
                                                    <TableCell>{formatMoney(item.principal_due)}</TableCell>
                                                    <TableCell>{formatMoney(item.interest_due)}</TableCell>
                                                    <TableCell>{formatMoney(item.fee_due)}</TableCell>
                                                    <TableCell
                                                        className="font-black">{formatMoney(item.total_due)}</TableCell>
                                                    <TableCell>{formatMoney(item.paid_amount)}</TableCell>
                                                    <TableCell>
                                                        <Badge
                                                            variant={item.status === "paid" ? "default" : "secondary"}>{titleCase(item.status)}</Badge>
                                                    </TableCell>
                                                    <TableCell className="whitespace-nowrap text-right">
                                                        <div className="flex justify-end gap-2">
                                                            {showPaymentAction ? (
                                                                <Button
                                                                    type="button"
                                                                    size="sm"
                                                                    disabled={!canPayNow}
                                                                    title={paymentActionTitle}
                                                                    onClick={() => openInstallmentPayment(item)}
                                                                >
                                                                    <HandCoins className="h-3.5 w-3.5"/>
                                                                    Pay installment
                                                                </Button>
                                                            ) : null}
                                                            {canAdjustDate ? (
                                                                <Button
                                                                    type="button"
                                                                    size="sm"
                                                                    variant="outline"
                                                                    onClick={() => openDueDateAdjustment(item)}
                                                                >
                                                                    <PenLine className="h-3.5 w-3.5"/>
                                                                    Adjust date
                                                                </Button>
                                                            ) : null}
                                                            {!showPaymentAction && !canAdjustDate ? (
                                                                lockedInstallment ? (
                                                                    <span
                                                                        className="self-center text-xs font-semibold text-muted-foreground">Locked</span>
                                                                ) : (
                                                                    <span
                                                                        className="self-center text-xs text-muted-foreground">—</span>
                                                                )
                                                            ) : null}
                                                        </div>
                                                    </TableCell>
                                                </TableRow>
                                            );
                                        })}
                                    </TableBody>
                                </Table>
                            </div>
                        </>
                    ) : null}
                    <DialogFooter className="mx-0 mb-0 flex-wrap">
                        <Button variant="outline" onClick={() => setScheduleOpen(false)}>Close</Button>
                        {selectedLoan ? (
                            <Button variant="outline"
                                    onClick={() => void printLoanDocument(selectedLoan, "repayment-schedule")}>
                                <Printer className="h-4 w-4"/>
                                Print PDF
                            </Button>
                        ) : null}
                        {selectedLoan && canSettleEarly && ["active", "defaulted"].includes(selectedLoan.status) ? (
                            <Button
                                onClick={() => {
                                    setScheduleOpen(false);
                                    setSettlementLoan(selectedLoan);
                                }}
                            >
                                <HandCoins className="h-4 w-4"/>
                                Settle early
                            </Button>
                        ) : null}
                        {selectedLoan && ["active", "defaulted"].includes(selectedLoan.status) ? (
                            <Button asChild>
                                <Link
                                    href={`/company/origination/new?borrower=${selectedLoan.borrower_id}&type=top_up&loan=${selectedLoan.id}`}
                                    onClick={() => setScheduleOpen(false)}>
                                    <Sparkles className="h-4 w-4"/>
                                    Apply for loan top-up
                                </Link>
                            </Button>
                        ) : null}
                    </DialogFooter>
                </div>
            </CustomDialog>

            <EarlySettlementDialog
                open={Boolean(settlementLoan)}
                loan={settlementLoan}
                methods={methods}
                onOpenChange={(open) => {
                    if (!open) setSettlementLoan(null);
                }}
                onCompleted={async (loanId) => {
                    const updated = await getLoan(loanId);
                    setLoans((rows) => rows.map((loan) => (loan.id === updated.id ? updated : loan)));
                    setSelectedLoan(updated);
                    setSettlementLoan(null);
                }}
            />

            <CustomDialog
                open={Boolean(payingInstallment)}
                onOpenChange={(open) => {
                    if (!open) closeInstallmentPayment();
                }}
                title="Pay installment"
                description={payingInstallment && selectedLoan ? `${selectedLoan.loan_reference} · Installment ${payingInstallment.installment_number}` : undefined}
                contentClassName="sm:max-w-xl"
            >
                <div className="space-y-5 p-5 sm:p-7">
                    {payingInstallment ? (
                        <>
                            <div className="grid gap-3 sm:grid-cols-2">
                                <Value label="Due date" value={formatDate(payingInstallment.due_date)}/>
                                <Value label="Remaining on installment"
                                       value={formatMoney(installmentOutstanding(payingInstallment))} emphasis/>
                                <Value label="Installment total" value={formatMoney(payingInstallment.total_due)}/>
                                <Value label="Already paid" value={formatMoney(payingInstallment.paid_amount)}/>
                            </div>

                            <Alert>
                                <HandCoins className="h-4 w-4"/>
                                <AlertTitle>Post a real repayment</AlertTitle>
                                <AlertDescription>
                                    This action creates the payment transaction, installment allocation, receipt,
                                    accounting entry, platform charge, and treasury movement. It can make a partial
                                    payment or clear this installment, but it cannot advance money into the next
                                    installment. Use the Payment desk for advance payments.
                                </AlertDescription>
                            </Alert>

                            <Field label="Amount received">
                                <Input
                                    type="number"
                                    min="0.01"
                                    step="0.01"
                                    max={installmentOutstanding(payingInstallment).toFixed(2)}
                                    value={installmentPaymentAmount}
                                    onChange={(event) => setInstallmentPaymentAmount(event.target.value)}
                                />
                            </Field>

                            <PaymentMethodFields
                                methods={methods}
                                value={installmentPaymentEvidence}
                                onChange={setInstallmentPaymentEvidence}
                                disabled={postingInstallmentPayment}
                            />
                        </>
                    ) : null}

                    <DialogFooter className="mx-0 mb-0">
                        <Button variant="outline" disabled={postingInstallmentPayment}
                                onClick={closeInstallmentPayment}>Cancel</Button>
                        <LoadingButton
                            loading={postingInstallmentPayment}
                            loadingText="Posting payment…"
                            disabled={!installmentPaymentAmount || Number(installmentPaymentAmount) <= 0}
                            onClick={() => void submitInstallmentPayment()}
                        >
                            <HandCoins className="h-4 w-4"/>
                            Confirm payment
                        </LoadingButton>
                    </DialogFooter>
                </div>
            </CustomDialog>

            <CustomDialog
                open={Boolean(editingInstallment)}
                onOpenChange={(open) => {
                    if (!open) closeDueDateAdjustment();
                }}
                title="Adjust installment due date"
                description={editingInstallment && selectedLoan ? `${selectedLoan.loan_reference} · Installment ${editingInstallment.installment_number}` : undefined}
                contentClassName="sm:max-w-xl"
            >
                <div className="space-y-5 p-5 sm:p-7">
                    {editingInstallment ? (
                        <>
                            <div className="grid gap-3 sm:grid-cols-2">
                                <Value label="Current due date" value={formatDate(editingInstallment.due_date)}/>
                                <Value label="Installment total" value={formatMoney(editingInstallment.total_due)}/>
                            </div>

                            <Alert>
                                <CalendarClock className="h-4 w-4"/>
                                <AlertTitle>Agreed due-date adjustment</AlertTitle>
                                <AlertDescription>
                                    This action can move the installment to a later agreed date only. Principal,
                                    interest, fees, and the installment total remain unchanged.
                                    {nextInstallmentForExtension ? ` The new date must remain before installment ${nextInstallmentForExtension.installment_number}, due ${formatDate(nextInstallmentForExtension.due_date)}.` : " This is the final installment, so its new date will also become the loan maturity date."}
                                </AlertDescription>
                            </Alert>

                            <Field label="Agreed new due date">
                                <Input
                                    type="date"
                                    value={extendedDueDate}
                                    min={dayAfterIsoDate(editingInstallment.due_date)}
                                    max={nextInstallmentForExtension ? dayBeforeIsoDate(nextInstallmentForExtension.due_date) : undefined}
                                    onChange={(event) => setExtendedDueDate(event.target.value)}
                                />
                            </Field>

                            <Field label="Agreement / reason">
                                <Textarea
                                    value={extensionNote}
                                    onChange={(event) => setExtensionNote(event.target.value)}
                                    placeholder="Example: Borrower requested an extension and the lender approved the new date on 28 July 2026."
                                    rows={4}
                                />
                            </Field>

                            <Field label="Agreement reference (optional)">
                                <Input
                                    value={extensionReference}
                                    onChange={(event) => setExtensionReference(event.target.value)}
                                    placeholder="Meeting note, approval, ticket, or document reference"
                                />
                            </Field>
                        </>
                    ) : null}

                    <DialogFooter className="mx-0 mb-0">
                        <Button variant="outline" disabled={extendingDueDate}
                                onClick={closeDueDateAdjustment}>Cancel</Button>
                        <LoadingButton
                            loading={extendingDueDate}
                            loadingText="Saving date…"
                            disabled={!extendedDueDate || extensionNote.trim().length < 3}
                            onClick={() => void saveDueDateAdjustment()}
                        >
                            <CalendarClock className="h-4 w-4"/>
                            Save adjusted date
                        </LoadingButton>
                    </DialogFooter>
                </div>
            </CustomDialog>

            <CustomDialog open={disburseOpen} onOpenChange={(open) => !disbursing && setDisburseOpen(open)}
                          title="Confirm loan disbursement"
                          description="Identify how the borrower receives the money. Non-cash channels require manually verified proof before posting."
                          contentClassName="sm:max-w-lg">
                <div className="space-y-5 p-5 sm:p-8">{selectedLoan && <div className="space-y-5">
                    <div className="rounded-3xl border bg-gradient-to-br from-amber-500/10 to-primary/8 p-5">
                        <div
                            className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-500/15 text-amber-700">
                            <Banknote className="h-6 w-6"/></div>
                        <p className="font-mono text-xs font-black text-primary">{selectedLoan.loan_reference}</p><p
                        className="mt-3 text-xs font-black uppercase tracking-[0.15em] text-muted-foreground">Principal
                        to issue</p><p
                        className="mt-1 text-3xl font-black">{formatMoney(selectedLoan.principal_amount)}</p><p
                        className="mt-3 text-sm text-muted-foreground">The borrower will
                        repay {formatMoney(selectedLoan.total_repayable)} in {selectedLoan.repayment_period} instalments
                        of approximately {formatMoney(selectedLoan.installment_amount)}.</p></div>
                    <PaymentMethodFields methods={methods} value={evidence} onChange={setEvidence} showGatewayRailPicker={false}/></div>}<DialogFooter
                    className="mx-0 mb-0"><Button variant="outline" onClick={() => setDisburseOpen(false)}
                                                  disabled={disbursing}>Cancel</Button><LoadingButton
                    loading={disbursing} loadingText="Posting disbursement..."
                    onClick={() => void disburse()}><CheckCircle2 className="h-4 w-4"/>Confirm
                    disbursement</LoadingButton></DialogFooter></div>
            </CustomDialog>
        </main>
    );
}

function Metric({icon: Icon, label, value, hint}: { icon: LucideIcon; label: string; value: string; hint: string }) {
    return <div className="loanhub-stat">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/12 text-primary"><Icon
            className="h-5 w-5"/></div>
        <p className="mt-4 text-xs font-black uppercase tracking-[0.16em] text-muted-foreground">{label}</p><p
        className="mt-1 text-2xl font-black">{value}</p><p className="mt-2 text-xs text-muted-foreground">{hint}</p>
    </div>;
}

function Field({label, children}: { label: string; children: ReactNode }) {
    return <div className="space-y-2"><Label>{label}</Label>{children}</div>;
}

function Value({label, value, emphasis = false}: { label: string; value: string; emphasis?: boolean }) {
    return <div className="rounded-2xl border bg-background/70 p-4"><p
        className="text-xs font-black uppercase tracking-[0.12em] text-muted-foreground">{label}</p><p
        className={`mt-1 break-words font-black ${emphasis ? "text-2xl text-primary" : "text-lg"}`}>{value}</p></div>;
}

function DocumentCard({icon: Icon, title, description, loading, onClick}: {
    icon: LucideIcon;
    title: string;
    description: string;
    loading: boolean;
    onClick: () => void
}) {
    return <div className="rounded-3xl border bg-card p-5">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary"><Icon
            className="h-5 w-5"/></div>
        <p className="mt-4 font-black">{title}</p><p
        className="mt-1 min-h-10 text-sm text-muted-foreground">{description}</p><LoadingButton className="mt-4 w-full"
                                                                                                variant="outline"
                                                                                                loading={loading}
                                                                                                loadingText="Generating PDF…"
                                                                                                onClick={onClick}><Printer
        className="h-4 w-4"/>Generate & print</LoadingButton></div>;
}
