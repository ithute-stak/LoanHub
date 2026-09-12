"use client";

import Link from "next/link";
import {usePathname, useRouter, useSearchParams} from "next/navigation";
import {
    useCallback,
    useEffect,
    useMemo,
    useState,
    type FormEvent,
    type ReactNode,
} from "react";
import {
    BadgeCheck,
    BookOpenCheck,
    CheckCircle2,
    ClipboardCheck,
    ExternalLink,
    FileSearch,
    PackagePlus,
    RefreshCcw,
    Search,
    ShieldAlert,
    UserRoundSearch,
    XCircle,
    type LucideIcon,
} from "lucide-react";

import {listLoanProducts} from "@/api/loanProducts";
import { calculateLoan } from "@/api/loans";
import {professionalApi} from "@/api/professional";
import {LoanProductDialog} from "@/components/loans/loan-product-dialog";
import {InstallmentDueDateFields, installmentDueDatesComplete, resizeInstallmentDueDates} from "@/components/loans/installment-due-date-fields";
import {MicroLoanPreview} from "@/components/loans/micro-loan-preview";
import {Alert, AlertDescription, AlertTitle} from "@/components/ui/alert";
import {Badge} from "@/components/ui/badge";
import {Button} from "@/components/ui/button";
import {Card, CardContent, CardDescription, CardHeader, CardTitle} from "@/components/ui/card";
import {CustomDialog} from "@/components/ui/custom-dialog";
import {DialogFooter} from "@/components/ui/dialog";
import {Input} from "@/components/ui/input";
import {Label} from "@/components/ui/label";
import {LoadingButton} from "@/components/ui/loading-button";
import {PageLoader} from "@/components/ui/page-loader";
import {SuggestionSearch} from "@/components/ui/suggestion-search";
import {StickyFilterBar} from "@/components/ui/sticky-filter-bar";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "@/components/ui/select";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
import {Tabs, TabsList, TabsTrigger} from "@/components/ui/tabs";
import {Textarea} from "@/components/ui/textarea";
import {formatDate, formatMoney, titleCase} from "@/lib/format";
import {useTenant} from "@/provider/tenantProvider";
import type { LoanCalculation } from "@/types/loan";
import type {LoanProduct} from "@/types/loanProduct";
import type {DirectLoanApplication} from "@/types/professional";
import {getErrorMessage} from "@/utils/apiError";
import {toast} from "@/utils/toast";

type ApplicationFilter = "pending" | "approved" | "rejected" | "all";

type ApprovalForm = {
    product_id: string;
    approved_amount: number;
    interest_rate: number;
    processing_fee: number;
    installment_due_dates: string[];
    decision_notes: string;
};

const emptyApproval: ApprovalForm = {
    product_id: "",
    approved_amount: 0,
    interest_rate: 0,
    processing_fee: 0,
    installment_due_dates: [],
    decision_notes: "",
};

