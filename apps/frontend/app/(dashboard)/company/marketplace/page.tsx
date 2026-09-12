"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import {
    ClipboardList,
    Search,
    SlidersHorizontal,
    Store,
    type LucideIcon,
} from "lucide-react";

import { ErrorPanel } from "@/components/portal/error-panel";
import { LoadingPanel } from "@/components/portal/loading-panel";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { PageLoader } from "@/components/ui/page-loader";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAppData } from "@/provider/appDataProvider";
import { useTenant } from "@/provider/tenantProvider";
import {
    DIRECT_APPLICATION_ROLES,
    LENDING_ROLES,
    hasRole,
} from "@/types/auth";
import type { MarketplaceRequestCard } from "@/types/marketplace";

import { InternalApplicationsWorkspace } from "./_components/internal-applications-workspace";
import { MarketplaceRequestCardView } from "./_components/marketplace-request-card";
import { MarketplaceRequestDialog } from "./_components/marketplace-request-dialog";

type MarketplaceWorkspace = "opportunities" | "applications";

export default function MarketplacePage() {
    return (
        <Suspense fallback={<PageLoader rows={7} />}>
            <MarketplaceWorkspacePage />
        </Suspense>
    );
}

function MarketplaceWorkspacePage() {
    const pathname = usePathname();
    const router = useRouter();
    const searchParams = useSearchParams();
    const { activeRole } = useTenant();

    const canBrowseOpportunities = hasRole(activeRole, LENDING_ROLES);
    const canProcessApplications = hasRole(activeRole, DIRECT_APPLICATION_ROLES);
    const requestedWorkspace = searchParams.get("workspace");
    const requestedApplicationId = searchParams.get("application");

    let workspace: MarketplaceWorkspace = canBrowseOpportunities
        ? "opportunities"
        : "applications";

    if ((requestedApplicationId || requestedWorkspace === "applications") && canProcessApplications) {
        workspace = "applications";
    } else if (requestedWorkspace === "opportunities" && canBrowseOpportunities) {
        workspace = "opportunities";
    }

    function changeWorkspace(value: string) {
        const next = value as MarketplaceWorkspace;
        const params = new URLSearchParams(searchParams.toString());
        params.set("workspace", next);
        if (next !== "applications") params.delete("application");
        router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    }

    if (!canBrowseOpportunities && !canProcessApplications) {
        return (
            <section className="rounded-3xl border bg-card p-8 text-center shadow-sm">
                <Store className="mx-auto h-12 w-12 text-muted-foreground" />
                <h1 className="mt-4 text-2xl font-black">Lending workspace unavailable</h1>
                <p className="mx-auto mt-2 max-w-xl text-sm text-muted-foreground">
                    Your active role does not have permission to browse marketplace opportunities or process internal loan applications.
                </p>
            </section>
        );
    }

    return (
        <main className="loanhub-page space-y-6">
            <section className="loanhub-hero overflow-hidden p-6 sm:p-8">
                <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
                    <div className="max-w-4xl">
                        <p className="text-xs font-black uppercase tracking-[0.22em] text-primary">
                            Lending opportunities and application processing
                        </p>
                        <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">
                            Marketplace & internal applications
                        </h1>
                        <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
                            Work from one lending desk: discover public borrower opportunities, or review applications submitted directly by your registered clients.
                        </p>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2 xl:min-w-[34rem]">
                        {canBrowseOpportunities ? (
                            <ChannelSummary
                                active={workspace === "opportunities"}
                                icon={Store}
                                title="Marketplace"
                                description="Unlock broadcasts and submit offers"
                                onClick={() => changeWorkspace("opportunities")}
                            />
                        ) : null}
                        {canProcessApplications ? (
                            <ChannelSummary
                                active={workspace === "applications"}
                                icon={ClipboardList}
                                title="Internal applications"
                                description="Review, approve and create loans"
                                onClick={() => changeWorkspace("applications")}
                            />
                        ) : null}
                    </div>
                </div>
            </section>

            <Tabs value={workspace} onValueChange={changeWorkspace} className="gap-5">
                <TabsList className={`grid h-auto w-full rounded-2xl p-1 ${canBrowseOpportunities && canProcessApplications ? "grid-cols-1 sm:grid-cols-2" : "grid-cols-1"}`}>
                    {canBrowseOpportunities ? (
                        <TabsTrigger value="opportunities" className="min-h-11 rounded-xl px-4 py-2.5">
                            <Store className="h-4 w-4" />
                            Marketplace opportunities
                        </TabsTrigger>
                    ) : null}
                    {canProcessApplications ? (
                        <TabsTrigger value="applications" className="min-h-11 rounded-xl px-4 py-2.5">
                            <ClipboardList className="h-4 w-4" />
                            Internal applications
                        </TabsTrigger>
                    ) : null}
                </TabsList>

                {canBrowseOpportunities ? (
                    <TabsContent value="opportunities" className="mt-0">
                        <MarketplaceOpportunitiesWorkspace />
                    </TabsContent>
                ) : null}

                {canProcessApplications ? (
                    <TabsContent value="applications" className="mt-0">
                        <InternalApplicationsWorkspace />
                    </TabsContent>
                ) : null}
            </Tabs>
        </main>
    );
}

