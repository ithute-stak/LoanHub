import Image from "next/image";
import Link from "next/link";
import { ArrowRight, BookOpen, Building2, LogIn, ShieldCheck } from "lucide-react";

const navItems = [
    { href: "/#platform", label: "Platform" },
    { href: "/#borrowers", label: "Borrowers" },
    { href: "/#institutions", label: "Institutions" },
    { href: "/#security", label: "Security" },
    { href: "/manual", label: "User manual" },
    { href: "/documentation", label: "Documentation" },
];

export function PublicSiteHeader() {
    return (
        <header className="sticky top-0 z-50 border-b border-white/10 bg-slate-950/90 text-white shadow-lg shadow-slate-950/10 backdrop-blur-xl">
            <div className="mx-auto flex min-h-16 max-w-7xl items-center justify-between gap-4 px-4 py-2 sm:px-6 lg:px-8">
                <Link href="/" className="flex min-w-0 items-center gap-3" aria-label="LoanHub home">
                    <Image
                        src="/loanhub-horizontal-logo.png"
                        alt="LoanHub"
                        width={196}
                        height={58}
                        priority
                        className="h-10 w-auto max-w-[150px] object-contain brightness-0 invert sm:max-w-[184px]"
                    />
                </Link>

                <nav className="hidden items-center gap-1 lg:flex" aria-label="Public navigation">
                    {navItems.map((item) => (
                        <Link
                            key={item.href}
                            href={item.href}
                            className="rounded-full px-3 py-2 text-sm font-semibold text-slate-300 transition hover:bg-white/10 hover:text-white"
                        >
                            {item.label}
                        </Link>
                    ))}
                </nav>

                <div className="flex shrink-0 items-center gap-2">
                    <Link
                        href="/login"
                        className="inline-flex items-center gap-2 rounded-full border border-white/15 px-3 py-2 text-sm font-bold text-white transition hover:border-emerald-400/60 hover:bg-white/10 sm:px-4"
                    >
                        <LogIn className="h-4 w-4" />
                        <span className="hidden sm:inline">Sign in</span>
                    </Link>
                    <Link
                        href="/choose-account-type"
                        className="inline-flex items-center gap-2 rounded-full bg-emerald-400 px-3 py-2 text-sm font-black text-slate-950 transition hover:bg-emerald-300 sm:px-4"
                    >
                        Get started
                        <ArrowRight className="h-4 w-4" />
                    </Link>
                </div>
            </div>
        </header>
    );
}

export function PublicSiteFooter() {
    return (
        <footer className="border-t border-slate-800 bg-slate-950 text-slate-300">
            <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-2 lg:grid-cols-4 lg:px-8">
                <div className="space-y-4 lg:col-span-2">
                    <Image
                        src="/loanhub-horizontal-logo.png"
                        alt="LoanHub"
                        width={210}
                        height={64}
                        className="h-11 w-auto object-contain brightness-0 invert"
                    />
                    <p className="max-w-xl text-sm leading-6 text-slate-400">
                        A multi-tenant lending marketplace and financial operating system built for borrowers,
                        lending institutions, branches and professional financial teams in Lesotho.
                    </p>
                    <div className="flex flex-wrap gap-2 text-xs font-semibold text-slate-400">
                        <span className="rounded-full border border-slate-800 px-3 py-1.5">Tenant isolation</span>
                        <span className="rounded-full border border-slate-800 px-3 py-1.5">Role-based access</span>
                        <span className="rounded-full border border-slate-800 px-3 py-1.5">Audit trail</span>
                        <span className="rounded-full border border-slate-800 px-3 py-1.5">HTTPS / WSS</span>
                    </div>
                </div>

                <div>
                    <h2 className="font-black text-white">Learn LoanHub</h2>
                    <div className="mt-4 grid gap-3 text-sm">
                        <Link href="/manual" className="inline-flex items-center gap-2 hover:text-emerald-300">
                            <BookOpen className="h-4 w-4" /> User manual
                        </Link>
                        <Link href="/documentation" className="inline-flex items-center gap-2 hover:text-emerald-300">
                            <Building2 className="h-4 w-4" /> Documentation centre
                        </Link>
                        <Link href="/privacy/loanhub-mobile" className="inline-flex items-center gap-2 hover:text-emerald-300">
                            <ShieldCheck className="h-4 w-4" /> Mobile privacy
                        </Link>
                    </div>
                </div>

                <div>
                    <h2 className="font-black text-white">Access</h2>
                    <div className="mt-4 grid gap-3 text-sm">
                        <Link href="/login" className="hover:text-emerald-300">Sign in</Link>
                        <Link href="/borrower-registration" className="hover:text-emerald-300">Register as borrower</Link>
                        <Link href="/register-company-admin" className="hover:text-emerald-300">Register an institution</Link>
                        <Link href="/lender-access" className="hover:text-emerald-300">Lender access</Link>
                    </div>
                </div>
            </div>

            <div className="border-t border-slate-900">
                <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-5 text-xs text-slate-500 sm:px-6 md:flex-row md:items-center md:justify-between lg:px-8">
                    <p>© {new Date().getFullYear()} LoanHub. Financial infrastructure for Lesotho.</p>
                    <p className="flex items-center gap-2">
                        Developed and maintained by
                        <Image
                            src="/ithute-solutions-developer-logo.png"
                            alt="Ithute Solutions"
                            width={92}
                            height={28}
                            className="h-5 w-auto object-contain opacity-80"
                        />
                    </p>
                </div>
            </div>
        </footer>
    );
}

export function PublicSectionHeading({
    eyebrow,
    title,
    description,
    align = "left",
}: {
    eyebrow: string;
    title: string;
    description: string;
    align?: "left" | "center";
}) {
    const alignment = align === "center" ? "mx-auto max-w-3xl text-center" : "max-w-3xl";
    return (
        <div className={alignment}>
            <p className="text-xs font-black uppercase tracking-[0.24em] text-emerald-600 dark:text-emerald-400">
                {eyebrow}
            </p>
            <h2 className="mt-3 text-3xl font-black tracking-tight text-slate-950 dark:text-white sm:text-4xl lg:text-5xl">
                {title}
            </h2>
            <p className="mt-4 text-base leading-7 text-slate-600 dark:text-slate-300 sm:text-lg">
                {description}
            </p>
        </div>
    );
}
