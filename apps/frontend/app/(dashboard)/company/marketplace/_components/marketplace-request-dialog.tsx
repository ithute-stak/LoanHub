"use client";


import { Input } from "@/components/ui/input";
import { DEFAULT_PAYMENT_METHOD_OPTIONS, EMPTY_PAYMENT_EVIDENCE, PaymentMethodFields, type PaymentEvidence } from "@/components/payments/payment-method-fields";
import { Textarea } from "@/components/ui/textarea";
import { NativeSelect } from "@/components/ui/native-select";
import { FormEvent, useEffect, useState } from "react";
import {
    BriefcaseBusiness,
    Calculator,
    Download,
    FileText,
    Loader2,
    LockKeyhole,
    Mail,
    MapPin,
    Phone,
    Send,
    ShieldCheck,
    UserRound,
    type LucideIcon,
} from "lucide-react";
import { toast } from "@/utils/toast";
import { calculateLoan } from "@/api/loans";
import { downloadMarketplaceEvidence } from "@/api/marketplace";

import { InstallmentDueDateFields, installmentDueDatesComplete, resizeInstallmentDueDates } from "@/components/loans/installment-due-date-fields";
import { CustomDialog } from "@/components/ui/custom-dialog";
import { formatMoney } from "@/lib/format";
import { INTEREST_METHOD_OPTIONS, interestMethodOption } from "@/lib/interest-methods";
import { LoadingButton } from "@/components/ui/loading-button";
import type { InterestMethod, LoanCalculation } from "@/types/loan";
import { useAppData } from "@/provider/appDataProvider";
import { useTenant } from "@/provider/tenantProvider";
import type { MarketplaceRequestCard } from "@/types/marketplace";
import { getErrorMessage } from "@/utils/apiError";

