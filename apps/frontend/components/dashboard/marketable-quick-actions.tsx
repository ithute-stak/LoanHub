import Link from "next/link";
import { BarChart3, FolderOpen, Globe2, Landmark, MessageCircleMore } from "lucide-react";

export function MarketableQuickActions({ base }: { base: "/company" | "/borrower" | "/superadmin" }) {
    const documentAction = base === "/company"
        ? { label: "Documents", href: "/company/documents", icon: FolderOpen, description: "Manage folders, reports, contracts, receipts and shared records." }
        : { label: base === "/borrower" ? "My files" : "File centre", href: `${base}/files`, icon: FolderOpen, description: "Store and retrieve organised records." };

    const actions = [
        { label: "Secure chat", href: `${base}/chat`, icon: MessageCircleMore, description: "Message authorised users and share documents." },
        documentAction,
        { label: base === "/borrower" ? "My analytics" : "Analytics", href: `${base}/analytics`, icon: BarChart3, description: "Explore trends, portfolio quality and operational insights." },
        ...(base === "/company" ? [
            { label: "Public website", href: "/company/website", icon: Globe2, description: "Build and publish your company loan website from live LoanHub data." },
        ] : []),
        ...(base !== "/borrower" ? [
            { label: "Accounting", href: `${base}/accounting`, icon: Landmark, description: "Review journals and financial statements." },
        ] : []),
    ];
    return <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">{actions.map(({ label, href, icon: Icon, description }) => <Link key={href} href={href} className="group rounded-2xl border bg-card p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-primary hover:shadow-md"><div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary group-hover:bg-primary group-hover:text-primary-foreground"><Icon className="h-5 w-5" /></div><p className="mt-4 font-black">{label}</p><p className="mt-1 text-xs leading-5 text-muted-foreground">{description}</p></Link>)}</section>;
}
