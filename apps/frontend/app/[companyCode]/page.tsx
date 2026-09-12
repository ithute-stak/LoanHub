"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight, BadgeCheck, Building2, Loader2, LockKeyhole, Mail, MapPin, Phone, ShieldCheck } from "lucide-react";

import { getPublicCompanyWebsite } from "@/api/companyWebsite";
import type { PublicCompanyWebsite } from "@/types/companyWebsite";
import { getErrorMessage } from "@/utils/apiError";

export default function PublicCompanyWebsitePage() {
    const params = useParams<{ companyCode: string }>();
    const code = params.companyCode;
    const [site, setSite] = useState<PublicCompanyWebsite | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);
        getPublicCompanyWebsite(code)
            .then((value) => { if (!cancelled) setSite(value); })
            .catch((reason: unknown) => { if (!cancelled) setError(getErrorMessage(reason, "This loan website is not available.")); })
            .finally(() => { if (!cancelled) setLoading(false); });
        return () => { cancelled = true; };
    }, [code]);

    if (loading) return <main className="flex min-h-dvh items-center justify-center bg-background"><Loader2 className="h-8 w-8 animate-spin text-primary" /></main>;
    if (!site || error) {
        return <main className="flex min-h-dvh items-center justify-center bg-slate-50 p-6"><section className="max-w-lg rounded-3xl border bg-white p-8 text-center shadow-sm"><Building2 className="mx-auto h-10 w-10 text-slate-400" /><h1 className="mt-4 text-2xl font-black">Website unavailable</h1><p className="mt-2 text-sm leading-6 text-slate-500">{error || "This company website has not been published."}</p><Link href="/" className="mt-6 inline-flex rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-black text-white">Go to LoanHub</Link></section></main>;
    }

    return site.template_key === "modern_finance" ? <ModernFinanceSite site={site} /> : <TrustCommunitySite site={site} />;
}

function accountHref(site: PublicCompanyWebsite) {
    return `/borrower-registration?company=${encodeURIComponent(site.public_code)}`;
}

function loginHref(site: PublicCompanyWebsite) {
    return `/login?company=${encodeURIComponent(site.public_code)}`;
}

function ProductCards({ site, dark = false }: { site: PublicCompanyWebsite; dark?: boolean }) {
    if (!site.show_loan_products) return null;
    return (
        <section id="loans" className="px-5 py-16 sm:px-8 lg:px-12">
            <div className="mx-auto max-w-7xl">
                <p className="text-xs font-black uppercase tracking-[0.16em]" style={{ color: site.accent_color }}>Available loans</p>
                <div className="mt-2 flex flex-col gap-3 md:flex-row md:items-end md:justify-between"><h2 className="text-3xl font-black tracking-tight">Choose a loan product that fits.</h2><p className={`max-w-xl text-sm leading-6 ${dark ? "text-slate-400" : "text-slate-500"}`}>These products are loaded from the company&apos;s active LoanHub product catalogue, so the public website follows the lending setup already managed in LoanHub.</p></div>
                {site.loan_products.length ? (
                    <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                        {site.loan_products.map((product) => (
                            <article key={product.id} className={`rounded-3xl border p-6 ${dark ? "border-white/10 bg-white/5" : "bg-white shadow-sm"}`}>
                                <div className="flex items-start justify-between gap-4"><h3 className="text-xl font-black">{product.name}</h3><BadgeCheck className="h-5 w-5 shrink-0" style={{ color: site.accent_color }} /></div>
                                {product.description && <p className={`mt-3 text-sm leading-6 ${dark ? "text-slate-400" : "text-slate-500"}`}>{product.description}</p>}
                                <div className="mt-6 grid grid-cols-2 gap-3 text-sm">
                                    <Stat label="Amount" value={`M ${product.min_amount.toLocaleString()} – ${product.max_amount.toLocaleString()}`} dark={dark} />
                                    <Stat label="Term" value={`${product.min_term_months}–${product.max_term_months} months`} dark={dark} />
                                    <Stat label="Interest" value={`${product.interest_rate_percent}%`} dark={dark} />
                                    <Stat label="Processing" value={`M ${product.processing_fee.toLocaleString()}`} dark={dark} />
                                </div>
                                {site.show_account_cta && <Link href={accountHref(site)} className="mt-6 inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl text-sm font-black text-white" style={{ backgroundColor: site.primary_color }}>Create account to continue <ArrowRight className="h-4 w-4" /></Link>}
                            </article>
                        ))}
                    </div>
                ) : <div className={`mt-8 rounded-3xl border border-dashed p-10 text-center text-sm ${dark ? "border-white/15 text-slate-400" : "text-slate-500"}`}>No public loan products are currently available. Please contact the company directly.</div>}
            </div>
        </section>
    );
}

