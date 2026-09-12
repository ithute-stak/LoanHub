import { Banknote, CreditCard, Eye, Percent, Sparkles, Unlock } from "lucide-react";

import { MetricCard } from "@/components/portal/metric-card";
import { formatMoney } from "@/lib/format";
import type { PlanPageStats } from "../_types/plan-page";

export function PlansOverview({ stats }: { stats: PlanPageStats }) {
    return (
        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard title="Configured plans" value={stats.totalPlans.toLocaleString()} description={`${stats.activePlans} active plan configurations`} icon={Sparkles} />
            <MetricCard title="Public plans" value={stats.publicPlans.toLocaleString()} description="Visible on company subscription pages" icon={Eye} />
            <MetricCard title="Active subscriptions" value={stats.activeSubscriptions.toLocaleString()} description={formatMoney(stats.subscriptionValue) + " in active subscription records"} icon={CreditCard} />
            <MetricCard title="Average platform fee" value={`${stats.averageTransactionFee.toFixed(3)}%`} description={`${stats.payPerUnlockPlans} plans charge per marketplace unlock`} icon={Percent} />
            <MetricCard title="Free plans" value={stats.freePlans.toLocaleString()} description="No monthly or annual subscription charge" icon={Banknote} />
            <MetricCard title="Pay-per-unlock plans" value={stats.payPerUnlockPlans.toLocaleString()} description="Marketplace access is billed per request" icon={Unlock} />
        </section>
    );
}
