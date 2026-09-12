"use client";

import Link from "next/link";
import {
    ArrowRight,
    Building2,
    ChartNoAxesCombined,
    CreditCard,
    FileChartColumn,
    FileText,
    GitBranch,
    History,
    Landmark,
    LayoutDashboard,
    MessageCircleMore,
    ServerCog,
    ShieldCheck,
    TriangleAlert,
    Users,
    WalletCards,
    type LucideIcon,
} from "lucide-react";
import { useMemo, useState } from "react";

import { formatMoney } from "@/lib/format";
import { useAppData } from "@/provider/appDataProvider";

type ControlModule = {
    slug: string;
    title: string;
    description: string;
    icon: LucideIcon;
    capabilities: string[];
    links?: Array<{ label: string; href: string }>;
    warning?: string;
};

const modules: ControlModule[] = [
    {
        slug: "global-portfolio",
        title: "Global portfolio intelligence",
        description: "Cross-tenant lending and repayment oversight for the entire LoanHub platform.",
        icon: ChartNoAxesCombined,
        capabilities: [
            "Search loans across all companies and compare lender performance.",
            "Track disbursements, collections, outstanding balances and arrears.",
            "Monitor portfolio quality, defaults, average loan size and repayment performance.",
            "Surface PAR30, PAR60 and PAR90 indicators when portfolio ageing data is available.",
        ],
        links: [
            { label: "Open platform loans", href: "/superadmin/loans" },
            { label: "Open reports", href: "/superadmin/reports" },
        ],
    },
    {
        slug: "borrowers",
        title: "Global borrower oversight",
        description: "Platform-level borrower discovery and risk visibility without silently changing tenant records.",
        icon: Users,
        capabilities: [
            "Locate borrowers across tenant boundaries using authorised identity fields.",
            "Review borrower loan exposure, payment history and linked tenant relationships.",
            "Maintain reviewed watchlist cases with reason, evidence, review date and resolution state.",
            "Keep borrower-risk decisions auditable and separate from ordinary company administration.",
        ],
    },
    {
        slug: "risk-fraud",
        title: "Risk & fraud centre",
        description: "Detect suspicious platform behaviour and direct cases into investigation workflows.",
        icon: TriangleAlert,
        capabilities: [
            "Flag duplicate identity numbers, phone numbers and suspicious account reuse.",
            "Surface unusual loan volumes, rapid profile changes, repeated failed access and abnormal write-offs.",
            "Track suspicious repayments and manual financial adjustments for review.",
            "Assign risk cases a severity, owner, evidence trail and resolution status.",
        ],
        links: [{ label: "Open activity log", href: "/superadmin/activity" }],
    },
    {
        slug: "compliance",
        title: "Compliance centre",
        description: "Central KYC, consent, document and policy oversight across companies.",
        icon: FileText,
        capabilities: [
            "Monitor KYC completeness and missing or expiring borrower documents.",
            "Review consent records, policy exceptions and company compliance status.",
            "Prepare compliance and regulatory reporting datasets from authorised records.",
            "Track remediation items with owners, due dates and evidence.",
        ],
        links: [{ label: "Open document studio", href: "/superadmin/documents" }],
    },
    {
        slug: "audit",
        title: "Audit & investigations",
        description: "Platform investigation centre for reconstructing sensitive actions and changes.",
        icon: History,
        capabilities: [
            "Investigate events by tenant, user, borrower, loan, transaction and date range.",
            "Preserve who performed an action, when it happened and the affected record.",
            "Record old and new values for sensitive changes where backend audit events provide them.",
            "Keep System Owner support activity visible in the same audit trail.",
        ],
        links: [{ label: "Open activity log", href: "/superadmin/activity" }],
    },
    {
        slug: "emergency",
        title: "Emergency control room",
        description: "High-risk platform switches are isolated from routine administration and must be strongly authorised.",
        icon: TriangleAlert,
        capabilities: [
            "Emergency stop for new loan creation or disbursement.",
            "Temporarily isolate a tenant or affected integration.",
            "Revoke sessions or place the platform into controlled maintenance mode.",
            "Require re-authentication, a reason, immutable audit entry and dual approval for destructive actions.",
        ],
        warning: "Emergency switches are intentionally not executed from the browser until the corresponding audited backend approval endpoints exist.",
    },
    {
        slug: "company-health",
        title: "Company health scoring",
        description: "A single operational view of tenant health and intervention priority.",
        icon: Building2,
        capabilities: [
            "Score companies using arrears, defaults, collection performance and unresolved operational issues.",
            "Include compliance gaps, suspicious activity and support escalations in health review.",
            "Classify tenants as Healthy, Watch, High Risk or Critical.",
            "Use the score as decision support rather than an automatic punitive action.",
        ],
        links: [{ label: "Open companies", href: "/superadmin/companies" }],
    },
    {
        slug: "support-sessions",
        title: "Controlled support sessions",
        description: "A governed foundation for future ‘view as company’ troubleshooting sessions.",
        icon: Building2,
        capabilities: [
            "Require a support reason before entering a tenant context.",
            "Display a permanent System Owner support-session banner while impersonating.",
            "Re-authenticate with MFA before privileged support access where configured.",
            "Audit every action taken during the support session and provide an explicit exit action.",
        ],
        warning: "Direct tenant impersonation stays disabled until server-side session-scoping and audit enforcement are implemented.",
    },
    {
        slug: "users-access",
        title: "Global users & access",
        description: "Cross-platform account administration for security and support operations.",
        icon: Users,
        capabilities: [
            "Search users across companies and inspect tenant/role relationships.",
            "Prepare lock, unlock, session revocation and password-reset workflows.",
            "Support MFA reset and suspicious-login investigation through audited privileged actions.",
            "Keep company roles separate from System Owner privileges.",
        ],
        links: [{ label: "Company administrators", href: "/superadmin/company-admins" }],
    },
    {
        slug: "security",
        title: "Security centre",
        description: "Platform security policy, access posture and incident visibility.",
        icon: ShieldCheck,
        capabilities: [
            "Centralise MFA enforcement, password policy and session-lifetime controls.",
            "Review suspicious login and security events.",
            "Govern API-key and privileged-session access.",
            "Prepare emergency session revocation and IP/device restriction workflows.",
        ],
        links: [
            { label: "My profile & security", href: "/superadmin/account" },
            { label: "System errors", href: "/superadmin/system-errors" },
        ],
    },
    {
        slug: "approvals",
        title: "Approval governance",
        description: "Four-eyes controls for high-impact financial and administrative actions.",
        icon: ShieldCheck,
        capabilities: [
            "Define actions requiring maker-checker or dual approval.",
            "Cover write-offs, payment reversals, balance corrections and ownership transfers.",
            "Protect company deletion, bulk deletion and platform-wide configuration changes.",
            "Record requester, approver, reason, decision and timestamps.",
        ],
    },
    {
        slug: "data-governance",
        title: "Data governance",
        description: "Controlled exports, retention, archive and privacy-related operational workflows.",
        icon: FileText,
        capabilities: [
            "Govern tenant data exports and archive requests.",
            "Track retention, anonymisation and deletion workflows.",
            "Record who accessed or exported sensitive platform data.",
            "Separate operational deletion requests from immutable financial audit records.",
        ],
        links: [{ label: "File centre", href: "/superadmin/files" }],
    },
    {
        slug: "financial-integrity",
        title: "Financial integrity",
        description: "Reconciliation and exception oversight that protects the financial history of the platform.",
        icon: Landmark,
        capabilities: [
            "Surface repayment-versus-ledger discrepancies and orphan transactions.",
            "Detect duplicate payments, failed postings, reversals and unusual adjustments.",
            "Use reversal or adjustment workflows instead of silent edits to posted financial records.",
            "Route material discrepancies through review and approval.",
        ],
        links: [
            { label: "Platform accounting", href: "/superadmin/accounting" },
            { label: "Payment register", href: "/superadmin/payments" },
        ],
    },
    {
        slug: "billing",
        title: "Platform billing",
        description: "Commercial administration for tenants, plans and platform service usage.",
        icon: CreditCard,
        capabilities: [
            "Manage subscription plans, trials, invoices, credits and grace periods.",
            "Review successful and pending platform billing transactions.",
            "Prepare tenant-specific limits, pricing and service allowances.",
            "Track SMS, email, storage or other metered usage when those providers expose usage data.",
        ],
        links: [
            { label: "Subscription plans", href: "/superadmin/plans" },
            { label: "Payment register", href: "/superadmin/payments" },
        ],
    },
    {
        slug: "feature-flags",
        title: "Feature management",
        description: "Controlled rollout surface for platform and tenant-scoped capabilities.",
        icon: ServerCog,
        capabilities: [
            "Define global and tenant-scoped feature flags.",
            "Stage experimental functionality before platform-wide rollout.",
            "Record who changed a flag, the reason and the effective scope.",
            "Keep risky feature changes behind approval policy where required.",
        ],
    },
    {
        slug: "configuration",
        title: "Global configuration",
        description: "System defaults and policy configuration shared across LoanHub.",
        icon: ServerCog,
        capabilities: [
            "Govern supported currencies, countries and identity-document types.",
            "Manage platform defaults for interest, repayments, penalties and statuses.",
            "Centralise notification and document-template defaults.",
            "Separate global defaults from tenant-specific overrides.",
        ],
    },
    {
        slug: "integrations",
        title: "API & integrations",
        description: "Operational visibility for payment, messaging, government and webhook integrations.",
        icon: GitBranch,
        capabilities: [
            "Track integration health and recent failures.",
            "Govern API clients, webhook endpoints and credential references.",
            "Surface payment, SMS and email provider incidents.",
            "Allow controlled isolation of a failing integration without changing unrelated tenants.",
        ],
    },
    {
        slug: "system-health",
        title: "System health",
        description: "Operational status for the services that keep LoanHub running.",
        icon: ChartNoAxesCombined,
        capabilities: [
            "Monitor API, database, storage, queues and scheduled/background jobs.",
            "Surface WebSocket, email and SMS delivery health when telemetry is available.",
            "Connect recent system errors to operational investigations.",
            "Keep health data read-only unless a privileged recovery workflow is explicitly invoked.",
        ],
        links: [{ label: "System errors", href: "/superadmin/system-errors" }],
    },
    {
        slug: "backups",
        title: "Backups & recovery",
        description: "Govern backup evidence and disaster-recovery operations.",
        icon: History,
        capabilities: [
            "Review backup history, freshness and failure state.",
            "Prepare approved tenant exports and controlled recovery operations.",
            "Require strong authorisation for production restoration.",
            "Record recovery drills and restoration evidence.",
        ],
        warning: "Production restore actions must remain server-controlled and cannot be implemented as an unaudited client-side button.",
    },
    {
        slug: "releases",
        title: "Developer & release centre",
        description: "Release, migration and deployment visibility for System Owners.",
        icon: ServerCog,
        capabilities: [
            "Display application, database migration and environment version information when exposed by the backend.",
            "Track deployment and build status alongside release notes.",
            "Link operational incidents to the release that introduced or resolved them.",
            "Coordinate feature-flag rollout with deployment health.",
        ],
        links: [{ label: "System update", href: "/superadmin/system-update" }],
    },
    {
        slug: "communications",
        title: "Platform communications",
        description: "Targeted announcements, maintenance notices and security communications.",
        icon: MessageCircleMore,
        capabilities: [
            "Prepare announcements for all companies or selected tenants.",
            "Target company owners or role groups where recipient data permits.",
            "Publish maintenance, security and release notices through supported channels.",
            "Retain delivery status and communication history.",
        ],
        links: [{ label: "Platform chat", href: "/superadmin/chat" }],
    },
    {
        slug: "support",
        title: "Support centre",
        description: "Central support operations for tenant requests and platform incidents.",
        icon: MessageCircleMore,
        capabilities: [
            "Organise tenant support requests by priority, owner and status.",
            "Associate diagnostics, documents and conversations with the case.",
            "Track resolution time and unresolved escalations.",
            "Escalate security, compliance or financial-integrity issues into specialist workflows.",
        ],
        links: [{ label: "User queries", href: "/superadmin/queries" }],
    },
];