function Stat({ label, value, dark }: { label: string; value: string; dark: boolean }) {
    return <div className={`rounded-2xl p-3 ${dark ? "bg-white/5" : "bg-slate-50"}`}><p className={`text-[10px] font-black uppercase tracking-wide ${dark ? "text-slate-500" : "text-slate-400"}`}>{label}</p><p className="mt-1 font-black">{value}</p></div>;
}

function ContactSection({ site, dark = false }: { site: PublicCompanyWebsite; dark?: boolean }) {
    return (
        <section id="contact" className={`px-5 py-14 sm:px-8 lg:px-12 ${dark ? "border-t border-white/10 bg-white/5" : "bg-slate-50"}`}>
            <div className="mx-auto grid max-w-7xl gap-8 md:grid-cols-2 md:items-center">
                <div><p className="text-xs font-black uppercase tracking-[0.16em]" style={{ color: site.accent_color }}>Contact</p><h2 className="mt-2 text-3xl font-black">Talk to {site.company_name}</h2><p className={`mt-3 text-sm leading-6 ${dark ? "text-slate-400" : "text-slate-500"}`}>Questions about eligibility, repayments or a product? Contact the lender using its published details.</p></div>
                <div className="grid gap-3">
                    {site.contact_phone && <a href={`tel:${site.contact_phone}`} className="flex items-center gap-3 rounded-2xl border p-4"><Phone className="h-5 w-5" style={{ color: site.accent_color }} /><span className="font-bold">{site.contact_phone}</span></a>}
                    {site.contact_email && <a href={`mailto:${site.contact_email}`} className="flex items-center gap-3 rounded-2xl border p-4"><Mail className="h-5 w-5" style={{ color: site.accent_color }} /><span className="font-bold">{site.contact_email}</span></a>}
                    {(site.company_address || site.company_district) && <div className="flex items-center gap-3 rounded-2xl border p-4"><MapPin className="h-5 w-5" style={{ color: site.accent_color }} /><span className="font-bold">{[site.company_address, site.company_district].filter(Boolean).join(", ")}</span></div>}
                </div>
            </div>
        </section>
    );
}

function TrustCommunitySite({ site }: { site: PublicCompanyWebsite }) {
    return (
        <main className="min-h-dvh bg-white text-slate-950">
            <nav className="sticky top-0 z-40 border-b bg-white/95 px-5 py-4 backdrop-blur sm:px-8 lg:px-12"><div className="mx-auto flex max-w-7xl items-center justify-between gap-4"><Link href={`/${site.public_code}`} className="flex items-center gap-2 font-black"><span className="flex h-9 w-9 items-center justify-center rounded-xl text-white" style={{ backgroundColor: site.primary_color }}><Building2 className="h-5 w-5" /></span>{site.company_name}</Link><div className="hidden items-center gap-5 text-sm font-bold md:flex"><a href="#loans">Loans</a><a href="#about">About</a><a href="#contact">Contact</a></div>{site.show_account_cta && <div className="flex gap-2"><Link href={loginHref(site)} className="hidden rounded-xl border px-4 py-2 text-sm font-black sm:inline-flex">Sign in</Link><Link href={accountHref(site)} className="rounded-xl px-4 py-2 text-sm font-black text-white" style={{ backgroundColor: site.primary_color }}>Create account</Link></div>}</div></nav>
            <section className="relative overflow-hidden bg-slate-50 px-5 py-20 sm:px-8 lg:px-12 lg:py-28"><div className="absolute -right-28 -top-28 h-96 w-96 rounded-full opacity-10 blur-3xl" style={{ backgroundColor: site.primary_color }} /><div className="relative mx-auto grid max-w-7xl gap-12 lg:grid-cols-[1fr_420px] lg:items-center"><div><span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1.5 text-xs font-black shadow-sm" style={{ color: site.primary_color }}><ShieldCheck className="h-4 w-4" />{site.hero_badge || "Secure lending powered by LoanHub"}</span><h1 className="mt-6 max-w-4xl text-4xl font-black tracking-tight sm:text-5xl lg:text-7xl">{site.headline}</h1><p className="mt-6 max-w-2xl text-base leading-8 text-slate-600">{site.subheadline}</p>{site.show_account_cta && <div className="mt-8 flex flex-wrap gap-3"><Link href={accountHref(site)} className="inline-flex h-12 items-center gap-2 rounded-xl px-5 text-sm font-black text-white" style={{ backgroundColor: site.primary_color }}>Create borrower account <ArrowRight className="h-4 w-4" /></Link><Link href={loginHref(site)} className="inline-flex h-12 items-center gap-2 rounded-xl border bg-white px-5 text-sm font-black"><LockKeyhole className="h-4 w-4" /> Existing borrower sign in</Link></div>}</div><div className="rounded-[2rem] border bg-white p-7 shadow-xl"><div className="flex h-14 w-14 items-center justify-center rounded-2xl text-white" style={{ backgroundColor: site.accent_color }}><ShieldCheck className="h-7 w-7" /></div><h2 className="mt-5 text-2xl font-black">Transparent digital lending</h2><p className="mt-3 text-sm leading-6 text-slate-500">Borrower accounts, application tracking and lender workflows connect back to LoanHub instead of running as a disconnected marketing site.</p><div className="mt-6 grid gap-3 text-sm font-bold"><span className="flex items-center gap-2"><BadgeCheck className="h-4 w-4" style={{ color: site.accent_color }} /> Active products from LoanHub</span><span className="flex items-center gap-2"><BadgeCheck className="h-4 w-4" style={{ color: site.accent_color }} /> Existing LoanHub borrower account flow</span><span className="flex items-center gap-2"><BadgeCheck className="h-4 w-4" style={{ color: site.accent_color }} /> Company-controlled public information</span></div></div></div></section>
            <ProductCards site={site} />
            <section id="about" className="px-5 py-16 sm:px-8 lg:px-12"><div className="mx-auto max-w-7xl"><p className="text-xs font-black uppercase tracking-[0.16em]" style={{ color: site.accent_color }}>About the lender</p><h2 className="mt-2 text-3xl font-black">{site.company_name}</h2><p className="mt-4 max-w-4xl text-base leading-8 text-slate-600">{site.about}</p>{(site.registration_number || site.license_number) && <div className="mt-6 flex flex-wrap gap-3 text-xs font-bold text-slate-500">{site.registration_number && <span className="rounded-full bg-slate-100 px-3 py-1.5">Registration: {site.registration_number}</span>}{site.license_number && <span className="rounded-full bg-slate-100 px-3 py-1.5">Licence: {site.license_number}</span>}</div>}</div></section>
            <ContactSection site={site} />
            <footer className="px-5 py-7 text-center text-xs text-slate-500"><span className="font-black">{site.company_name}</span> · Digital lending website powered by LoanHub</footer>
        </main>
    );
}

