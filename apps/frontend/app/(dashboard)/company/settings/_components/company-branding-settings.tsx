"use client";

import { BadgeCheck, Building2, ImagePlus, Loader2, ShieldCheck } from "lucide-react";

import type { CompanySettingsModel } from "../_hooks/use-company-settings";

export function CompanyBrandingSettings({
    companyName,
    branding,
    canManage,
    uploadingLogo,
    uploadLogo,
}: {
    companyName: string;
    branding: CompanySettingsModel["branding"];
    canManage: boolean;
    uploadingLogo: CompanySettingsModel["uploadingLogo"];
    uploadLogo: CompanySettingsModel["uploadLogo"];
}) {
    return (
        <section className="overflow-hidden rounded-3xl border bg-card shadow-sm">
            <div className="border-b bg-gradient-to-r from-primary/10 via-background to-emerald-500/10 p-5 sm:p-7">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                        <div className="flex items-center gap-2 text-primary">
                            <ImagePlus className="h-5 w-5" />
                            <span className="text-xs font-black uppercase tracking-[0.16em]">Document identity</span>
                        </div>
                        <h2 className="mt-2 text-2xl font-black">Company document branding</h2>
                        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
                            Every FastAPI-generated contract, repayment schedule, statement and payment slip can display LoanHub and {companyName} together.
                        </p>
                    </div>
                    <div className="rounded-2xl border bg-background/80 p-4 shadow-sm backdrop-blur">
                        <p className="text-xs font-black uppercase tracking-wide text-muted-foreground">Current layout</p>
                        <div className="mt-2 flex items-center gap-3">
                            <div className="flex h-10 w-20 items-center justify-center rounded-xl bg-primary/10 text-xs font-black text-primary">LoanHub</div>
                            <div className="h-px w-8 bg-border" />
                            <div className="flex h-10 w-20 items-center justify-center rounded-xl bg-emerald-500/10 text-xs font-black text-emerald-700">Company</div>
                        </div>
                    </div>
                </div>
            </div>

            <div className="grid gap-5 p-5 sm:p-7 lg:grid-cols-2">
                <LogoUploadCard
                    title="System-side company logo"
                    description="Optional company logo stored for left-side layouts. LoanHub remains the default system identity."
                    existingName={branding?.left_logo_file?.original_name ?? null}
                    disabled={!canManage || uploadingLogo === "right"}
                    busy={uploadingLogo === "left"}
                    onFileSelect={(file) => void uploadLogo("left", file)}
                    icon={<Building2 className="h-5 w-5" />}
                />
                <LogoUploadCard
                    title="Primary company logo"
                    description="Displayed on the right side of generated documents alongside the LoanHub logo."
                    existingName={branding?.right_logo_file?.original_name ?? null}
                    disabled={!canManage || uploadingLogo === "left"}
                    busy={uploadingLogo === "right"}
                    onFileSelect={(file) => void uploadLogo("right", file)}
                    icon={<BadgeCheck className="h-5 w-5" />}
                />
            </div>

            <div className="mx-5 mb-5 flex items-start gap-3 rounded-2xl bg-muted/50 p-4 text-xs leading-5 text-muted-foreground sm:mx-7 sm:mb-7">
                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                Use a transparent PNG or a clean JPEG/WebP with enough whitespace. Uploaded logos are stored in LoanHub’s managed-file system and are not exposed publicly.
            </div>
        </section>
    );
}

function LogoUploadCard({
    title,
    description,
    existingName,
    disabled,
    busy,
    onFileSelect,
    icon,
}: {
    title: string;
    description: string;
    existingName: string | null;
    disabled: boolean;
    busy: boolean;
    onFileSelect: (file: File | null) => void;
    icon: React.ReactNode;
}) {
    return (
        <article className="rounded-3xl border bg-muted/15 p-5 transition hover:border-primary/30">
            <div className="flex items-start gap-3">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">{icon}</div>
                <div>
                    <h3 className="font-black">{title}</h3>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">{description}</p>
                </div>
            </div>
            <div className="mt-5 rounded-2xl border bg-background p-4">
                <p className="text-[11px] font-black uppercase tracking-wide text-muted-foreground">Current file</p>
                <p className="mt-2 truncate text-sm font-bold">{existingName ?? "No company logo uploaded"}</p>
            </div>
            <label className={`mt-4 flex h-12 items-center justify-center gap-2 rounded-xl border bg-background px-4 text-sm font-black transition ${disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer hover:border-primary hover:text-primary"}`}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ImagePlus className="h-4 w-4" />}
                {busy ? "Uploading logo..." : "Choose logo image"}
                <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    className="hidden"
                    disabled={disabled || busy}
                    onChange={(event) => onFileSelect(event.target.files?.[0] ?? null)}
                />
            </label>
        </article>
    );
}
