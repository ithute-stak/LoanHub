"use client";

import { LoanRequest } from "@/types/loanRequest";
import { WalletCards, Layers, Clock } from "lucide-react";

interface AnalyticsOverviewProps {
    data: LoanRequest[];
}

export default function AnalyticsOverview({ data }: AnalyticsOverviewProps) {
    const totalVolume = data.reduce((sum, item) => sum + (item.requested_amount || 0), 0);
    const activeCount = data.filter((item) => item.status === "open").length;

    const itemsWithTerms = data.filter((item) => item.preferred_term_months);
    const avgTerm = itemsWithTerms.length
        ? Math.round(itemsWithTerms.reduce((sum, item) => sum + (item.preferred_term_months || 0), 0) / itemsWithTerms.length)
        : 0;

    return (
        <div className="grid gap-4 md:grid-cols-3">
            <div className="flex items-center gap-4 rounded-2xl border border-border bg-card p-5 shadow-sm">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
                    <WalletCards className="h-6 w-6" />
                </div>
                <div>
                    <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Portfolio Volume</p>
                    <h3 className="text-xl font-black mt-0.5 text-foreground">
                        M{totalVolume.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </h3>
                </div>
            </div>

            <div className="flex items-center gap-4 rounded-2xl border border-border bg-card p-5 shadow-sm">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-500">
                    <Layers className="h-6 w-6" />
                </div>
                <div>
                    <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Active Open Requests</p>
                    <h3 className="text-xl font-black mt-0.5 text-foreground">{activeCount} Requests</h3>
                </div>
            </div>

            <div className="flex items-center gap-4 rounded-2xl border border-border bg-card p-5 shadow-sm">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-500/10 text-blue-500">
                    <Clock className="h-6 w-6" />
                </div>
                <div>
                    <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Avg Preferred Term</p>
                    <h3 className="text-xl font-black mt-0.5 text-foreground">{avgTerm} Months</h3>
                </div>
            </div>
        </div>
    );
}