"use client";


import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { SuggestionSearch } from "@/components/ui/suggestion-search";
import { StickyFilterBar } from "@/components/ui/sticky-filter-bar";
import { Edit3, Plus, Search, Trash2, Users } from "lucide-react";

import { formatMoney } from "@/lib/format";
import type { SubscriptionPlan } from "@/types/billing";
import type { PlanActivityFilter, PlanVisibilityFilter } from "../_types/plan-page";
import {
    formatFeatureName,
    formatLimit,
    getAnnualSavings,
    getEnabledFeatures,
} from "../_lib/plan-utils";
import { PlanActivityBadge, PlanVisibilityBadge } from "./plan-badges";

type Props = {
    plans: SubscriptionPlan[];
    loading: boolean;
    search: string;
    activityFilter: PlanActivityFilter;
    visibilityFilter: PlanVisibilityFilter;
    subscriptionCounts: Map<string, number>;
    onSearchChange: (value: string) => void;
    onActivityFilterChange: (value: PlanActivityFilter) => void;
    onVisibilityFilterChange: (value: PlanVisibilityFilter) => void;
    onCreate: () => void;
    onEdit: (plan: SubscriptionPlan) => void;
    onDelete: (plan: SubscriptionPlan) => void;
};

export function PlansManagement({
    plans,
    loading,
    search,
    activityFilter,
    visibilityFilter,
    subscriptionCounts,
    onSearchChange,
    onActivityFilterChange,
    onVisibilityFilterChange,
    onCreate,
    onEdit,
    onDelete,
}: Props) {
    return (
        <section className="space-y-5">
            <div className="flex flex-col gap-4 rounded-3xl border bg-card p-5 shadow-sm lg:flex-row lg:items-center lg:justify-between">
                <div>
                    <h2 className="text-xl font-black">Manual plan configuration</h2>
                    <p className="mt-1 text-sm text-muted-foreground">Control pricing, fees, feature access, limits and availability without changing code.</p>
                </div>
                <button type="button" onClick={onCreate} className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-5 text-sm font-bold text-primary-foreground hover:bg-primary/90">
                    <Plus className="h-4 w-4" />
                    Create plan
                </button>
            </div>

            <StickyFilterBar
                ariaLabel="Subscription plan search and filters"
                className="rounded-3xl data-[floating=true]:border"
            >
            <div className="grid gap-3 rounded-[inherit] border bg-card/95 p-5 shadow-sm backdrop-blur md:grid-cols-[1fr_220px_220px]">
                <SuggestionSearch
                    value={search}
                    onValueChange={onSearchChange}
                    suggestions={plans.map((plan) => ({
                        value: plan.name,
                        label: plan.name,
                        description: `${plan.code} · ${formatMoney(plan.monthly_price)}/month`,
                        keywords: [plan.id, plan.code, plan.description ?? "", plan.is_active ? "active" : "inactive", plan.is_public ? "public" : "private"],
                    }))}
                    placeholder="Type a plan name, code or description..."
                    suggestionLabel="Subscription plans"
                    emptyMessage="No plan matches that text."
                />
                <NativeSelect value={activityFilter} onChange={(event) => onActivityFilterChange(event.target.value as PlanActivityFilter)} className="h-11 rounded-xl border bg-background px-3 text-sm font-semibold">
                    <option value="all">All activity</option>
                    <option value="active">Active only</option>
                    <option value="inactive">Inactive only</option>
                </NativeSelect>
                <NativeSelect value={visibilityFilter} onChange={(event) => onVisibilityFilterChange(event.target.value as PlanVisibilityFilter)} className="h-11 rounded-xl border bg-background px-3 text-sm font-semibold">
                    <option value="all">All visibility</option>
                    <option value="public">Public only</option>
                    <option value="private">Private only</option>
                </NativeSelect>
            </div>
            </StickyFilterBar>

            {loading && plans.length === 0 ? (
                <div className="grid gap-5 lg:grid-cols-2 2xl:grid-cols-3">
                    {Array.from({ length: 3 }).map((_, index) => <div key={index} className="h-96 animate-pulse rounded-3xl border bg-muted" />)}
                </div>
            ) : plans.length === 0 ? (
                <div className="rounded-3xl border bg-card px-6 py-16 text-center shadow-sm">
                    <SparkleEmpty />
                    <h3 className="mt-4 text-lg font-black">No plans found</h3>
                    <p className="mt-1 text-sm text-muted-foreground">Create a plan or change the current filters.</p>
                </div>
            ) : (
                <div className="grid gap-5 lg:grid-cols-2 2xl:grid-cols-3">
                    {plans.map((plan) => {
                        const enabledFeatures = getEnabledFeatures(plan);
                        const annualSavings = getAnnualSavings(plan);
                        const subscriptions = subscriptionCounts.get(plan.id) ?? 0;
                        return (
                            <article key={plan.id} className="flex flex-col overflow-hidden rounded-3xl border bg-card shadow-sm transition hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-lg">
                                <div className="border-b p-5">
                                    <div className="flex items-start justify-between gap-4">
                                        <div>
                                            <h3 className="text-xl font-black">{plan.name}</h3>
                                            <p className="mt-1 text-xs font-black uppercase tracking-[0.18em] text-primary">{plan.code}</p>
                                        </div>
                                        <div className="flex flex-col items-end gap-2">
                                            <PlanActivityBadge active={plan.is_active} />
                                            <PlanVisibilityBadge isPublic={plan.is_public} />
                                        </div>
                                    </div>
                                    <p className="mt-4 min-h-12 text-sm leading-6 text-muted-foreground">{plan.description || "No plan description has been provided."}</p>
                                </div>

                                <div className="grid grid-cols-2 gap-3 p-5">
                                    <PriceBox label="Monthly" value={formatMoney(plan.monthly_price)} />
                                    <PriceBox label="Annual" value={formatMoney(plan.annual_price)} note={annualSavings > 0 ? `Save ${formatMoney(annualSavings)}` : undefined} />
                                    <PriceBox label="Unlock fee" value={formatMoney(plan.marketplace_unlock_fee)} />
                                    <PriceBox label="Transaction fee" value={`${Number(plan.transaction_fee_percent).toFixed(3)}%`} />
                                </div>

                                <div className="space-y-4 border-t p-5">
                                    <div>
                                        <p className="text-xs font-black uppercase tracking-wide text-muted-foreground">Resource limits</p>
                                        <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                                            <LimitBox label="Branches" value={formatLimit(plan.limits?.branches)} />
                                            <LimitBox label="Staff" value={formatLimit(plan.limits?.staff)} />
                                            <LimitBox label="Products" value={formatLimit(plan.limits?.products)} />
                                        </div>
                                    </div>

                                    <div>
                                        <p className="text-xs font-black uppercase tracking-wide text-muted-foreground">Enabled features</p>
                                        <div className="mt-3 flex flex-wrap gap-2">
                                            {enabledFeatures.length > 0 ? enabledFeatures.slice(0, 6).map((feature) => (
                                                <span key={feature} className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-bold text-primary">{formatFeatureName(feature)}</span>
                                            )) : <span className="text-xs text-muted-foreground">No feature switches enabled</span>}
                                        </div>
                                    </div>
                                </div>

                                <div className="mt-auto flex items-center justify-between gap-3 border-t bg-muted/20 p-5">
                                    <div className="inline-flex items-center gap-2 text-sm font-bold text-muted-foreground">
                                        <Users className="h-4 w-4" />
                                        {subscriptions} subscription{subscriptions === 1 ? "" : "s"}
                                    </div>
                                    <div className="flex gap-2">
                                        <button type="button" onClick={() => onEdit(plan)} className="inline-flex h-9 items-center gap-2 rounded-xl border bg-background px-3 text-sm font-bold hover:border-primary hover:text-primary">
                                            <Edit3 className="h-4 w-4" /> Edit
                                        </button>
                                        <button type="button" onClick={() => onDelete(plan)} className="inline-flex h-9 items-center gap-2 rounded-xl border border-red-200 bg-background px-3 text-sm font-bold text-red-600 hover:bg-red-50 dark:border-red-900 dark:hover:bg-red-950/30">
                                            <Trash2 className="h-4 w-4" />
                                            <span className="sr-only sm:not-sr-only">Delete</span>
                                        </button>
                                    </div>
                                </div>
                            </article>
                        );
                    })}
                </div>
            )}
        </section>
    );
}

function PriceBox({ label, value, note }: { label: string; value: string; note?: string }) {
    return <div className="rounded-2xl bg-muted/50 p-3"><p className="text-xs font-bold text-muted-foreground">{label}</p><p className="mt-1 font-black">{value}</p>{note && <p className="mt-1 text-[11px] font-bold text-green-600">{note}</p>}</div>;
}

function LimitBox({ label, value }: { label: string; value: string }) {
    return <div className="rounded-xl border bg-background p-2"><p className="text-[11px] font-bold text-muted-foreground">{label}</p><p className="mt-1 text-sm font-black">{value}</p></div>;
}

function SparkleEmpty() {
    return <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-primary"><Plus className="h-7 w-7" /></div>;
}
