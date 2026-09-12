import type { Metadata } from "next";
import Link from "next/link";
import {
    ArrowRight,
    BadgeCheck,
    Banknote,
    BarChart3,
    BookOpen,
    BriefcaseBusiness,
    Building2,
    CheckCircle2,
    ClipboardCheck,
    FileLock2,
    FileText,
    HandCoins,
    Headphones,
    Landmark,
    LayoutDashboard,
    LockKeyhole,
    MessageCircle,
    Network,
    PhoneCall,
    ReceiptText,
    Scale,
    ShieldCheck,
    Sparkles,
    Users,
    WalletCards,
    Workflow,
    Zap,
} from "lucide-react";

import { LivePlatformStats } from "@/components/marketing/live-platform-stats";
import {
    PublicSectionHeading,
    PublicSiteFooter,
    PublicSiteHeader,
} from "@/components/marketing/public-site-shell";

export const metadata: Metadata = {
    title: "LoanHub | Lending marketplace and financial operating system for Lesotho",
    description:
        "Discover LoanHub: borrower marketplace, loan servicing, collections, payments, accounting, reporting, HR, communication, files and multi-branch operations for Lesotho.",
};

const capabilities = [
    {
        icon: HandCoins,
        title: "Marketplace & origination",
        description:
            "Borrowers can broadcast funding requests, lenders can review redacted opportunities, unlock authorised details and compete with structured offers.",
        points: ["Loan requests", "Lender offers", "Direct applications", "Affordability workflows"],
    },
    {
        icon: Users,
        title: "Borrower intelligence",
        description:
            "A shared borrower profile brings employment, affordability, consent, banking, supporting documents and lending history into one controlled workflow.",
        points: ["KYC profile", "Employment & income", "Bank accounts", "Consent-led sharing"],
    },
    {
        icon: WalletCards,
        title: "Loan servicing",
        description:
            "Move an approved facility through disbursement, schedules, allocations, balances, maturity, early settlement, restructuring and completion.",
        points: ["Repayment schedules", "Top-ups", "Early settlement", "Renewal policies"],
    },
    {
        icon: ClipboardCheck,
        title: "Collections & recovery",
        description:
            "Give collections teams a dedicated operating queue for due and overdue accounts, follow-up activity, recovery coordination and evidence.",
        points: ["Overdue monitoring", "Collection cases", "Follow-up activity", "Maturity recovery"],
    },
    {
        icon: Banknote,
        title: "Payments & treasury",
        description:
            "Control disbursements, repayments, transaction evidence, gateway-backed channels, daily branch cash, funding transfers and treasury submissions.",
        points: ["Repayment posting", "Payment evidence", "Branch cash", "Treasury controls"],
    },
    {
        icon: ReceiptText,
        title: "Accounting & reconciliation",
        description:
            "Operate a double-entry accounting foundation with chart of accounts, journals, trial balance, financial statements and reconciliation workflows.",
        points: ["Balanced journals", "Trial balance", "Profit & loss", "Bank reconciliation"],
    },
    {
        icon: BarChart3,
        title: "Reports & analytics",
        description:
            "Turn daily operations into branch, company and platform analytics with scheduled PDF/CSV reports and midnight reconciliation routines.",
        points: ["Portfolio analytics", "Branch performance", "Scheduled reports", "Operational reconciliation"],
    },
    {
        icon: BriefcaseBusiness,
        title: "HR & performance",
        description:
            "Run workforce records alongside lending operations: departments, positions, attendance, leave, payroll, assets, recruitment, training and performance reviews.",
        points: ["Attendance & leave", "Payroll", "Assets", "Goals & reviews"],
    },
    {
        icon: MessageCircle,
        title: "Realtime collaboration",
        description:
            "Keep authorised teams and borrowers connected with persistent notifications, presence, group/direct chat, read state, voice notes and attachments.",
        points: ["Realtime chat", "Presence", "Voice notes", "Actionable notifications"],
    },
    {
        icon: PhoneCall,
        title: "Call management",
        description:
            "Support company-controlled calling, recording policy, supervision, retention and quality review when approved WebRTC/SIP infrastructure is provisioned.",
        points: ["Call records", "Recording controls", "Quality review", "Supervision policy"],
    },
    {
        icon: FileLock2,
        title: "Documents & files",
        description:
            "Manage borrower evidence and company work with permissioned uploads, integrity checks, encryption, visibility controls, document revisions and signatures.",
        points: ["Managed files", "Document studio", "Revisions", "Controlled sharing"],
    },
    {
        icon: Network,
        title: "Company operating system",
        description:
            "Coordinate branches, staff roles, client cases, APIs, webhooks, institution governance, company websites and workspace tools from one tenant-aware platform.",
        points: ["Multi-branch tenancy", "API & webhooks", "Client casework", "Workspace tools"],
    },
];

