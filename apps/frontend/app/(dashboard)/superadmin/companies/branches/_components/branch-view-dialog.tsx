"use client";

import {
    Building2,
    CalendarDays,
    Edit3,
    GitBranch,
    MapPin,
    Phone,
} from "lucide-react";

import {
    CustomDialog,
} from "@/components/ui/custom-dialog";

import type {
    BranchesPageModel,
} from "../_hooks/use-branches-page";

import {
    formatBranchDate,
} from "../_lib/branch-utils";

import {
    BranchStatusBadge,
} from "./branch-badges";

type Props =
    BranchesPageModel["viewDialog"];

function DetailCard({
    label,
    value,
}: {
    label: string;
    value?: string | null;
}) {
    return (
        <div className="rounded-2xl border bg-background p-4">
            <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
                {label}
            </p>

            <p className="mt-2 break-words font-black">
                {value || "Not available"}
            </p>
        </div>
    );
}

export function BranchViewDialog({
    branch,
    company,
    staffCount,
    activeStaffCount,
    onOpenChange,
    onEdit,
}: Props) {
    if (!branch) {
        return null;
    }

    return (
        <CustomDialog
            open
            onOpenChange={
                onOpenChange
            }
            title={branch.name}
            banner="/ithute-solutions-mark.png"
            contentClassName="sm:max-w-3xl"
        >
            <div className="space-y-6 px-5 py-6 sm:px-8">
                <div className="flex flex-col gap-4 rounded-2xl border bg-muted/20 p-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-center gap-3">
                        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
                            <GitBranch className="h-6 w-6" />
                        </div>

                        <div>
                            <p className="font-black">
                                {branch.name}
                            </p>

                            <p className="mt-1 text-sm text-muted-foreground">
                                {company?.name ??
                                    "Unknown company"}
                            </p>
                        </div>
                    </div>

                    <BranchStatusBadge
                        active={
                            branch.is_active
                        }
                    />
                </div>

                <section>
                    <div className="mb-3 flex items-center gap-2">
                        <Building2 className="h-5 w-5 text-primary" />

                        <h3 className="font-black">
                            Operations
                        </h3>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-3">
                        <DetailCard
                            label="Company"
                            value={
                                company?.name ??
                                "Unknown company"
                            }
                        />

                        <DetailCard
                            label="Assigned staff"
                            value={`${staffCount} staff member${
                                staffCount === 1
                                    ? ""
                                    : "s"
                            }`}
                        />

                        <DetailCard
                            label="Active staff"
                            value={`${activeStaffCount} active`}
                        />
                    </div>
                </section>

                <section>
                    <div className="mb-3 flex items-center gap-2">
                        <MapPin className="h-5 w-5 text-primary" />

                        <h3 className="font-black">
                            Location
                        </h3>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2">
                        <DetailCard
                            label="District"
                            value={
                                branch.district
                            }
                        />

                        <DetailCard
                            label="Town or village"
                            value={branch.town}
                        />

                        <div className="sm:col-span-2">
                            <DetailCard
                                label="Physical address"
                                value={
                                    branch.address
                                }
                            />
                        </div>
                    </div>
                </section>

                <section>
                    <div className="mb-3 flex items-center gap-2">
                        <Phone className="h-5 w-5 text-primary" />

                        <h3 className="font-black">
                            Contact
                        </h3>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2">
                        <DetailCard
                            label="Phone"
                            value={
                                branch.phone
                            }
                        />

                        <DetailCard
                            label="Email"
                            value={
                                branch.email
                            }
                        />
                    </div>
                </section>

                <section>
                    <div className="mb-3 flex items-center gap-2">
                        <CalendarDays className="h-5 w-5 text-primary" />

                        <h3 className="font-black">
                            Record information
                        </h3>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2">
                        <DetailCard
                            label="Created"
                            value={formatBranchDate(
                                branch.created_at,
                            )}
                        />

                        <DetailCard
                            label="Last updated"
                            value={formatBranchDate(
                                branch.updated_at,
                            )}
                        />
                    </div>
                </section>
            </div>

            <div className="flex justify-end border-t bg-muted/20 px-5 py-4 sm:px-8">
                <button
                    type="button"
                    onClick={() =>
                        onEdit(branch)
                    }
                    className="inline-flex h-11 items-center gap-2 rounded-xl bg-primary px-5 text-sm font-black text-primary-foreground shadow-sm transition hover:bg-primary/90"
                >
                    <Edit3 className="h-4 w-4" />
                    Edit branch
                </button>
            </div>
        </CustomDialog>
    );
}
