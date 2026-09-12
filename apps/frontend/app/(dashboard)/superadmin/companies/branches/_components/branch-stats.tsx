import {
    Activity,
    Building2,
    BuildingIcon,
    GitBranch,
    MapPin,
    UserRoundCheck,
    UserRoundX,
    Users,
    type LucideIcon,
} from "lucide-react";

import type {
    BranchPageStats,
} from "../_types/branch-page";

import {
    formatPercentage,
} from "../_lib/branch-utils";

type MetricCardProps = {
    title: string;
    value: string;
    description: string;
    icon: LucideIcon;
};

function MetricCard({
    title,
    value,
    description,
    icon: Icon,
}: MetricCardProps) {
    return (
        <article className="group rounded-3xl border bg-card p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-lg">
            <div className="flex items-start justify-between gap-4">
                <div>
                    <p className="text-sm font-semibold text-muted-foreground">
                        {title}
                    </p>

                    <p className="mt-3 text-3xl font-black tracking-tight">
                        {value}
                    </p>

                    <p className="mt-2 text-xs leading-5 text-muted-foreground">
                        {description}
                    </p>
                </div>

                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary transition group-hover:scale-105">
                    <Icon className="h-6 w-6" />
                </div>
            </div>
        </article>
    );
}

export function BranchStats({
    stats,
}: {
    stats: BranchPageStats;
}) {
    return (
        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard
                title="Registered branches"
                value={stats.totalBranches.toLocaleString()}
                description={`${stats.newBranchesLast30Days} added during the last 30 days`}
                icon={GitBranch}
            />

            <MetricCard
                title="Active branches"
                value={stats.activeBranches.toLocaleString()}
                description={`${formatPercentage(
                    stats.activeRate,
                )} of all branches are operational`}
                icon={Activity}
            />

            <MetricCard
                title="Inactive branches"
                value={stats.inactiveBranches.toLocaleString()}
                description="Branches currently unavailable for operations"
                icon={BuildingIcon}
            />

            <MetricCard
                title="Companies represented"
                value={stats.companiesWithBranches.toLocaleString()}
                description={`${stats.companiesWithoutBranches} companies do not have a branch`}
                icon={Building2}
            />

            <MetricCard
                title="Districts covered"
                value={stats.districtsCovered.toLocaleString()}
                description="Geographic branch coverage across Lesotho"
                icon={MapPin}
            />

            <MetricCard
                title="Assigned staff"
                value={stats.assignedStaff.toLocaleString()}
                description={`${stats.averageStaffPerBranch.toFixed(
                    1,
                )} staff members per branch`}
                icon={Users}
            />

            <MetricCard
                title="Branches with staff"
                value={stats.branchesWithStaff.toLocaleString()}
                description="Branches with at least one assigned staff member"
                icon={UserRoundCheck}
            />

            <MetricCard
                title="Branches without staff"
                value={stats.branchesWithoutStaff.toLocaleString()}
                description={`${stats.averageBranchesPerCompany.toFixed(
                    1,
                )} branches per represented company`}
                icon={UserRoundX}
            />
        </section>
    );
}
