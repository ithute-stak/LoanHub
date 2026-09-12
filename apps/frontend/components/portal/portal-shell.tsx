"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
    Banknote,
    BookOpenCheck,
    BriefcaseBusiness,
    Building2,
    ChartNoAxesCombined,
    ChevronDown,
    ChevronRight,
    CircleDollarSign,
    ContactRound,
    CreditCard,
    FileChartColumn,
    FilePenLine,
    FileText,
    FolderOpen,
    GitBranch,
    HandCoins,
    History,
    Landmark,
    LayoutDashboard,
    LogOut,
    Menu,
    MessageCircleMore,
    MessageSquarePlus,
    PackageSearch,
    PanelLeftClose,
    PanelLeftOpen,
    Phone,
    Settings,
    Search,
    ShieldCheck,
    Store,
    Users,
    UsersRound,
    WalletCards,
    X,
    type LucideIcon,
    Gavel,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { InterfaceScaleController } from "@/components/accessibility/interface-scale-controller";
import { WorkspaceModeToggle, useWorkspaceFullscreen } from "@/components/accessibility/workspace-mode";
import { IthuteBrand, IthutePoweredBy } from "@/components/brand/ithute-brand";
import { ChatLauncher } from "@/components/chat/chat-launcher";
import { GlobalBorrowerLookup } from "@/components/clients/global-borrower-lookup";
import { NotificationBell } from "@/components/notifications/notification-bell";
import { ThemeSwitcher } from "@/components/theme-switcher";
import { NativeSelect } from "@/components/ui/native-select";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import { titleCase } from "@/lib/format";
import { useAppData } from "@/provider/appDataProvider";
import { useTenant } from "@/provider/tenantProvider";
import { useAppDispatch } from "@/store/hooks";
import { logoutUser } from "@/store/slices/authSlice";
import {
    ACCOUNTING_ROLES,
    CASHIER_ROLES,
    COLLECTIONS_ROLES,
    COMPANY_MANAGEMENT_ROLES,
    DIRECT_APPLICATION_ROLES,
    HR_ROLES,
    LENDING_ROLES,
    LENDING_OPERATIONS_ROLES,
    PERFORMANCE_ROLES,
    REPORTING_ROLES,
    TRANSPARENCY_ROLES,
    TREASURY_ROLES,
    hasRole,
    type UserRole,
} from "@/types/auth";

type NavItem = {
    label: string;
    href: string;
    icon: LucideIcon;
    roles?: readonly UserRole[];
    children?: NavItem[];
    activePaths?: string[];
};

type RoutePaletteItem = {
    label: string;
    href: string;
    icon: LucideIcon;
    group?: string;
};

const WORKFORCE_ROLES: readonly UserRole[] = Array.from(new Set([
    ...COMPANY_MANAGEMENT_ROLES,
    ...HR_ROLES,
    ...PERFORMANCE_ROLES,
]));

