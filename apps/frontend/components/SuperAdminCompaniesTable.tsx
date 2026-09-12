"use client";


import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { SuggestionSearch } from "@/components/ui/suggestion-search";
import {
    Building2,
    CheckCircle2,
    Copy,
    Eye,
    Loader2,
    MoreHorizontal,
    Pencil,
    Power,
    PowerOff,
    RefreshCcw,
    Search,
    Trash2,
    XCircle,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
    activateCompany,
    approveCompany,
    deactivateCompany,
    deleteCompany,
    fetchCompanies,
    LoanCompany,
    LoanCompanyPayload,
    rejectCompany,
    updateCompany,
} from "@/store/slices/companiesSlice";

import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import Link from "next/link";

import { CompanyEditDialog } from "@/app/(dashboard)/superadmin/companies/_components/company-edit-dialog";
import { toast } from "@/utils/toast";

export function SuperAdminCompaniesTable() {
    const dispatch = useAppDispatch();

    const {
        companies,
        loading,
        actionLoadingId,
        error,
    } = useAppSelector((state) => state.companies);

    const [query, setQuery] = useState("");
    const [status, setStatus] = useState("all");
    const [active, setActive] = useState("all");
    const [district, setDistrict] = useState("all");
    const [companyToEdit, setCompanyToEdit] = useState<LoanCompany | null>(null);
    const [isSavingCompany, setIsSavingCompany] = useState(false);

    useEffect(() => {
        const timer = window.setTimeout(() => {
            void dispatch(fetchCompanies());
        }, 0);
        return () => window.clearTimeout(timer);
    }, [dispatch]);

    const districts = useMemo(() => {
        return Array.from(
            new Set(
                companies
                    .map((company) => company.district)
                    .filter(Boolean),
            ),
        ).sort();
    }, [companies]);

    const filteredCompanies = useMemo(() => {
        return companies.filter((company) => {
            const searchValue = query.trim().toLowerCase();

            const matchesSearch =
                searchValue.length === 0 ||
                company.name.toLowerCase().includes(searchValue) ||
                company.registration_number.toLowerCase().includes(searchValue) ||
                company.license_number.toLowerCase().includes(searchValue) ||
                company.phone.toLowerCase().includes(searchValue) ||
                company.email.toLowerCase().includes(searchValue) ||
                company.website.toLowerCase().includes(searchValue) ||
                company.address.toLowerCase().includes(searchValue) ||
                company.district.toLowerCase().includes(searchValue) ||
                company.status.toLowerCase().includes(searchValue);

            const matchesStatus =
                status === "all" || company.status === status;

            const matchesActive =
                active === "all" ||
                (active === "active" && company.is_active) ||
                (active === "inactive" && !company.is_active);

            const matchesDistrict =
                district === "all" || company.district === district;

            return (
                matchesSearch &&
                matchesStatus &&
                matchesActive &&
                matchesDistrict
            );
        });
    }, [companies, query, status, active, district]);



    const resetFilters = () => {
        setQuery("");
        setStatus("all");
        setActive("all");
        setDistrict("all");
    };

    const saveCompany = async (payload: Partial<LoanCompanyPayload>) => {
        if (!companyToEdit || isSavingCompany) return;

        setIsSavingCompany(true);
        try {
            await dispatch(
                updateCompany({
                    id: companyToEdit.id,
                    payload,
                }),
            ).unwrap();
            toast.success(`${companyToEdit.name} updated successfully`);
            setCompanyToEdit(null);
        } catch (caught: unknown) {
            toast.error(
                typeof caught === "string"
                    ? caught
                    : "The company could not be updated.",
            );
        } finally {
            setIsSavingCompany(false);
        }
    };

    return (
        <>
        <section className="rounded-4xl border border-border bg-card p-6 shadow-sm">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
                <div>
                    <h2 className="text-xl font-black">
                        Loan Companies
                    </h2>
                    <p className="mt-1 text-sm text-muted-foreground">
                        Manage company joining requests, approval, rejection and activation.
                    </p>
                </div>

                <button
                    type="button"
                    onClick={() => dispatch(fetchCompanies())}
                    className="group flex w-fit cursor-pointer items-center gap-2 rounded-xl border border-border bg-background px-4 py-2 text-sm font-bold transition-all hover:-translate-y-0.5 hover:border-primary hover:text-primary active:scale-[0.98]"
                >
                    <RefreshCcw className="h-4 w-4 transition-transform duration-300 group-hover:rotate-180" />
                    Refresh
                </button>
            </div>

            <div className="mt-6 grid gap-3 xl:grid-cols-[1.4fr_0.7fr_0.7fr_0.8fr_auto]">
                <SuggestionSearch
                    value={query}
                    onValueChange={setQuery}
                    suggestions={companies.map((company) => ({
                        value: company.name,
                        label: company.name,
                        description: `${company.registration_number} · ${company.district}`,
                        keywords: [company.id, company.license_number, company.phone, company.email, company.website, company.address, company.status],
                    }))}
                    placeholder="Type a company, registration, phone or district..."
                    suggestionLabel="Loan companies"
                    emptyMessage="No company matches that text."
                    className="h-12 rounded-2xl"
                />

                <NativeSelect
                    value={status}
                    onChange={(event) => setStatus(event.target.value)}
                    className="h-12 cursor-pointer rounded-2xl border border-border bg-background px-4 text-sm font-bold outline-none"
                >
                    <option value="all">All statuses</option>
                    <option value="pending">Pending</option>
                    <option value="approved">Approved</option>
                    <option value="rejected">Rejected</option>
                </NativeSelect>

                <NativeSelect
                    value={active}
                    onChange={(event) => setActive(event.target.value)}
                    className="h-12 cursor-pointer rounded-2xl border border-border bg-background px-4 text-sm font-bold outline-none"
                >
                    <option value="all">All active</option>
                    <option value="active">Active only</option>
                    <option value="inactive">Inactive only</option>
                </NativeSelect>

                <NativeSelect
                    value={district}
                    onChange={(event) => setDistrict(event.target.value)}
                    className="h-12 cursor-pointer rounded-2xl border border-border bg-background px-4 text-sm font-bold outline-none"
                >
                    <option value="all">All districts</option>
                    {districts.map((item) => (
                        <option key={item} value={item}>
                            {item}
                        </option>
                    ))}
                </NativeSelect>

                <button
                    type="button"
                    onClick={resetFilters}
                    className="h-12 cursor-pointer rounded-2xl border border-border bg-background px-4 text-sm font-black transition-all hover:border-primary hover:text-primary"
                >
                    Reset
                </button>
            </div>

            <div className="mt-4 flex items-center justify-between text-sm">
                <p className="font-semibold text-muted-foreground">
                    Showing{" "}
                    <span className="font-black text-foreground">
            {filteredCompanies.length}
          </span>{" "}
                    of{" "}
                    <span className="font-black text-foreground">
            {companies.length}
          </span>{" "}
                    companies
                </p>
            </div>

            <div className="mt-6 overflow-hidden rounded-2xl border border-border">
                <div className="overflow-x-auto">
                    <table className="w-full min-w-[1150px] text-left text-sm">
                        <thead className="bg-background text-xs uppercase text-muted-foreground">
                        <tr>
                            <th className="px-4 py-4">Company</th>
                            <th className="px-4 py-4">Registration</th>
                            <th className="px-4 py-4">District</th>
                            <th className="px-4 py-4">Phone</th>
                            <th className="px-4 py-4">Status</th>
                            <th className="px-4 py-4">Active</th>
                            <th className="px-4 py-4">Created</th>
                            <th className="px-4 py-4 text-right">Actions</th>
                        </tr>
                        </thead>

                        <tbody>
                        {loading ? (
                            <tr>
                                <td colSpan={8} className="px-4 py-14 text-center">
                                    <div className="flex items-center justify-center gap-2 font-bold text-muted-foreground">
                                        <Loader2 className="h-5 w-5 animate-spin" />
                                        Loading companies...
                                    </div>
                                </td>
                            </tr>
                        ) : filteredCompanies.length === 0 ? (
                            <tr>
                                <td colSpan={8} className="px-4 py-14 text-center">
                                    <div className="mx-auto flex max-w-sm flex-col items-center">
                                        <div className="mb-4 rounded-2xl bg-primary/10 p-4 text-primary">
                                            <Building2 className="h-8 w-8" />
                                        </div>

                                        <p className="font-black">
                                            No companies found
                                        </p>

                                        <p className="mt-1 text-sm text-muted-foreground">
                                            Try changing your filters.
                                        </p>
                                    </div>
                                </td>
                            </tr>
                        ) : (
                            filteredCompanies.map((company) => (
                                <CompanyRow
                                    key={company.id}
                                    company={company}
                                    loading={actionLoadingId === company.id}
                                    onApprove={() => dispatch(approveCompany(company.id))}
                                    onReject={() => dispatch(rejectCompany(company.id))}
                                    onActivate={() => dispatch(activateCompany(company.id))}
                                    onDeactivate={() =>
                                        dispatch(deactivateCompany(company.id))
                                    }
                                    onDelete={() => dispatch(deleteCompany(company.id))}
                                    onEdit={() => setCompanyToEdit(company)}
                                />
                            ))
                        )}
                        </tbody>
                    </table>
                </div>
            </div>
        </section>

        <CompanyEditDialog
            company={companyToEdit}
            open={Boolean(companyToEdit)}
            isSaving={isSavingCompany}
            onOpenChange={(open) => {
                if (!open && !isSavingCompany) setCompanyToEdit(null);
            }}
            onSave={saveCompany}
        />
        </>
    );
}

