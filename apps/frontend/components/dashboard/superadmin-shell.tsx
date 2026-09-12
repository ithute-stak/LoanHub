"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
    Building2,
    ChartNoAxesCombined,
    ChevronDown,
    ChevronRight,
    ContactRound,
    CreditCard,
    FileChartColumn,
    FileText,
    FilePenLine,
    FolderOpen,
    GitBranch,
    History,
    Landmark,
    LayoutDashboard,
    LogOut,
    Menu,
    MessageCircleMore,
    MessageSquarePlus,
    ServerCog,
    ShieldCheck,
    TriangleAlert,
    Users,
    WalletCards,
    X,
    type LucideIcon,
} from "lucide-react";
import { type ReactNode, useMemo, useState } from "react";

import { InterfaceScaleController } from "@/components/accessibility/interface-scale-controller";
import { WorkspaceModeToggle, useWorkspaceFullscreen } from "@/components/accessibility/workspace-mode";
import { IthuteBrand, IthutePoweredBy } from "@/components/brand/ithute-brand";
import { ChatLauncher } from "@/components/chat/chat-launcher";
import { NotificationBell } from "@/components/notifications/notification-bell";
import { ThemeSwitcher } from "@/components/theme-switcher";
import { RoleSwitcher } from "@/components/admin/role-switcher";
import { useAppData } from "@/provider/appDataProvider";
import { useAppDispatch } from "@/store/hooks";
import { logoutUser } from "@/store/slices/authSlice";

type NavigationChild = { label: string; href: string; icon: LucideIcon };
type NavigationGroup = { label: string; icon: LucideIcon; href?: string; children?: NavigationChild[] };

const navigation: NavigationGroup[] = [
    { label: "Owner command centre", icon: LayoutDashboard, href: "/superadmin" },
    { label: "Platform operations", icon: ShieldCheck, children: [
        { label: "Owner control room", href: "/superadmin/control", icon: ShieldCheck },
        { label: "Global portfolio", href: "/superadmin/control/global-portfolio", icon: ChartNoAxesCombined },
        { label: "Global borrowers", href: "/superadmin/control/borrowers", icon: Users },
        { label: "Risk & fraud", href: "/superadmin/control/risk-fraud", icon: TriangleAlert },
        { label: "Compliance centre", href: "/superadmin/control/compliance", icon: FileText },
        { label: "Audit & investigations", href: "/superadmin/control/audit", icon: History },
        { label: "Emergency controls", href: "/superadmin/control/emergency", icon: ServerCog },
    ]},
    { label: "Tenant management", icon: Building2, children: [
        { label: "All companies", href: "/superadmin/companies", icon: Building2 },
        { label: "Company branches", href: "/superadmin/companies/branches", icon: GitBranch },
        { label: "Company administrators", href: "/superadmin/company-admins", icon: Users },
        { label: "Company health", href: "/superadmin/control/company-health", icon: ChartNoAxesCombined },
        { label: "Support sessions", href: "/superadmin/control/support-sessions", icon: ContactRound },
    ]},
    { label: "Users & security", icon: Users, children: [
        { label: "Global user access", href: "/superadmin/control/users-access", icon: Users },
        { label: "Security centre", href: "/superadmin/control/security", icon: ShieldCheck },
        { label: "Approvals governance", href: "/superadmin/control/approvals", icon: History },
        { label: "Data governance", href: "/superadmin/control/data-governance", icon: FileText },
    ]},
    { label: "Loan ecosystem", icon: FileText, children: [
        { label: "Loan requests and loans", href: "/superadmin/loans", icon: FileText },
        { label: "Platform payment register", href: "/superadmin/payments", icon: WalletCards },
        { label: "Finance rules & claims", href: "/superadmin/finance", icon: Landmark },
        { label: "Financial integrity", href: "/superadmin/control/financial-integrity", icon: ShieldCheck },
    ]},
    { label: "Finance and billing", icon: Landmark, children: [
        { label: "Platform accounting", href: "/superadmin/accounting", icon: Landmark },
        { label: "Automated reports", href: "/superadmin/reports", icon: FileChartColumn },
        { label: "Subscription plans", href: "/superadmin/plans", icon: CreditCard },
        { label: "Platform billing", href: "/superadmin/control/billing", icon: WalletCards },
    ]},
    { label: "Platform configuration", icon: ServerCog, children: [
        { label: "Feature flags", href: "/superadmin/control/feature-flags", icon: ServerCog },
        { label: "Global configuration", href: "/superadmin/control/configuration", icon: ServerCog },
        { label: "LelefaPayGate", href: "/superadmin/lelefapaygate", icon: WalletCards },
        { label: "API & integrations", href: "/superadmin/control/integrations", icon: GitBranch },
        { label: "Experian credit bureau", href: "/superadmin/control/integrations/experian", icon: ShieldCheck },
        { label: "System health", href: "/superadmin/control/system-health", icon: ChartNoAxesCombined },
        { label: "Backups & recovery", href: "/superadmin/control/backups", icon: History },
        { label: "Releases", href: "/superadmin/control/releases", icon: ServerCog },
    ]},
    { label: "Communication & support", icon: MessageCircleMore, children: [
        { label: "Platform chat", href: "/superadmin/chat", icon: MessageCircleMore },
        { label: "Communications", href: "/superadmin/control/communications", icon: MessageSquarePlus },
        { label: "Support centre", href: "/superadmin/control/support", icon: ContactRound },
        { label: "Document studio", href: "/superadmin/documents", icon: FilePenLine },
        { label: "File centre", href: "/superadmin/files", icon: FolderOpen },
    ]},
    { label: "People and performance", icon: ContactRound, children: [
        { label: "Platform employees", href: "/superadmin/employees", icon: Users },
        { label: "Platform performance", href: "/superadmin/performance", icon: ChartNoAxesCombined },
    ]},
    { label: "Transparency and health", icon: History, children: [
        { label: "Activity log", href: "/superadmin/activity", icon: History },
        { label: "System errors", href: "/superadmin/system-errors", icon: TriangleAlert },
        { label: "System update", href: "/superadmin/system-update", icon: ServerCog },
        { label: "User queries", href: "/superadmin/queries", icon: MessageSquarePlus },
    ]},
];