const borrowerJourney = [
    ["01", "Create your account", "Register once, secure your identity and build the borrower profile used across LoanHub."],
    ["02", "Complete your assessment", "Add employment, income, expenses, bank accounts, supporting documents and the consents you choose to give."],
    ["03", "Request funding", "Create a loan request and make it available to eligible lenders through the marketplace workflow."],
    ["04", "Compare offers", "Review structured lender offers and choose the facility that fits your needs instead of repeating the same application everywhere."],
    ["05", "Manage the loan", "Follow repayment schedules, payments, documents, messages, reminders and loan status from your own workspace."],
];

const institutionJourney = [
    ["01", "Register the institution", "Create the company workspace and complete the approval and governance details required by LoanHub."],
    ["02", "Build the operating structure", "Create branches, add staff and assign business roles so each team member sees the work they are authorised to perform."],
    ["03", "Configure lending", "Create products, calculation methods, fees, decision controls and the origination workflow used by the institution."],
    ["04", "Acquire and evaluate business", "Work with existing clients, direct applications and marketplace requests; review affordability and supporting evidence."],
    ["05", "Service and recover", "Approve, disburse, schedule, collect, restructure, settle and recover facilities while preserving an auditable record."],
    ["06", "Run the institution", "Use treasury, accounting, reporting, HR, performance, documents, communication and analytics without leaving LoanHub."],
];

const operatingRoles = [
    {
        title: "Platform governance",
        text: "SuperAdmin and platform teams govern institutions, plans, service-wide reporting, support, compliance, incidents and platform operations.",
    },
    {
        title: "Institution leadership",
        text: "Company owners, administrators and branch managers control settings, branches, staff, lending, billing, finance and branch performance.",
    },
    {
        title: "Professional operations",
        text: "Loan, finance, collections, compliance, audit, risk, treasury, HR, performance, support and technology roles work within scoped permissions.",
    },
    {
        title: "Borrowers",
        text: "Borrowers manage their own profile, requests, offers, loans, payments, files and conversations without belonging permanently to one lender.",
    },
];

const securityControls = [
    "Isolated company tenants and branch-aware access",
    "Role-based permissions across operational teams",
    "Auditable business actions and request correlation",
    "AES-GCM encryption at rest for managed files and chat content",
    "HTTPS/WSS production transport through the public edge",
    "Safe user-facing error references while technical diagnostics remain restricted",
    "Permissioned file visibility, checksums and controlled sharing",
    "Platform-owner support access designed to be time-limited and auditable",
];