export function InternalApplicationsWorkspace() {
    const pathname = usePathname();
    const router = useRouter();
    const searchParams = useSearchParams();
    const requestedApplicationId = searchParams.get("application");
    const {activeRole} = useTenant();
    const [applications, setApplications] = useState<DirectLoanApplication[]>([]);
    const [products, setProducts] = useState<LoanProduct[]>([]);
    const [loading, setLoading] = useState(true);
    const [working, setWorking] = useState(false);
    const [search, setSearch] = useState("");
    const [filter, setFilter] = useState<ApplicationFilter>("pending");
    const [selected, setSelected] = useState<DirectLoanApplication | null>(null);
    const [approval, setApproval] = useState<ApprovalForm>(emptyApproval);
    const [rejectReason, setRejectReason] = useState("");
    const [calculation, setCalculation] = useState<LoanCalculation | null>(null);
    const [calculating, setCalculating] = useState(false);
    const [productDialog, setProductDialog] = useState(false);

    const canReview = Boolean(activeRole && ["company_owner", "company_admin", "branch_manager", "risk_manager"].includes(activeRole));
    const canApprove = Boolean(activeRole && ["company_owner", "company_admin", "branch_manager"].includes(activeRole));
    const canManageProducts = Boolean(activeRole && ["company_owner", "company_admin"].includes(activeRole));

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [applicationRows, productRows] = await Promise.all([
                professionalApi.listDirect(),
                listLoanProducts(),
            ]);
            setApplications(applicationRows);
            setProducts(productRows.filter((product) => product.is_active));
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Internal applications could not be loaded."));
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        const timer = window.setTimeout(() => void load(), 0);
        return () => window.clearTimeout(timer);
    }, [load]);

    const selectedProduct = useMemo(
        () => products.find((product) => product.id === approval.product_id) ?? null,
        [approval.product_id, products],
    );

    useEffect(() => {
        let cancelled = false;
        const timer = window.setTimeout(() => {
            if (!selected || !selectedProduct || approval.approved_amount <= 0 || selected.term_count <= 0 || !installmentDueDatesComplete(approval.installment_due_dates, selected.term_count)) {
                setCalculation(null);
                setCalculating(false);
                return;
            }
            setCalculating(true);
            void calculateLoan({
                principal: approval.approved_amount,
                rate_percent: approval.interest_rate,
                months: selected.term_count,
                processing_fee: approval.processing_fee,
                interest_method: selectedProduct.interest_method,
                due_dates: approval.installment_due_dates,
            })
                .then((result) => {
                    if (!cancelled) setCalculation(result);
                })
                .catch((error: unknown) => {
                    if (!cancelled) {
                        setCalculation(null);
                        toast.error(getErrorMessage(error, "The approval calculation could not be completed."));
                    }
                })
                .finally(() => {
                    if (!cancelled) setCalculating(false);
                });
        }, 300);
        return () => {
            cancelled = true;
            window.clearTimeout(timer);
        };
    }, [approval.approved_amount, approval.installment_due_dates, approval.interest_rate, approval.processing_fee, selected, selectedProduct]);

    const filtered = useMemo(() => {
        const value = search.trim().toLowerCase();
        return applications.filter((application) => {
            const statusMatches = filter === "all"
                || (filter === "pending" && ["submitted", "under_review"].includes(application.status))
                || application.status === filter;
            if (!statusMatches) return false;
            if (!value) return true;
            return [
                application.application_reference,
                application.borrower_name,
                application.account_reference,
                application.product_name,
                application.loan_reference,
            ].filter(Boolean).some((item) => String(item).toLowerCase().includes(value));
        });
    }, [applications, filter, search]);

    const counts = useMemo(() => ({
        pending: applications.filter((item) => ["submitted", "under_review"].includes(item.status)).length,
        approved: applications.filter((item) => item.status === "approved").length,
        rejected: applications.filter((item) => item.status === "rejected").length,
    }), [applications]);

    const openApplication = useCallback((application: DirectLoanApplication) => {
        const product = products.find((item) => item.id === application.product_id) ?? products[0] ?? null;
        setSelected(application);
        setApproval({
            product_id: product?.id ?? "",
            approved_amount: Number(application.approved_amount ?? application.requested_amount),
            interest_rate: Number(application.interest_rate ?? product?.interest_rate_percent ?? 0),
            processing_fee: Number(product?.processing_fee ?? 0),
            installment_due_dates: resizeInstallmentDueDates(application.installment_due_dates ?? [], application.term_count),
            decision_notes: application.decision_notes ?? "",
        });
        setRejectReason("");
        setCalculation(null);
    }, [products]);

    useEffect(() => {
        if (!requestedApplicationId || applications.length === 0 || selected) return;
        const match = applications.find((application) => application.id === requestedApplicationId);
        if (!match) return;
        const timer = window.setTimeout(() => openApplication(match), 0);
        return () => window.clearTimeout(timer);
    }, [applications, openApplication, requestedApplicationId, selected]);

    function chooseProduct(productId: string) {
        const product = products.find((item) => item.id === productId);
        setApproval((current) => ({
            ...current,
            product_id: productId,
            interest_rate: Number(product?.interest_rate_percent ?? current.interest_rate),
            processing_fee: Number(product?.processing_fee ?? current.processing_fee),
            approved_amount: product
                ? Math.min(Math.max(current.approved_amount || Number(product.min_amount), Number(product.min_amount)), Number(product.max_amount))
                : current.approved_amount,
        }));
    }

    function replaceApplication(updated: DirectLoanApplication) {
        setApplications((current) => current.map((item) => item.id === updated.id ? updated : item));
        setSelected(updated);
    }

    function closeApplication() {
        setSelected(null);
        if (!requestedApplicationId) return;

        const params = new URLSearchParams(searchParams.toString());
        params.delete("application");
        const query = params.toString();
        router.replace(query ? `${pathname}?${query}` : pathname, {scroll: false});
    }

    async function startReview() {
        if (!selected) return;
        setWorking(true);
        try {
            const updated = await professionalApi.reviewDirect(selected.id, {
                notes: approval.decision_notes.trim() || null,
            });
            replaceApplication(updated);
            toast.success("Application moved to review");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "The application could not enter review."));
        } finally {
            setWorking(false);
        }
    }

    async function approveApplication(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!selected || !selectedProduct || !calculation) return;
        setWorking(true);
        try {
            const result = await professionalApi.approveDirect(selected.id, {
                product_id: selectedProduct.id,
                approved_amount: approval.approved_amount,
                interest_rate: approval.interest_rate,
                processing_fee: approval.processing_fee,
                installment_due_dates: approval.installment_due_dates,
                decision_notes: approval.decision_notes.trim() || null,
            });
            replaceApplication(result.application);
            toast.success("Application approved", {
                description: `Loan ${result.application.loan_reference ?? result.loan.loan_reference} is ready for cash disbursement.`,
            });
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "The application could not be approved."));
        } finally {
            setWorking(false);
        }
    }

    async function rejectApplication() {
        if (!selected || rejectReason.trim().length < 3) return;
        setWorking(true);
        try {
            const updated = await professionalApi.rejectDirect(selected.id, {reason: rejectReason.trim()});
            replaceApplication(updated);
            toast.success("Application rejected");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "The application could not be rejected."));
        } finally {
            setWorking(false);
        }
    }

    if (loading) return <PageLoader rows={7}/>;

    return (
        <div className="space-y-6">
            <section className="rounded-3xl border border-border/70 bg-card p-5 shadow-sm sm:p-6">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                        <p className="text-xs font-black uppercase tracking-[0.2em] text-primary">Private lending channel</p>
                        <h2 className="mt-2 text-2xl font-black tracking-tight">Internal application queue</h2>
                        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                            Review applications submitted directly by registered clients, verify affordability, select the loan product and create the approved loan.
                        </p>
                    </div>
                    <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                        <Button variant="outline" onClick={() => void load()}><RefreshCcw className="h-4 w-4"/>Refresh</Button>
                        {canManageProducts ? <Button variant="outline" onClick={() => setProductDialog(true)}><PackagePlus className="h-4 w-4"/>New loan product</Button> : null}
                        <Button asChild><Link href="/company/clients"><UserRoundSearch className="h-4 w-4"/>Open client book</Link></Button>
                    </div>
                </div>
            </section>

            <div className="grid gap-4 sm:grid-cols-3">
                <Metric title="Awaiting decision" value={counts.pending} icon={ClipboardCheck}/>
                <Metric title="Approved" value={counts.approved} icon={BadgeCheck}/>
                <Metric title="Rejected" value={counts.rejected} icon={XCircle}/>
            </div>

            <Card className="overflow-visible rounded-3xl border-border/70 shadow-sm">
                <StickyFilterBar
                    ariaLabel="Internal application search and status filters"
                    className="rounded-t-3xl data-[floating=true]:rounded-2xl data-[floating=true]:border"
                >
                <CardHeader className="rounded-[inherit] border-b bg-muted/20">
                    <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
                        <div><CardTitle>Application queue</CardTitle><CardDescription>Select an application to review
                            the borrower, product and automatic instalment calculation.</CardDescription></div>
                        <div className="flex flex-col gap-3 sm:flex-row">
                            <SuggestionSearch
                                value={search}
                                onValueChange={setSearch}
                                suggestions={applications.map((application) => ({
                                    value: application.borrower_name || application.application_reference,
                                    label: application.borrower_name || application.application_reference,
                                    description: `${application.application_reference} · ${titleCase(application.status)}`,
                                    keywords: [
                                        application.id,
                                        application.account_reference ?? "",
                                        application.loan_reference ?? "",
                                        application.purpose ?? "",
                                        application.product_name ?? "",
                                    ],
                                }))}
                                placeholder="Type a borrower, application or loan number..."
                                suggestionLabel="Internal applications"
                                emptyMessage="No application matches that text."
                                wrapperClassName="min-w-64"
                            />
                            <Tabs value={filter}
                                  onValueChange={(value) => setFilter(value as ApplicationFilter)}><TabsList><TabsTrigger
                                value="pending">Pending</TabsTrigger><TabsTrigger
                                value="approved">Approved</TabsTrigger><TabsTrigger
                                value="rejected">Rejected</TabsTrigger><TabsTrigger
                                value="all">All</TabsTrigger></TabsList></Tabs>
                        </div>
                    </div>
                </CardHeader>
                </StickyFilterBar>
                <CardContent className="overflow-hidden rounded-b-3xl p-0">
                    <Table>
                        <TableHeader><TableRow><TableHead>Application</TableHead><TableHead>Borrower</TableHead><TableHead>Product</TableHead><TableHead>Request</TableHead><TableHead>Status</TableHead><TableHead
                            className="text-right">Action</TableHead></TableRow></TableHeader>
                        <TableBody>
                            {filtered.length === 0 ?
                                <TableRow><TableCell colSpan={6} className="h-44 text-center text-muted-foreground">No
                                    internal applications match this
                                    view.</TableCell></TableRow> : filtered.map((application) => (
                                    <TableRow key={application.id}
                                              className={requestedApplicationId === application.id ? "bg-primary/5" : undefined}>
                                        <TableCell><p
                                            className="font-mono text-xs font-black">{application.application_reference}</p>
                                            <p className="mt-1 text-xs text-muted-foreground">{formatDate(application.created_at)}</p>
                                        </TableCell>
                                        <TableCell><p className="font-black">{application.borrower_name}</p><p
                                            className="text-xs text-muted-foreground">{application.account_reference ?? "Registered borrower"}</p>
                                        </TableCell>
                                        <TableCell>{application.product_name ?? <span className="text-amber-700">Select during processing</span>}</TableCell>
                                        <TableCell><p
                                            className="font-black">{formatMoney(application.requested_amount)}</p><p
                                            className="text-xs text-muted-foreground">{application.term_count} months</p>
                                        </TableCell>
                                        <TableCell><StatusBadge status={application.status}/></TableCell>
                                        <TableCell className="text-right"><Button size="sm"
                                                                                  variant={application.status === "approved" ? "outline" : "default"}
                                                                                  onClick={() => openApplication(application)}><FileSearch
                                            className="h-4 w-4"/>{application.status === "approved" ? "View" : "Process"}
                                        </Button></TableCell>
                                    </TableRow>
                                ))}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>

            <CustomDialog
                open={Boolean(selected)}
                onOpenChange={(open) => !open && !working && closeApplication()}
                title={selected ? `${selected.application_reference} — ${selected.borrower_name}` : "Process application"}
                description={selected ? `${formatMoney(selected.requested_amount)} requested for ${selected.term_count} months · ${titleCase(selected.status)}` : undefined}
            >
                {selected ? (
                    <form onSubmit={approveApplication} className="space-y-6 p-6 sm:p-8">
                        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                            <Info label="Client number" value={selected.account_reference ?? "Not available"}/>
                            <Info label="Monthly income"
                                  value={formatMoney(numberFromRecord(selected.affordability_snapshot, "monthly_income"))}/>
                            <Info label="Existing loans"
                                  value={formatMoney(numberFromRecord(selected.affordability_snapshot, "existing_loan_total"))}/>
                            <Info label="Channel" value="Internal company application"/>
                        </div>

                        {booleanFromRecord(selected.credit_warning, "blacklisted") ? (
                            <Alert variant="destructive"><ShieldAlert className="h-4 w-4"/><AlertTitle>Credit
                                warning</AlertTitle><AlertDescription>{textFromRecord(selected.credit_warning, "blacklist_reason") || "The borrower is marked by the credit check."}</AlertDescription></Alert>
                        ) : textFromRecord(selected.credit_warning, "warning") ? (
                            <Alert><ShieldAlert className="h-4 w-4"/><AlertTitle>Active obligation
                                warning</AlertTitle><AlertDescription>{textFromRecord(selected.credit_warning, "warning")}</AlertDescription></Alert>
                        ) : null}

                        {selected.status === "approved" ? (
                            <div className="space-y-5">
                                <Alert><CheckCircle2 className="h-4 w-4"/><AlertTitle>Loan created
                                    successfully</AlertTitle><AlertDescription>The application was converted into
                                    loan <strong>{selected.loan_reference}</strong>. Finance can now record the verified payment
                                    disbursement.</AlertDescription></Alert>
                                <Button asChild className="w-full"><Link href="/company/loans"><ExternalLink
                                    className="h-4 w-4"/>Open approved loans</Link></Button>
                            </div>
                        ) : selected.status === "rejected" ? (
                            <Alert variant="destructive"><XCircle className="h-4 w-4"/><AlertTitle>Application
                                rejected</AlertTitle><AlertDescription>{selected.decision_notes || "No decision reason was recorded."}</AlertDescription></Alert>
                        ) : (
                            <>
                                {!canApprove ? (
                                    <Alert><ClipboardCheck className="h-4 w-4"/><AlertTitle>Manager decision
                                        required</AlertTitle><AlertDescription>Your active role can view or prepare this
                                        application, but approval is reserved for the Branch Manager, Company
                                        Administrator or Company Owner.</AlertDescription></Alert>
                                ) : null}

                                <div className="grid gap-5 sm:grid-cols-2">
                                    <div className="space-y-2 sm:col-span-2">
                                        <div className="flex items-end justify-between gap-3"><Label>Loan
                                            product</Label>{canManageProducts ?
                                            <Button type="button" size="sm" variant="ghost"
                                                    onClick={() => setProductDialog(true)}><PackagePlus
                                                className="h-4 w-4"/>Create product</Button> : null}</div>
                                        <Select value={approval.product_id || "none"}
                                                onValueChange={chooseProduct}><SelectTrigger><SelectValue
                                            placeholder="Select a loan product"/></SelectTrigger><SelectContent><SelectItem
                                            value="none" disabled>Select a loan
                                            product</SelectItem>{products.map((product) => <SelectItem key={product.id}
                                                                                                       value={product.id}>{product.name} · {Number(product.interest_rate_percent)}%</SelectItem>)}
                                        </SelectContent></Select>
                                        {selectedProduct ?
                                            <p className="text-xs text-muted-foreground">Allowed {formatMoney(selectedProduct.min_amount)}–{formatMoney(selectedProduct.max_amount)} · {selectedProduct.min_term_months}–{selectedProduct.max_term_months} months</p> : null}
                                    </div>
                                    <Field label="Approved amount"><Input type="number" required
                                                                          min={selectedProduct ? Number(selectedProduct.min_amount) : 1}
                                                                          max={selectedProduct ? Number(selectedProduct.max_amount) : undefined}
                                                                          step="0.01"
                                                                          value={approval.approved_amount || ""}
                                                                          onChange={(event) => setApproval((current) => ({
                                                                              ...current,
                                                                              approved_amount: Number(event.target.value || 0)
                                                                          }))}/></Field>
                                    <Field label="Term"><Input value={`${selected.term_count} months`}
                                                               disabled/></Field>
                                    <InstallmentDueDateFields
                                        count={selected.term_count}
                                        value={approval.installment_due_dates}
                                        onChange={(dates) => setApproval((current) => ({ ...current, installment_due_dates: dates }))}
                                    />
                                    <Field label={`${selectedProduct ? selectedProduct.interest_method.replaceAll("_", " ") : "Interest"} rate (%)`}><Input type="number" required min={0} max={100}
                                                                              step="0.001"
                                                                              value={approval.interest_rate}
                                                                              onChange={(event) => setApproval((current) => ({
                                                                                  ...current,
                                                                                  interest_rate: Number(event.target.value || 0)
                                                                              }))}/></Field>
                                    <Field label="Processing fee"><Input type="number" required min={0} step="0.01"
                                                                         value={approval.processing_fee}
                                                                         onChange={(event) => setApproval((current) => ({
                                                                             ...current,
                                                                             processing_fee: Number(event.target.value || 0)
                                                                         }))}/></Field>
                                    <div className="space-y-2 sm:col-span-2"><Label>Review or approval
                                        notes</Label><Textarea value={approval.decision_notes}
                                                               onChange={(event) => setApproval((current) => ({
                                                                   ...current,
                                                                   decision_notes: event.target.value
                                                               }))}
                                                               placeholder="Affordability assessment, verified documents and conditions"/>
                                    </div>
                                </div>

                                <MicroLoanPreview calculation={calculation} calculating={calculating}/>

                                {canApprove ? <div className="space-y-2"><Label>Rejection reason</Label><Textarea
                                    value={rejectReason} onChange={(event) => setRejectReason(event.target.value)}
                                    placeholder="Required only when rejecting the application"/></div> : null}

                                <DialogFooter className="mx-0 mb-0 flex-wrap">
                                    <Button type="button" variant="outline" onClick={closeApplication}
                                            disabled={working}>Close</Button>
                                    {selected.status === "submitted" && canReview ?
                                        <LoadingButton type="button" variant="secondary" loading={working}
                                                       loadingText="Starting review…"
                                                       onClick={() => void startReview()}><BookOpenCheck
                                            className="h-4 w-4"/>Start review</LoadingButton> : null}
                                    {canApprove ? <LoadingButton type="button" variant="destructive" loading={working}
                                                                 loadingText="Rejecting…"
                                                                 disabled={rejectReason.trim().length < 3}
                                                                 onClick={() => void rejectApplication()}><XCircle
                                        className="h-4 w-4"/>Reject</LoadingButton> : null}
                                    {canApprove ? <LoadingButton type="submit" loading={working}
                                                                 loadingText="Approving and creating loan…"
                                                                 disabled={!selectedProduct || !calculation || calculating}><CheckCircle2
                                        className="h-4 w-4"/>Approve and create loan</LoadingButton> : null}
                                </DialogFooter>
                            </>
                        )}
                    </form>
                ) : null}
            </CustomDialog>

            <LoanProductDialog
                open={productDialog}
                onOpenChange={setProductDialog}
                onSaved={(product) => {
                    setProducts((current) => [product, ...current.filter((item) => item.id !== product.id)]);
                    setApproval((current) => ({
                        ...current,
                        product_id: product.id,
                        interest_rate: Number(product.interest_rate_percent),
                        processing_fee: Number(product.processing_fee),
                        approved_amount: Math.min(
                            Math.max(current.approved_amount || Number(product.min_amount), Number(product.min_amount)),
                            Number(product.max_amount),
                        ),
                    }));
                }}
            />
        </div>
    );
}

