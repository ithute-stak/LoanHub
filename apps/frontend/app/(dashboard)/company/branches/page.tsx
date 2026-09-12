"use client";


import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import {FormEvent, useMemo, useState} from "react";
import {Building2, GitBranch, Loader2, MapPin, Plus, Power, PowerOff, Search} from "lucide-react";
import {toast} from "@/utils/toast";

import {branchApi} from "@/api/branch";
import {MetricCard} from "@/components/portal/metric-card";
import {StatusBadge} from "@/components/portal/status-badge";
import {useAppData} from "@/provider/appDataProvider";
import {useTenant} from "@/provider/tenantProvider";
import {COMPANY_MANAGEMENT_ROLES, hasRole} from "@/types/auth";
import {getErrorMessage} from "@/utils/apiError";
import { CustomDialog } from "@/components/ui/custom-dialog";
import { SuggestionSearch } from "@/components/ui/suggestion-search";
import { StickyFilterBar } from "@/components/ui/sticky-filter-bar";

export default function CompanyBranchesPage() {
    const {branches, currentCompany, companyStaff, refreshAllData} = useAppData();
    const {activeRole} = useTenant();
    const [search, setSearch] = useState("");
    const [showForm, setShowForm] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [form, setForm] = useState({name: "", district: "", town: "", address: "", phone: "", email: "", is_headquarters: false});
    const canManage = hasRole(activeRole, COMPANY_MANAGEMENT_ROLES);

    const filtered = useMemo(() => {
        const query = search.trim().toLowerCase();
        return branches.filter((branch) => !query || [branch.name, branch.district, branch.town, branch.address].some((value) => String(value ?? "").toLowerCase().includes(query)));
    }, [branches, search]);

    async function createBranch(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!currentCompany) return;
        setSubmitting(true);
        try {
            await branchApi.create({company_id: currentCompany.id, ...form, is_active: true});
            toast.success("Branch created successfully");
            setForm({name: "", district: "", town: "", address: "", phone: "", email: "", is_headquarters: false});
            setShowForm(false);
            await refreshAllData();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not create the branch"));
        } finally {
            setSubmitting(false);
        }
    }

    async function toggleBranch(id: string, active: boolean) {
        try {
            if (active) await branchApi.deactivate(id); else await branchApi.activate(id);
            toast.success(active ? "Branch deactivated" : "Branch activated");
            await refreshAllData();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not update branch status"));
        }
    }

    return (
        <div className="space-y-6">
            <section
                className="flex flex-col gap-5 rounded-3xl border bg-card p-6 shadow-sm md:flex-row md:items-end md:justify-between md:p-8">
                <div><h1 className="text-3xl font-black">Company branches</h1><p
                    className="mt-2 text-sm text-muted-foreground">Control locations, contact channels, branch status
                    and staff coverage.</p></div>
                {canManage && <button type="button" onClick={() => setShowForm(true)}
                                      className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground">
                    <Plus className="h-4 w-4"/>Add branch</button>}
            </section>

            <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <MetricCard title="Branches" value={branches.length.toLocaleString()}
                            description="All company service locations" icon={GitBranch}/>
                <MetricCard title="Active" value={branches.filter((branch) => branch.is_active).length.toLocaleString()}
                            description="Branches currently operating" icon={Power}/>
                <MetricCard title="Districts"
                            value={new Set(branches.map((branch) => branch.district)).size.toLocaleString()}
                            description="Regional business coverage" icon={MapPin}/>
                <MetricCard title="Assigned staff"
                            value={companyStaff.filter((staff) => staff.branch_id).length.toLocaleString()}
                            description="Staff linked to a branch" icon={Building2}/>
            </section>

            <section className="overflow-visible rounded-3xl border bg-card shadow-sm">
                <StickyFilterBar
                    ariaLabel="Branch directory search"
                    className="rounded-t-3xl data-[floating=true]:rounded-2xl data-[floating=true]:border"
                >
                    <div className="rounded-[inherit] border-b bg-card p-5">
                        <SuggestionSearch
                            value={search}
                            onValueChange={setSearch}
                            suggestions={branches.map((branch) => ({
                                value: branch.name,
                                label: branch.name,
                                description: [branch.district, branch.town].filter(Boolean).join(" · "),
                                keywords: [branch.id, branch.address ?? "", branch.phone ?? "", branch.email ?? ""],
                            }))}
                            placeholder="Type a branch, district, town or contact..."
                            suggestionLabel="Branches"
                            emptyMessage="No branch matches that text."
                        />
                    </div>
                </StickyFilterBar>
                <div className="overflow-hidden rounded-b-3xl">
                    <div className="overflow-x-auto">
                    <table className="w-full min-w-[850px] text-sm">
                        <thead className="bg-muted/60 text-left text-xs uppercase text-muted-foreground">
                        <tr>
                            <th className="px-5 py-4">Branch</th>
                            <th className="px-4 py-4">Location</th>
                            <th className="px-4 py-4">Contact</th>
                            <th className="px-4 py-4">Staff</th>
                            <th className="px-4 py-4">Status</th>
                            <th className="px-5 py-4 text-right">Action</th>
                        </tr>
                        </thead>
                        <tbody>
                        {filtered.length === 0 ? <tr>
                            <td colSpan={6} className="px-5 py-16 text-center text-muted-foreground">No branches
                                found.
                            </td>
                        </tr> : filtered.map((branch) => {
                            const assigned = companyStaff.filter((staff) => staff.branch_id === branch.id).length;
                            return <tr key={branch.id} className="border-t hover:bg-muted/30">
                                <td className="px-5 py-4"><div className="flex flex-wrap items-center gap-2"><span className="font-black">{branch.name}</span>{branch.is_headquarters ? <Badge>Headquarters</Badge> : null}</div></td>
                                <td className="px-4 py-4"><p className="font-bold">{branch.district}</p><p
                                    className="mt-1 text-xs text-muted-foreground">{branch.town || branch.address || "No town supplied"}</p>
                                </td>
                                <td className="px-4 py-4"><p>{branch.phone || "No phone"}</p><p
                                    className="mt-1 text-xs text-muted-foreground">{branch.email || "No email"}</p></td>
                                <td className="px-4 py-4 font-black">{assigned}</td>
                                <td className="px-4 py-4"><StatusBadge
                                    value={branch.is_active ? "active" : "inactive"}/></td>
                                <td className="px-5 py-4 text-right">{canManage &&
                                    <button type="button" onClick={() => void toggleBranch(branch.id, branch.is_active)}
                                            className={`inline-flex h-9 items-center gap-2 rounded-xl border px-3 text-xs font-black ${branch.is_active ? "text-red-600" : "text-green-600"}`}>{branch.is_active ?
                                        <PowerOff className="h-4 w-4"/> : <Power
                                            className="h-4 w-4"/>}{branch.is_active ? "Deactivate" : "Activate"}</button>}</td>
                            </tr>;
                        })}
                        </tbody>
                    </table>
                    </div>
                </div>
            </section>

            {showForm && <CustomDialog
                open={showForm}
                onOpenChange={(nextOpen) => {
                    if (!submitting) {
                        setShowForm(nextOpen);
                    }
                }}
                title="Create branch"
                contentClassName="sm:max-w-2xl"
            >
                <form
                    onSubmit={createBranch}
                    className="flex min-h-0 flex-col"
                >
                    <div className="space-y-5 px-5 py-6 sm:px-7">
                        <div>
                            <h3 className="text-lg font-black">
                                Branch information
                            </h3>

                            <p className="mt-1 text-sm text-muted-foreground">
                                Add another operating location to{" "}
                                <span className="font-bold text-foreground">
                        {currentCompany?.name ?? "the current company"}
                    </span>
                                .
                            </p>
                        </div>

                        <div className="grid gap-4 sm:grid-cols-2">
                            {(
                                [
                                    [
                                        "name",
                                        "Branch name",
                                        "e.g. Maseru Central",
                                    ],
                                    [
                                        "district",
                                        "District",
                                        "e.g. Maseru",
                                    ],
                                    [
                                        "town",
                                        "Town or village",
                                        "e.g. Thetsane",
                                    ],
                                    [
                                        "address",
                                        "Physical address",
                                        "Street, building or landmark",
                                    ],
                                    [
                                        "phone",
                                        "Phone number",
                                        "e.g. +266 5800 0000",
                                    ],
                                    [
                                        "email",
                                        "Email address",
                                        "branch@example.com",
                                    ],
                                ] as const
                            ).map(
                                ([
                                     key,
                                     label,
                                     placeholder,
                                 ]) => {
                                    const isRequired =
                                        key === "name" ||
                                        key === "district";

                                    const isAddress =
                                        key === "address";

                                    return (
                                        <label
                                            key={key}
                                            className={
                                                isAddress
                                                    ? "sm:col-span-2"
                                                    : ""
                                            }
                                        >
                                <span className="mb-2 block text-sm font-bold">
                                    {label}

                                    {isRequired && (
                                        <span className="text-red-500">
                                            {" "}
                                            *
                                        </span>
                                    )}
                                </span>

                                            {isAddress ? (
                                                <Textarea
                                                    name={key}
                                                    required={isRequired}
                                                    value={form[key]}
                                                    onChange={(event) =>
                                                        setForm(
                                                            (current) => ({
                                                                ...current,
                                                                [key]:
                                                                event
                                                                    .target
                                                                    .value,
                                                            }),
                                                        )
                                                    }
                                                    disabled={submitting}
                                                    placeholder={
                                                        placeholder
                                                    }
                                                    className={[
                                                        "min-h-24 w-full resize-y rounded-xl border",
                                                        "bg-background px-3 py-2.5 text-sm",
                                                        "outline-none transition",
                                                        "placeholder:text-muted-foreground",
                                                        "focus:border-primary focus:ring-2 focus:ring-primary/20",
                                                        "disabled:cursor-not-allowed disabled:opacity-60",
                                                    ].join(" ")}
                                                />
                                            ) : (
                                                <Input
                                                    name={key}
                                                    type={
                                                        key === "email"
                                                            ? "email"
                                                            : key ===
                                                            "phone"
                                                                ? "tel"
                                                                : "text"
                                                    }
                                                    required={isRequired}
                                                    value={form[key]}
                                                    onChange={(event) =>
                                                        setForm(
                                                            (current) => ({
                                                                ...current,
                                                                [key]:
                                                                event
                                                                    .target
                                                                    .value,
                                                            }),
                                                        )
                                                    }
                                                    disabled={submitting}
                                                    placeholder={
                                                        placeholder
                                                    }
                                                    autoFocus={
                                                        key === "name"
                                                    }
                                                    className={[
                                                        "h-11 w-full rounded-xl border",
                                                        "bg-background px-3 text-sm",
                                                        "outline-none transition",
                                                        "placeholder:text-muted-foreground",
                                                        "focus:border-primary focus:ring-2 focus:ring-primary/20",
                                                        "disabled:cursor-not-allowed disabled:opacity-60",
                                                    ].join(" ")}
                                                />
                                            )}
                                        </label>
                                    );
                                },
                            )}
                        </div>
                        <label className="flex cursor-pointer items-start gap-3 rounded-2xl border bg-muted/20 p-4">
                            <Checkbox checked={form.is_headquarters} onCheckedChange={(value) => setForm((current) => ({...current, is_headquarters: value === true}))} disabled={submitting} />
                            <span><span className="block font-black">Make this the headquarters branch</span><span className="mt-1 block text-xs leading-5 text-muted-foreground">Only one branch can be headquarters. Selecting this branch moves the headquarters label from the previous branch and makes it the daily consolidation point.</span></span>
                        </label>
                    </div>

                    <div className="sticky bottom-0 flex flex-col-reverse gap-3 border-t bg-card px-5 py-4 sm:flex-row sm:justify-end sm:px-7">
                        <button
                            type="button"
                            onClick={() =>
                                setShowForm(false)
                            }
                            disabled={submitting}
                            className={[
                                "h-11 rounded-xl border px-5 text-sm font-bold",
                                "transition hover:bg-muted",
                                "disabled:cursor-not-allowed disabled:opacity-60",
                            ].join(" ")}
                        >
                            Cancel
                        </button>

                        <button
                            type="submit"
                            disabled={submitting}
                            className={[
                                "inline-flex h-11 items-center justify-center gap-2",
                                "rounded-xl bg-primary px-5 text-sm font-black",
                                "text-primary-foreground transition",
                                "hover:bg-primary/90",
                                "disabled:cursor-not-allowed disabled:opacity-60",
                            ].join(" ")}
                        >
                            {submitting && (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            )}

                            {submitting
                                ? "Creating branch..."
                                : "Create branch"}
                        </button>
                    </div>
                </form>
            </CustomDialog>}
        </div>
    );
}
