"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    Banknote,
    BriefcaseBusiness,
    Building2,
    ChartNoAxesCombined,
    CircleDollarSign,
    ContactRound,
    CreditCard,
    FileChartColumn,
    FilePenLine,
    FileText,
    FolderOpen,
    Gavel,
    GitBranch,
    HandCoins,
    Headphones,
    History,
    Home,
    Landmark,
    Menu,
    MessageCircleMore,
    MessageSquarePlus,
    PackageSearch,
    ReceiptText,
    ServerCog,
    Settings,
    ShieldCheck,
    Store,
    TriangleAlert,
    UserRound,
    UsersRound,
    WalletCards,
    X,
    type LucideIcon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { InterfaceScaleController } from "@/components/accessibility/interface-scale-controller";
import { ThemeSwitcher } from "@/components/theme-switcher";
import { useTenant } from "@/provider/tenantProvider";
import {
    ACCOUNTING_ROLES,
    CASHIER_ROLES,
    COLLECTIONS_ROLES,
    COMPANY_MANAGEMENT_ROLES,
    DIRECT_APPLICATION_ROLES,
    HR_ROLES,
    LENDING_OPERATIONS_ROLES,
    LENDING_ROLES,
    PERFORMANCE_ROLES,
    REPORTING_ROLES,
    TRANSPARENCY_ROLES,
    TREASURY_ROLES,
    hasRole,
    type UserRole,
} from "@/types/auth";

type AppMode = "company" | "borrower" | "platform" | "superadmin";

type MobileNavItem = {
    label: string;
    shortLabel?: string;
    href: string;
    icon: LucideIcon;
    roles?: readonly UserRole[];
};

const WORKFORCE_ROLES: readonly UserRole[] = Array.from(new Set([
    ...COMPANY_MANAGEMENT_ROLES,
    ...HR_ROLES,
    ...PERFORMANCE_ROLES,
]));

