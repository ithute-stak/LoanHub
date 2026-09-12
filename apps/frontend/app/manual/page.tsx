import type { Metadata } from "next";
import Link from "next/link";
import {
    AlertTriangle,
    ArrowLeft,
    BadgeCheck,
    BookOpen,
    Building2,
    CheckCircle2,
    CircleHelp,
    FileLock2,
    HandCoins,
    KeyRound,
    Landmark,
    MessageCircle,
    ReceiptText,
    ShieldCheck,
    Users,
    WalletCards,
} from "lucide-react";

import { PrintManualButton } from "@/components/marketing/print-manual-button";
import { PublicSiteFooter, PublicSiteHeader } from "@/components/marketing/public-site-shell";

export const metadata: Metadata = {
    title: "LoanHub User Manual | Borrowers, institutions and staff",
    description:
        "Public LoanHub user manual covering account setup, borrower workflows, institution administration, lending, payments, collections, accounting, reports, files, communication and troubleshooting.",
};

const sections = [
    ["getting-started", "Getting started"],
    ["borrower", "Borrower guide"],
    ["institution", "Institution setup"],
    ["roles", "Roles & access"],
    ["lending", "Lending lifecycle"],
    ["payments", "Payments & collections"],
    ["finance", "Accounting & reporting"],
    ["workforce", "HR & operations"],
    ["communication", "Chat, calls & files"],
    ["security", "Security & privacy"],
    ["troubleshooting", "Troubleshooting"],
] as const;

const roleRows = [
    ["Platform owner / SuperAdmin", "Service-wide institutions, plans, platform finance, reports, audit, incidents and technical operations."],
    ["Company owner", "Highest institution authority for settings, branches, staff, products, lending, billing, HR, accounting and reports."],
    ["Company administrator", "Day-to-day institution administration and cross-department coordination."],
    ["Branch manager", "Branch staff, lending work, collections, performance and branch reporting."],
    ["Loan officer", "Marketplace requests, authorised detail unlocks, assessment and lender offers."],
    ["Finance / treasury", "Disbursements, repayments, reconciliation, accounting, cash and financial evidence."],
    ["Collections officer", "Due and overdue accounts, recovery cases and collection follow-up."],
    ["Compliance / risk / audit", "Access review, evidence, regulatory controls, credit risk and independent oversight."],
    ["HR / performance", "Employee records, reporting lines, attendance, payroll, goals and reviews."],
    ["Customer / IT support", "Authorised user assistance, notifications, communication, incidents and safe escalation."],
    ["Borrower", "Personal profile, funding requests, offers, loans, payments, files and conversations."],
] as const;

function ManualSection({
    id,
    icon: Icon,
    title,
    intro,
    children,
}: {
    id: string;
    icon: typeof BookOpen;
    title: string;
    intro: string;
    children: React.ReactNode;
}) {
    return (
        <section id={id} className="scroll-mt-28 border-t border-slate-200 py-12 first:border-t-0 first:pt-0 dark:border-slate-800">
            <div className="flex items-start gap-4">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300">
                    <Icon className="h-5 w-5" />
                </span>
                <div>
                    <h2 className="text-2xl font-black tracking-tight sm:text-3xl">{title}</h2>
                    <p className="mt-2 max-w-3xl leading-7 text-slate-600 dark:text-slate-300">{intro}</p>
                </div>
            </div>
            <div className="mt-7 space-y-7 pl-0 sm:pl-[60px]">{children}</div>
        </section>
    );
}

function StepList({ items }: { items: Array<[string, string]> }) {
    return (
        <ol className="grid gap-3">
            {items.map(([title, text], index) => (
                <li key={title} className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 sm:grid-cols-[36px_1fr] dark:border-slate-800 dark:bg-slate-900/60">
                    <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-950 text-xs font-black text-white dark:bg-emerald-400 dark:text-slate-950">
                        {index + 1}
                    </span>
                    <div>
                        <h3 className="font-black">{title}</h3>
                        <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">{text}</p>
                    </div>
                </li>
            ))}
        </ol>
    );
}

function Note({ children, warning = false }: { children: React.ReactNode; warning?: boolean }) {
    const Icon = warning ? AlertTriangle : ShieldCheck;
    return (
        <div className={`flex gap-3 rounded-2xl border p-4 text-sm leading-6 ${warning ? "border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100" : "border-emerald-200 bg-emerald-50 text-emerald-950 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-100"}`}>
            <Icon className="mt-0.5 h-5 w-5 shrink-0" />
            <div>{children}</div>
        </div>
    );
}

