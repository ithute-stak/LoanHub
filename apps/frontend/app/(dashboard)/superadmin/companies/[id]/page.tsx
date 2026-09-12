"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import {
    Activity,
    ArrowLeft,
    Building2,
    CreditCard,
    FileText,
    MapPin,
    Settings2,
    Users,
    Wallet,
} from "lucide-react";

import { InstitutionGovernanceSettings } from "@/app/(dashboard)/company/settings/_components/institution-governance-settings";
import { useAppData } from "@/provider/appDataProvider";

function money(value: number): string {
    return new Intl.NumberFormat("en-LS", {
        style: "currency",
        currency: "LSL",
        maximumFractionDigits: 2,
    }).format(value || 0);
}

function formatStatus(value?: string | null): string {
    return String(value ?? "unknown")
        .replaceAll("_", " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export default function CompanyDashboardPage() {
    const params = useParams<{ id: string }>();
    const companyId = String(params.id);
    const {
        companies,
        branches,
        companyStaff,
        loans,
        payments,
        isCompaniesLoading,
    } = useAppData();

    const company = companies.find((item) => item.id === companyId);
    const companyBranches = branches.filter((item) => item.company_id === companyId);
    const staff = companyStaff.filter((item) => item.company_id === companyId);
    const companyLoans = loans.filter((item) => item.company_id === companyId);
    const companyPayments = payments.filter((item) => item.company_id === companyId);

    const activeLoans = companyLoans.filter((item) => ["approved", "active"].includes(item.status));
    const overdueLoans = companyLoans.filter((item) => item.is_overdue);
    const portfolioBalance = companyLoans.reduce((total, item) => total + Number(item.balance || 0), 0);
    const successfulPayments = companyPayments
        .filter((item) => item.status === "succeeded")
        .reduce((total, item) => total + Number(item.amount || 0), 0);

    if (isCompaniesLoading && !company) {
        return <div className="h-96 animate-pulse rounded-3xl bg-muted" />;
    }

    if (!company) {
        return (
            <section className="rounded-3xl border bg-card p-8 text-center shadow-sm">
                <Building2 className="mx-auto h-12 w-12 text-muted-foreground" />
                <h1 className="mt-4 text-2xl font-black">Company not found</h1>
                <p className="mt-2 text-sm text-muted-foreground">The tenant may have been removed, suspended or is outside your current dataset.</p>
                <Link href="/superadmin/companies" className="mt-6 inline-flex h-11 items-center gap-2 rounded-xl bg-primary px-5 text-sm font-black text-primary-foreground">
                    <ArrowLeft className="h-4 w-4" /> Return to companies
                </Link>
            </section>
        );
    }

    const links = [
        { title: "Branches", text: `${companyBranches.length} registered`, icon: MapPin, href: `/superadmin/companies/branches?company=${companyId}` },
        { title: "Staff", text: `${staff.length} memberships`, icon: Users, href: `/superadmin/company-admins?company=${companyId}` },
        { title: "Loans", text: `${companyLoans.length} total`, icon: CreditCard, href: `/superadmin/loans?company=${companyId}` },
        { title: "Reports", text: "Generate company report", icon: FileText, href: `/superadmin/reports?company=${companyId}` },
    ];

    return (
        <main className="space-y-6">
            <Link href="/superadmin/companies" className="inline-flex items-center gap-2 text-sm font-black text-muted-foreground hover:text-foreground">
                <ArrowLeft className="h-4 w-4" /> All companies
            </Link>

            <section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8">
                <div className="absolute -left-20 -top-20 h-72 w-72 rounded-full bg-primary/10 blur-3xl" />
                <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
                    <div className="flex items-start gap-4">
                        <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-3xl bg-primary/10 text-primary">
                            <Building2 className="h-8 w-8" />
                        </div>
                        <div>
                            <p className="text-xs font-black uppercase tracking-[0.16em] text-primary">Tenant overview</p>
                            <h1 className="mt-1 text-3xl font-black tracking-tight">{company.name}</h1>
                            <p className="mt-2 text-sm text-muted-foreground">{company.email || company.phone || "No public contact supplied"}</p>
                            <div className="mt-3 flex flex-wrap gap-2">
                                <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-black text-primary">{formatStatus(company.status)}</span>
                                <span className={`rounded-full px-3 py-1 text-xs font-black ${company.is_active ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400" : "bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-400"}`}>{company.is_active ? "Active" : "Inactive"}</span>
                            </div>
                        </div>
                    </div>
                    <Link href={`/superadmin/companies?focus=${companyId}`} className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-5 text-sm font-black text-primary-foreground">
                        <Settings2 className="h-4 w-4" /> Manage tenant
                    </Link>
                </div>
            </section>

            <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <Metric title="Active loans" value={String(activeLoans.length)} detail={`${overdueLoans.length} overdue`} icon={CreditCard} />
                <Metric title="Outstanding portfolio" value={money(portfolioBalance)} detail={`${companyLoans.length} total loans`} icon={Wallet} />
                <Metric title="Successful payments" value={money(successfulPayments)} detail={`${companyPayments.length} ledger records`} icon={Activity} />
                <Metric title="Operating footprint" value={`${companyBranches.length} branches`} detail={`${staff.length} staff memberships`} icon={MapPin} />
            </section>

            <section className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
                <article className="rounded-3xl border bg-card p-6 shadow-sm">
                    <h2 className="text-lg font-black">Company information</h2>
                    <dl className="mt-5 space-y-4 text-sm">
                        <Info label="Phone" value={company.phone} />
                        <Info label="District" value={company.district} />
                        <Info label="Registration number" value={company.registration_number} />
                        <Info label="Licence number" value={company.license_number} />
                        <Info label="Address" value={company.address} />
                    </dl>
                </article>

                <article className="rounded-3xl border bg-card p-6 shadow-sm">
                    <h2 className="text-lg font-black">Operational modules</h2>
                    <p className="mt-1 text-sm text-muted-foreground">Open a live, company-filtered workspace. No demonstration totals are used on this page.</p>
                    <div className="mt-5 grid gap-3 sm:grid-cols-2">
                        {links.map(({ title, text, icon: Icon, href }) => (
                            <Link key={title} href={href} className="group flex items-center gap-3 rounded-2xl border bg-background p-4 transition hover:border-primary hover:shadow-sm">
                                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary"><Icon className="h-5 w-5" /></span>
                                <span><span className="block text-sm font-black">{title}</span><span className="text-xs text-muted-foreground">{text}</span></span>
                            </Link>
                        ))}
                    </div>
                </article>
            </section>

            <section className="space-y-4">
                <div>
                    <h2 className="text-2xl font-black">Governance oversight</h2>
                    <p className="mt-1 text-sm text-muted-foreground">
                        Review or update this institution&apos;s regulatory, privacy, security,
                        responsible-AI and GovStack readiness evidence. Every saved change is audited.
                    </p>
                </div>
                <InstitutionGovernanceSettings
                    canManage
                    institutionType={company.institution_type ?? "loan_company"}
                    companyId={company.id}
                />
            </section>
        </main>
    );
}

function Metric({ title, value, detail, icon: Icon }: { title: string; value: string; detail: string; icon: typeof Building2 }) {
    return <article className="rounded-3xl border bg-card p-5 shadow-sm"><div className="flex items-center justify-between"><div><p className="text-sm font-bold text-muted-foreground">{title}</p><p className="mt-2 text-2xl font-black">{value}</p><p className="mt-1 text-xs text-muted-foreground">{detail}</p></div><span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary"><Icon className="h-5 w-5" /></span></div></article>;
}

function Info({ label, value }: { label: string; value?: string | null }) {
    return <div className="flex items-start justify-between gap-5 border-b pb-3 last:border-0 last:pb-0"><dt className="text-muted-foreground">{label}</dt><dd className="max-w-[62%] text-right font-black">{value || "Not provided"}</dd></div>;
}