function MarketplaceOpportunitiesWorkspace() {
    const {
        marketplaceRequests,
        isMarketplaceLoading,
        errors,
        refreshAllData,
    } = useAppData();
    const [search, setSearch] = useState("");
    const [district, setDistrict] = useState("all");
    const [unlockFilter, setUnlockFilter] = useState("all");
    const [selected, setSelected] = useState<MarketplaceRequestCard | null>(null);

    const districts = useMemo(
        () => Array.from(new Set(
            marketplaceRequests
                .map((item) => item.borrower.district)
                .filter((item): item is string => Boolean(item)),
        )).sort(),
        [marketplaceRequests],
    );

    const filtered = useMemo(() => {
        const query = search.trim().toLowerCase();
        return marketplaceRequests.filter((item) => {
            const matchesSearch =
                !query ||
                item.loan_purpose?.toLowerCase().includes(query) ||
                item.borrower.district?.toLowerCase().includes(query) ||
                item.borrower.employment_status.toLowerCase().includes(query) ||
                String(item.requested_amount).includes(query);
            const matchesDistrict = district === "all" || item.borrower.district === district;
            const matchesUnlock =
                unlockFilter === "all" ||
                (unlockFilter === "unlocked" && item.is_unlocked) ||
                (unlockFilter === "locked" && !item.is_unlocked);
            return matchesSearch && matchesDistrict && matchesUnlock;
        });
    }, [district, marketplaceRequests, search, unlockFilter]);

    return (
        <div className="space-y-6">
            <section className="rounded-3xl border border-border/70 bg-card p-5 shadow-sm sm:p-6">
                <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
                    <div>
                        <p className="text-xs font-black uppercase tracking-[0.2em] text-primary">Public lending channel</p>
                        <h2 className="mt-2 text-2xl font-black tracking-tight">Borrower opportunities</h2>
                        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
                            Assess borrower broadcasts, unlock qualified opportunities and submit competitive offers.
                        </p>
                    </div>
                    <div className="grid w-full gap-3 sm:grid-cols-2 xl:max-w-3xl xl:grid-cols-3">
                        <div className="relative">
                            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                            <Input
                                value={search}
                                onChange={(event) => setSearch(event.target.value)}
                                placeholder="Purpose, district, amount..."
                                className="h-11 w-full rounded-xl border bg-background pl-10 pr-3"
                            />
                        </div>
                        <NativeSelect
                            value={district}
                            onChange={(event) => setDistrict(event.target.value)}
                            className="h-11 rounded-xl border bg-background px-3"
                        >
                            <option value="all">All districts</option>
                            {districts.map((item) => <option key={item} value={item}>{item}</option>)}
                        </NativeSelect>
                        <div className="relative sm:col-span-2 xl:col-span-1">
                            <SlidersHorizontal className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                            <NativeSelect
                                value={unlockFilter}
                                onChange={(event) => setUnlockFilter(event.target.value)}
                                className="h-11 w-full appearance-none rounded-xl border bg-background pl-10 pr-3"
                            >
                                <option value="all">All opportunities</option>
                                <option value="unlocked">Unlocked</option>
                                <option value="locked">Locked</option>
                            </NativeSelect>
                        </div>
                    </div>
                </div>
            </section>

            {errors.marketplace ? (
                <ErrorPanel message={errors.marketplace} onRetry={() => void refreshAllData()} />
            ) : null}

            {isMarketplaceLoading && marketplaceRequests.length === 0 ? (
                <LoadingPanel label="Loading marketplace opportunities..." />
            ) : filtered.length === 0 ? (
                <section className="rounded-3xl border bg-card p-10 text-center sm:p-12">
                    <Store className="mx-auto h-12 w-12 text-muted-foreground" />
                    <h2 className="mt-4 text-xl font-black">No matching loan requests</h2>
                    <p className="mt-2 text-sm text-muted-foreground">
                        New borrower broadcasts will appear here automatically.
                    </p>
                </section>
            ) : (
                <section className="grid gap-5 md:grid-cols-2 2xl:grid-cols-3">
                    {filtered.map((request) => (
                        <MarketplaceRequestCardView key={request.id} request={request} onOpen={setSelected} />
                    ))}
                </section>
            )}

            <MarketplaceRequestDialog
                request={selected}
                open={Boolean(selected)}
                onOpenChange={(open) => !open && setSelected(null)}
            />
        </div>
    );
}

function ChannelSummary({
    active,
    icon: Icon,
    title,
    description,
    onClick,
}: {
    active: boolean;
    icon: LucideIcon;
    title: string;
    description: string;
    onClick: () => void;
}) {
    return (
        <button
            type="button"
            onClick={onClick}
            className={`flex min-w-0 items-center gap-3 rounded-2xl border p-4 text-left transition ${
                active
                    ? "border-primary/30 bg-primary/10 shadow-sm"
                    : "border-border/70 bg-background/75 hover:border-primary/25 hover:bg-background"
            }`}
        >
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Icon className="h-5 w-5" />
            </span>
            <span className="min-w-0">
                <span className="block truncate text-sm font-black">{title}</span>
                <span className="mt-0.5 block text-xs leading-5 text-muted-foreground">{description}</span>
            </span>
        </button>
    );
}
