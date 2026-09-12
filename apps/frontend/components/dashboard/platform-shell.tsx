"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ChevronRight, FilePenLine, Headphones, LayoutDashboard, LogOut, Menu, ReceiptText, X } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import { InterfaceScaleController } from "@/components/accessibility/interface-scale-controller";
import { WorkspaceModeToggle, useWorkspaceFullscreen } from "@/components/accessibility/workspace-mode";
import { IthuteBrand, IthutePoweredBy } from "@/components/brand/ithute-brand";
import { NotificationBell } from "@/components/notifications/notification-bell";
import { ThemeSwitcher } from "@/components/theme-switcher";
import { titleCase } from "@/lib/format";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { logoutUser } from "@/store/slices/authSlice";
import { PLATFORM_FINANCE_ROLES } from "@/types/auth";

export function PlatformShell({ children }: { children: ReactNode }) {
    const pathname = usePathname();
    const router = useRouter();
    const dispatch = useAppDispatch();
    const user = useAppSelector((state) => state.auth.user);
    const [open, setOpen] = useState(false);
    const fullscreenWorkspace = useWorkspaceFullscreen();
    const displayName = user?.person?.full_name || [user?.person?.first_name, user?.person?.last_name].filter(Boolean).join(" ") || user?.phone || "Platform user";
    const navigation = useMemo(() => {
        const items = [
            { label: "Dashboard", href: "/platform", icon: LayoutDashboard },
            { label: "Document studio", href: "/platform/documents", icon: FilePenLine },
            ...(user?.role && PLATFORM_FINANCE_ROLES.includes(user.role)
                ? [{ label: "Cash finance support", href: "/platform/support", icon: ReceiptText }]
                : [{ label: "Support workspace", href: "/platform/support", icon: Headphones }]),
        ];
        return items;
    }, [user?.role]);

    async function logout() {
        await dispatch(logoutUser());
        router.replace("/login");
    }

    const sidebar = <div className="flex h-full flex-col bg-card"><div className="border-b p-5"><IthuteBrand href="/platform" subtitle="Platform operations workspace" /></div><div className="border-b p-4"><Link href="/platform/account" onClick={() => setOpen(false)} className={`group flex items-center gap-3 rounded-2xl border p-3 transition hover:border-primary/40 hover:bg-primary/5 ${pathname === "/platform/account" ? "border-primary/40 bg-primary/5" : ""}`}><div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-sm font-black text-primary">{displayName.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase()}</div><div className="min-w-0 flex-1"><p className="truncate text-sm font-black">{displayName}</p><p className="mt-1 text-xs text-muted-foreground">{titleCase(user?.role)}</p><p className="mt-1 text-[10px] font-bold uppercase tracking-wide text-primary">My profile & security</p></div><ChevronRight className="h-4 w-4 text-muted-foreground transition group-hover:translate-x-0.5 group-hover:text-primary" /></Link></div><nav className="flex-1 space-y-1 overflow-y-auto p-4">{navigation.map((item) => { const Icon = item.icon; const active = item.href === pathname || (item.href !== "/platform" && pathname.startsWith(`${item.href}/`)); return <Link key={item.href} href={item.href} onClick={() => setOpen(false)} className={`flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-bold ${active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}><Icon className="h-5 w-5" />{item.label}</Link>; })}</nav><div className="border-t p-4"><button onClick={() => void logout()} className="flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-sm font-bold text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30"><LogOut className="h-4 w-4" />Logout</button><div className="mt-4"><IthutePoweredBy /></div></div></div>;

    return (
        <div className="min-h-screen bg-muted/20">
            {!fullscreenWorkspace ? (
                <aside className="fixed inset-y-0 left-0 z-40 hidden w-72 border-r bg-card lg:block">{sidebar}</aside>
            ) : null}

            {open ? (
                <div className={`fixed inset-0 z-50 ${fullscreenWorkspace ? "" : "lg:hidden"}`}>
                    <button aria-label="Close overlay" className="absolute inset-0 bg-black/50" onClick={() => setOpen(false)} />
                    <aside className="relative h-full w-[88%] max-w-80 bg-card shadow-2xl">
                        <button aria-label="Close menu" onClick={() => setOpen(false)} className="absolute right-3 top-3 z-10 rounded-xl border bg-background p-2"><X className="h-4 w-4" /></button>
                        {sidebar}
                    </aside>
                </div>
            ) : null}

            <div className={fullscreenWorkspace ? "" : "lg:pl-72"}>
                {!fullscreenWorkspace ? (
                    <header className="sticky top-0 z-30 flex min-h-16 items-center justify-between border-b bg-background/90 px-4 py-3 backdrop-blur sm:px-6">
                        <div className="flex items-center gap-3">
                            <button aria-label="Open menu" onClick={() => setOpen(true)} className="rounded-xl border p-2 lg:hidden"><Menu className="h-5 w-5" /></button>
                            <div><p className="text-sm font-black sm:text-base">LoanHub platform team</p><p className="text-xs text-muted-foreground">Role-controlled operational access</p></div>
                        </div>
                        <div className="flex items-center gap-2"><WorkspaceModeToggle /><InterfaceScaleController /><ThemeSwitcher /><NotificationBell role={user?.role} /></div>
                    </header>
                ) : (
                    <div className="fixed right-3 top-3 z-40 flex items-center gap-1.5 rounded-2xl border bg-background/95 p-1.5 shadow-xl backdrop-blur">
                        <button type="button" aria-label="Open platform navigation" title="Open navigation" onClick={() => setOpen(true)} className="inline-flex h-10 w-10 items-center justify-center rounded-xl border bg-background transition hover:bg-muted"><Menu className="h-5 w-5" /></button>
                        <InterfaceScaleController />
                        <ThemeSwitcher />
                        <NotificationBell role={user?.role} />
                        <WorkspaceModeToggle />
                    </div>
                )}
                <main className={fullscreenWorkspace ? "min-h-screen p-2 sm:p-3" : "p-3 sm:p-5 lg:p-6"}>{children}</main>
            </div>
        </div>
    );
}