const faq = [
    {
        question: "Is LoanHub only for one loan company?",
        answer: "No. LoanHub is multi-tenant. Independent institutions operate inside isolated company and branch scopes while the platform layer governs the service as a whole.",
    },
    {
        question: "Does a borrower belong to the company that first registers them?",
        answer: "The borrower profile is designed as a platform-level profile. Company-specific agreements and authorised relationship data remain scoped to the relevant lender while the borrower can work across the marketplace.",
    },
    {
        question: "Can institutions run multiple branches?",
        answer: "Yes. Branches, branch staff, branch lending activity, collections, performance and reporting are first-class parts of the company operating model.",
    },
    {
        question: "Does LoanHub include accounting?",
        answer: "Yes. LoanHub includes a double-entry accounting foundation with journals, chart of accounts, trial balance and financial reporting. Production accounting policies should still be reviewed by a qualified accountant.",
    },
    {
        question: "Are documents and messages protected?",
        answer: "LoanHub supports permissioned managed files and AES-GCM encryption at rest for managed files and chat text. Production traffic is protected through HTTPS/WSS. This is server-managed encryption, not client-to-client end-to-end encryption.",
    },
    {
        question: "Does LoanHub support payment integrations?",
        answer: "LoanHub has payment, gateway, treasury and reconciliation workflows. Live electronic channels depend on the relevant provider onboarding, credentials and approvals for the institution using them.",
    },
    {
        question: "Can staff communicate and manage calls in LoanHub?",
        answer: "Yes. Internal realtime chat, notifications and file attachments are built in. Controlled calling and recording features require approved WebRTC/SIP infrastructure and company policy before live use.",
    },
    {
        question: "Where can a new user learn the system?",
        answer: "Use the public LoanHub User Manual and Documentation Centre linked throughout this website. They explain onboarding, borrower workflows, institution operations, finance, reporting, security and troubleshooting.",
    },
];