const companyNavigation: NavItem[] = [
    { label: "Dashboard", href: "/company", icon: LayoutDashboard },
    {
        label: "Company command centre",
        href: "/company/command-centre",
        icon: LayoutDashboard,
    },
    { label: "Chat", href: "/company/chat", icon: MessageCircleMore },
    {
        label: "Clients & lending",
        href: "/company/clients",
        icon: ContactRound,
        activePaths: [
            "/company/marketplace",
            "/company/legacy-cashout-register",
            "/company/origination",
            "/company/loans",
            "/company/lending-operations",
            "/company/borrower-requests",
            "/company/products",
        ],
        children: [
            { label: "Clients", href: "/company/clients", icon: ContactRound, roles: LENDING_ROLES },
            { label: "Marketplace", href: "/company/marketplace", icon: Store, roles: DIRECT_APPLICATION_ROLES },
            { label: "Legacy cash-out register", href: "/company/legacy-cashout-register", icon: BookOpenCheck, roles: LENDING_ROLES },
            { label: "Credit origination", href: "/company/origination", icon: ShieldCheck, roles: DIRECT_APPLICATION_ROLES },
            { label: "Loans & contracts", href: "/company/loans", icon: HandCoins },
            { label: "Lending operations", href: "/company/lending-operations", icon: BriefcaseBusiness, roles: LENDING_OPERATIONS_ROLES },
            { label: "Loan products", href: "/company/products", icon: PackageSearch, roles: COMPANY_MANAGEMENT_ROLES },
            { label: "Borrower service requests", href: "/company/borrower-requests", icon: MessageSquarePlus, roles: LENDING_OPERATIONS_ROLES },
        ],
    },
    { label: "Calls & recordings", href: "/company/calls", icon: Phone, roles: LENDING_ROLES },
    {
        label: "Payments & finance",
        href: "/company/payments",
        icon: WalletCards,
        activePaths: [
            "/company/cashier",
            "/company/payment-operations",
            "/company/expense-management",
            "/company/finance",
        ],
        children: [
            { label: "Payment register", href: "/company/payments", icon: WalletCards },
            { label: "Payment desk", href: "/company/cashier", icon: Banknote, roles: CASHIER_ROLES },
            { label: "Payment automation", href: "/company/payment-operations", icon: WalletCards, roles: LENDING_OPERATIONS_ROLES },
            { label: "Accounting & expenses", href: "/company/expense-management", icon: CircleDollarSign, roles: TREASURY_ROLES },
            { label: "Agreements & charges", href: "/company/finance", icon: Landmark, roles: ACCOUNTING_ROLES },
        ],
    },
    { label: "Collections & legal", href: "/company/collections", icon: Gavel, roles: COLLECTIONS_ROLES },
    {
        label: "Document centre",
        href: "/company/documents",
        icon: FilePenLine,
        activePaths: ["/company/files", "/company/reports"],
        children: [
            { label: "Documents & library", href: "/company/documents", icon: FolderOpen },
            { label: "Report library", href: "/company/documents?tab=reports", icon: FileChartColumn, roles: REPORTING_ROLES },
        ],
    },
    {
        label: "Workforce & HR",
        href: "/company/hr",
        icon: UsersRound,
        roles: WORKFORCE_ROLES,
        activePaths: ["/company/people", "/company/staff", "/company/employees", "/company/performance"],
        children: [
            { label: "Command centre", href: "/company/hr", icon: LayoutDashboard, roles: HR_ROLES },
            {
                label: "People & access",
                href: "/company/people?tab=access",
                icon: Users,
                roles: COMPANY_MANAGEMENT_ROLES,
                activePaths: ["/company/staff"],
            },
            {
                label: "Employee records",
                href: "/company/people?tab=employees",
                icon: ContactRound,
                roles: HR_ROLES,
                activePaths: ["/company/employees"],
            },
            { label: "Performance", href: "/company/performance", icon: ChartNoAxesCombined, roles: PERFORMANCE_ROLES },
        ],
    },
    {
        label: "Company administration",
        href: "/company/branches",
        icon: Building2,
        activePaths: ["/company/website", "/company/billing", "/company/settings"],
        children: [
            { label: "Branches", href: "/company/branches", icon: GitBranch },
            { label: "Public website", href: "/company/website", icon: Store, roles: COMPANY_MANAGEMENT_ROLES },
            { label: "Subscription", href: "/company/billing", icon: CreditCard, roles: COMPANY_MANAGEMENT_ROLES },
            { label: "Settings", href: "/company/settings", icon: Settings, roles: COMPANY_MANAGEMENT_ROLES },
        ],
    },
    {
        label: "Governance & reporting",
        href: "/company/control-centre",
        icon: ShieldCheck,
        activePaths: ["/company/reports", "/company/activity", "/company/queries"],
        children: [
            { label: "Control & assurance", href: "/company/control-centre", icon: ShieldCheck, roles: TRANSPARENCY_ROLES },
            { label: "Activity log", href: "/company/activity", icon: History, roles: TRANSPARENCY_ROLES },
            { label: "Support queries", href: "/company/queries", icon: MessageSquarePlus },
        ],
    },
];

const borrowerNavigation: NavItem[] = [
    { label: "Dashboard", href: "/borrower", icon: LayoutDashboard },
    { label: "Chat", href: "/borrower/chat", icon: MessageCircleMore },
    { label: "Loan requests", href: "/borrower/requests", icon: FileText },
    { label: "My loans", href: "/borrower/loans", icon: HandCoins },
    { label: "Payments", href: "/borrower/payments", icon: Banknote },
    { label: "Documents", href: "/borrower/documents", icon: FilePenLine },
    { label: "My files", href: "/borrower/files", icon: FolderOpen },
    { label: "Support queries", href: "/borrower/queries", icon: MessageSquarePlus },
    { label: "Complaints & privacy", href: "/borrower/complaints", icon: ShieldCheck },
    { label: "Profile", href: "/borrower/profile", icon: Users },
];


