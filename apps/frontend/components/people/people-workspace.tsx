"use client";

import {
    BadgeCheck,
    BriefcaseBusiness,
    Building2,
    ShieldCheck,
    UserRoundCog,
    Users,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { EmployeeManagementPage } from "@/components/employees/employee-management-page";
import { StaffAccessPanel } from "@/components/people/staff-access-panel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAppData } from "@/provider/appDataProvider";
import { useTenant } from "@/provider/tenantProvider";
import {
    COMPANY_MANAGEMENT_ROLES,
    HR_ROLES,
    hasRole,
} from "@/types/auth";

type PeopleTab = "access" | "employees";

export function PeopleWorkspace() {
    const params = useSearchParams();
    const { activeRole } = useTenant();
    const { companyStaff, activeStaffCount, branches } = useAppData();

    const canManageAccess = hasRole(activeRole, COMPANY_MANAGEMENT_ROLES);
    const canManageEmployees = hasRole(activeRole, HR_ROLES);
    const requestedTab = params.get("tab");

    const preferredTab = useMemo<PeopleTab>(() => {
        if (requestedTab === "employees" && canManageEmployees) return "employees";
        if (requestedTab === "access" && canManageAccess) return "access";
        if (canManageAccess) return "access";
        return "employees";
    }, [canManageAccess, canManageEmployees, requestedTab]);

    const [tab, setTab] = useState<PeopleTab>(preferredTab);

    useEffect(() => {
        setTab(preferredTab);
    }, [preferredTab]);

    const uniquePeople = new Set(companyStaff.map((staff) => staff.user_id)).size;
    const multiRolePeople = useMemo(() => {
        const counts = new Map<string, number>();
        for (const staff of companyStaff) {
            counts.set(staff.user_id, (counts.get(staff.user_id) ?? 0) + 1);
        }
        return Array.from(counts.values()).filter((count) => count > 1).length;
    }, [companyStaff]);

    return (
        <main className="space-y-6">
            <section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8">
                <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-primary/10 blur-3xl" />
                <div className="relative">
                    <div className="flex items-center gap-2 text-primary">
                        <Users className="h-5 w-5" />
                        <span className="text-xs font-black uppercase tracking-[0.16em]">Workforce and access control</span>
                    </div>
                    <h1 className="mt-2 text-3xl font-black tracking-tight">People & staff</h1>
                    <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                        Manage one person across multiple roles, branch access, employment records, reporting lines, goals and reviews from one coordinated workspace.
                    </p>
                </div>
            </section>

            <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <PeopleMetric icon={Users} label="Unique people" value={uniquePeople.toLocaleString()} note="Distinct users assigned to the company" />
                <PeopleMetric icon={UserRoundCog} label="Active memberships" value={activeStaffCount.toLocaleString()} note="Active role assignments across the company" />
                <PeopleMetric icon={BadgeCheck} label="Multiple-role users" value={multiRolePeople.toLocaleString()} note="People who can switch between assigned roles" />
                <PeopleMetric icon={Building2} label="Branches" value={branches.length.toLocaleString()} note="Operational locations available for assignment" />
            </section>

            <Tabs value={tab} onValueChange={(value) => setTab(value as PeopleTab)} className="space-y-5">
                <TabsList className="h-auto w-full flex-wrap justify-start rounded-2xl border bg-card p-1.5">
                    {canManageAccess && (
                        <TabsTrigger value="access" className="min-w-44 rounded-xl px-4 py-2.5">
                            <ShieldCheck className="h-4 w-4" /> Access & roles
                        </TabsTrigger>
                    )}
                    {canManageEmployees && (
                        <TabsTrigger value="employees" className="min-w-44 rounded-xl px-4 py-2.5">
                            <BriefcaseBusiness className="h-4 w-4" /> Employee records
                        </TabsTrigger>
                    )}
                </TabsList>

                {canManageAccess && (
                    <TabsContent value="access">
                        <StaffAccessPanel embedded />
                    </TabsContent>
                )}

                {canManageEmployees && (
                    <TabsContent value="employees">
                        <EmployeeManagementPage embedded />
                    </TabsContent>
                )}
            </Tabs>
        </main>
    );
}

function PeopleMetric({
    icon: Icon,
    label,
    value,
    note,
}: {
    icon: typeof Users;
    label: string;
    value: string;
    note: string;
}) {
    return (
        <article className="rounded-3xl border bg-card p-5 shadow-sm">
            <div className="flex items-start justify-between gap-4">
                <div>
                    <p className="text-xs font-black uppercase tracking-[0.12em] text-muted-foreground">{label}</p>
                    <p className="mt-2 text-2xl font-black">{value}</p>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">{note}</p>
                </div>
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                    <Icon className="h-5 w-5" />
                </div>
            </div>
        </article>
    );
}