export function MarketplaceRequestDialog({
    request,
    open,
    onOpenChange,
}: {
    request: MarketplaceRequestCard | null;
    open: boolean;
    onOpenChange: (open: boolean) => void;
}) {
    const {
        selectedMarketplaceRequest,
        isMarketplaceLoading,
        branches,
        loadMarketplaceRequest,
        unlockMarketplaceRequest,
        submitLoanOffer,
    } = useAppData();
    const { activeBranchId } = useTenant();
    const [unlocking, setUnlocking] = useState(false);
    const [unlockEvidence, setUnlockEvidence] = useState<PaymentEvidence>(EMPTY_PAYMENT_EVIDENCE);
    const [submitting, setSubmitting] = useState(false);
    const [approvedAmount, setApprovedAmount] = useState("");
    const [termMonths, setTermMonths] = useState("6");
    const [installmentDueDates, setInstallmentDueDates] = useState<string[]>(() => resizeInstallmentDueDates([], 6));
    const [interestRate, setInterestRate] = useState("36");
    const [interestMethod, setInterestMethod] = useState<InterestMethod>("daily_accrual_reducing");
    const [processingFee, setProcessingFee] = useState("0");
    const [branchId, setBranchId] = useState(activeBranchId ?? "");
    const [notes, setNotes] = useState("");
    const [calculation, setCalculation] = useState<LoanCalculation | null>(null);
    const [calculating, setCalculating] = useState(false);

    useEffect(() => {
        if (!open || !request) return;
        const timer = window.setTimeout(() => {
            setApprovedAmount(String(request.requested_amount));
            setBranchId(activeBranchId ?? "");
            setUnlockEvidence(EMPTY_PAYMENT_EVIDENCE);
            void loadMarketplaceRequest(request.id).catch(() => undefined);
        }, 0);
        return () => window.clearTimeout(timer);
    }, [activeBranchId, loadMarketplaceRequest, open, request]);

    useEffect(() => {
        setInstallmentDueDates((current) => resizeInstallmentDueDates(current, Math.trunc(Number(termMonths || 0))));
    }, [termMonths]);

    useEffect(() => {
        const principal = Number(approvedAmount || 0);
        const months = Math.trunc(Number(termMonths || 0));
        const rate = Number(interestRate || 0);
        const fee = Number(processingFee || 0);
        if (principal <= 0 || months <= 0 || rate < 0 || fee < 0 || !installmentDueDatesComplete(installmentDueDates, months)) {
            const resetTimer = window.setTimeout(() => setCalculation(null), 0);
            return () => window.clearTimeout(resetTimer);
        }
        const timer = window.setTimeout(() => {
            setCalculating(true);
            void calculateLoan({
                principal,
                rate_percent: rate,
                months,
                processing_fee: fee,
                interest_method: interestMethod,
                due_dates: installmentDueDates,
            })
                .then(setCalculation)
                .catch((error: unknown) => {
                    setCalculation(null);
                    toast.error(getErrorMessage(error, "The official loan calculation failed"));
                })
                .finally(() => setCalculating(false));
        }, 250);
        return () => window.clearTimeout(timer);
    }, [approvedAmount, installmentDueDates, interestMethod, interestRate, processingFee, termMonths]);

    if (!request) return null;

    const requestId = request.id;

    async function handleUnlock(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setUnlocking(true);
        try {
            const unlock = await unlockMarketplaceRequest(requestId, {
                payment_method: unlockEvidence.payment_method,
                proof_reference: unlockEvidence.proof_reference.trim() || null,
                proof_url: unlockEvidence.proof_url.trim() || null,
                proof_notes: unlockEvidence.proof_notes.trim() || null,
            });
            toast.success(
                unlock.status === "unlocked"
                    ? "Borrower profile unlocked"
                    : "Unlock payment has been initiated",
            );
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not unlock the request"));
        } finally {
            setUnlocking(false);
        }
    }

    async function handleOffer(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setSubmitting(true);
        try {
            await submitLoanOffer({
                loan_request_id: requestId,
                branch_id: branchId || null,
                approved_amount: Number(approvedAmount),
                term_months: Number(termMonths),
                interest_rate_percent: Number(interestRate),
                processing_fee: Number(processingFee),
                calculation_method: interestMethod,
                installment_due_dates: installmentDueDates,
                notes: notes.trim() || null,
            });
            toast.success("Loan offer sent to the borrower");
            onOpenChange(false);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not send the offer"));
        } finally {
            setSubmitting(false);
        }
    }

    const detail =
        selectedMarketplaceRequest?.id === request.id
            ? selectedMarketplaceRequest
            : null;
    const unlocked = Boolean(detail?.is_unlocked && detail.borrower_detail);

    return (
        <CustomDialog
            open={open}
            onOpenChange={onOpenChange}
            title={`Loan request · ${formatMoney(request.requested_amount)}`}
            description="Review the redacted opportunity, unlock verified borrower details and submit one competitive offer for your company."
            contentClassName="sm:max-w-6xl"
        >
            <div className="p-6 sm:p-8">
                {isMarketplaceLoading && !detail ? (
                    <div className="flex min-h-48 items-center justify-center">
                        <Loader2 className="h-7 w-7 animate-spin text-primary" />
                    </div>
                ) : unlocked && detail?.borrower_detail ? (
                    <div className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
                        <section className="space-y-4 rounded-3xl border bg-muted/20 p-5">
                            <div className="flex items-center gap-3">
                                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                                    <UserRound className="h-6 w-6" />
                                </div>
                                <div>
                                    <p className="text-lg font-black">{detail.borrower_detail.full_name}</p>
                                    <p className="text-xs text-muted-foreground">Verified borrower profile</p>
                                </div>
                            </div>
                            <Info icon={Phone} label="Phone" value={detail.borrower_detail.phone} />
                            <Info icon={Mail} label="Email" value={detail.borrower_detail.email ?? "Not supplied"} />
                            <Info icon={MapPin} label="Location" value={[detail.borrower_detail.district, detail.borrower_detail.town_or_village].filter(Boolean).join(", ") || "Not supplied"} />
                            <Info icon={BriefcaseBusiness} label="Employment" value={[detail.borrower_detail.employment_status, detail.borrower_detail.employer_name].filter(Boolean).join(" · ")} />
                            <div className="grid grid-cols-2 gap-3">
                                <DataBox label="Monthly income" value={formatMoney(detail.borrower_detail.monthly_income)} />
                                <DataBox label="Existing loans" value={formatMoney(detail.borrower_detail.existing_loan_total)} />
                            </div>
                            <div className="rounded-2xl border border-green-200 bg-green-50 p-3 text-xs font-semibold text-green-700 dark:border-green-900 dark:bg-green-950/30 dark:text-green-400">
                                <ShieldCheck className="mr-2 inline h-4 w-4" />
                                Credit-check consent: {detail.borrower_detail.consent_to_credit_checks ? "Granted" : "Not granted"}
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <DataBox label="Verified monthly income" value={formatMoney(detail.borrower_detail.total_monthly_income)} />
                                <DataBox label="Monthly commitments" value={formatMoney(detail.borrower_detail.total_monthly_commitments)} />
                                <DataBox label="Disposable income" value={formatMoney(detail.borrower_detail.disposable_monthly_income)} />
                                <DataBox label="Debt-to-income" value={detail.borrower_detail.debt_to_income_percent == null ? "Not available" : `${detail.borrower_detail.debt_to_income_percent.toFixed(1)}%`} />
                                <DataBox label="Dependants" value={String(detail.borrower_detail.dependants)} />
                                <DataBox label="Profile readiness" value={`${detail.borrower_detail.profile_completeness}%`} />
                            </div>
                            <div className="rounded-2xl border p-3 text-xs text-muted-foreground">
                                <p className="font-bold text-foreground">Additional evaluation details</p>
                                <p className="mt-2">Employment: {[detail.borrower_detail.employment_type, detail.borrower_detail.job_title, detail.borrower_detail.employment_start_date].filter(Boolean).join(" · ") || "Not supplied"}</p>
                                <p className="mt-1">Residence: {[detail.borrower_detail.residential_status, detail.borrower_detail.years_at_address == null ? null : `${detail.borrower_detail.years_at_address} years at address`].filter(Boolean).join(" · ") || "Not supplied"}</p>
                                <p className="mt-1">Bank identity: {detail.borrower_detail.bank_name && detail.borrower_detail.account_last_four ? `${detail.borrower_detail.bank_name} · ending ${detail.borrower_detail.account_last_four}` : "Not supplied"}</p>
                            </div>
                            <div className="rounded-2xl border p-3">
                                <div className="flex items-center justify-between gap-3">
                                    <p className="text-sm font-black">Confidential evaluation evidence</p>
                                    <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-bold text-primary">
                                        {detail.borrower_detail.evidence_documents.length} files
                                    </span>
                                </div>
                                {detail.borrower_detail.evidence_documents.length ? (
                                    <div className="mt-3 space-y-2">
                                        {detail.borrower_detail.evidence_documents.map((document) => (
                                            <div key={document.id} className="flex items-center justify-between gap-3 rounded-xl bg-muted/40 p-3">
                                                <div className="min-w-0">
                                                    <p className="truncate text-xs font-bold">{document.original_name}</p>
                                                    <p className="mt-1 text-[11px] text-muted-foreground">{evidenceLabel(document.category)} · {fileSize(document.size_bytes)}</p>
                                                </div>
                                                <button
                                                    type="button"
                                                    onClick={() => {
                                                        void downloadMarketplaceEvidence(document).catch((error: unknown) => {
                                                            toast.error(getErrorMessage(error, "Could not download the evidence"));
                                                        });
                                                    }}
                                                    className="rounded-lg border p-2 hover:border-primary hover:text-primary"
                                                    title="Download confidential evidence"
                                                >
                                                    <Download className="h-4 w-4" />
                                                </button>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="mt-3 text-xs text-muted-foreground">
                                        {detail.borrower_detail.consent_to_share_documents
                                            ? "The borrower has not supplied shareable evidence yet."
                                            : "The borrower has not granted evidence-sharing consent."}
                                    </p>
                                )}
                            </div>
                            {detail.borrower_detail.missing_requirements.length ? (
                                <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-300">
                                    <FileText className="mr-2 inline h-4 w-4" />
                                    Still needed: {detail.borrower_detail.missing_requirements.join(", ")}
                                </div>
                            ) : null}
                        </section>

                        <form onSubmit={handleOffer} className="space-y-4 rounded-3xl border p-5">
                            <div>
                                <h3 className="text-lg font-black">Prepare company offer</h3>
                                <p className="mt-1 text-sm text-muted-foreground">The borrower will compare this with offers from other companies. Choose the calculation method the borrower will compare with other offers.</p>
                            </div>
                            <div className="grid gap-4 sm:grid-cols-2">
                                <Field label="Approved amount">
                                    <Input type="number" min="1" step="0.01" required value={approvedAmount} onChange={(e) => setApprovedAmount(e.target.value)} className="h-11 w-full rounded-xl border bg-background px-3" />
                                </Field>
                                <Field label="Term in months">
                                    <Input type="number" min="1" required value={termMonths} onChange={(e) => setTermMonths(e.target.value)} className="h-11 w-full rounded-xl border bg-background px-3" />
                                </Field>
                                <InstallmentDueDateFields
                                    count={Math.trunc(Number(termMonths || 0))}
                                    value={installmentDueDates}
                                    onChange={setInstallmentDueDates}
                                />
                                <Field label="Interest method">
                                    <NativeSelect value={interestMethod} onChange={(event) => setInterestMethod(event.target.value as InterestMethod)} className="h-11 w-full rounded-xl border bg-background px-3">
                                        {INTEREST_METHOD_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                                    </NativeSelect>
                                </Field>
                                <Field label={interestMethodOption(interestMethod).rateLabel}>
                                    <Input type="number" min="0" step="0.01" required value={interestRate} onChange={(e) => setInterestRate(e.target.value)} className="h-11 w-full rounded-xl border bg-background px-3" />
                                    <p className="mt-1 text-xs text-muted-foreground">{interestMethodOption(interestMethod).description}</p>
                                </Field>
                                <Field label="Processing fee">
                                    <Input type="number" min="0" step="0.01" required value={processingFee} onChange={(e) => setProcessingFee(e.target.value)} className="h-11 w-full rounded-xl border bg-background px-3" />
                                </Field>
                                <Field label="Servicing branch">
                                    <NativeSelect value={branchId} onChange={(e) => setBranchId(e.target.value)} className="h-11 w-full rounded-xl border bg-background px-3">
                                        <option value="">Company head office</option>
                                        {branches.filter((branch) => branch.is_active).map((branch) => (
                                            <option key={branch.id} value={branch.id}>{branch.name}</option>
                                        ))}
                                    </NativeSelect>
                                </Field>
                                <div className="rounded-2xl bg-primary/10 p-4">
                                    <div className="flex items-center gap-2 text-primary">
                                        <Calculator className="h-4 w-4" />
                                        <span className="text-xs font-black uppercase">Estimated installment</span>
                                    </div>
                                    <p className="mt-2 text-xl font-black">{calculating ? "Calculating..." : formatMoney(calculation?.monthly_installment ?? 0)}</p>
                                    <p className="mt-1 text-xs text-muted-foreground">Total {formatMoney(calculation?.total_repayable ?? 0)} · official API result</p>
                                </div>
                            </div>
                            <Field label="Offer notes">
                                <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} className="w-full rounded-xl border bg-background p-3" placeholder="Conditions, required documents or repayment notes..." />
                            </Field>
                            <LoadingButton type="submit" loading={submitting} loadingText="Submitting offer..." disabled={calculating || !calculation} className="w-full">
                                <Send className="h-4 w-4" />Submit loan offer
                            </LoadingButton>
                        </form>
                    </div>
                ) : (
                    <div className="grid gap-5 lg:grid-cols-2">
                        <section className="rounded-3xl border bg-muted/20 p-5">
                            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
                                <LockKeyhole className="h-7 w-7" />
                            </div>
                            <h3 className="mt-4 text-xl font-black">Borrower identity is protected</h3>
                            <p className="mt-2 text-sm leading-6 text-muted-foreground">
                                Your company can assess the district, employment category, income band and requested terms before paying. Full identity, contacts and affordability information are only returned after access is granted.
                            </p>
                            <div className="mt-5 grid grid-cols-2 gap-3">
                                <DataBox label="District" value={request.borrower.district ?? "Private"} />
                                <DataBox label="Income band" value={request.borrower.monthly_income_band ?? "Private"} />
                                <DataBox label="Employment" value={request.borrower.employment_status.replaceAll("_", " ")} />
                                <DataBox label="Unlock price" value={formatMoney(request.unlock_price)} />
                            </div>
                        </section>

                        <form onSubmit={handleUnlock} className="space-y-4 rounded-3xl border p-5">
                            <div>
                                <h3 className="text-lg font-black">Unlock this opportunity</h3>
                                <p className="mt-1 text-sm text-muted-foreground">
                                    Subscription plans may include free access. Otherwise, the configured pay-per-request fee is charged.
                                </p>
                            </div>
                            <PaymentMethodFields
                                methods={DEFAULT_PAYMENT_METHOD_OPTIONS}
                                value={unlockEvidence}
                                onChange={setUnlockEvidence}
                            />
                            <LoadingButton type="submit" loading={unlocking} loadingText="Recording access payment..." className="w-full">
                                <LockKeyhole className="h-4 w-4" />Record payment and unlock · {formatMoney(request.unlock_price)}
                            </LoadingButton>
                        </form>
                    </div>
                )}
            </div>
        </CustomDialog>
    );
}

function Field({ label, children }: { label: string; children: import("react").ReactNode }) {
    return (
        <label className="block">
            <span className="mb-2 block text-sm font-bold">{label}</span>
            {children}
        </label>
    );
}

function DataBox({ label, value }: { label: string; value: string }) {
    return (
        <div className="rounded-2xl bg-muted/60 p-3">
            <p className="text-[11px] font-bold uppercase text-muted-foreground">{label}</p>
            <p className="mt-1 text-sm font-black capitalize">{value}</p>
        </div>
    );
}

function Info({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
    return (
        <div className="flex items-start gap-3 rounded-2xl bg-background p-3">
            <Icon className="mt-0.5 h-4 w-4 text-primary" />
            <div>
                <p className="text-[11px] font-bold uppercase text-muted-foreground">{label}</p>
                <p className="mt-1 text-sm font-bold">{value}</p>
            </div>
        </div>
    );
}

function evidenceLabel(category: string) {
    const labels: Record<string, string> = {
        borrower_identity: "Identity",
        borrower_proof_of_address: "Proof of address",
        borrower_payslip: "Income proof",
        borrower_bank_statement: "Bank statement",
        borrower_employment: "Employment evidence",
        borrower_existing_debt: "Existing debt",
        borrower_business: "Business evidence",
        borrower_other: "Other evidence",
    };
    return labels[category] ?? category.replaceAll("_", " ");
}

function fileSize(bytes: number) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
