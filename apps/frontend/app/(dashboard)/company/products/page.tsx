"use client";


import { Input } from "@/components/ui/input";
import {
    Boxes,
    CheckCircle2,
    Edit3,
    Loader2,
    MoreHorizontal,
    PackagePlus,
    Power,
    PowerOff,
    Search,
    Trash2,
} from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "@/utils/toast";

import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ErrorPanel } from "@/components/portal/error-panel";
import { LoanProductDialog } from "@/components/loans/loan-product-dialog";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { LoadingPanel } from "@/components/portal/loading-panel";
import { SuggestionSearch } from "@/components/ui/suggestion-search";
import { StickyFilterBar } from "@/components/ui/sticky-filter-bar";
import { MetricCard } from "@/components/portal/metric-card";
import { formatMoney } from "@/lib/format";
import { interestMethodLabel } from "@/lib/interest-methods";
import { useAppData } from "@/provider/appDataProvider";
import type { LoanProduct } from "@/types/loanProduct";
import { getErrorMessage } from "@/utils/apiError";

export default function CompanyLoanProductsPage() {
    const {
        loanProducts,
        loanProductsCount,
        activeLoanProductsCount,
        isLoanProductsLoading,
        errors,
        setLoanProductActive,
        deleteLoanProduct,
        refreshAllData,
    } = useAppData();

    const [search, setSearch] = useState("");
    const [dialogOpen, setDialogOpen] = useState(false);
    const [editing, setEditing] = useState<LoanProduct | null>(null);
    const [workingId, setWorkingId] = useState<string | null>(null);
    const [deleteTarget, setDeleteTarget] = useState<LoanProduct | null>(null);

    const filteredProducts = useMemo(() => {
        const term = search.trim().toLowerCase();
        if (!term) return loanProducts;
        return loanProducts.filter((product) =>
            [product.name, product.description]
                .filter(Boolean)
                .some((value) => String(value).toLowerCase().includes(term)),
        );
    }, [loanProducts, search]);

    const averageRate = useMemo(() => {
        if (!loanProducts.length) return 0;
        return (
            loanProducts.reduce(
                (total, product) => total + Number(product.interest_rate_percent || 0),
                0,
            ) / loanProducts.length
        );
    }, [loanProducts]);

    function openCreate() {
        setEditing(null);
        setDialogOpen(true);
    }

    function openEdit(product: LoanProduct) {
        setEditing(product);
        setDialogOpen(true);
    }

    async function toggleProduct(product: LoanProduct) {
        setWorkingId(product.id);
        try {
            await setLoanProductActive(product.id, !product.is_active);
            toast.success(product.is_active ? "Product deactivated" : "Product activated");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Product status could not be changed"));
        } finally {
            setWorkingId(null);
        }
    }

    async function removeProduct() {
        if (!deleteTarget) return;
        setWorkingId(deleteTarget.id);
        try {
            await deleteLoanProduct(deleteTarget.id);
            toast.success("Loan product deleted");
            setDeleteTarget(null);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Product could not be deleted"));
        } finally {
            setWorkingId(null);
        }
    }

    if (isLoanProductsLoading && loanProducts.length === 0) {
        return <LoadingPanel label="Loading loan products" />;
    }

    return (
        <div className="space-y-6">
            <section className="flex flex-col gap-4 rounded-3xl border bg-card p-6 shadow-sm sm:flex-row sm:items-end sm:justify-between">
                <div>
                    <p className="text-xs font-black uppercase tracking-[0.2em] text-primary">
                        Company configuration
                    </p>
                    <h1 className="mt-2 text-3xl font-black tracking-tight">Loan products</h1>
                    <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
                        Define the lending ranges, terms, rates and fees that your teams can offer.
                    </p>
                </div>
                <Button type="button" onClick={openCreate}>
                    <PackagePlus className="h-4 w-4" />
                    New product
                </Button>
            </section>

            {errors.loanProducts && (
                <ErrorPanel
                    message={errors.loanProducts}
                    onRetry={() => void refreshAllData()}
                />
            )}

            <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <MetricCard title="Products" value={loanProductsCount.toLocaleString()} description="Configured lending products" icon={Boxes} />
                <MetricCard title="Active" value={activeLoanProductsCount.toLocaleString()} description="Available to lending teams" icon={CheckCircle2} />
                <MetricCard title="Average rate" value={`${averageRate.toFixed(2)}%`} description="Across all configured products" icon={Power} />
                <MetricCard title="Inactive" value={(loanProductsCount - activeLoanProductsCount).toLocaleString()} description="Hidden from new offers" icon={PowerOff} />
            </section>

            <section className="overflow-visible rounded-3xl border bg-card shadow-sm">
                <StickyFilterBar
                    ariaLabel="Loan product search"
                    className="rounded-t-3xl data-[floating=true]:rounded-2xl data-[floating=true]:border"
                >
                    <div className="rounded-[inherit] border-b bg-card p-5">
                        <SuggestionSearch
                            value={search}
                            onValueChange={setSearch}
                            suggestions={loanProducts.map((product) => ({
                                value: product.name,
                                label: product.name,
                                description: `${formatMoney(product.min_amount)}–${formatMoney(product.max_amount)} · ${interestMethodLabel(product.interest_method)}`,
                                keywords: [product.id, product.description ?? "", product.is_active ? "active" : "inactive"],
                            }))}
                            placeholder="Type a product name, method or status..."
                            suggestionLabel="Loan products"
                            emptyMessage="No loan product matches that text."
                            wrapperClassName="max-w-xl"
                        />
                    </div>
                </StickyFilterBar>

                <div className="grid gap-4 overflow-hidden rounded-b-3xl p-5 md:grid-cols-2 2xl:grid-cols-3">
                    {filteredProducts.map((product) => (
                        <article key={product.id} className="rounded-3xl border p-5 transition hover:border-primary/30 hover:shadow-md">
                            <div className="flex items-start justify-between gap-4">
                                <div>
                                    <div className="flex flex-wrap items-center gap-2">
                                        <h2 className="text-lg font-black">{product.name}</h2>
                                        <span className={`rounded-full px-2.5 py-1 text-[11px] font-black ${product.is_active ? "bg-green-100 text-green-700 dark:bg-green-950/40 dark:text-green-400" : "bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-400"}`}>
                                            {product.is_active ? "Active" : "Inactive"}
                                        </span>
                                    </div>
                                    <p className="mt-2 line-clamp-2 text-sm leading-6 text-muted-foreground">
                                        {product.description || "No product description supplied."}
                                    </p>
                                </div>

                                {workingId === product.id ? (
                                    <Loader2 className="h-5 w-5 animate-spin text-primary" />
                                ) : (
                                    <DropdownMenu>
                                        <DropdownMenuTrigger asChild>
                                            <Button type="button" variant="outline" size="icon-sm">
                                                <MoreHorizontal className="h-4 w-4" />
                                                <span className="sr-only">Product actions</span>
                                            </Button>
                                        </DropdownMenuTrigger>
                                        <DropdownMenuContent align="end">
                                            <DropdownMenuItem onClick={() => openEdit(product)}>
                                                <Edit3 className="mr-2 h-4 w-4" /> Edit
                                            </DropdownMenuItem>
                                            <DropdownMenuItem onClick={() => void toggleProduct(product)}>
                                                {product.is_active ? <PowerOff className="mr-2 h-4 w-4" /> : <Power className="mr-2 h-4 w-4" />}
                                                {product.is_active ? "Deactivate" : "Activate"}
                                            </DropdownMenuItem>
                                            <DropdownMenuSeparator />
                                            <DropdownMenuItem onClick={() => setDeleteTarget(product)} className="text-red-600">
                                                <Trash2 className="mr-2 h-4 w-4" /> Delete
                                            </DropdownMenuItem>
                                        </DropdownMenuContent>
                                    </DropdownMenu>
                                )}
                            </div>

                            <div className="mt-5 grid grid-cols-2 gap-3 text-sm lg:grid-cols-3">
                                <Data label="Amount" value={`${formatMoney(product.min_amount)} – ${formatMoney(product.max_amount)}`} />
                                <Data label="Term" value={`${product.min_term_months} – ${product.max_term_months} months`} />
                                <Data label="Method" value={interestMethodLabel(product.interest_method)} />
                                <Data label="Rate" value={`${Number(product.interest_rate_percent).toFixed(3)}%${product.interest_method === "micro_loan" ? " per cycle" : " p.a."}`} />
                                <Data label="Processing fee" value={formatMoney(product.processing_fee)} />
                            </div>
                        </article>
                    ))}

                    {filteredProducts.length === 0 && (
                        <div className="col-span-full py-16 text-center">
                            <Boxes className="mx-auto h-10 w-10 text-muted-foreground" />
                            <h2 className="mt-4 font-black">No loan products found</h2>
                            <p className="mt-1 text-sm text-muted-foreground">Create a product or change your search.</p>
                        </div>
                    )}
                </div>
            </section>

            <LoanProductDialog
                open={dialogOpen}
                onOpenChange={(open) => {
                    setDialogOpen(open);
                    if (!open) setEditing(null);
                }}
                product={editing}
                onSaved={async () => {
                    await refreshAllData();
                }}
            />
            <ConfirmDialog
                open={Boolean(deleteTarget)}
                onOpenChange={(open) => !open && workingId === null && setDeleteTarget(null)}
                title="Delete loan product?"
                description={`Delete ${deleteTarget?.name ?? "this loan product"}? This action cannot be undone.`}
                confirmLabel="Delete product"
                destructive
                loading={workingId === deleteTarget?.id}
                onConfirm={removeProduct}
            />
        </div>
    );
}

function Data({ label, value }: { label: string; value: string }) {
    return <div className="rounded-2xl bg-muted/60 p-3"><p className="text-[11px] font-black uppercase text-muted-foreground">{label}</p><p className="mt-1 font-bold">{value}</p></div>;
}