function ModernFinanceSite({ site }: { site: PublicCompanyWebsite }) {
    return (
        <main className="min-h-dvh bg-slate-950 text-white">
            <nav className="sticky top-0 z-40 border-b border-white/10 bg-slate-950/95 px-5 py-4 backdrop-blur sm:px-8 lg:px-12"><div className="mx-auto flex max-w-7xl items-center justify-between gap-4"><Link href={`/${site.public_code}`} className="flex items-center gap-2 font-black"><span className="flex h-9 w-9 items-center justify-center rounded-xl" style={{ backgroundColor: site.accent_color }}><Building2 className="h-5 w-5" /></span>{site.company_name}</Link><div className="hidden items-center gap-5 text-sm font-bold text-slate-300 md:flex"><a href="#loans">Products</a><a href="#about">Company</a><a href="#contact">Contact</a></div>{site.show_account_cta && <Link href={accountHref(site)} className="rounded-xl px-4 py-2 text-sm font-black text-white" style={{ backgroundColor: site.primary_color }}>Get started</Link>}</div></nav>
            <section className="relative overflow-hidden px-5 py-24 sm:px-8 lg:px-12 lg:py-32"><div className="absolute left-1/2 top-0 h-[500px] w-[700px] -translate-x-1/2 rounded-full opacity-20 blur-[120px]" style={{ backgroundColor: site.primary_color }} /><div className="relative mx-auto max-w-7xl"><span className="inline-flex rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-black" style={{ color: site.accent_color }}>{site.hero_badge || "Digital lending on LoanHub"}</span><h1 className="mt-7 max-w-5xl text-5xl font-black tracking-[-0.05em] sm:text-6xl lg:text-8xl">{site.headline}</h1><p className="mt-7 max-w-2xl text-base leading-8 text-slate-300">{site.subheadline}</p>{site.show_account_cta && <div className="mt-9 flex flex-wrap gap-3"><Link href={accountHref(site)} className="inline-flex h-12 items-center gap-2 rounded-xl px-5 text-sm font-black text-white" style={{ backgroundColor: site.primary_color }}>Open borrower account <ArrowRight className="h-4 w-4" /></Link><Link href={loginHref(site)} className="inline-flex h-12 items-center rounded-xl border border-white/15 bg-white/5 px-5 text-sm font-black">Sign in</Link></div>}</div></section>
            <ProductCards site={site} dark />
            <section id="about" className="border-y border-white/10 bg-white/5 px-5 py-16 sm:px-8 lg:px-12"><div className="mx-auto grid max-w-7xl gap-7 lg:grid-cols-[300px_1fr]"><div><p className="text-xs font-black uppercase tracking-[0.16em]" style={{ color: site.accent_color }}>Company</p><h2 className="mt-2 text-3xl font-black">{site.company_name}</h2></div><p className="max-w-4xl text-base leading-8 text-slate-300">{site.about}</p></div></section>
            <ContactSection site={site} dark />
            <footer className="border-t border-white/10 px-5 py-7 text-center text-xs text-slate-500">{site.company_name} · Powered by LoanHub</footer>
        </main>
    );
}
