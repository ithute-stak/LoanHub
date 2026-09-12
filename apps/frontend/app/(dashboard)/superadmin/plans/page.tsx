"use client";

import { AlertCircle, RefreshCcw, ShieldCheck } from "lucide-react";

import { PlanDeleteDialog } from "./_components/plan-delete-dialog";
import { PlanEditorDialog } from "./_components/plan-editor-dialog";
import { PlansManagement } from "./_components/plans-management";
import { PlansOverview } from "./_components/plans-overview";
import { usePlansPage } from "./_hooks/use-plans-page";

export default function PlatformPlansPage() {
    const page = usePlansPage();
    const deletingPlanCount = page.planToDelete
        ? page.subscriptionCounts.get(page.planToDelete.id) ?? 0
        : 0;

    return (
        <main className="space-y-6">
            <section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8">
                <div className="absolute -right-28 -top-28 h-72 w-72 rounded-full bg-primary/10 blur-3xl" />
                <div className="relative flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <div className="inline-flex items-center gap-2 rounded-full border bg-background px-4 py-2 text-xs font-black text-muted-foreground">
                            <ShieldCheck className="h-4 w-4 text-primary" />
                            Platform owner configuration
                        </div>
                        <h1 className="mt-5 text-3xl font-black tracking-tight md:text-4xl">Pricing and subscription plans</h1>
                        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground md:text-base">
                            Manually control LoanHub subscription prices, marketplace unlock charges, transaction fees, tenant limits, feature access and plan visibility.
                        </p>
                    </div>
                    <button
                        type="button"
                        onClick={() => void page.refreshBilling()}
                        disabled={page.loading}
                        className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border bg-background px-4 text-sm font-bold hover:border-primary hover:text-primary disabled:opacity-50"
                    >
                        <RefreshCcw className={`h-4 w-4 ${page.loading ? "animate-spin" : ""}`} />
                        Refresh billing
                    </button>
                </div>
            </section>

            {page.error && (
                <section className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">
                    <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
                    <div>
                        <p className="font-black">Billing configuration could not be loaded</p>
                        <p className="mt-1 text-sm">{page.error}</p>
                    </div>
                </section>
            )}

            <PlansOverview stats={page.stats} />

            <PlansManagement
                plans={page.plans}
                loading={page.loading}
                search={page.search}
                activityFilter={page.activityFilter}
                visibilityFilter={page.visibilityFilter}
                subscriptionCounts={page.subscriptionCounts}
                onSearchChange={page.setSearch}
                onActivityFilterChange={page.setActivityFilter}
                onVisibilityFilterChange={page.setVisibilityFilter}
                onCreate={page.openCreate}
                onEdit={page.openEdit}
                onDelete={page.setPlanToDelete}
            />

            <PlanEditorDialog
                open={Boolean(page.editor)}
                mode={page.editor?.mode ?? "create"}
                plan={page.editor?.plan ?? null}
                saving={page.saving}
                onOpenChange={(open) => {
                    if (!open) page.closeEditor();
                }}
                onSubmit={page.submitPlan}
            />

            <PlanDeleteDialog
                plan={page.planToDelete}
                subscriptionCount={deletingPlanCount}
                deleting={page.deleting}
                onOpenChange={(open) => {
                    if (!open && !page.deleting) page.setPlanToDelete(null);
                }}
                onConfirm={page.confirmDelete}
            />
        </main>
    );
}