function isPathActive(pathname: string, href: string): boolean {
    return href === "/superadmin" ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);
}

function NavigationGroupItem({ group, pathname, onNavigate }: { group: NavigationGroup; pathname: string; onNavigate: () => void }) {
    const childActive = group.children?.some((item) => isPathActive(pathname, item.href));
    const groupActive = Boolean((group.href && isPathActive(pathname, group.href)) || childActive);
    const [expanded, setExpanded] = useState(groupActive);
    const Icon = group.icon;
    if (group.href) return <Link href={group.href} onClick={onNavigate} className={`flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-bold transition ${groupActive ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}><Icon className="h-5 w-5" />{group.label}</Link>;
    return <div className="space-y-1"><button type="button" onClick={() => setExpanded((value) => !value)} className={`flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left text-sm font-bold ${groupActive ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}><Icon className="h-5 w-5" /><span className="flex-1">{group.label}</span><ChevronDown className={`h-4 w-4 transition ${expanded ? "rotate-180" : ""}`} /></button>{expanded && <div className="space-y-1 pl-4">{group.children?.map((item) => { const ChildIcon = item.icon; const active = isPathActive(pathname, item.href); return <Link key={item.href} href={item.href} onClick={onNavigate} className={`flex items-center gap-3 rounded-2xl px-4 py-2.5 text-sm font-semibold ${active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}><ChildIcon className="h-4 w-4" />{item.label}</Link>; })}</div>}</div>;
}

export function SuperAdminShell({ children }: { children: ReactNode }) {
    const pathname = usePathname();
    const router = useRouter();
    const dispatch = useAppDispatch();
    const { user, pendingCompaniesCount, payments } = useAppData();
    const [mobileOpen, setMobileOpen] = useState(false);
    const fullscreenWorkspace = useWorkspaceFullscreen();
    const displayName = useMemo(() => user?.person?.full_name || [user?.person?.first_name, user?.person?.last_name].filter(Boolean).join(" ") || user?.email || user?.phone || "Platform administrator", [user]);
    const pendingPayments = useMemo(() => payments.filter((payment) => payment.status === "pending").length, [payments]);

    async function handleLogout() { await dispatch(logoutUser()); router.replace("/login"); router.refresh(); }

    const sidebar = <div className="flex h-full flex-col bg-card"><div className="border-b p-5"><IthuteBrand href="/superadmin" subtitle="System owner · platform control" /></div><div className="border-b p-4"><div className="grid grid-cols-2 gap-2"><Link href="/superadmin/companies" className="rounded-2xl bg-amber-500/10 p-3 text-amber-700"><p className="text-xl font-black">{pendingCompaniesCount}</p><p className="mt-1 text-[11px] font-bold">Pending tenants</p></Link><Link href="/superadmin/payments" className="rounded-2xl bg-primary/10 p-3 text-primary"><p className="text-xl font-black">{pendingPayments}</p><p className="mt-1 text-[11px] font-bold">Pending payments</p></Link></div></div><nav className="flex-1 space-y-2 overflow-y-auto p-4">{navigation.map((group) => <NavigationGroupItem key={group.label} group={group} pathname={pathname} onNavigate={() => setMobileOpen(false)} />)}</nav><div className="border-t p-4"><Link href="/superadmin/account" onClick={() => setMobileOpen(false)} className={`group mb-3 flex items-center gap-3 rounded-2xl border p-3 transition hover:border-primary/40 hover:bg-primary/5 ${pathname === "/superadmin/account" ? "border-primary/40 bg-primary/5" : ""}`}><div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-sm font-black text-primary">{displayName.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase()}</div><div className="min-w-0 flex-1"><p className="truncate text-sm font-black">{displayName}</p><p className="mt-1 truncate text-xs text-muted-foreground">{user?.email ?? user?.phone}</p><p className="mt-1 text-[10px] font-bold uppercase tracking-wide text-primary">My profile & security</p></div><ChevronRight className="h-4 w-4 text-muted-foreground transition group-hover:translate-x-0.5 group-hover:text-primary" /></Link><button type="button" onClick={() => void handleLogout()} className="flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-sm font-bold text-red-600 hover:bg-red-50"><LogOut className="h-4 w-4" />Logout</button><div className="mt-4"><IthutePoweredBy /></div></div></div>;

    return (
        <div className="min-h-screen bg-muted/20">
            {!fullscreenWorkspace ? <aside className="fixed inset-y-0 left-0 z-40 hidden w-72 border-r bg-card lg:block">{sidebar}</aside> : null}

            {mobileOpen ? <div className={`fixed inset-0 z-50 ${fullscreenWorkspace ? "" : "lg:hidden"}`}><button type="button" aria-label="Close navigation overlay" onClick={() => setMobileOpen(false)} className="absolute inset-0 bg-black/50" /><aside className="relative h-full w-[88%] max-w-80 bg-card shadow-2xl"><button type="button" aria-label="Close navigation" onClick={() => setMobileOpen(false)} className="absolute right-3 top-3 z-10 rounded-xl border bg-background p-2"><X className="h-4 w-4" /></button>{sidebar}</aside></div> : null}

            <div className={fullscreenWorkspace ? "" : "lg:pl-72"}>
                {!fullscreenWorkspace ? <header className="sticky top-0 z-30 flex min-h-16 items-center justify-between gap-4 border-b bg-background/90 px-4 py-3 backdrop-blur sm:px-6"><div className="flex min-w-0 items-center gap-3"><button type="button" onClick={() => setMobileOpen(true)} className="rounded-xl border p-2 lg:hidden"><Menu className="h-5 w-5" /></button><div className="min-w-0"><p className="truncate text-sm font-black sm:text-base">System owner control centre</p><p className="truncate text-xs text-muted-foreground">Multi-tenant oversight, risk, compliance, security and platform operations</p></div></div><div className="flex items-center gap-2"><RoleSwitcher /><WorkspaceModeToggle /><InterfaceScaleController /><ThemeSwitcher /><ChatLauncher role={user?.role} /><NotificationBell role={user?.role} /></div></header> : <div className="fixed right-3 top-3 z-40 flex items-center gap-1.5 rounded-2xl border bg-background/95 p-1.5 shadow-xl backdrop-blur"><button type="button" aria-label="Open platform navigation" title="Open navigation" onClick={() => setMobileOpen(true)} className="inline-flex h-10 w-10 items-center justify-center rounded-xl border bg-background transition hover:bg-muted"><Menu className="h-5 w-5" /></button><RoleSwitcher /><InterfaceScaleController /><ThemeSwitcher /><ChatLauncher role={user?.role} /><NotificationBell role={user?.role} /><WorkspaceModeToggle /></div>}
                <main className={fullscreenWorkspace ? "min-h-screen p-2 sm:p-3" : "p-3 sm:p-5 lg:p-6"}>{children}</main>
            </div>
        </div>
    );
}
