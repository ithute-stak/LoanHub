"use client";

import Link from "next/link";
import { Headphones, ShieldCheck, Users } from "lucide-react";
import { useAppSelector } from "@/store/hooks";
import { PLATFORM_FINANCE_ROLES } from "@/types/auth";
import { titleCase } from "@/lib/format";

export default function PlatformDashboardPage() {
    const user = useAppSelector((state) => state.auth.user);
    const finance = Boolean(user?.role && PLATFORM_FINANCE_ROLES.includes(user.role));
    return <div className="space-y-6"><section className="rounded-3xl border bg-card p-6 shadow-sm md:p-8"><p className="text-xs font-black uppercase tracking-[0.22em] text-primary">Platform staff</p><h1 className="mt-2 text-3xl font-black">Welcome to your {titleCase(user?.role)} workspace</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">Your account shows only the modules granted to your platform role. Sensitive configuration changes remain restricted to the system owner.</p></section><section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{finance && <Card href="/superadmin/finance" icon={ShieldCheck} title="Finance" description="Review fees, verified payment channels, tenant agreements, transaction charges, ledgers and claims." />}<Card href="/platform/support" icon={Headphones} title="Support workspace" description="Use controlled support procedures without receiving merchant credentials or unrestricted owner access." /><div className="rounded-3xl border bg-card p-5"><Users className="h-8 w-8 text-primary" /><h2 className="mt-4 text-lg font-black">Least-privilege account</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">Your platform role is separated from tenant-company roles and is recorded in the audit trail.</p></div></section></div>;
}
function Card({ href, icon: Icon, title, description }: { href: string; icon: typeof ShieldCheck; title: string; description: string }) { return <Link href={href} className="rounded-3xl border bg-card p-5 transition hover:-translate-y-0.5 hover:shadow-md"><Icon className="h-8 w-8 text-primary" /><h2 className="mt-4 text-lg font-black">{title}</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p></Link>; }