function ModuleCard({ module }: { module: ControlModule }) {
    const Icon = module.icon;
    return (
        <Link href={`/superadmin/control/${module.slug}`} className="group rounded-3xl border bg-card p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md">
            <div className="flex items-start justify-between gap-4">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary"><Icon className="h-5 w-5" /></div>
                <ArrowRight className="h-4 w-4 text-muted-foreground transition group-hover:translate-x-1 group-hover:text-primary" />
            </div>
            <h2 className="mt-4 text-base font-black">{module.title}</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{module.description}</p>
        </Link>
    );
}

export function SuperAdminOwnerControl({ selectedModule }: { selectedModule?: string }) {
    const {
        companiesCount,
        approvedCompaniesCount,
        pendingCompaniesCount,
        companyStaffCount,
        borrowersCount,
        loanRequestsCount,
        openLoanRequestsCount,
        payments,
        successfulPaymentsTotal,
    } = useAppData();
    const [query, setQuery] = useState("");

    const filteredModules = useMemo(() => {
        const normalized = query.trim().toLowerCase();
        if (!normalized) return modules;
        return modules.filter((module) => [module.title, module.description, ...module.capabilities].join(" ").toLowerCase().includes(normalized));
    }, [query]);

    const selectedControlModule = selectedModule ? modules.find((item) => item.slug === selectedModule) : undefined;
    const pendingPayments = payments.filter((payment) => payment.status === "pending").length;

    if (selectedModule && !selectedControlModule) {
        return (
            <section className="rounded-3xl border bg-card p-8 shadow-sm">
                <p className="text-xs font-black uppercase tracking-[0.2em] text-primary">System Owner</p>
                <h1 className="mt-3 text-3xl font-black">Unknown control module</h1>
                <p className="mt-2 text-sm text-muted-foreground">The requested owner-control module is not registered.</p>
                <Link href="/superadmin/control" className="mt-6 inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-black text-primary-foreground">Return to control room <ArrowRight className="h-4 w-4" /></Link>
            </section>
        );
    }

    if (selectedControlModule) {
        const Icon = selectedControlModule.icon;
        return (
            <main className="space-y-6">
                <section className="rounded-3xl border bg-card p-6 shadow-sm md:p-8">
                    <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
                        <div className="max-w-3xl">
                            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary"><Icon className="h-6 w-6" /></div>
                            <p className="mt-5 text-xs font-black uppercase tracking-[0.2em] text-primary">System Owner · Super Admin only</p>
                            <h1 className="mt-2 text-3xl font-black tracking-tight md:text-4xl">{selectedControlModule.title}</h1>
                            <p className="mt-3 text-sm leading-6 text-muted-foreground md:text-base">{selectedControlModule.description}</p>
                        </div>
                        <Link href="/superadmin/control" className="inline-flex h-11 items-center justify-center rounded-xl border px-4 text-sm font-black hover:border-primary hover:text-primary">All owner controls</Link>
                    </div>
                </section>

                {selectedControlModule.warning ? <section className="rounded-3xl border border-amber-500/30 bg-amber-500/10 p-5"><div className="flex gap-3"><TriangleAlert className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" /><div><p className="font-black text-amber-800">Protected operation</p><p className="mt-1 text-sm leading-6 text-amber-800/80">{selectedControlModule.warning}</p></div></div></section> : null}

                <section className="grid gap-4 lg:grid-cols-[1.4fr_0.6fr]">
                    <div className="rounded-3xl border bg-card p-6 shadow-sm">
                        <h2 className="text-xl font-black">Owner capabilities</h2>
                        <div className="mt-5 space-y-3">{selectedControlModule.capabilities.map((capability) => <div key={capability} className="flex gap-3 rounded-2xl border bg-muted/20 p-4"><ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" /><p className="text-sm leading-6">{capability}</p></div>)}</div>
                    </div>
                    <div className="space-y-4">
                        <div className="rounded-3xl border bg-card p-6 shadow-sm"><h2 className="font-black">Safety policy</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">System Owner actions are not allowed to become invisible superpowers. Sensitive changes must be authenticated, reasoned, approved where necessary and written to the audit trail.</p></div>
                        {selectedControlModule.links?.length ? <div className="rounded-3xl border bg-card p-6 shadow-sm"><h2 className="font-black">Connected LoanHub workspaces</h2><div className="mt-4 space-y-2">{selectedControlModule.links.map((link) => <Link key={link.href} href={link.href} className="flex items-center justify-between rounded-xl border px-4 py-3 text-sm font-bold hover:border-primary hover:text-primary"><span>{link.label}</span><ArrowRight className="h-4 w-4" /></Link>)}</div></div> : null}
                    </div>
                </section>
            </main>
        );
    }

    return (
        <main className="space-y-6">
            <section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8">
                <div className="absolute -left-20 -top-24 h-72 w-72 rounded-full bg-primary/10 blur-3xl" />
                <div className="relative">
                    <div className="inline-flex items-center gap-2 rounded-full border bg-background px-4 py-2 text-xs font-black text-muted-foreground"><ShieldCheck className="h-4 w-4 text-primary" />System Owner / Super Admin</div>
                    <h1 className="mt-5 text-3xl font-black tracking-tight md:text-4xl">LoanHub platform operating console</h1>
                    <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground md:text-base">Cross-tenant oversight for risk, compliance, security, billing, financial integrity, support, integrations and platform operations. Tenant administrators remain confined to their own companies.</p>
                    <div className="mt-6 max-w-2xl"><label htmlFor="owner-control-search" className="text-xs font-black uppercase tracking-[0.16em] text-muted-foreground">Global owner command search</label><input id="owner-control-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search risk, borrowers, billing, backups, security..." className="mt-2 h-12 w-full rounded-2xl border bg-background px-4 text-sm outline-none transition focus:border-primary" /></div>
                </div>
            </section>

            <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-3xl border bg-card p-5"><Building2 className="h-5 w-5 text-primary" /><p className="mt-3 text-2xl font-black">{companiesCount.toLocaleString()}</p><p className="text-xs font-bold text-muted-foreground">Companies · {approvedCompaniesCount} approved · {pendingCompaniesCount} pending</p></div>
                <div className="rounded-3xl border bg-card p-5"><Users className="h-5 w-5 text-primary" /><p className="mt-3 text-2xl font-black">{(companyStaffCount + borrowersCount).toLocaleString()}</p><p className="text-xs font-bold text-muted-foreground">Profiles · {borrowersCount} borrowers</p></div>
                <div className="rounded-3xl border bg-card p-5"><FileText className="h-5 w-5 text-primary" /><p className="mt-3 text-2xl font-black">{loanRequestsCount.toLocaleString()}</p><p className="text-xs font-bold text-muted-foreground">Loan requests · {openLoanRequestsCount} open</p></div>
                <div className="rounded-3xl border bg-card p-5"><WalletCards className="h-5 w-5 text-primary" /><p className="mt-3 text-2xl font-black">{formatMoney(successfulPaymentsTotal)}</p><p className="text-xs font-bold text-muted-foreground">Successful transaction value · {pendingPayments} pending</p></div>
            </section>

            <section>
                <div className="mb-4 flex items-end justify-between gap-4"><div><h2 className="text-xl font-black">Owner control modules</h2><p className="mt-1 text-sm text-muted-foreground">{filteredModules.length} platform capabilities available from this workspace.</p></div><Link href="/superadmin/reports" className="hidden items-center gap-2 text-sm font-black text-primary sm:inline-flex">Reports <FileChartColumn className="h-4 w-4" /></Link></div>
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{filteredModules.map((item) => <ModuleCard key={item.slug} module={item} />)}</div>
            </section>

            <section className="rounded-3xl border bg-card p-6 shadow-sm">
                <div className="flex items-start gap-4"><div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary"><LayoutDashboard className="h-5 w-5" /></div><div><h2 className="font-black">System Owner boundary</h2><p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground">This workspace deliberately separates observation from destructive mutation. Existing working LoanHub routes are connected directly; new high-risk controls are exposed as governed operational modules and stay non-destructive until their server-side audit, re-authentication and approval contracts are implemented.</p></div></div>
            </section>
        </main>
    );
}