export default function UserManualPage() {
    return (
        <div className="min-h-screen bg-white text-slate-950 dark:bg-slate-950 dark:text-white">
            <PublicSiteHeader />
            <main>
                <section className="bg-slate-950 text-white print:bg-white print:text-black">
                    <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8 lg:py-20">
                        <Link href="/" className="inline-flex items-center gap-2 text-sm font-bold text-slate-300 hover:text-emerald-300 print:hidden">
                            <ArrowLeft className="h-4 w-4" /> Back to LoanHub website
                        </Link>
                        <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_auto] lg:items-end">
                            <div>
                                <p className="text-xs font-black uppercase tracking-[0.24em] text-emerald-300 print:text-emerald-700">Public operating guide</p>
                                <h1 className="mt-4 max-w-4xl text-4xl font-black tracking-tight sm:text-6xl">LoanHub User Manual</h1>
                                <p className="mt-5 max-w-3xl text-base leading-7 text-slate-300 print:text-slate-700 sm:text-lg">
                                    A practical guide for borrowers, institution owners, branch teams and specialist staff. Use it before onboarding, during training, or whenever you need to understand where a LoanHub workflow belongs.
                                </p>
                            </div>
                            <PrintManualButton />
                        </div>
                    </div>
                </section>

                <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 lg:grid-cols-[250px_minmax(0,1fr)] lg:px-8 lg:py-16">
                    <aside className="print:hidden lg:sticky lg:top-24 lg:h-fit">
                        <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-900">
                            <p className="px-2 text-xs font-black uppercase tracking-[0.2em] text-slate-400">In this manual</p>
                            <nav className="mt-3 grid gap-1" aria-label="Manual sections">
                                {sections.map(([href, label]) => (
                                    <Link key={href} href={`#${href}`} className="rounded-xl px-3 py-2 text-sm font-bold text-slate-600 transition hover:bg-white hover:text-emerald-700 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-emerald-300">
                                        {label}
                                    </Link>
                                ))}
                            </nav>
                            <Link href="/documentation" className="mt-4 flex items-center justify-between rounded-xl bg-slate-950 px-3 py-3 text-sm font-black text-white dark:bg-emerald-400 dark:text-slate-950">
                                Documentation centre <BookOpen className="h-4 w-4" />
                            </Link>
                        </div>
                    </aside>

                    <article className="min-w-0">
                        <ManualSection
                            id="getting-started"
                            icon={KeyRound}
                            title="Getting started"
                            intro="LoanHub has separate entry paths for borrowers, institutions and existing users. Start with the account type that matches the work you need to do."
                        >
                            <div className="grid gap-4 md:grid-cols-3">
                                <Link href="/borrower-registration" className="rounded-2xl border border-slate-200 p-5 transition hover:border-emerald-300 hover:bg-emerald-50 dark:border-slate-800 dark:hover:border-emerald-800 dark:hover:bg-emerald-950/30">
                                    <Users className="h-6 w-6 text-emerald-600" />
                                    <h3 className="mt-4 font-black">Borrower</h3>
                                    <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">Create a personal account and complete your borrower assessment.</p>
                                </Link>
                                <Link href="/register-company-admin" className="rounded-2xl border border-slate-200 p-5 transition hover:border-emerald-300 hover:bg-emerald-50 dark:border-slate-800 dark:hover:border-emerald-800 dark:hover:bg-emerald-950/30">
                                    <Building2 className="h-6 w-6 text-emerald-600" />
                                    <h3 className="mt-4 font-black">Institution</h3>
                                    <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">Register the company/institution and its initial administrator.</p>
                                </Link>
                                <Link href="/login" className="rounded-2xl border border-slate-200 p-5 transition hover:border-emerald-300 hover:bg-emerald-50 dark:border-slate-800 dark:hover:border-emerald-800 dark:hover:bg-emerald-950/30">
                                    <Landmark className="h-6 w-6 text-emerald-600" />
                                    <h3 className="mt-4 font-black">Existing user</h3>
                                    <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">Sign in and LoanHub directs you to the workspace allowed by your role.</p>
                                </Link>
                            </div>
                            <StepList items={[
                                ["Use your own account", "Do not share passwords or use another staff member's login. Audit and approval evidence depends on knowing who performed each action."],
                                ["Confirm the active institution and branch", "Company staff should confirm their active company, branch and role before changing records."],
                                ["Complete the information relevant to your role", "Borrowers complete personal and affordability information; institution teams complete company, branch, staff and lending setup."],
                                ["Use business references when asking for help", "Where LoanHub displays a friendly request, loan, client or incident reference, use it when communicating with support rather than copying internal database identifiers."],
                            ]} />
                        </ManualSection>

                        <ManualSection
                            id="borrower"
                            icon={Users}
                            title="Borrower guide"
                            intro="The borrower workspace is designed to let a person build a reusable profile, request funding and manage resulting loans without becoming the permanent property of one lending company."
                        >
                            <StepList items={[
                                ["Register and verify your account", "Complete borrower registration with the identity and contact information requested by LoanHub."],
                                ["Build the borrower profile", "Add employment status, employer/job information, income, living expenses, existing debt and residential details."],
                                ["Add banking and assessment details", "Maintain the banking information and affordability inputs used by authorised lending workflows."],
                                ["Upload supporting evidence", "Add identity, payslip, bank statement, residence or employment evidence where the assessment requires it."],
                                ["Review consent choices", "Profile sharing, document sharing and credit checks are controlled by explicit borrower consent fields. Read what you are authorising before continuing."],
                                ["Create a loan request", "State the funding need and submit the request into the marketplace when you are ready for eligible lenders to respond."],
                                ["Compare lender offers", "Review the terms returned through LoanHub before accepting an offer. Do not accept based only on the instalment; understand the full repayable amount and schedule."],
                                ["Manage an active loan", "Use your loan workspace to follow due dates, payment status, balance, reminders, documents and conversations."],
                                ["Keep your profile current", "Update relevant employment, financial, banking and supporting information when it changes so future evaluations are based on current facts."],
                            ]} />
                            <Note>
                                LoanHub separates the shared borrower profile from lender-specific agreements. A lender should only access borrower information through the permissions and relationship controls provided by the platform.
                            </Note>
                        </ManualSection>

                        <ManualSection
                            id="institution"
                            icon={Building2}
                            title="Institution setup"
                            intro="Institution owners and administrators create the structure within which branches, staff, lending products and operating teams work."
                        >
                            <StepList items={[
                                ["Register the institution", "Provide the institution identity, registration/contact information and initial administrator details required by the onboarding flow."],
                                ["Complete governance and settings", "Review institution settings, governance information, billing/subscription state and any platform approval requirements."],
                                ["Create branches", "Add headquarters and operating branches with their district, town, contacts and active status."],
                                ["Add staff memberships", "Create or invite the people who work for the institution and give them only the roles required for their responsibilities."],
                                ["Configure lending products", "Define product terms, calculation methods, repayment behaviour, fees and other controls before officers create or approve facilities."],
                                ["Configure finance and integrations", "Where applicable, complete payment, treasury, credit-bureau, gateway or webhook configuration through the authorised settings screens."],
                                ["Train each team in its own queue", "Loan officers, finance, collections, compliance, HR and other functions should use their role-specific workflows rather than sharing an owner/admin account."],
                            ]} />
                            <Note warning>
                                Live payment, credit-bureau and controlled-calling integrations can require third-party onboarding, credentials, provider approval or infrastructure. A configuration screen does not by itself mean an external provider has activated the service.
                            </Note>
                        </ManualSection>

                        <ManualSection
                            id="roles"
                            icon={ShieldCheck}
                            title="Roles and access"
                            intro="LoanHub uses platform roles, company memberships, branch context and specialist business roles to decide what a user may see or change."
                        >
                            <div className="overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-800">
                                <div className="overflow-x-auto">
                                    <table className="w-full min-w-[680px] text-left text-sm">
                                        <thead className="bg-slate-950 text-white">
                                            <tr>
                                                <th className="px-4 py-3 font-black">Role group</th>
                                                <th className="px-4 py-3 font-black">Primary responsibility</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                                            {roleRows.map(([role, responsibility]) => (
                                                <tr key={role} className="align-top">
                                                    <td className="px-4 py-3 font-bold">{role}</td>
                                                    <td className="px-4 py-3 leading-6 text-slate-600 dark:text-slate-300">{responsibility}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                            <Note>
                                If a screen or action is missing, first confirm the active role, company and branch. Do not solve a permission problem by giving a user a broader role than their job requires.
                            </Note>
                        </ManualSection>

                        <ManualSection
                            id="lending"
                            icon={HandCoins}
                            title="Lending lifecycle"
                            intro="LoanHub supports both marketplace-led and direct professional lending workflows, then manages the resulting facility through servicing and completion."
                        >
                            <StepList items={[
                                ["Receive or create the application", "A lender can work with marketplace requests, direct applications or authorised existing-client workflows."],
                                ["Evaluate affordability and evidence", "Review the borrower profile, income, expenses, debt, bank information, supporting files, consent and any permitted credit/compliance evidence."],
                                ["Apply product and decision controls", "Use the institution's configured product, calculation method, fees and credit decision rules rather than inventing terms outside the system."],
                                ["Create or approve the offer/facility", "Record the approved principal, rate, repayment period, instalment and total repayable through the controlled workflow."],
                                ["Disburse with evidence", "Finance should only mark a disbursement in line with the institution's approved payment method and evidence."],
                                ["Service the schedule", "LoanHub tracks repayment schedules, allocations, balances, due dates, overdue state and maturity."],
                                ["Handle change formally", "Use supported top-up, restructure, renewal or early-settlement workflows so the audit trail remains understandable."],
                                ["Complete or recover", "A fully settled facility can complete; missed obligations move into the collections/recovery workflows rather than being silently edited away."],
                            ]} />
                        </ManualSection>

                        <ManualSection
                            id="payments"
                            icon={WalletCards}
                            title="Payments, treasury and collections"
                            intro="Money movement requires stronger evidence than ordinary record editing. LoanHub separates posting, evidence, branch cash, reconciliation and recovery responsibilities."
                        >
                            <div className="grid gap-4 md:grid-cols-2">
                                {[
                                    ["Repayments", "Post or verify repayments against the correct loan and preserve the payment channel/evidence required by the workflow."],
                                    ["Disbursements", "Finance teams control outgoing loan funds and the user responsible for the disbursement is recorded."],
                                    ["Treasury", "Branch opening values, money-in/money-out entries, funding transfers and daily submissions support branch cash accountability."],
                                    ["Collections", "Due and overdue facilities can generate collection cases and follow-up activity while maturity recovery runs as a controlled background workflow."],
                                ].map(([title, text]) => (
                                    <div key={title} className="rounded-2xl border border-slate-200 p-5 dark:border-slate-800">
                                        <h3 className="font-black">{title}</h3>
                                        <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">{text}</p>
                                    </div>
                                ))}
                            </div>
                            <Note warning>
                                Never mark a payment successful only because a user says it was paid. Use verified provider status or the institution&apos;s approved manual evidence process.
                            </Note>
                        </ManualSection>

                        <ManualSection
                            id="finance"
                            icon={ReceiptText}
                            title="Accounting, reconciliation and reporting"
                            intro="LoanHub links lending operations to financial evidence through a double-entry accounting foundation, reconciliation routines and generated reports."
                        >
                            <StepList items={[
                                ["Use the chart of accounts", "Maintain the accounts needed for the institution's accounting policy rather than posting everything to generic buckets."],
                                ["Post balanced journals", "Journal entries should balance before posting. Corrections should be traceable rather than rewriting history without evidence."],
                                ["Review trial balance and statements", "Use trial balance, profit/loss and balance-sheet views to review the accounting position generated by posted activity."],
                                ["Reconcile external evidence", "Use bank statement/reconciliation workflows and approved exceptions to explain differences between operational records and external evidence."],
                                ["Generate and schedule reports", "Run manual reports when needed and configure scheduled PDF/CSV outputs for recurring management information."],
                                ["Review automated reconciliation", "LoanHub includes midnight operational reconciliation routines; investigate exceptions instead of treating automation as a substitute for review."],
                            ]} />
                            <Note warning>
                                LoanHub provides a double-entry accounting foundation. The institution&apos;s production chart, tax treatment, recognition policies and statutory reporting should be reviewed by a qualified accountant.
                            </Note>
                        </ManualSection>

                        <ManualSection
                            id="workforce"
                            icon={BadgeCheck}
                            title="HR, performance and company operations"
                            intro="LoanHub can operate beyond the loan desk, giving the institution a connected workspace for workforce and internal operations."
                        >
                            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                                {["Departments & positions", "Attendance & shifts", "Leave management", "Payroll runs & entries", "Assets & assignments", "Recruitment & candidates", "Training programmes", "Performance goals", "Reviews & analytics", "Client case records", "Company operating records", "APIs & webhooks"].map((item) => (
                                    <div key={item} className="flex items-center gap-3 rounded-xl bg-slate-100 px-4 py-3 text-sm font-bold dark:bg-slate-900">
                                        <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" /> {item}
                                    </div>
                                ))}
                            </div>
                            <Note>
                                HR, compliance and finance evidence can contain highly sensitive information. Use confidential visibility and role restrictions instead of sharing records broadly for convenience.
                            </Note>
                        </ManualSection>

                        <ManualSection
                            id="communication"
                            icon={MessageCircle}
                            title="Chat, calls, notifications and files"
                            intro="Communication is part of the operating record. LoanHub keeps collaboration close to the business workflow while preserving access controls."
                        >
                            <div className="grid gap-4 md:grid-cols-3">
                                {[
                                    ["Realtime communication", "Direct/group conversations, presence, typing state, read state, voice notes and managed attachments."],
                                    ["Managed files", "Permissioned upload/download, checksums, encrypted storage, visibility controls and report/document storage."],
                                    ["Controlled calling", "Employee call records, company calling policy, recording retention, supervision and quality review where approved infrastructure is provisioned."],
                                ].map(([title, text]) => (
                                    <div key={title} className="rounded-2xl border border-slate-200 p-5 dark:border-slate-800">
                                        <h3 className="font-black">{title}</h3>
                                        <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">{text}</p>
                                    </div>
                                ))}
                            </div>
                            <Note warning>
                                LoanHub does not treat arbitrary Android cellular-call recording as a reliable controlled recording path. Live recording/supervision requires the approved WebRTC/SIP media path, company policy and the appropriate notice/consent process.
                            </Note>
                        </ManualSection>

                        <ManualSection
                            id="security"
                            icon={FileLock2}
                            title="Security, privacy and evidence"
                            intro="Every user should understand the difference between being able to see a record and being authorised to disclose or change it."
                        >
                            <div className="grid gap-3">
                                {[
                                    "LoanHub isolates institution tenants and uses active company/branch context when enforcing business access.",
                                    "Managed files and chat text support authenticated AES-GCM encryption at rest. The authorised LoanHub server can decrypt content to deliver permitted workflows; this is not client-to-client end-to-end encryption.",
                                    "Production web and realtime traffic are designed to run through HTTPS/WSS.",
                                    "Ordinary users receive safe error messages and a request reference; technical diagnostics are restricted to authorised platform operations.",
                                    "Audit and transparency controls are designed to make important CRUD/business activity attributable and reviewable.",
                                    "Sensitive HR, compliance and finance evidence should use confidential visibility and the narrowest practical role access.",
                                ].map((item) => (
                                    <div key={item} className="flex gap-3 rounded-2xl border border-slate-200 p-4 dark:border-slate-800">
                                        <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
                                        <p className="text-sm leading-6 text-slate-600 dark:text-slate-300">{item}</p>
                                    </div>
                                ))}
                            </div>
                            <div className="flex flex-wrap gap-3 print:hidden">
                                <Link href="/privacy/loanhub-mobile" className="rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-black text-white dark:bg-emerald-400 dark:text-slate-950">Mobile privacy notice</Link>
                                <Link href="/documentation#security" className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-black dark:border-slate-700">Security documentation</Link>
                            </div>
                        </ManualSection>

                        <ManualSection
                            id="troubleshooting"
                            icon={CircleHelp}
                            title="Troubleshooting and safe support"
                            intro="Most support problems can be narrowed down without exposing private information or giving a user excessive access."
                        >
                            <StepList items={[
                                ["Check the active role", "If a menu/action is missing, confirm that the user is operating under the correct professional role."],
                                ["Check company and branch context", "Company users should confirm the active institution and branch before assuming a record is missing."],
                                ["Refresh the session safely", "If authentication has expired, sign in again instead of repeatedly retrying a protected action with stale credentials."],
                                ["Use the displayed reference", "For safe errors, record the request/incident reference and the action being attempted. Do not send passwords, tokens or private keys to support."],
                                ["Check external dependency status", "Payment, credit-bureau or calling issues may depend on third-party onboarding, credentials, callbacks or infrastructure outside LoanHub."],
                                ["Escalate with minimum necessary data", "Share only the business reference and context needed for support to investigate. Avoid sending borrower documents or personal financial details in uncontrolled channels."],
                            ]} />

                            <div className="rounded-3xl bg-slate-950 p-6 text-white print:border print:border-slate-300 print:bg-white print:text-black">
                                <h3 className="text-xl font-black">Quick operating rules</h3>
                                <ul className="mt-4 grid gap-3 text-sm leading-6 text-slate-300 print:text-slate-700">
                                    <li>• Confirm active company and branch before changing company records.</li>
                                    <li>• Use friendly business references rather than raw database identifiers in support communication.</li>
                                    <li>• Do not mark money successful without verified provider status or approved manual evidence.</li>
                                    <li>• Keep HR, compliance and finance evidence confidential unless the workflow explicitly requires broader access.</li>
                                    <li>• Do not share passwords, API tokens, JWT keys or deployment secrets.</li>
                                </ul>
                            </div>
                        </ManualSection>
                    </article>
                </div>
            </main>
            <PublicSiteFooter />
        </div>
    );
}