export default function LoanHubLandingPage() {
    return (
        <div className="min-h-screen bg-white text-slate-950 dark:bg-slate-950 dark:text-white">
            <PublicSiteHeader />

            <main>
                <section className="relative overflow-hidden bg-slate-950 text-white">
                    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
                        <div className="absolute -left-24 top-16 h-80 w-80 rounded-full bg-emerald-500/20 blur-3xl" />
                        <div className="absolute right-[-6rem] top-[-4rem] h-96 w-96 rounded-full bg-sky-500/15 blur-3xl" />
                        <div className="absolute bottom-[-8rem] left-1/2 h-80 w-80 -translate-x-1/2 rounded-full bg-violet-500/10 blur-3xl" />
                    </div>

                    <div className="relative mx-auto grid max-w-7xl gap-12 px-4 py-16 sm:px-6 sm:py-20 lg:grid-cols-[1.08fr_.92fr] lg:items-center lg:px-8 lg:py-28">
                        <div>
                            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-400/25 bg-emerald-400/10 px-3 py-1.5 text-xs font-black uppercase tracking-[0.18em] text-emerald-300">
                                <Sparkles className="h-4 w-4" />
                                Lending infrastructure for Lesotho
                            </div>
                            <h1 className="mt-6 max-w-4xl text-4xl font-black leading-[1.02] tracking-[-0.04em] sm:text-6xl lg:text-7xl">
                                One connected system for the entire lending journey.
                            </h1>
                            <p className="mt-6 max-w-2xl text-base leading-7 text-slate-300 sm:text-xl sm:leading-8">
                                LoanHub connects borrowers, lenders, branches and professional financial teams through a secure marketplace and a complete loan operating system—from first request to final repayment, reporting and recovery.
                            </p>

                            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                                <Link
                                    href="/choose-account-type"
                                    className="inline-flex items-center justify-center gap-2 rounded-2xl bg-emerald-400 px-6 py-3.5 text-sm font-black text-slate-950 shadow-lg shadow-emerald-500/20 transition hover:-translate-y-0.5 hover:bg-emerald-300"
                                >
                                    Start with LoanHub <ArrowRight className="h-4 w-4" />
                                </Link>
                                <Link
                                    href="/manual"
                                    className="inline-flex items-center justify-center gap-2 rounded-2xl border border-white/15 bg-white/5 px-6 py-3.5 text-sm font-black text-white transition hover:bg-white/10"
                                >
                                    <BookOpen className="h-4 w-4" /> Read the user manual
                                </Link>
                            </div>

                            <div className="mt-8 flex flex-wrap gap-x-6 gap-y-3 text-sm font-semibold text-slate-300">
                                {["Borrower marketplace", "Multi-branch operations", "Accounting & reports", "Realtime collaboration"].map((item) => (
                                    <span key={item} className="inline-flex items-center gap-2">
                                        <CheckCircle2 className="h-4 w-4 text-emerald-400" /> {item}
                                    </span>
                                ))}
                            </div>
                        </div>

                        <div className="relative">
                            <div className="absolute -inset-6 rounded-[2rem] bg-gradient-to-br from-emerald-400/20 via-transparent to-sky-500/20 blur-2xl" />
                            <div className="relative overflow-hidden rounded-[2rem] border border-white/10 bg-slate-900/90 p-5 shadow-2xl shadow-black/30 backdrop-blur sm:p-7">
                                <div className="flex items-center justify-between gap-4 border-b border-white/10 pb-5">
                                    <div>
                                        <p className="text-xs font-black uppercase tracking-[0.2em] text-emerald-300">LoanHub operating map</p>
                                        <p className="mt-1 text-lg font-black">From opportunity to evidence</p>
                                    </div>
                                    <span className="rounded-xl bg-emerald-400/10 p-2.5 text-emerald-300">
                                        <LayoutDashboard className="h-5 w-5" />
                                    </span>
                                </div>

                                <div className="mt-5 grid gap-3 sm:grid-cols-2">
                                    {[
                                        ["Marketplace", "Requests → offers", HandCoins],
                                        ["Servicing", "Disburse → repay", Workflow],
                                        ["Finance", "Post → reconcile", ReceiptText],
                                        ["Reporting", "Measure → improve", BarChart3],
                                    ].map(([title, text, Icon]) => {
                                        const IconComponent = Icon as typeof HandCoins;
                                        return (
                                            <div key={title as string} className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                                                <IconComponent className="h-5 w-5 text-emerald-300" />
                                                <p className="mt-4 font-black">{title as string}</p>
                                                <p className="mt-1 text-sm text-slate-400">{text as string}</p>
                                            </div>
                                        );
                                    })}
                                </div>

                                <div className="mt-5 rounded-2xl border border-emerald-400/20 bg-emerald-400/[0.06] p-4">
                                    <div className="flex items-start gap-3">
                                        <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-300" />
                                        <div>
                                            <p className="font-black">Governed at every layer</p>
                                            <p className="mt-1 text-sm leading-6 text-slate-300">
                                                Tenant isolation, branch scope, professional roles, audit evidence and controlled files follow the same operating model.
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="relative mx-auto max-w-7xl px-4 pb-14 sm:px-6 lg:px-8">
                        <div className="rounded-[1.75rem] border border-white/10 bg-white/[0.04] p-5 backdrop-blur sm:p-6 [&_article]:border-white/10 [&_article]:bg-white/[0.04] [&_article_p]:text-white [&_article_p+_p]:text-slate-400 [&_article_span]:bg-white/5">
                            <LivePlatformStats compact />
                        </div>
                    </div>
                </section>

                <section id="platform" className="scroll-mt-24 bg-slate-50 py-20 dark:bg-slate-900/40 sm:py-24">
                    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
                        <PublicSectionHeading
                            eyebrow="One platform, many operating teams"
                            title="LoanHub is more than a loan register."
                            description="It combines marketplace acquisition, lending operations and the surrounding work a professional financial institution needs to run with control and visibility."
                            align="center"
                        />

                        <div className="mt-12 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                            {capabilities.map(({ icon: Icon, title, description, points }) => (
                                <article
                                    key={title}
                                    className="group rounded-[1.5rem] border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-1 hover:border-emerald-300 hover:shadow-xl hover:shadow-slate-200/60 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-emerald-800 dark:hover:shadow-black/20"
                                >
                                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-700 transition group-hover:bg-emerald-500 group-hover:text-white dark:bg-emerald-950/60 dark:text-emerald-300">
                                        <Icon className="h-5 w-5" />
                                    </div>
                                    <h3 className="mt-5 text-xl font-black tracking-tight">{title}</h3>
                                    <p className="mt-3 text-sm leading-6 text-slate-600 dark:text-slate-300">{description}</p>
                                    <div className="mt-5 flex flex-wrap gap-2">
                                        {points.map((point) => (
                                            <span key={point} className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                                                {point}
                                            </span>
                                        ))}
                                    </div>
                                </article>
                            ))}
                        </div>
                    </div>
                </section>

                <section className="py-20 sm:py-24">
                    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
                        <PublicSectionHeading
                            eyebrow="Real platform activity"
                            title="See LoanHub grow without exposing customer data."
                            description="These figures come from LoanHub itself and are published only as platform-wide counts. Personal details, company balances, loan values and tenant-level breakdowns stay private."
                        />
                        <div className="mt-10">
                            <LivePlatformStats />
                        </div>
                    </div>
                </section>

                <section id="borrowers" className="scroll-mt-24 overflow-hidden bg-slate-950 py-20 text-white sm:py-24">
                    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
                        <div className="grid gap-12 lg:grid-cols-[.78fr_1.22fr] lg:items-start">
                            <div className="lg:sticky lg:top-28">
                                <p className="text-xs font-black uppercase tracking-[0.24em] text-emerald-300">For borrowers</p>
                                <h2 className="mt-4 text-3xl font-black tracking-tight sm:text-5xl">One profile. More control over your borrowing journey.</h2>
                                <p className="mt-5 text-base leading-7 text-slate-300">
                                    LoanHub is designed so a borrower can build a reusable financial assessment, request funding, compare offers and keep track of the resulting loan relationship from one place.
                                </p>
                                <Link href="/borrower-registration" className="mt-7 inline-flex items-center gap-2 rounded-2xl bg-emerald-400 px-5 py-3 text-sm font-black text-slate-950 hover:bg-emerald-300">
                                    Register as a borrower <ArrowRight className="h-4 w-4" />
                                </Link>
                            </div>

                            <div className="grid gap-4">
                                {borrowerJourney.map(([step, title, text]) => (
                                    <article key={step} className="grid gap-4 rounded-3xl border border-white/10 bg-white/[0.04] p-5 sm:grid-cols-[64px_1fr] sm:p-6">
                                        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-400 font-black text-slate-950">{step}</div>
                                        <div>
                                            <h3 className="text-xl font-black">{title}</h3>
                                            <p className="mt-2 leading-7 text-slate-300">{text}</p>
                                        </div>
                                    </article>
                                ))}
                            </div>
                        </div>
                    </div>
                </section>

                <section id="institutions" className="scroll-mt-24 py-20 sm:py-24">
                    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
                        <div className="grid gap-12 lg:grid-cols-[1.15fr_.85fr]">
                            <div>
                                <PublicSectionHeading
                                    eyebrow="For lenders and financial institutions"
                                    title="Build the lending business around the loan book—not beside it."
                                    description="LoanHub joins customer acquisition, loan servicing, finance, workforce and governance so branches and specialist teams can work from the same controlled source of truth."
                                />
                                <div className="mt-8 grid gap-3 sm:grid-cols-2">
                                    {institutionJourney.map(([step, title, text]) => (
                                        <article key={step} className="rounded-2xl border border-slate-200 bg-slate-50 p-5 dark:border-slate-800 dark:bg-slate-900">
                                            <p className="text-xs font-black text-emerald-600 dark:text-emerald-400">STEP {step}</p>
                                            <h3 className="mt-2 font-black">{title}</h3>
                                            <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">{text}</p>
                                        </article>
                                    ))}
                                </div>
                            </div>

                            <aside className="rounded-[2rem] bg-emerald-500 p-7 text-slate-950 shadow-2xl shadow-emerald-500/10 sm:p-9">
                                <Building2 className="h-10 w-10" />
                                <h3 className="mt-6 text-3xl font-black tracking-tight">A workspace for the whole institution.</h3>
                                <p className="mt-4 leading-7 text-emerald-950/80">
                                    Banks, microfinance institutions, loan companies, cooperatives, development finance institutions and government lending programmes can be represented through LoanHub&apos;s institution model.
                                </p>
                                <div className="mt-7 grid gap-3">
                                    {["Company and branch administration", "Professional staff roles", "Borrower/client casework", "Loan products and decision controls", "Finance, treasury and accounting", "Analytics, reports and audit evidence"].map((item) => (
                                        <div key={item} className="flex items-center gap-3 rounded-xl bg-white/45 px-4 py-3 text-sm font-bold">
                                            <BadgeCheck className="h-4 w-4 shrink-0" /> {item}
                                        </div>
                                    ))}
                                </div>
                                <Link href="/register-company-admin" className="mt-7 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-slate-950 px-5 py-3.5 text-sm font-black text-white transition hover:bg-slate-900">
                                    Register an institution <ArrowRight className="h-4 w-4" />
                                </Link>
                            </aside>
                        </div>
                    </div>
                </section>

                <section className="bg-slate-50 py-20 dark:bg-slate-900/40 sm:py-24">
                    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
                        <PublicSectionHeading
                            eyebrow="Role-aware operations"
                            title="The right workspace for the right responsibility."
                            description="LoanHub separates authority by platform, company, branch and borrower context so specialist teams can work quickly without turning every user into an administrator."
                            align="center"
                        />
                        <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                            {operatingRoles.map((role, index) => (
                                <article key={role.title} className="rounded-3xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
                                    <span className="text-4xl font-black text-emerald-500/30">0{index + 1}</span>
                                    <h3 className="mt-5 text-lg font-black">{role.title}</h3>
                                    <p className="mt-3 text-sm leading-6 text-slate-600 dark:text-slate-300">{role.text}</p>
                                </article>
                            ))}
                        </div>
                    </div>
                </section>

                <section id="security" className="scroll-mt-24 py-20 sm:py-24">
                    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
                        <div className="grid gap-12 rounded-[2rem] bg-slate-950 p-6 text-white sm:p-10 lg:grid-cols-[.85fr_1.15fr] lg:p-14">
                            <div>
                                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-400 text-slate-950">
                                    <LockKeyhole className="h-6 w-6" />
                                </div>
                                <p className="mt-7 text-xs font-black uppercase tracking-[0.24em] text-emerald-300">Security & governance</p>
                                <h2 className="mt-4 text-3xl font-black tracking-tight sm:text-5xl">Control is part of the workflow, not an afterthought.</h2>
                                <p className="mt-5 leading-7 text-slate-300">
                                    LoanHub&apos;s security model is built around tenant boundaries, active roles, branch context, protected evidence and traceable operations. Sensitive diagnostics remain separated from ordinary user-facing errors.
                                </p>
                            </div>
                            <div className="grid gap-3 sm:grid-cols-2">
                                {securityControls.map((control) => (
                                    <div key={control} className="flex gap-3 rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                                        <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-300" />
                                        <p className="text-sm font-semibold leading-6 text-slate-200">{control}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </section>

                <section className="bg-emerald-50 py-20 dark:bg-emerald-950/20 sm:py-24">
                    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
                        <PublicSectionHeading
                            eyebrow="Learn before you operate"
                            title="A public manual and documentation centre are part of the product."
                            description="New borrowers, institution owners and staff should not have to guess how the platform works. LoanHub now puts the most important operating guidance directly on the public website."
                        />
                        <div className="mt-10 grid gap-4 lg:grid-cols-3">
                            <Link href="/manual" className="group rounded-3xl bg-slate-950 p-7 text-white transition hover:-translate-y-1 hover:shadow-xl">
                                <BookOpen className="h-8 w-8 text-emerald-300" />
                                <h3 className="mt-7 text-2xl font-black">Complete user manual</h3>
                                <p className="mt-3 text-sm leading-6 text-slate-300">Getting started, borrower workflows, institution setup, lending operations, payments, collections, finance, reporting and troubleshooting.</p>
                                <span className="mt-7 inline-flex items-center gap-2 text-sm font-black text-emerald-300">Open manual <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" /></span>
                            </Link>
                            <Link href="/documentation" className="group rounded-3xl border border-emerald-200 bg-white p-7 transition hover:-translate-y-1 hover:shadow-xl dark:border-emerald-900 dark:bg-slate-900">
                                <FileText className="h-8 w-8 text-emerald-600 dark:text-emerald-300" />
                                <h3 className="mt-7 text-2xl font-black">Documentation centre</h3>
                                <p className="mt-3 text-sm leading-6 text-slate-600 dark:text-slate-300">Quick-start guides, role guidance, security notes, operational checklists, privacy information and technical access points.</p>
                                <span className="mt-7 inline-flex items-center gap-2 text-sm font-black text-emerald-700 dark:text-emerald-300">Browse documentation <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" /></span>
                            </Link>
                            <div className="rounded-3xl border border-emerald-200 bg-white p-7 dark:border-emerald-900 dark:bg-slate-900">
                                <Headphones className="h-8 w-8 text-emerald-600 dark:text-emerald-300" />
                                <h3 className="mt-7 text-2xl font-black">Start in the right place</h3>
                                <p className="mt-3 text-sm leading-6 text-slate-600 dark:text-slate-300">Borrowers and institutions have separate registration paths, while existing users go straight to secure sign-in.</p>
                                <div className="mt-6 grid gap-2 text-sm font-bold">
                                    <Link href="/borrower-registration" className="rounded-xl bg-slate-100 px-4 py-3 hover:bg-emerald-100 dark:bg-slate-800 dark:hover:bg-emerald-950">Borrower registration</Link>
                                    <Link href="/register-company-admin" className="rounded-xl bg-slate-100 px-4 py-3 hover:bg-emerald-100 dark:bg-slate-800 dark:hover:bg-emerald-950">Institution registration</Link>
                                    <Link href="/login" className="rounded-xl bg-slate-100 px-4 py-3 hover:bg-emerald-100 dark:bg-slate-800 dark:hover:bg-emerald-950">Existing user sign-in</Link>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                <section className="py-20 sm:py-24">
                    <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
                        <PublicSectionHeading
                            eyebrow="Frequently asked questions"
                            title="Know what LoanHub is designed to do."
                            description="The answers below reflect the implemented platform model and its current production boundaries."
                            align="center"
                        />
                        <div className="mt-10 grid gap-3">
                            {faq.map((item) => (
                                <details key={item.question} className="group rounded-2xl border border-slate-200 bg-white p-5 open:border-emerald-300 open:shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:open:border-emerald-800">
                                    <summary className="cursor-pointer list-none pr-8 font-black marker:hidden">
                                        {item.question}
                                    </summary>
                                    <p className="mt-3 text-sm leading-7 text-slate-600 dark:text-slate-300">{item.answer}</p>
                                </details>
                            ))}
                        </div>
                    </div>
                </section>

                <section className="px-4 pb-20 sm:px-6 sm:pb-24 lg:px-8">
                    <div className="mx-auto max-w-7xl overflow-hidden rounded-[2rem] bg-gradient-to-br from-emerald-500 to-emerald-300 p-7 text-slate-950 sm:p-10 lg:p-14">
                        <div className="grid gap-8 lg:grid-cols-[1fr_auto] lg:items-end">
                            <div>
                                <p className="text-xs font-black uppercase tracking-[0.22em]">Ready when you are</p>
                                <h2 className="mt-4 max-w-3xl text-3xl font-black tracking-tight sm:text-5xl">Borrow, lend and operate from one connected financial platform.</h2>
                                <p className="mt-4 max-w-2xl leading-7 text-emerald-950/80">Choose the account path that matches your role, or read the manual first and understand the full workflow before creating an account.</p>
                            </div>
                            <div className="flex flex-col gap-3 sm:flex-row lg:flex-col xl:flex-row">
                                <Link href="/choose-account-type" className="inline-flex items-center justify-center gap-2 rounded-2xl bg-slate-950 px-6 py-3.5 text-sm font-black text-white hover:bg-slate-900">Create an account <ArrowRight className="h-4 w-4" /></Link>
                                <Link href="/manual" className="inline-flex items-center justify-center gap-2 rounded-2xl bg-white/60 px-6 py-3.5 text-sm font-black hover:bg-white"><BookOpen className="h-4 w-4" /> Read manual</Link>
                            </div>
                        </div>
                    </div>
                </section>
            </main>

            <PublicSiteFooter />
        </div>
    );
}