function filterNavigation(items: NavItem[], role: UserRole | null): NavItem[] {
    return items.flatMap((item) => {
        const children = item.children ? filterNavigation(item.children, role) : undefined;
        const allowed = !item.roles || hasRole(role, item.roles);
        if (!allowed || (item.children && !children?.length)) return [];
        return [{ ...item, children }];
    });
}

function itemMatchesPath(item: NavItem, pathname: string, searchParams: URLSearchParams): boolean {
    const [itemPath, itemQuery = ""] = item.href.split("?", 2);
    const pathMatches = pathname === itemPath
        || (itemPath !== "/company" && itemPath !== "/borrower" && pathname.startsWith(`${itemPath}/`))
        || Boolean(item.activePaths?.some((path) => pathname === path || pathname.startsWith(`${path}/`)));

    if (!pathMatches) return false;
    if (!itemQuery || pathname !== itemPath) return true;

    const expected = new URLSearchParams(itemQuery);
    return Array.from(expected.entries()).every(([key, value]) => searchParams.get(key) === value);
}

function navItemIsActive(item: NavItem, pathname: string, searchParams: URLSearchParams): boolean {
    return itemMatchesPath(item, pathname, searchParams)
        || Boolean(item.children?.some((child) => navItemIsActive(child, pathname, searchParams)));
}

function flattenRoutes(items: NavItem[], group?: string): RoutePaletteItem[] {
    return items.flatMap((item) => [
        { label: item.label, href: item.href, icon: item.icon, group },
        ...(item.children ? flattenRoutes(item.children, item.label) : []),
    ]);
}

function SidebarTooltip({
    collapsed,
    label,
    children,
}: {
    collapsed: boolean;
    label: string;
    children: ReactNode;
}) {
    if (!collapsed) return children;
    return (
        <Tooltip>
            <TooltipTrigger asChild>{children}</TooltipTrigger>
            <TooltipContent side="right" sideOffset={10}>{label}</TooltipContent>
        </Tooltip>
    );
}

