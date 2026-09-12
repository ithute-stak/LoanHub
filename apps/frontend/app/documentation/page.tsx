import type { Metadata } from "next";
import Link from "next/link";
import {
    ArrowLeft,
    ArrowRight,
    BookOpen,
    Building2,
    CheckCircle2,
    CircleHelp,
    Code2,
    FileCheck2,
    FileText,
    Landmark,
    LockKeyhole,
    MessageCircle,
    Scale,
    ShieldCheck,
    Users,
    WalletCards,
    Workflow,
} from "lucide-react";

import { PublicSiteFooter, PublicSiteHeader } from "@/components/marketing/public-site-shell";

export const metadata: Metadata = {
    title: "LoanHub Documentation Centre | Guides, privacy and operations",
    description:
        "LoanHub public documentation for borrowers, lending institutions, staff operations, security, reporting, integrations and support.",
};

const guideCards = [
    {
        icon: BookOpen,
        title: "Complete user manual",
        text: "The full public operating guide for borrowers, institutions and specialist staff. It can be printed or saved as PDF from your browser.",
        href: "/manual",
        action: "Open manual",
    },
    {
        icon: Users,
        title: "Borrower quick start",
        text: "Registration, assessment profile, supporting evidence, consents, funding requests, offers and active-loan management.",
        href: "/manual#borrower",
        action: "Borrower guide",
    },
    {
        icon: Building2,
        title: "Institution quick start",
        text: "Company registration, governance, branches, staff roles, lending products, finance setup and operational training.",
        href: "/manual#institution",
        action: "Institution guide",
    },
    {
        icon: Workflow,
        title: "Lending lifecycle",
        text: "From application and affordability assessment through approval, disbursement, repayment, restructure, settlement and recovery.",
        href: "/manual#lending",
        action: "Lending guide",
    },
    {
        icon: WalletCards,
        title: "Finance operations",
        text: "Payments, treasury, collections, accounting, reconciliation and recurring reporting guidance for controlled financial operations.",
        href: "/manual#payments",
        action: "Finance guide",
    },
    {
        icon: ShieldCheck,
        title: "Security & privacy",
        text: "Tenant boundaries, roles, audit evidence, encrypted storage, safe error handling and privacy-aware operating rules.",
        href: "/manual#security",
        action: "Security guide",
    },
];

const checklists = [
    {
        title: "Before a borrower requests funding",
        items: [
            "Account registration is complete.",
            "Employment and affordability information is current.",
            "Banking information is reviewed.",
            "Required supporting documents are available.",
            "Consent choices are understood and recorded.",
        ],
    },
    {
        title: "Before an institution starts lending",
        items: [
            "Institution registration and approval are complete.",
            "Branches and staff memberships are configured.",
            "Each staff member has the narrowest suitable role.",
            "Loan products and calculation methods are reviewed.",
            "Payment/integration dependencies are activated where needed.",
            "Finance, collections and reporting responsibilities are assigned.",
        ],
    },
    {
        title: "Before marking money as successful",
        items: [
            "The correct borrower and loan are selected.",
            "The payment/disbursement channel is correct.",
            "Provider status or approved manual evidence is available.",
            "The user performing the action is authorised.",
            "Any reconciliation evidence is retained for review.",
        ],
    },
];

const boundaries = [
    {
        icon: Landmark,
        title: "Payment providers",
        text: "LoanHub contains payment and gateway workflows, but live external channels still depend on provider onboarding, credentials, callbacks, authorisation and certification appropriate to the institution.",
    },
    {
        icon: MessageCircle,
        title: "Controlled calling",
        text: "Call records, recording policy and quality controls are built in. Reliable live recording/supervision requires approved WebRTC/SIP infrastructure and the required notice/consent process.",
    },
    {
        icon: Scale,
        title: "Accounting policy",
        text: "The platform provides a double-entry accounting foundation. A qualified accountant should review the institution's production chart, recognition, tax and statutory reporting policies.",
    },
    {
        icon: FileCheck2,
        title: "File storage at scale",
        text: "The production stack supports managed files. Multi-server deployments should use appropriate object storage and malware scanning rather than treating one local VPS volume as a distributed storage system.",
    },
];