const navigationByMode: Record<AppMode, MobileNavItem[]> = {
    company: [
        { label: "Dashboard", shortLabel: "Home", href: "/company", icon: Home },
        { label: "Chat", href: "/company/chat", icon: MessageCircleMore },
        { label: "Marketplace", href: "/company/marketplace", icon: Store, roles: DIRECT_APPLICATION_ROLES },
        { label: "Clients", href: "/company/clients", icon: ContactRound, roles: LENDING_ROLES },
        { label: "Credit origination", shortLabel: "Originate", href: "/company/origination", icon: ShieldCheck, roles: DIRECT_APPLICATION_ROLES },
        { label: "Loans & contracts", shortLabel: "Loans", href: "/company/loans", icon: HandCoins },
        { label: "Payment desk", href: "/company/cashier", icon: Banknote, roles: CASHIER_ROLES },
        { label: "Payment register", shortLabel: "Payments", href: "/company/payments", icon: WalletCards },
        { label: "Accounting & expenses", href: "/company/expense-management", icon: CircleDollarSign, roles: TREASURY_ROLES },
        { label: "Lending operations", href: "/company/lending-operations", icon: BriefcaseBusiness, roles: LENDING_OPERATIONS_ROLES },
        { label: "Payment automation", shortLabel: "Automation", href: "/company/payment-operations", icon: WalletCards, roles: LENDING_OPERATIONS_ROLES },
        { label: "Control & assurance", shortLabel: "Controls", href: "/company/control-centre", icon: ShieldCheck, roles: TRANSPARENCY_ROLES },
        { label: "Collections & legal", href: "/company/collections", icon: Gavel, roles: COLLECTIONS_ROLES },
        { label: "Agreements & charges", href: "/company/finance", icon: Landmark, roles: ACCOUNTING_ROLES },
        { label: "Reports", href: "/company/reports", icon: FileChartColumn, roles: REPORTING_ROLES },
        { label: "Documents", href: "/company/documents", icon: FilePenLine },
        { label: "Files", href: "/company/files", icon: FolderOpen },
        { label: "Loan products", href: "/company/products", icon: PackageSearch, roles: COMPANY_MANAGEMENT_ROLES },
        { label: "Branches", href: "/company/branches", icon: GitBranch },
        { label: "Workforce & HR", href: "/company/hr", icon: UsersRound, roles: WORKFORCE_ROLES },
        { label: "Activity log", href: "/company/activity", icon: History, roles: TRANSPARENCY_ROLES },
        { label: "Subscription", href: "/company/billing", icon: CreditCard, roles: COMPANY_MANAGEMENT_ROLES },
        { label: "Support queries", href: "/company/queries", icon: MessageSquarePlus },
        { label: "Settings", href: "/company/settings", icon: Settings, roles: COMPANY_MANAGEMENT_ROLES },
        { label: "My profile", shortLabel: "Profile", href: "/company/account", icon: UserRound },
    ],
    borrower: [
        { label: "Dashboard", shortLabel: "Home", href: "/borrower", icon: Home },
        { label: "Chat", href: "/borrower/chat", icon: MessageCircleMore },
        { label: "Loan requests", shortLabel: "Requests", href: "/borrower/requests", icon: FileText },
        { label: "My loans", shortLabel: "Loans", href: "/borrower/loans", icon: HandCoins },
        { label: "Payments", href: "/borrower/payments", icon: Banknote },
        { label: "Documents", href: "/borrower/documents", icon: FilePenLine },
        { label: "My files", href: "/borrower/files", icon: FolderOpen },
        { label: "Support queries", href: "/borrower/queries", icon: MessageSquarePlus },
        { label: "Complaints & privacy", shortLabel: "Rights", href: "/borrower/complaints", icon: ShieldCheck },
        { label: "Profile", href: "/borrower/profile", icon: UserRound },
        { label: "Account & security", shortLabel: "Account", href: "/borrower/account", icon: Settings },
    ],
    platform: [
        { label: "Dashboard", shortLabel: "Home", href: "/platform", icon: Home },
        { label: "Document studio", shortLabel: "Docs", href: "/platform/documents", icon: FilePenLine },
        { label: "Support workspace", shortLabel: "Support", href: "/platform/support", icon: Headphones },
        { label: "Cash finance support", shortLabel: "Finance", href: "/platform/support", icon: ReceiptText },
        { label: "My profile", shortLabel: "Profile", href: "/platform/account", icon: UserRound },
    ],
    superadmin: [
        { label: "Dashboard", shortLabel: "Home", href: "/superadmin", icon: Home },
        { label: "Platform chat", href: "/superadmin/chat", icon: MessageCircleMore },
        { label: "Document studio", href: "/superadmin/documents", icon: FilePenLine },
        { label: "File centre", href: "/superadmin/files", icon: FolderOpen },
        { label: "All companies", shortLabel: "Tenants", href: "/superadmin/companies", icon: Building2 },
        { label: "Company branches", href: "/superadmin/companies/branches", icon: GitBranch },
        { label: "Company administrators", href: "/superadmin/company-admins", icon: UsersRound },
        { label: "Loan requests and loans", shortLabel: "Loans", href: "/superadmin/loans", icon: FileText },
        { label: "Platform payment register", href: "/superadmin/payments", icon: WalletCards },
        { label: "Finance rules & claims", href: "/superadmin/finance", icon: Landmark },
        { label: "Platform accounting", href: "/superadmin/accounting", icon: Landmark },
        { label: "Automated reports", shortLabel: "Reports", href: "/superadmin/reports", icon: FileChartColumn },
        { label: "Subscription plans", href: "/superadmin/plans", icon: CreditCard },
        { label: "Platform employees", href: "/superadmin/employees", icon: UsersRound },
        { label: "Platform performance", href: "/superadmin/performance", icon: ChartNoAxesCombined },
        { label: "Activity log", href: "/superadmin/activity", icon: History },
        { label: "System errors", href: "/superadmin/system-errors", icon: TriangleAlert },
        { label: "System update", href: "/superadmin/system-update", icon: ServerCog },
        { label: "User queries", href: "/superadmin/queries", icon: MessageSquarePlus },
        { label: "My profile", shortLabel: "Profile", href: "/superadmin/account", icon: UserRound },
    ],
};

const quickHrefsByMode: Record<AppMode, string[]> = {
    company: ["/company", "/company/clients", "/company/origination", "/company/loans"],
    borrower: ["/borrower", "/borrower/requests", "/borrower/loans", "/borrower/payments"],
    platform: ["/platform", "/platform/documents", "/platform/support", "/platform/account"],
    superadmin: ["/superadmin", "/superadmin/companies", "/superadmin/loans", "/superadmin/reports"],
};