export function PortalShell({ children, mode }: { children: ReactNode; mode: "company" | "borrower" }) {
    const pathname = usePathname();
    const router = useRouter();
    const searchParams = useSearchParams();
    const searchQuery = searchParams.toString();
    const dispatch = useAppDispatch();
    const [mobileOpen, setMobileOpen] = useState(false);
    const [callFabOpen, setCallFabOpen] = useState(false);
    const [routeSearchOpen, setRouteSearchOpen] = useState(false);
    const [routeQuery, setRouteQuery] = useState("");
    const [routeHighlight, setRouteHighlight] = useState(0);
    const routeSearchInputRef = useRef<HTMLInputElement>(null);
    const [desktopCollapsed, setDesktopCollapsed] = useState(false);
    const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({});
    const [groupsReady, setGroupsReady] = useState(false);
    const fullscreenWorkspace = useWorkspaceFullscreen();
    const { user, currentCompany, getCompanyName } = useAppData();
    const {
        companyMemberships,
        availableRoles,
        activeCompanyId,
        activeRole,
        hasMultipleCompanies,
        hasMultipleRoles,
        switchCompany,
        switchRole,
    } = useTenant();

    useEffect(() => {
        const stored = window.localStorage.getItem(`loanhub.${mode}.sidebar-collapsed`);
        setDesktopCollapsed(stored === "true");
    }, [mode]);

    useEffect(() => {
        window.localStorage.setItem(`loanhub.${mode}.sidebar-collapsed`, String(desktopCollapsed));
    }, [desktopCollapsed, mode]);

    useEffect(() => {
        setCallFabOpen(false);
    }, [pathname, searchQuery]);

    useEffect(() => {
        const stored = window.localStorage.getItem(`loanhub.${mode}.sidebar-groups`);
        try {
            setExpandedGroups(stored ? JSON.parse(stored) as Record<string, boolean> : {});
        } catch {
            window.localStorage.removeItem(`loanhub.${mode}.sidebar-groups`);
            setExpandedGroups({});
        } finally {
            setGroupsReady(true);
        }
    }, [mode]);

    useEffect(() => {
        if (!groupsReady) return;
        window.localStorage.setItem(`loanhub.${mode}.sidebar-groups`, JSON.stringify(expandedGroups));
    }, [expandedGroups, groupsReady, mode]);

    const navigation = useMemo(() => {
        const items = mode === "company" ? companyNavigation : borrowerNavigation;
        return filterNavigation(items, activeRole);
    }, [activeRole, mode]);

    const routePaletteItems = useMemo(() => Array.from(
        new Map(flattenRoutes(navigation).map((item) => [item.href, item])).values(),
    ), [navigation]);
    const filteredRoutePaletteItems = useMemo(() => {
        const query = routeQuery.trim().toLowerCase();
        if (!query) return routePaletteItems;
        return routePaletteItems.filter((item) => (
            [item.label, item.group, item.href]
                .filter(Boolean)
                .join(" ")
                .toLowerCase()
                .includes(query)
        ));
    }, [routePaletteItems, routeQuery]);

    useEffect(() => {
        if (!routeSearchOpen) return;
        const focusTimer = window.setTimeout(() => routeSearchInputRef.current?.focus(), 0);
        return () => window.clearTimeout(focusTimer);
    }, [routeSearchOpen]);

    useEffect(() => {
        let previousShiftAt = 0;
        const onKeyDown = (event: KeyboardEvent) => {
            if (
                event.key === "Shift"
                && !event.repeat
                && !event.altKey
                && !event.ctrlKey
                && !event.metaKey
            ) {
                const now = Date.now();
                if (now - previousShiftAt <= 450) {
                    event.preventDefault();
                    previousShiftAt = 0;
                    setRouteQuery("");
                    setRouteHighlight(0);
                    setRouteSearchOpen(true);
                } else {
                    previousShiftAt = now;
                }
                return;
            }

            if (event.key === "Escape") {
                setRouteSearchOpen(false);
            }
        };

        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, []);

    function openRouteSearch() {
        setRouteQuery("");
        setRouteHighlight(0);
        setRouteSearchOpen(true);
    }

    function navigateToRoute(item: RoutePaletteItem) {
        setRouteSearchOpen(false);
        router.push(item.href);
    }

    useEffect(() => {
        const activeGroups = navigation.filter(
            (item) => item.children?.length && navItemIsActive(item, pathname, new URLSearchParams(searchQuery)),
        );
        if (!activeGroups.length) return;
        setExpandedGroups((current) => {
            const next = { ...current };
            let changed = false;
            for (const item of activeGroups) {
                if (!next[item.href]) {
                    next[item.href] = true;
                    changed = true;
                }
            }
            return changed ? next : current;
        });
    }, [navigation, pathname, searchQuery]);

    const displayName = user?.person?.full_name
        || [user?.person?.first_name, user?.person?.last_name].filter(Boolean).join(" ")
        || user?.phone
        || "LoanHub user";
    const accountHref = mode === "company" ? "/company/account" : "/borrower/account";
    const initials = displayName
        .split(/\s+/)
        .slice(0, 2)
        .map((part) => part[0])
        .join("")
        .toUpperCase();

    async function handleLogout() {
        await dispatch(logoutUser());
        router.replace("/login");
    }

    function renderSidebar(collapsed: boolean, mobile = false) {
        return (
            <div className="flex h-full flex-col bg-card">
                <div className={`relative border-b ${collapsed ? "px-3 py-4" : "p-5"}`}>
                    <IthuteBrand
                        href={mode === "company" ? "/company" : "/borrower"}
                        compact={collapsed}
                        subtitle={mode === "company" ? "Company lending workspace" : "Borrower financial portal"}
                    />
                    {!mobile && (
                        <button
                            type="button"
                            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                            onClick={() => setDesktopCollapsed((value) => !value)}
                            className={`absolute top-1/2 hidden -translate-y-1/2 rounded-xl border bg-background p-2 text-muted-foreground shadow-sm transition hover:border-primary hover:text-primary lg:inline-flex ${collapsed ? "-right-4" : "right-3"}`}
                        >
                            {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
                        </button>
                    )}
                </div>

                {mode === "company" && (
                    collapsed ? (
                        <div className="border-b px-3 py-4">
                            <SidebarTooltip collapsed label={`${currentCompany?.name ?? "Company account"} · Working as ${titleCase(activeRole)}`}>
                                <button
                                    type="button"
                                    onClick={() => setDesktopCollapsed(false)}
                                    className="flex h-11 w-full items-center justify-center rounded-xl bg-primary/10 text-primary transition hover:bg-primary hover:text-primary-foreground"
                                    aria-label="Expand sidebar to switch company or role"
                                >
                                    <Building2 className="h-5 w-5" />
                                </button>
                            </SidebarTooltip>
                        </div>
                    ) : (
                        <div className="border-b p-4">
                            <div className="space-y-3">
                                {hasMultipleCompanies ? (
                                    <label className="block">
                                        <span className="mb-2 block text-xs font-bold uppercase text-muted-foreground">Active company</span>
                                        <div className="relative">
                                            <NativeSelect
                                                value={activeCompanyId ?? ""}
                                                onChange={(event) => switchCompany(event.target.value)}
                                                className="h-11 w-full appearance-none rounded-xl border bg-background px-3 pr-9 text-sm font-bold"
                                            >
                                                {companyMemberships.map((membership) => (
                                                    <option key={membership.company_id} value={membership.company_id}>
                                                        {getCompanyName(membership.company_id)}
                                                    </option>
                                                ))}
                                            </NativeSelect>
                                            <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2" />
                                        </div>
                                    </label>
                                ) : (
                                    <div className="rounded-2xl bg-muted/60 p-3">
                                        <p className="truncate text-sm font-black">{currentCompany?.name ?? "Company account"}</p>
                                    </div>
                                )}
                                {hasMultipleRoles ? (
                                    <label className="block">
                                        <span className="mb-2 block text-xs font-bold uppercase text-muted-foreground">Working as</span>
                                        <div className="relative">
                                            <NativeSelect
                                                value={activeRole ?? ""}
                                                onChange={(event) => switchRole(event.target.value as UserRole)}
                                                className="h-11 w-full appearance-none rounded-xl border bg-background px-3 pr-9 text-sm font-bold"
                                            >
                                                {availableRoles.map((membership) => (
                                                    <option key={membership.id} value={membership.role}>
                                                        {titleCase(membership.role)}{membership.is_primary ? " (primary)" : ""}
                                                    </option>
                                                ))}
                                            </NativeSelect>
                                            <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2" />
                                        </div>
                                    </label>
                                ) : (
                                    <p className="px-1 text-xs font-semibold text-muted-foreground">Working as {titleCase(activeRole)}</p>
                                )}
                            </div>
                        </div>
                    )
                )}

                <nav className={`flex-1 space-y-1 overflow-y-auto ${collapsed ? "px-3 py-4" : "p-4"}`}>
                    {navigation.map((item) => {
                        const params = new URLSearchParams(searchQuery);
                        const active = navItemIsActive(item, pathname, params);
                        const Icon = item.icon;
                        const hasChildren = Boolean(item.children?.length);

                        if (hasChildren && !collapsed) {
                            const open = expandedGroups[item.href] ?? active;
                            const groupId = `sidebar-group-${item.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
                            return (
                                <div key={item.href} className="space-y-1">
                                    <button
                                        type="button"
                                        aria-expanded={open}
                                        aria-controls={groupId}
                                        onClick={() => setExpandedGroups((current) => ({
                                            ...current,
                                            [item.href]: !(current[item.href] ?? active),
                                        }))}
                                        className={`flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left text-sm font-bold transition ${active ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}
                                    >
                                        <Icon className="h-5 w-5 shrink-0" />
                                        <span className="min-w-0 flex-1 truncate">{item.label}</span>
                                        <ChevronDown className={`h-4 w-4 shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
                                    </button>
                                    {open && (
                                        <div id={groupId} className="ml-5 space-y-1 border-l pl-3">
                                            {item.children?.map((child) => {
                                                const ChildIcon = child.icon;
                                                const childActive = navItemIsActive(child, pathname, params);
                                                return (
                                                    <Link
                                                        key={child.href}
                                                        href={child.href}
                                                        onClick={() => setMobileOpen(false)}
                                                        className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-bold transition ${childActive ? "bg-primary/10 text-primary ring-1 ring-primary/20" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}
                                                    >
                                                        <ChildIcon className="h-4 w-4 shrink-0" />
                                                        <span className="truncate">{child.label}</span>
                                                    </Link>
                                                );
                                            })}
                                        </div>
                                    )}
                                </div>
                            );
                        }

                        const targetHref = hasChildren ? item.children?.[0]?.href ?? item.href : item.href;
                        const link = (
                            <Link
                                key={item.href}
                                href={targetHref}
                                onClick={() => setMobileOpen(false)}
                                aria-label={collapsed ? item.label : undefined}
                                className={`flex items-center rounded-2xl text-sm font-bold transition ${collapsed ? "h-11 justify-center px-2" : "gap-3 px-4 py-3"} ${active ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}
                            >
                                <Icon className="h-5 w-5 shrink-0" />
                                {!collapsed && <span className="truncate">{item.label}</span>}
                            </Link>
                        );
                        return (
                            <SidebarTooltip key={item.href} collapsed={collapsed} label={item.label}>
                                {link}
                            </SidebarTooltip>
                        );
                    })}
                </nav>

                <div className={`border-t ${collapsed ? "p-3" : "p-4"}`}>
                    <SidebarTooltip collapsed={collapsed} label="My profile & security">
                        <Link
                            href={accountHref}
                            onClick={() => setMobileOpen(false)}
                            aria-label="Open my LoanHub profile and security settings"
                            className={`group mb-3 flex items-center rounded-2xl border transition hover:border-primary/40 hover:bg-primary/5 ${collapsed ? "h-12 justify-center p-1" : "gap-3 p-3"} ${pathname === accountHref ? "border-primary/40 bg-primary/5" : ""}`}
                        >
                            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-sm font-black text-primary">
                                {initials}
                            </div>
                            {!collapsed && (
                                <>
                                    <div className="min-w-0 flex-1">
                                        <p className="truncate text-sm font-black">{displayName}</p>
                                        <p className="mt-1 truncate text-xs text-muted-foreground">{user?.email ?? user?.phone}</p>
                                        <p className="mt-1 text-[10px] font-bold uppercase tracking-wide text-primary">My profile & security</p>
                                    </div>
                                    <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground transition group-hover:translate-x-0.5 group-hover:text-primary" />
                                </>
                            )}
                        </Link>
                    </SidebarTooltip>
                    <SidebarTooltip collapsed={collapsed} label="Logout">
                        <button
                            type="button"
                            onClick={() => void handleLogout()}
                            aria-label="Logout"
                            className={`flex w-full items-center rounded-2xl text-sm font-bold text-red-600 transition hover:bg-red-50 dark:hover:bg-red-950/30 ${collapsed ? "h-11 justify-center px-2" : "gap-3 px-4 py-3"}`}
                        >
                            <LogOut className="h-4 w-4 shrink-0" />
                            {!collapsed && "Logout"}
                        </button>
                    </SidebarTooltip>
                    {!collapsed && <div className="mt-4"><IthutePoweredBy /></div>}
                </div>
            </div>
        );
    }

    return (
        <TooltipProvider delayDuration={150}>
            <div className="min-h-screen bg-muted/20">
                {!fullscreenWorkspace ? (
                    <aside className={`fixed inset-y-0 left-0 z-40 hidden border-r bg-card transition-[width] duration-300 lg:block ${desktopCollapsed ? "w-[5.25rem]" : "w-72"}`}>
                        {renderSidebar(desktopCollapsed)}
                    </aside>
                ) : null}

                {mobileOpen && (
                    <div className={`fixed inset-0 z-50 ${fullscreenWorkspace ? "" : "lg:hidden"}`}>
                        <button
                            type="button"
                            aria-label="Close menu overlay"
                            className="absolute inset-0 bg-black/50"
                            onClick={() => setMobileOpen(false)}
                        />
                        <aside className="relative h-full w-[88%] max-w-80 bg-card shadow-2xl">
                            <button
                                type="button"
                                aria-label="Close menu"
                                onClick={() => setMobileOpen(false)}
                                className="absolute right-3 top-3 z-10 rounded-xl border bg-background p-2"
                            >
                                <X className="h-4 w-4" />
                            </button>
                            {renderSidebar(false, true)}
                        </aside>
                    </div>
                )}

                <div className={fullscreenWorkspace ? "" : `transition-[padding] duration-300 ${desktopCollapsed ? "lg:pl-[5.25rem]" : "lg:pl-72"}`}>
                    {!fullscreenWorkspace ? (
                        <header className="sticky top-0 z-30 flex min-h-16 items-center justify-between gap-4 border-b bg-background/90 px-4 py-3 backdrop-blur sm:px-6">
                            <div className="flex min-w-0 items-center gap-3">
                                <button
                                    type="button"
                                    aria-label="Open menu"
                                    onClick={() => setMobileOpen(true)}
                                    className="rounded-xl border p-2 lg:hidden"
                                >
                                    <Menu className="h-5 w-5" />
                                </button>
                                <div className="min-w-0">
                                    <p className="truncate text-sm font-black sm:text-base">
                                        {mode === "company" ? currentCompany?.name ?? "Company workspace" : "Borrower workspace"}
                                    </p>
                                    <p className="truncate text-xs text-muted-foreground">Secure lending, communication and document management</p>
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                {mode === "company" && hasRole(activeRole, LENDING_ROLES) ? <GlobalBorrowerLookup /> : null}
                                <button
                                    type="button"
                                    onClick={openRouteSearch}
                                    aria-label="Search LoanHub routes"
                                    title="Search LoanHub routes (press Shift twice)"
                                    className="hidden h-10 items-center gap-2 rounded-xl border bg-background px-3 text-sm font-bold text-muted-foreground transition hover:border-primary hover:text-primary xl:inline-flex"
                                >
                                    <Search className="h-4 w-4" />
                                    <span>Search pages</span>
                                    <kbd className="rounded border bg-muted px-1.5 py-0.5 text-[10px] font-semibold">Shift Shift</kbd>
                                </button>
                                <WorkspaceModeToggle />
                                <InterfaceScaleController />
                                <ThemeSwitcher />
                                <ChatLauncher role={user?.role} />
                                <NotificationBell role={user?.role} />
                            </div>
                        </header>
                    ) : (
                        <div className="fixed inset-x-2 top-2 z-40 flex min-w-0 items-center gap-1.5 rounded-2xl border bg-background/95 p-1.5 shadow-xl backdrop-blur sm:inset-x-3 sm:top-3">
                            {mode === "company" && hasRole(activeRole, LENDING_ROLES) ? (
                                <GlobalBorrowerLookup forceExpanded className="max-w-xl" />
                            ) : (
                                <div className="min-w-0 flex-1" />
                            )}
                            <div className="ml-auto flex shrink-0 items-center gap-1.5">
                                <WorkspaceModeToggle />
                                <InterfaceScaleController />
                                <ThemeSwitcher />
                                <ChatLauncher role={user?.role} />
                                <NotificationBell role={user?.role} />
                                <button
                                    type="button"
                                    aria-label="Open LoanHub navigation"
                                    title="Open navigation"
                                    onClick={() => setMobileOpen(true)}
                                    className="inline-flex h-10 w-10 items-center justify-center rounded-xl border bg-background transition hover:bg-muted"
                                >
                                    <Menu className="h-5 w-5" />
                                </button>
                            </div>
                        </div>
                    )}
                    <main className={fullscreenWorkspace ? "min-h-screen px-2 pb-2 pt-[4.5rem] sm:px-3 sm:pb-3 sm:pt-20" : "p-3 sm:p-5 lg:p-6"}>{children}</main>
                </div>
                {routeSearchOpen ? (
                    <div className="fixed inset-0 z-[70] flex items-start justify-center bg-slate-950/45 p-4 pt-[10vh] sm:pt-[16vh]">
                        <button
                            type="button"
                            aria-label="Close route search"
                            className="absolute inset-0 cursor-default"
                            onClick={() => setRouteSearchOpen(false)}
                        />
                        <section
                            role="dialog"
                            aria-modal="true"
                            aria-label="Search LoanHub routes"
                            className="relative z-10 w-full max-w-2xl overflow-hidden rounded-3xl border bg-background shadow-2xl"
                        >
                            <div className="flex items-center gap-3 border-b px-4 py-3">
                                <Search className="h-5 w-5 shrink-0 text-primary" />
                                <input
                                    ref={routeSearchInputRef}
                                    value={routeQuery}
                                    onChange={(event) => {
                                        setRouteQuery(event.target.value);
                                        setRouteHighlight(0);
                                    }}
                                    onKeyDown={(event) => {
                                        if (event.key === "ArrowDown") {
                                            event.preventDefault();
                                            setRouteHighlight((current) => Math.min(
                                                current + 1,
                                                Math.max(filteredRoutePaletteItems.length - 1, 0),
                                            ));
                                        } else if (event.key === "ArrowUp") {
                                            event.preventDefault();
                                            setRouteHighlight((current) => Math.max(current - 1, 0));
                                        } else if (event.key === "Enter") {
                                            event.preventDefault();
                                            const item = filteredRoutePaletteItems[routeHighlight];
                                            if (item) navigateToRoute(item);
                                        }
                                    }}
                                    placeholder="Search LoanHub pages, features or routes…"
                                    className="h-10 min-w-0 flex-1 bg-transparent text-base font-semibold outline-none placeholder:text-muted-foreground"
                                />
                                <kbd className="hidden rounded-lg border bg-muted px-2 py-1 text-xs text-muted-foreground sm:inline">Esc</kbd>
                            </div>
                            <div className="max-h-[min(60vh,32rem)] overflow-y-auto p-2">
                                {filteredRoutePaletteItems.length ? (
                                    filteredRoutePaletteItems.map((item, index) => {
                                        const Icon = item.icon;
                                        const selected = index === routeHighlight;
                                        return (
                                            <button
                                                key={item.href}
                                                type="button"
                                                onMouseEnter={() => setRouteHighlight(index)}
                                                onClick={() => navigateToRoute(item)}
                                                className={[
                                                    "flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-left transition",
                                                    selected ? "bg-primary text-primary-foreground" : "hover:bg-muted",
                                                ].join(" ")}
                                            >
                                                <Icon className="h-5 w-5 shrink-0" />
                                                <span className="min-w-0 flex-1">
                                                    <span className="block truncate text-sm font-black">{item.label}</span>
                                                    <span className={[
                                                        "block truncate text-xs",
                                                        selected ? "text-primary-foreground/80" : "text-muted-foreground",
                                                    ].join(" ")}>
                                                        {item.group ? item.group + " · " : ""}{item.href}
                                                    </span>
                                                </span>
                                            </button>
                                        );
                                    })
                                ) : (
                                    <p className="px-4 py-10 text-center text-sm text-muted-foreground">
                                        {"No permitted LoanHub route matches “" + routeQuery + "”."}
                                    </p>
                                )}
                            </div>
                            <p className="border-t px-4 py-2 text-xs text-muted-foreground">
                                Press Shift twice anywhere to open · ↑ ↓ to select · Enter to open · Esc to close
                            </p>
                        </section>
                    </div>
                ) : null}
                {mode === "company" && hasRole(activeRole, LENDING_ROLES) && !fullscreenWorkspace ? (
                    <div className="fixed bottom-5 right-5 z-30 flex flex-col items-end gap-2">
                        {callFabOpen ? (
                            <div id="calling-quick-actions" role="menu" aria-label="Calling quick actions" className="w-52 rounded-2xl border bg-background p-2 shadow-xl">
                                <Link
                                    href="/company/calls"
                                    role="menuitem"
                                    className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-bold transition hover:bg-muted"
                                >
                                    <Phone className="h-4 w-4 text-primary" />
                                    Start a call
                                </Link>
                                <Link
                                    href="/company/calls?tab=phonebook"
                                    role="menuitem"
                                    className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-bold transition hover:bg-muted"
                                >
                                    <ContactRound className="h-4 w-4 text-primary" />
                                    Company phone book
                                </Link>
                            </div>
                        ) : null}
                        <button
                            type="button"
                            aria-label={callFabOpen ? "Close calling quick actions" : "Open calling quick actions"}
                            aria-expanded={callFabOpen}
                            aria-controls="calling-quick-actions"
                            title={callFabOpen ? "Close calling actions" : "Call a borrower"}
                            onClick={() => setCallFabOpen((open) => !open)}
                            className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg transition hover:scale-105 hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
                        >
                            {callFabOpen ? <X className="h-6 w-6" /> : <Phone className="h-6 w-6" />}
                        </button>
                    </div>
                ) : null}
            </div>
        </TooltipProvider>
    );
}
