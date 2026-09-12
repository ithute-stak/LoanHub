"use client";

import {
    AlertCircle,
    BadgeCheck,
    Building2,
    FileSignature,
    ImagePlus,
    Landmark,
    Settings2,
    Share2,
    ShieldCheck,
} from "lucide-react";
import { useEffect, useState } from "react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { CompanyBrandingSettings } from "./_components/company-branding-settings";
import { CompanyLoanSettingsPanel } from "./_components/company-loan-settings";
import { CompanySettingsForm } from "./_components/company-settings-form";
import { CompanySettingsHeader } from "./_components/company-settings-header";
import { CompanySettingsSidebar } from "./_components/company-settings-sidebar";
import { CompanySettingsSkeleton } from "./_components/company-settings-skeleton";
import { InstitutionGovernanceSettings } from "./_components/institution-governance-settings";
import { CompanySocialSharingSettings } from "./_components/company-social-sharing-settings";
import { CompanyTopUpRulesSettings } from "./_components/company-top-up-rules-settings";
import { useCompanySettings } from "./_hooks/use-company-settings";

const VALID_TABS = new Set(["profile", "governance", "branding", "loan-settings", "top-up-rules", "social-sharing"]);

export default function CompanySettingsPage() {
    const settings = useCompanySettings();
    const [tab, setTab] = useState("profile");

    useEffect(() => {
        const requested = new URLSearchParams(window.location.search).get("tab");
        if (requested && VALID_TABS.has(requested)) setTab(requested);
    }, []);

    if (settings.isLoading) {
        return <CompanySettingsSkeleton />;
    }

    if (!settings.currentCompany) {
        return (
            <main className="flex min-h-[55vh] items-center justify-center">
                <section className="w-full max-w-xl rounded-3xl border bg-card p-8 text-center shadow-sm">
                    <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400">
                        <Building2 className="h-8 w-8" />
                    </div>
                    <h1 className="mt-5 text-2xl font-black">Company profile unavailable</h1>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">
                        Your account is not connected to an active company tenant, or the company data could not be loaded.
                    </p>
                    {settings.pageError && (
                        <div className="mt-5 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-left text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">
                            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                            <span>{settings.pageError}</span>
                        </div>
                    )}
                    <button type="button" onClick={settings.refreshAllData} className="mt-6 h-11 rounded-xl bg-primary px-5 text-sm font-black text-primary-foreground">
                        Retry loading company
                    </button>
                </section>
            </main>
        );
    }

    const rightLogoReady = Boolean(settings.branding?.right_logo_file);

    return (
        <main className="space-y-6">
            <CompanySettingsHeader
                companyName={settings.currentCompany.name}
                refreshing={settings.isLoading}
                onRefresh={settings.refreshAllData}
            />

            <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <SummaryCard
                    icon={BadgeCheck}
                    label="Profile completion"
                    value={`${settings.profileCompletion}%`}
                    detail={settings.profileCompletion === 100 ? "Official profile is complete" : "Some official details still need attention"}
                />
                <SummaryCard
                    icon={ImagePlus}
                    label="Document branding"
                    value={rightLogoReady ? "Ready" : "Needs logo"}
                    detail={rightLogoReady ? "Company logo will appear on generated documents" : "Upload the right-side company logo"}
                />
                <SummaryCard
                    icon={ShieldCheck}
                    label="Loan top-ups"
                    value="Company rules"
                    detail="Set this tenant's top-up eligibility, history and exception rules"
                />
                <SummaryCard
                    icon={FileSignature}
                    label="Loan contracts"
                    value="Company default"
                    detail="Choose the contract template used automatically for new loan contracts"
                />
            </section>

            <Tabs value={tab} onValueChange={setTab} className="gap-5">
                <div className="overflow-x-auto rounded-2xl border bg-card p-2 shadow-sm">
                    <TabsList className="grid h-12 min-w-[1240px] w-full grid-cols-6 rounded-xl">
                        <TabsTrigger value="profile" className="rounded-lg px-4 font-black">
                            <Settings2 className="h-4 w-4" /> Company profile
                        </TabsTrigger>
                        <TabsTrigger value="governance" className="rounded-lg px-4 font-black">
                            <Landmark className="h-4 w-4" /> Governance & compliance
                        </TabsTrigger>
                        <TabsTrigger value="branding" className="rounded-lg px-4 font-black">
                            <ImagePlus className="h-4 w-4" /> Document branding
                        </TabsTrigger>
                        <TabsTrigger value="loan-settings" className="rounded-lg px-4 font-black">
                            <FileSignature className="h-4 w-4" /> Loan settings
                        </TabsTrigger>
                        <TabsTrigger value="top-up-rules" className="rounded-lg px-4 font-black">
                            <ShieldCheck className="h-4 w-4" /> Loan top-up rules
                        </TabsTrigger>
                        <TabsTrigger value="social-sharing" className="rounded-lg px-4 font-black">
                            <Share2 className="h-4 w-4" /> Social sharing
                        </TabsTrigger>
                    </TabsList>
                </div>

                <TabsContent value="profile">
                    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
                        <CompanySettingsForm
                            form={settings.form}
                            errors={settings.errors}
                            canManage={settings.canManage}
                            submitting={settings.submitting}
                            isDirty={settings.isDirty}
                            updateField={settings.updateField}
                            reset={settings.reset}
                            save={settings.save}
                        />
                        <CompanySettingsSidebar
                            company={settings.currentCompany}
                            completion={settings.profileCompletion}
                            branding={settings.branding}
                        />
                    </div>
                </TabsContent>

                <TabsContent value="governance">
                    <InstitutionGovernanceSettings
                        canManage={settings.canManage}
                        institutionType={settings.currentCompany.institution_type ?? "loan_company"}
                    />
                </TabsContent>

                <TabsContent value="branding">
                    <CompanyBrandingSettings
                        companyName={settings.currentCompany.name}
                        branding={settings.branding}
                        canManage={settings.canManage}
                        uploadingLogo={settings.uploadingLogo}
                        uploadLogo={settings.uploadLogo}
                    />
                </TabsContent>

                <TabsContent value="loan-settings">
                    <CompanyLoanSettingsPanel canManage={settings.canManage} />
                </TabsContent>

                <TabsContent value="top-up-rules">
                    <CompanyTopUpRulesSettings canManage={settings.canManage} />
                </TabsContent>

                <TabsContent value="social-sharing">
                    <CompanySocialSharingSettings
                        companyId={settings.currentCompany.id}
                        canManage={settings.canManage}
                    />
                </TabsContent>
            </Tabs>
        </main>
    );
}

function SummaryCard({
    icon: Icon,
    label,
    value,
    detail,
}: {
    icon: typeof Building2;
    label: string;
    value: string;
    detail: string;
}) {
    return (
        <article className="rounded-3xl border bg-card p-5 shadow-sm">
            <div className="flex items-start gap-3">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                    <Icon className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                    <p className="text-xs font-black uppercase tracking-wide text-muted-foreground">{label}</p>
                    <p className="mt-1 text-xl font-black">{value}</p>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">{detail}</p>
                </div>
            </div>
        </article>
    );
}
