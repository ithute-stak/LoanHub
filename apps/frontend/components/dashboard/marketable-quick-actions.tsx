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
    return (
        <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5 2xl:gap-4">
            {actions.map(({ label, href, icon: Icon, description }) => (
                <Link
                    key={href}
                    href={href}
                    className="group min-w-0 rounded-2xl border bg-card p-4 shadow-sm transition hover:border-primary 2xl:p-5"
                >
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary group-hover:bg-primary group-hover:text-primary-foreground 2xl:h-10 2xl:w-10">
                        <Icon className="h-4 w-4 2xl:h-5 2xl:w-5" />
                    </div>
                    <p className="mt-3 font-black 2xl:mt-4">{label}</p>
                    <p className="mt-1 text-[11px] leading-4 text-muted-foreground 2xl:text-xs 2xl:leading-5">{description}</p>
                </Link>
            ))}
        </section>
    );
}
