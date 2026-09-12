"use client";

import {
    Building2,
    Download,
    Plus,
    RefreshCcw,
    ShieldCheck,
} from "lucide-react";

import type {
    BranchesPageModel,
} from "../_hooks/use-branches-page";

type Props =
    BranchesPageModel["header"];

export function BranchesHeader({
    totalBranches,
    isLoading,
    onRefresh,
    onExport,
    onCreate,
}: Props) {
    return (
        <section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8">
            <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-primary/10 blur-3xl" />
            <div className="absolute -bottom-32 -left-24 h-72 w-72 rounded-full bg-primary/5 blur-3xl" />

            <div className="relative flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
                <div>
                    <div className="inline-flex items-center gap-2 rounded-full border bg-background/80 px-4 py-2 text-xs font-black text-muted-foreground shadow-sm backdrop-blur">
                        <ShieldCheck className="h-4 w-4 text-primary" />
                        Super administrator
                    </div>

                    <div className="mt-5 flex items-start gap-4">
                        <div className="hidden h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg sm:flex">
                            <Building2 className="h-7 w-7" />
                        </div>

                        <div>
                            <h1 className="text-3xl font-black tracking-tight md:text-4xl">
                                Branch management
                            </h1>

                            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground md:text-base">
                                Create, monitor and manage every
                                lending-company branch, its activity,
                                location and assigned staff.
                            </p>

                            <p className="mt-3 text-xs font-bold text-primary">
                                {totalBranches.toLocaleString()} branch
                                {totalBranches === 1 ? "" : "es"} registered
                            </p>
                        </div>
                    </div>
                </div>

                <div className="flex flex-wrap gap-3">
                    <button
                        type="button"
                        onClick={onExport}
                        disabled={totalBranches === 0}
                        className="inline-flex h-11 items-center gap-2 rounded-xl border bg-background px-4 text-sm font-bold transition hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        <Download className="h-4 w-4" />
                        Export CSV
                    </button>

                    <button
                        type="button"
                        onClick={onRefresh}
                        disabled={isLoading}
                        className="inline-flex h-11 items-center gap-2 rounded-xl border bg-background px-4 text-sm font-bold transition hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        <RefreshCcw
                            className={`h-4 w-4 ${
                                isLoading
                                    ? "animate-spin"
                                    : ""
                            }`}
                        />
                        Refresh
                    </button>

                    <button
                        type="button"
                        onClick={onCreate}
                        className="inline-flex h-11 items-center gap-2 rounded-xl bg-primary px-5 text-sm font-black text-primary-foreground shadow-lg transition hover:-translate-y-0.5 hover:bg-primary/90"
                    >
                        <Plus className="h-4 w-4" />
                        Add branch
                    </button>
                </div>
            </div>
        </section>
    );
}