function CompanyRow({
                        company,
                        loading,
                        onApprove,
                        onReject,
                        onActivate,
                        onDeactivate,
                        onDelete,
                        onEdit,
                    }: {
    company: LoanCompany;
    loading: boolean;
    onApprove: () => void;
    onReject: () => void;
    onActivate: () => void;
    onDeactivate: () => void;
    onDelete: () => void;
    onEdit: () => void;
}) {
    const copyCompanyId = async () => {
        await navigator.clipboard.writeText(company.id);
    };

    return (
        <tr className="border-t border-border transition-all hover:bg-background/70">
            <td className="px-4 py-4">
                <Link href={`/superadmin/companies/${company.id}`}>
                    <div className="flex items-center gap-3 cursor-pointer">
                        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                            <Building2 className="h-5 w-5" />
                        </div>

                        <div>
                            <p className="font-black">
                                {company.name}
                            </p>

                            <p className="text-xs text-muted-foreground">
                                {company.email}
                            </p>
                        </div>
                    </div>
                </Link>
            </td>

            <td className="px-4 py-4">
                <p className="font-bold">
                    {company.registration_number}
                </p>
                <p className="text-xs text-muted-foreground">
                    License: {company.license_number}
                </p>
            </td>

            <td className="px-4 py-4 font-semibold">
                {company.district}
            </td>

            <td className="px-4 py-4 font-semibold">
                {company.phone}
            </td>

            <td className="px-4 py-4">
                <StatusBadge status={company.status} />
            </td>

            <td className="px-4 py-4">
                <ActiveBadge active={company.is_active} />
            </td>

            <td className="px-4 py-4 font-semibold">
                {new Date(company.created_at).toLocaleDateString()}
            </td>

            <td className="px-4 py-4">
                <div className="flex justify-end">
                    {loading ? (
                        <button
                            type="button"
                            disabled
                            className="flex items-center gap-2 rounded-xl border border-border px-3 py-2 text-xs font-black text-muted-foreground"
                        >
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Working
                        </button>
                    ) : (
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <button
                                    type="button"
                                    className="cursor-pointer rounded-xl border border-border px-3 py-2 text-muted-foreground transition-all hover:-translate-y-0.5 hover:border-primary hover:text-primary active:scale-[0.98]"
                                >
                                    <MoreHorizontal className="h-4 w-4" />
                                </button>
                            </DropdownMenuTrigger>

                            <DropdownMenuContent align="end" className="w-56">
                                <DropdownMenuLabel>
                                    Company Actions
                                </DropdownMenuLabel>
                                <DropdownMenuSeparator />

                                <DropdownMenuItem className="cursor-pointer gap-2">
                                    <Eye className="h-4 w-4" />
                                    View Company
                                </DropdownMenuItem>

                                <DropdownMenuItem
                                    onClick={onEdit}
                                    className="cursor-pointer gap-2"
                                >
                                    <Pencil className="h-4 w-4" />
                                    Edit Company
                                </DropdownMenuItem>

                                <DropdownMenuItem
                                    onClick={copyCompanyId}
                                    className="cursor-pointer gap-2"
                                >
                                    <Copy className="h-4 w-4" />
                                    Copy Company ID
                                </DropdownMenuItem>

                                <DropdownMenuSeparator />

                                {company.status === "pending" && (
                                    <>
                                        <DropdownMenuItem
                                            onClick={onApprove}
                                            className="cursor-pointer gap-2 text-green-600 focus:text-green-600"
                                        >
                                            <CheckCircle2 className="h-4 w-4" />
                                            Approve Company
                                        </DropdownMenuItem>

                                        <DropdownMenuItem
                                            onClick={onReject}
                                            className="cursor-pointer gap-2 text-destructive focus:text-destructive"
                                        >
                                            <XCircle className="h-4 w-4" />
                                            Reject Company
                                        </DropdownMenuItem>
                                    </>
                                )}

                                {company.is_active ? (
                                    <DropdownMenuItem
                                        onClick={onDeactivate}
                                        className="cursor-pointer gap-2 text-destructive focus:text-destructive"
                                    >
                                        <PowerOff className="h-4 w-4" />
                                        Deactivate Company
                                    </DropdownMenuItem>
                                ) : company.status === 'approved' ? (
                                    <DropdownMenuItem
                                        onClick={onActivate}
                                        className="cursor-pointer gap-2 text-green-600 focus:text-green-600"
                                    >
                                        <Power className="h-4 w-4" />
                                        Activate Company
                                    </DropdownMenuItem>
                                ) : company.status === 'rejected'&& (
                                    <>
                                        <DropdownMenuItem
                                            onClick={onApprove}
                                            className="cursor-pointer gap-2 text-green-600 focus:text-green-600"
                                        >
                                            <CheckCircle2 className="h-4 w-4" />
                                            Approve Company
                                        </DropdownMenuItem>
                                    </>
                                ) }

                                <DropdownMenuSeparator />

                                <DropdownMenuItem
                                    onClick={onDelete}
                                    className="cursor-pointer gap-2 text-destructive focus:text-destructive"
                                >
                                    <Trash2 className="h-4 w-4" />
                                    Delete Company
                                </DropdownMenuItem>
                            </DropdownMenuContent>
                        </DropdownMenu>
                    )}
                </div>
            </td>
        </tr>
    );
}

function StatusBadge({ status }: { status: string }) {
    const normalized = status.toLowerCase();

    const className =
        normalized === "approved"
            ? "bg-green-500/10 text-green-600"
            : normalized === "rejected"
                ? "bg-destructive/10 text-destructive"
                : "bg-primary/10 text-primary";

    return (
        <span className={`rounded-full px-3 py-1 text-xs font-black ${className}`}>
      {status.replaceAll("_", " ").toUpperCase()}
    </span>
    );
}

function ActiveBadge({ active }: { active: boolean }) {
    return (
        <span
            className={`rounded-full px-3 py-1 text-xs font-black ${
                active
                    ? "bg-green-500/10 text-green-600"
                    : "bg-destructive/10 text-destructive"
            }`}
        >
      {active ? "ACTIVE" : "INACTIVE"}
    </span>
    );
}