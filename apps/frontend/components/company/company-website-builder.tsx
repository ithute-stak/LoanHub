"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import {
    Check,
    Copy,
    ExternalLink,
    Globe2,
    LayoutTemplate,
    Loader2,
    MonitorSmartphone,
    Rocket,
    Save,
    ShieldCheck,
} from "lucide-react";

import {
    getCompanyWebsiteLoanProducts,
    getMyCompanyWebsite,
    publishCompanyWebsite,
    startCompanyWebsite,
    updateCompanyWebsite,
} from "@/api/companyWebsite";
import type {
    CompanyWebsiteProfile,
    CompanyWebsiteTemplate,
    PublicLoanProduct,
} from "@/types/companyWebsite";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

const TEMPLATES: Array<{ key: CompanyWebsiteTemplate; name: string; description: string }> = [
    {
        key: "trust_community",
        name: "Trust & Community",
        description: "Warm, credible lending presentation with strong trust signals and clear borrower actions.",
    },
    {
        key: "modern_finance",
        name: "Modern Finance",
        description: "Sharper digital-finance layout with bold product cards, clean statistics and a modern application journey.",
    },
];

export function CompanyWebsiteBuilder() {
    const [profile, setProfile] = useState<CompanyWebsiteProfile | null>(null);
    const [products, setProducts] = useState<PublicLoanProduct[]>([]);
    const [loading, setLoading] = useState(true);
    const [starting, setStarting] = useState(false);
    const [saving, setSaving] = useState(false);
    const [publishing, setPublishing] = useState(false);
    const [dirty, setDirty] = useState(false);
    const [origin, setOrigin] = useState("");

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [website, loanProducts] = await Promise.all([
                getMyCompanyWebsite(),
                getCompanyWebsiteLoanProducts(),
            ]);
            setProfile(website);
            setProducts(loanProducts);
            setDirty(false);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not load the company website builder."));
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { void load(); }, [load]);
    useEffect(() => { setOrigin(window.location.origin); }, []);

    const publicUrl = useMemo(
        () => profile ? `${origin || "https://loanhub.com"}/${profile.public_code}` : "",
        [origin, profile],
    );

    async function start() {
        setStarting(true);
        try {
            const [value, loanProducts] = await Promise.all([
                startCompanyWebsite(),
                getCompanyWebsiteLoanProducts(),
            ]);
            setProfile(value);
            setProducts(loanProducts);
            toast.success("Your unique LoanHub website address is ready.");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not start the website builder."));
        } finally {
            setStarting(false);
        }
    }

    function patch<K extends keyof CompanyWebsiteProfile>(key: K, value: CompanyWebsiteProfile[K]) {
        setProfile((current) => current ? { ...current, [key]: value } : current);
        setDirty(true);
    }

    async function save(): Promise<boolean> {
        if (!profile || saving) return !dirty;
        if (!dirty) return true;
        setSaving(true);
        try {
            const value = await updateCompanyWebsite({
                template_key: profile.template_key,
                headline: profile.headline,
                subheadline: profile.subheadline,
                about: profile.about,
                primary_color: profile.primary_color,
                accent_color: profile.accent_color,
                hero_badge: profile.hero_badge,
                contact_phone: profile.contact_phone,
                contact_email: profile.contact_email,
                show_loan_products: profile.show_loan_products,
                show_account_cta: profile.show_account_cta,
                custom_sections: profile.custom_sections,
            });
            setProfile(value);
            setDirty(false);
            toast.success("Website customisation saved.");
            return true;
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not save the website."));
            return false;
        } finally {
            setSaving(false);
        }
    }

    async function togglePublished() {
        if (!profile || publishing) return;
        if (dirty && !(await save())) return;
        setPublishing(true);
        try {
            const value = await publishCompanyWebsite(!profile.is_published);
            setProfile(value);
            toast.success(value.is_published ? "Company website is now public." : "Company website is now private.");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not change website publishing status."));
        } finally {
            setPublishing(false);
        }
    }

    if (loading) {
        return <div className="flex min-h-[70vh] items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>;
    }

    if (!profile) {
        return (
            <main className="space-y-6">
                <section className="overflow-hidden rounded-3xl border bg-card p-7 shadow-sm md:p-10">
                    <div className="max-w-3xl">
                        <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1.5 text-xs font-black text-primary"><Globe2 className="h-4 w-4" /> LoanHub Website Builder</div>
                        <h1 className="mt-5 text-3xl font-black tracking-tight md:text-5xl">Give your loan company its own professional website.</h1>
                        <p className="mt-4 max-w-2xl text-sm leading-7 text-muted-foreground md:text-base">
                            LoanHub generates a unique public address only when you start customising. Choose a template, publish your real active LoanHub loan products and keep borrower account actions connected to the existing platform.
                        </p>
                        <button type="button" onClick={() => void start()} disabled={starting} className="mt-7 inline-flex h-12 items-center gap-2 rounded-xl bg-primary px-5 text-sm font-black text-primary-foreground disabled:opacity-50">
                            {starting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Rocket className="h-4 w-4" />} Start customising website
                        </button>
                    </div>
                </section>
                <section className="grid gap-4 md:grid-cols-2">
                    {TEMPLATES.map((template) => <TemplatePreview key={template.key} template={template.key} name={template.name} description={template.description} />)}
                </section>
            </main>
        );
    }

    return (
        <main className="space-y-5">
            <section className="flex flex-col gap-4 rounded-3xl border bg-card p-5 shadow-sm xl:flex-row xl:items-center xl:justify-between">
                <div>
                    <div className="flex items-center gap-2 text-primary"><Globe2 className="h-5 w-5" /><span className="text-xs font-black uppercase tracking-[0.14em]">Company Website Builder</span></div>
                    <h1 className="mt-2 text-2xl font-black">{profile.company_name} public website</h1>
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        <span className={`rounded-full px-2.5 py-1 font-black ${profile.is_published ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300" : "bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300"}`}>{profile.is_published ? "Published" : "Draft"}</span>
                        <span className="font-mono">/{profile.public_code}</span>
                        <span>· {products.length} active LoanHub product{products.length === 1 ? "" : "s"}</span>
                    </div>
                </div>
                <div className="flex flex-wrap gap-2">
                    <button type="button" onClick={() => { void navigator.clipboard.writeText(publicUrl); toast.success("Website address copied."); }} className="inline-flex h-10 items-center gap-2 rounded-xl border px-3 text-xs font-black hover:border-primary hover:text-primary"><Copy className="h-4 w-4" /> Copy address</button>
                    {profile.is_published && <Link href={`/${profile.public_code}`} target="_blank" className="inline-flex h-10 items-center gap-2 rounded-xl border px-3 text-xs font-black hover:border-primary hover:text-primary"><ExternalLink className="h-4 w-4" /> Open site</Link>}
                    <button type="button" disabled={!dirty || saving} onClick={() => void save()} className="inline-flex h-10 items-center gap-2 rounded-xl border px-3 text-xs font-black disabled:opacity-40">{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save</button>
                    <button type="button" disabled={publishing} onClick={() => void togglePublished()} className="inline-flex h-10 items-center gap-2 rounded-xl bg-primary px-4 text-xs font-black text-primary-foreground disabled:opacity-50">{publishing ? <Loader2 className="h-4 w-4 animate-spin" /> : profile.is_published ? <ShieldCheck className="h-4 w-4" /> : <Rocket className="h-4 w-4" />}{profile.is_published ? "Unpublish" : "Publish website"}</button>
                </div>
            </section>

            <section className="grid min-h-[720px] gap-5 xl:grid-cols-[390px_minmax(0,1fr)]">
                <aside className="space-y-5 rounded-3xl border bg-card p-5 shadow-sm xl:max-h-[calc(100dvh-7rem)] xl:overflow-y-auto">
                    <div>
                        <h2 className="flex items-center gap-2 font-black"><LayoutTemplate className="h-4 w-4" /> Website template</h2>
                        <div className="mt-3 grid gap-3">
                            {TEMPLATES.map((template) => (
                                <button key={template.key} type="button" onClick={() => patch("template_key", template.key)} className={`rounded-2xl border p-4 text-left transition ${profile.template_key === template.key ? "border-primary ring-2 ring-primary/20" : "hover:border-primary/50"}`}>
                                    <div className="flex items-center justify-between gap-3"><strong className="text-sm">{template.name}</strong>{profile.template_key === template.key && <Check className="h-4 w-4 text-primary" />}</div>
                                    <p className="mt-1 text-xs leading-5 text-muted-foreground">{template.description}</p>
                                </button>
                            ))}
                        </div>
                    </div>

                    <EditorField label="Hero badge"><input value={profile.hero_badge ?? ""} onChange={(event) => patch("hero_badge", event.target.value)} className="website-builder-input" /></EditorField>
                    <EditorField label="Main headline"><textarea value={profile.headline} onChange={(event) => patch("headline", event.target.value)} rows={3} className="website-builder-input min-h-24 resize-y" /></EditorField>
                    <EditorField label="Subheadline"><textarea value={profile.subheadline ?? ""} onChange={(event) => patch("subheadline", event.target.value)} rows={4} className="website-builder-input min-h-28 resize-y" /></EditorField>
                    <EditorField label="About company"><textarea value={profile.about ?? ""} onChange={(event) => patch("about", event.target.value)} rows={5} className="website-builder-input min-h-32 resize-y" /></EditorField>

                    <div className="grid grid-cols-2 gap-3">
                        <EditorField label="Primary colour"><input type="color" value={profile.primary_color} onChange={(event) => patch("primary_color", event.target.value.toUpperCase())} className="h-11 w-full rounded-xl border bg-background p-1" /></EditorField>
                        <EditorField label="Accent colour"><input type="color" value={profile.accent_color} onChange={(event) => patch("accent_color", event.target.value.toUpperCase())} className="h-11 w-full rounded-xl border bg-background p-1" /></EditorField>
                    </div>
                    <EditorField label="Public phone"><input value={profile.contact_phone ?? ""} onChange={(event) => patch("contact_phone", event.target.value)} className="website-builder-input" /></EditorField>
                    <EditorField label="Public email"><input type="email" value={profile.contact_email ?? ""} onChange={(event) => patch("contact_email", event.target.value)} className="website-builder-input" /></EditorField>

                    <Toggle label="Show active LoanHub loan products" checked={profile.show_loan_products} onChange={(value) => patch("show_loan_products", value)} />
                    <Toggle label="Show create-account and sign-in actions" checked={profile.show_account_cta} onChange={(value) => patch("show_account_cta", value)} />
                </aside>

                <section className="min-w-0 overflow-hidden rounded-3xl border bg-muted/20 shadow-sm">
                    <div className="flex items-center justify-between border-b bg-card px-4 py-3">
                        <div className="flex items-center gap-2"><MonitorSmartphone className="h-4 w-4 text-primary" /><span className="text-xs font-black">Live website preview</span></div>
                        <span className="hidden max-w-[60%] truncate font-mono text-[11px] text-muted-foreground md:inline">{publicUrl}</span>
                    </div>
                    <div className="h-[calc(100%-49px)] overflow-auto bg-background">
                        <BuilderPreview profile={profile} products={products} />
                    </div>
                </section>
            </section>
            <style jsx global>{`
                .website-builder-input { width: 100%; min-height: 44px; border-radius: 0.75rem; border: 1px solid hsl(var(--border)); background: hsl(var(--background)); padding: 0.65rem 0.8rem; font-size: 0.875rem; outline: none; }
                .website-builder-input:focus { border-color: hsl(var(--primary)); box-shadow: 0 0 0 2px hsl(var(--primary) / .14); }
            `}</style>
        </main>
    );
}