function modeForPath(pathname: string): AppMode | null {
    if (pathname === "/company" || pathname.startsWith("/company/")) return "company";
    if (pathname === "/borrower" || pathname.startsWith("/borrower/")) return "borrower";
    if (pathname === "/platform" || pathname.startsWith("/platform/")) return "platform";
    if (pathname === "/superadmin" || pathname.startsWith("/superadmin/")) return "superadmin";
    return null;
}

function isActive(pathname: string, href: string): boolean {
    if (["/company", "/borrower", "/platform", "/superadmin"].includes(href)) {
        return pathname === href;
    }
    return pathname === href || pathname.startsWith(`${href}/`);
}

function dedupeByHref(items: MobileNavItem[]): MobileNavItem[] {
    const seen = new Set<string>();
    return items.filter((item) => {
        if (seen.has(item.href)) return false;
        seen.add(item.href);
        return true;
    });
}

export function MobileAppNavigation() {
    const pathname = usePathname();
    const { activeRole } = useTenant();
    const [moreOpen, setMoreOpen] = useState(false);
    const mode = modeForPath(pathname);

    const navigation = useMemo(() => {
        if (!mode) return [];
        const role = mode === "company" ? activeRole : null;
        return dedupeByHref(navigationByMode[mode].filter((item) => !item.roles || hasRole(role, item.roles)));
    }, [activeRole, mode]);

    const quickItems = useMemo(() => {
        if (!mode) return [];
        const preferred = quickHrefsByMode[mode]
            .map((href) => navigation.find((item) => item.href === href))
            .filter((item): item is MobileNavItem => Boolean(item));
        const fallback = navigation.filter((item) => !preferred.some((candidate) => candidate.href === item.href));
        return [...preferred, ...fallback].slice(0, 4);
    }, [mode, navigation]);

    useEffect(() => {
        setMoreOpen(false);
    }, [pathname]);

    useEffect(() => {
        const root = document.documentElement;
        if (!mode) {
            delete root.dataset.loanhubMobileApp;
            return;
        }

        const media = window.matchMedia("(max-width: 1023px)");
        const sync = () => {
            if (media.matches) root.dataset.loanhubMobileApp = "true";
            else delete root.dataset.loanhubMobileApp;
        };
        sync();
        media.addEventListener("change", sync);
        return () => {
            media.removeEventListener("change", sync);
            delete root.dataset.loanhubMobileApp;
        };
    }, [mode]);

    useEffect(() => {
        if (!moreOpen) return;
        const previousOverflow = document.body.style.overflow;
        document.body.style.overflow = "hidden";
        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key === "Escape") setMoreOpen(false);
        };
        window.addEventListener("keydown", onKeyDown);
        return () => {
            document.body.style.overflow = previousOverflow;
            window.removeEventListener("keydown", onKeyDown);
        };
    }, [moreOpen]);

    if (!mode || quickItems.length === 0) return null;

    const currentIsQuick = quickItems.some((item) => isActive(pathname, item.href));

    return (
        <>
            <nav
                data-loanhub-mobile-nav="true"
                aria-label="Primary app navigation"
                className="loanhub-mobile-bottom-nav fixed inset-x-0 bottom-0 z-[70] border-t border-border/80 bg-background/95 shadow-[0_-10px_35px_-20px_rgba(15,23,42,0.45)] backdrop-blur-xl lg:hidden"
            >
                <div className="mx-auto grid min-h-[4.25rem] max-w-2xl grid-cols-5 px-1 sm:px-3">
                    {quickItems.map((item) => {
                        const Icon = item.icon;
                        const active = isActive(pathname, item.href);
                        return (
                            <Link
                                key={item.href}
                                href={item.href}
                                aria-current={active ? "page" : undefined}
                                className={`group relative flex min-w-0 flex-col items-center justify-center gap-1 rounded-2xl px-1 py-2 text-[10px] font-bold transition active:scale-95 sm:text-[11px] ${active ? "text-primary" : "text-muted-foreground hover:text-foreground"}`}
                            >
                                <span className={`flex h-8 min-w-11 items-center justify-center rounded-full px-3 transition ${active ? "bg-primary/12 text-primary" : "group-hover:bg-muted"}`}>
                                    <Icon className="h-5 w-5" strokeWidth={active ? 2.5 : 2} />
                                </span>
                                <span className="max-w-full truncate">{item.shortLabel ?? item.label}</span>
                                {active ? <span className="absolute bottom-1 h-1 w-1 rounded-full bg-primary" aria-hidden /> : null}
                            </Link>
                        );
                    })}
                    <button
                        type="button"
                        data-testid="mobile-nav-more"
                        aria-haspopup="dialog"
                        aria-expanded={moreOpen}
                        onClick={() => setMoreOpen(true)}
                        className={`group relative flex min-w-0 flex-col items-center justify-center gap-1 rounded-2xl px-1 py-2 text-[10px] font-bold transition active:scale-95 sm:text-[11px] ${!currentIsQuick ? "text-primary" : "text-muted-foreground hover:text-foreground"}`}
                    >
                        <span className={`flex h-8 min-w-11 items-center justify-center rounded-full px-3 transition ${!currentIsQuick ? "bg-primary/12" : "group-hover:bg-muted"}`}>
                            <Menu className="h-5 w-5" />
                        </span>
                        <span>More</span>
                        {!currentIsQuick ? <span className="absolute bottom-1 h-1 w-1 rounded-full bg-primary" aria-hidden /> : null}
                    </button>
                </div>
            </nav>

            {moreOpen ? (
                <div className="fixed inset-0 z-[90] lg:hidden">
                    <button
                        type="button"
                        aria-label="Close app menu"
                        className="absolute inset-0 bg-slate-950/55 backdrop-blur-sm"
                        onClick={() => setMoreOpen(false)}
                    />
                    <section
                        role="dialog"
                        aria-modal="true"
                        aria-labelledby="loanhub-mobile-tools-title"
                        data-testid="mobile-nav-more-sheet"
                        className="loanhub-mobile-more-sheet absolute inset-x-0 bottom-0 mx-auto flex max-h-[84dvh] max-w-3xl flex-col overflow-hidden rounded-t-[2rem] border border-b-0 bg-background shadow-2xl"
                    >
                        <div className="mx-auto mt-2 h-1.5 w-12 rounded-full bg-muted-foreground/25" aria-hidden />
                        <div className="flex items-center justify-between gap-3 border-b px-4 pb-3 pt-2 sm:px-6">
                            <div className="min-w-0">
                                <h2 id="loanhub-mobile-tools-title" className="text-base font-black sm:text-lg">LoanHub tools</h2>
                                <p className="truncate text-xs text-muted-foreground">All workspace navigation in one place</p>
                            </div>
                            <button
                                type="button"
                                aria-label="Close tools"
                                onClick={() => setMoreOpen(false)}
                                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border bg-background transition hover:bg-muted"
                            >
                                <X className="h-5 w-5" />
                            </button>
                        </div>

                        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-3 py-3 sm:px-5 sm:py-4">
                            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                                {navigation.map((item) => {
                                    const Icon = item.icon;
                                    const active = isActive(pathname, item.href);
                                    return (
                                        <Link
                                            key={`${item.href}-${item.label}`}
                                            href={item.href}
                                            onClick={() => setMoreOpen(false)}
                                            aria-current={active ? "page" : undefined}
                                            className={`flex min-h-20 items-center gap-3 rounded-2xl border p-3 text-left transition active:scale-[0.98] ${active ? "border-primary/40 bg-primary/10 text-primary" : "bg-card hover:border-primary/30 hover:bg-muted/50"}`}
                                        >
                                            <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${active ? "bg-primary text-primary-foreground" : "bg-muted text-foreground"}`}>
                                                <Icon className="h-5 w-5" />
                                            </span>
                                            <span className="min-w-0 text-xs font-black leading-4 sm:text-sm">
                                                {item.label}
                                            </span>
                                        </Link>
                                    );
                                })}
                            </div>
                        </div>

                        <div className="loanhub-safe-area-bottom border-t bg-muted/20 px-4 py-3 sm:px-6">
                            <div className="flex items-center justify-between gap-3">
                                <div>
                                    <p className="text-xs font-black">Display</p>
                                    <p className="text-[10px] text-muted-foreground">Size and theme</p>
                                </div>
                                <div className="flex items-center gap-2">
                                    <InterfaceScaleController />
                                    <ThemeSwitcher />
                                </div>
                            </div>
                        </div>
                    </section>
                </div>
            ) : null}
        </>
    );
}