export default function DocumentationPage() {
    return (
        <div className="min-h-screen bg-white text-slate-950 dark:bg-slate-950 dark:text-white">
            <PublicSiteHeader />
            <main>
                <section className="border-b border-slate-800 bg-slate-950 text-white">
                    <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8 lg:py-20">
                        <Link href="/" className="inline-flex items-center gap-2 text-sm font-bold text-slate-300 hover:text-emerald-300">
                            <ArrowLeft className="h-4 w-4" /> Back to LoanHub website
                        </Link>
                        <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_auto] lg:items-end">
                            <div>
                                <p className="text-xs font-black uppercase tracking-[0.24em] text-emerald-300">Knowledge base</p>
                                <h1 className="mt-4 max-w-4xl text-4xl font-black tracking-tight sm:text-6xl">LoanHub Documentation Centre</h1>
                                <p className="mt-5 max-w-3xl text-base leading-7 text-slate-300 sm:text-lg">
                                    Practical guidance for visitors, borrowers, institution owners and operating teams—without publishing deployment secrets, private customer data or internal security credentials.
                                </p>
                            </div>
                            <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
                                <p className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">Fastest route</p>
                                <Link href="/manual" className="mt-3 inline-flex items-center gap-2 font-black text-emerald-300">
                                    Read the complete user manual <ArrowRight className="h-4 w-4" />
                                </Link>
                            </div>
                        </div>
                    </div>
                </section>

                <section className="py-16 sm:py-20">
                    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
                        <div className="max-w-3xl">
                            <p className="text-xs font-black uppercase tracking-[0.24em] text-emerald-600 dark:text-emerald-400">Guides</p>
                            <h2 className="mt-3 text-3xl font-black tracking-tight sm:text-4xl">Start with the document that matches your task.</h2>
                            <p className="mt-4 leading-7 text-slate-600 dark:text-slate-300">Every guide below points into the public manual so new users can learn the system without needing access to a private company workspace.</p>
                        </div>
                        <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                            {guideCards.map(({ icon: Icon, title, text, href, action }) => (
                                <Link key={title} href={href} className="group rounded-3xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-1 hover:border-emerald-300 hover:shadow-xl dark:border-slate-800 dark:bg-slate-900 dark:hover:border-emerald-800">
                                    <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300"><Icon className="h-5 w-5" /></span>
                                    <h3 className="mt-5 text-xl font-black">{title}</h3>
                                    <p className="mt-3 text-sm leading-6 text-slate-600 dark:text-slate-300">{text}</p>
                                    <span className="mt-6 inline-flex items-center gap-2 text-sm font-black text-emerald-700 dark:text-emerald-300">{action} <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" /></span>
                                </Link>
                            ))}
                        </div>
                    </div>
                </section>

                <section id="security" className="scroll-mt-24 bg-slate-50 py-16 dark:bg-slate-900/40 sm:py-20">
                    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
                        <div className="grid gap-10 lg:grid-cols-[.9fr_1.1fr]">
                            <div>
                                <LockKeyhole className="h-9 w-9 text-emerald-600 dark:text-emerald-300" />
                                <h2 className="mt-5 text-3xl font-black tracking-tight sm:text-4xl">Security information that visitors should know</h2>
                                <p className="mt-4 leading-7 text-slate-600 dark:text-slate-300">
                                    Public documentation explains how users should operate securely without revealing private deployment details, credentials or sensitive internal diagnostics.
                                </p>
                                <Link href="/privacy/loanhub-mobile" className="mt-7 inline-flex items-center gap-2 rounded-2xl bg-slate-950 px-5 py-3 text-sm font-black text-white dark:bg-emerald-400 dark:text-slate-950">
                                    Mobile privacy notice <ArrowRight className="h-4 w-4" />
                                </Link>
                            </div>
                            <div className="grid gap-3 sm:grid-cols-2">
                                {[
                                    ["Tenant isolation", "Independent institutions operate inside isolated tenant scopes with branch-aware business access."],
                                    ["Professional roles", "Authorisation is separated across platform, institution, branch and specialist operating roles."],
                                    ["Encrypted storage", "Managed files and chat text support authenticated AES-GCM encryption at rest."],
                                    ["Secure transport", "The production public edge is designed to serve application and realtime traffic over HTTPS/WSS."],
                                    ["Audit evidence", "Important business actions are designed to be attributable and reviewable through audit/transparency controls."],
                                    ["Safe error handling", "Ordinary users receive safe error messages and request references while technical diagnostics remain restricted."],
                                ].map(([title, text]) => (
                                    <article key={title} className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
                                        <ShieldCheck className="h-5 w-5 text-emerald-600 dark:text-emerald-300" />
                                        <h3 className="mt-4 font-black">{title}</h3>
                                        <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">{text}</p>
                                    </article>
                                ))}
                            </div>
                        </div>
                    </div>
                </section>

                <section className="py-16 sm:py-20">
                    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
                        <div className="max-w-3xl">
                            <p className="text-xs font-black uppercase tracking-[0.24em] text-emerald-600 dark:text-emerald-400">Operational checklists</p>
                            <h2 className="mt-3 text-3xl font-black tracking-tight sm:text-4xl">Use a checklist before high-impact actions.</h2>
                        </div>
                        <div className="mt-10 grid gap-4 lg:grid-cols-3">
                            {checklists.map((checklist) => (
                                <article key={checklist.title} className="rounded-3xl border border-slate-200 p-6 dark:border-slate-800">
                                    <h3 className="text-lg font-black">{checklist.title}</h3>
                                    <ul className="mt-5 grid gap-3">
                                        {checklist.items.map((item) => (
                                            <li key={item} className="flex gap-3 text-sm leading-6 text-slate-600 dark:text-slate-300">
                                                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" /> {item}
                                            </li>
                                        ))}
                                    </ul>
                                </article>
                            ))}
                        </div>
                    </div>
                </section>

                <section className="bg-slate-950 py-16 text-white sm:py-20">
                    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
                        <div className="max-w-3xl">
                            <p className="text-xs font-black uppercase tracking-[0.24em] text-emerald-300">Production boundaries</p>
                            <h2 className="mt-3 text-3xl font-black tracking-tight sm:text-4xl">Know what requires external approval or professional review.</h2>
                            <p className="mt-4 leading-7 text-slate-300">LoanHub can coordinate the workflow, but some capabilities depend on regulated providers, institution policy, infrastructure or specialist professional judgement.</p>
                        </div>
                        <div className="mt-10 grid gap-4 md:grid-cols-2">
                            {boundaries.map(({ icon: Icon, title, text }) => (
                                <article key={title} className="rounded-3xl border border-white/10 bg-white/[0.04] p-6">
                                    <Icon className="h-6 w-6 text-emerald-300" />
                                    <h3 className="mt-5 text-lg font-black">{title}</h3>
                                    <p className="mt-2 text-sm leading-6 text-slate-300">{text}</p>
                                </article>
                            ))}
                        </div>
                    </div>
                </section>

                <section className="py-16 sm:py-20">
                    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
                        <div className="grid gap-8 rounded-[2rem] border border-slate-200 bg-emerald-50 p-7 dark:border-emerald-900 dark:bg-emerald-950/20 sm:p-10 lg:grid-cols-[1fr_auto] lg:items-center">
                            <div>
                                <CircleHelp className="h-8 w-8 text-emerald-700 dark:text-emerald-300" />
                                <h2 className="mt-5 text-2xl font-black sm:text-3xl">Need to report a problem?</h2>
                                <p className="mt-3 max-w-3xl leading-7 text-slate-600 dark:text-slate-300">
                                    Capture the action you were performing, the friendly LoanHub business/request reference and the time of the problem. Do not send passwords, tokens, private keys or unnecessary borrower documents through uncontrolled channels.
                                </p>
                            </div>
                            <Link href="/manual#troubleshooting" className="inline-flex items-center justify-center gap-2 rounded-2xl bg-slate-950 px-5 py-3 text-sm font-black text-white dark:bg-emerald-400 dark:text-slate-950">
                                Troubleshooting guide <ArrowRight className="h-4 w-4" />
                            </Link>
                        </div>
                    </div>
                </section>

                <section className="px-4 pb-16 sm:px-6 sm:pb-20 lg:px-8">
                    <div className="mx-auto max-w-7xl rounded-[2rem] bg-slate-100 p-7 dark:bg-slate-900 sm:p-10">
                        <div className="grid gap-6 lg:grid-cols-3">
                            <div>
                                <FileText className="h-6 w-6 text-emerald-600" />
                                <h3 className="mt-4 font-black">User documentation</h3>
                                <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">Manual, role guidance, operating rules and checklists for people using LoanHub.</p>
                            </div>
                            <div>
                                <Code2 className="h-6 w-6 text-emerald-600" />
                                <h3 className="mt-4 font-black">Technical API reference</h3>
                                <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">Authorised integrators can use the API documentation exposed by the LoanHub backend deployment, subject to the permissions of the endpoints they call.</p>
                                <a href="https://api.loanhub.co.ls/docs" className="mt-3 inline-flex items-center gap-2 text-sm font-black text-emerald-700 dark:text-emerald-300">Open API docs <ArrowRight className="h-4 w-4" /></a>
                            </div>
                            <div>
                                <Landmark className="h-6 w-6 text-emerald-600" />
                                <h3 className="mt-4 font-black">Product access</h3>
                                <div className="mt-3 grid gap-2 text-sm font-bold">
                                    <Link href="/borrower-registration" className="hover:text-emerald-700 dark:hover:text-emerald-300">Borrower registration</Link>
                                    <Link href="/register-company-admin" className="hover:text-emerald-700 dark:hover:text-emerald-300">Institution registration</Link>
                                    <Link href="/login" className="hover:text-emerald-700 dark:hover:text-emerald-300">Existing user sign-in</Link>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>
            </main>
            <PublicSiteFooter />
        </div>
    );
}