function EditorField({ label, children }: { label: string; children: ReactNode }) {
    return <label className="block"><span className="mb-1.5 block text-xs font-black text-muted-foreground">{label}</span>{children}</label>;
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
    return <label className="flex cursor-pointer items-center justify-between gap-4 rounded-2xl border p-3"><span className="text-xs font-black">{label}</span><input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} className="h-5 w-5 accent-primary" /></label>;
}

function TemplatePreview({ template, name, description }: { template: CompanyWebsiteTemplate; name: string; description: string }) {
    return <article className={`overflow-hidden rounded-3xl border bg-card shadow-sm ${template === "modern_finance" ? "p-2" : "p-5"}`}><div className={`h-40 rounded-2xl ${template === "modern_finance" ? "bg-slate-950 p-5 text-white" : "bg-primary/10 p-5"}`}><div className="h-3 w-24 rounded-full bg-current opacity-25" /><div className="mt-5 h-5 w-2/3 rounded-full bg-current opacity-60" /><div className="mt-2 h-3 w-1/2 rounded-full bg-current opacity-20" /><div className="mt-5 h-8 w-28 rounded-xl bg-current opacity-80" /></div><div className="p-2 pt-4"><h3 className="font-black">{name}</h3><p className="mt-1 text-xs leading-5 text-muted-foreground">{description}</p></div></article>;
}