function StatusBadge({status}: { status: string }) {
    const variant = status === "rejected" ? "destructive" : status === "approved" ? "default" : "secondary";
    return <Badge variant={variant}>{titleCase(status)}</Badge>;
}

function Metric({title, value, icon: Icon}: { title: string; value: number; icon: LucideIcon }) {
    return <Card className="rounded-3xl border-border/70 bg-gradient-to-br from-card to-primary/5"><CardContent
        className="flex items-center gap-4 p-5">
        <div className="rounded-2xl bg-primary/10 p-3 text-primary"><Icon className="h-5 w-5"/></div>
        <div><p className="text-xs font-black uppercase tracking-wider text-muted-foreground">{title}</p><p
            className="mt-1 text-2xl font-black">{value}</p></div>
    </CardContent></Card>;
}

function Info({label, value}: { label: string; value: string }) {
    return <div className="rounded-2xl border bg-muted/25 p-4"><p
        className="text-[11px] font-black uppercase tracking-wider text-muted-foreground">{label}</p><p
        className="mt-1 font-bold">{value}</p></div>;
}

function Field({label, children}: { label: string; children: ReactNode }) {
    return <div className="space-y-2"><Label>{label}</Label>{children}</div>;
}

function numberFromRecord(record: Record<string, unknown>, key: string): number {
    const value = record[key];
    if (typeof value === "number") return Number.isFinite(value) ? value : 0;
    if (typeof value === "string") {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : 0;
    }
    return 0;
}

function textFromRecord(record: Record<string, unknown>, key: string): string {
    const value = record[key];
    return typeof value === "string" ? value : "";
}

function booleanFromRecord(record: Record<string, unknown>, key: string): boolean {
    return record[key] === true;
}