function BuilderPreview({ profile, products }: { profile: CompanyWebsiteProfile; products: PublicLoanProduct[] }) {
    const modern = profile.template_key === "modern_finance";
    const visibleProducts = profile.show_loan_products ? products : [];
    return (
        <div className={modern ? "min-h-full bg-slate-950 text-white" : "min-h-full bg-white text-slate-950"}>
            <nav className="flex items-center justify-between gap-4 px-6 py-5 md:px-10"><strong className="text-lg">{profile.company_name}</strong><div className="flex gap-2 text-xs font-bold"><span>Loans</span><span>About</span><span>Contact</span></div></nav>
            <section className={`px-6 py-14 md:px-10 md:py-20 ${modern ? "border-y border-white/10" : "bg-slate-50"}`}>
                <div className="max-w-3xl"><span className="inline-flex rounded-full px-3 py-1 text-xs font-black" style={{ backgroundColor: `${profile.accent_color}20`, color: profile.accent_color }}>{profile.hero_badge || "Powered by LoanHub"}</span><h1 className="mt-5 text-4xl font-black tracking-tight md:text-6xl">{profile.headline}</h1><p className={`mt-5 max-w-2xl leading-7 ${modern ? "text-slate-300" : "text-slate-600"}`}>{profile.subheadline}</p>{profile.show_account_cta && <div className="mt-7 flex flex-wrap gap-3"><span className="rounded-xl px-5 py-3 text-sm font-black text-white" style={{ backgroundColor: profile.primary_color }}>Create borrower account</span><span className={`rounded-xl border px-5 py-3 text-sm font-black ${modern ? "border-white/20" : "border-slate-300"}`}>Sign in</span></div>}</div>
            </section>
            {profile.show_loan_products && (
                <section className="px-6 py-12 md:px-10">
                    <p className="text-xs font-black uppercase tracking-[0.15em]" style={{ color: profile.accent_color }}>Active LoanHub products</p>
                    <h2 className="mt-2 text-2xl font-black">Real products from the current company database</h2>
                    {visibleProducts.length ? (
                        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                            {visibleProducts.map((product) => (
                                <div key={product.id} className={`rounded-2xl border p-5 ${modern ? "border-white/10 bg-white/5" : "bg-white"}`}>
                                    <strong>{product.name}</strong>
                                    <p className={`mt-2 text-xs ${modern ? "text-slate-400" : "text-slate-500"}`}>M {product.min_amount.toLocaleString()} – M {product.max_amount.toLocaleString()} · {product.min_term_months}–{product.max_term_months} months</p>
                                    <p className="mt-3 text-sm font-black" style={{ color: profile.accent_color }}>{product.interest_rate_percent}% interest</p>
                                </div>
                            ))}
                        </div>
                    ) : <p className={`mt-5 rounded-2xl border border-dashed p-6 text-sm ${modern ? "border-white/15 text-slate-400" : "text-slate-500"}`}>No active company loan products are currently stored in LoanHub.</p>}
                </section>
            )}
            <section className={`px-6 py-12 md:px-10 ${modern ? "bg-white/5" : "bg-slate-50"}`}><h2 className="text-2xl font-black">About {profile.company_name}</h2><p className={`mt-3 max-w-3xl leading-7 ${modern ? "text-slate-300" : "text-slate-600"}`}>{profile.about}</p></section>
        </div>
    );
}
