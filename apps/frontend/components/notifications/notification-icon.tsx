import {
    BadgeDollarSign,
    Bell,
    Building2,
    CalendarCheck,
    ChartNoAxesCombined,
    ContactRound,
    CreditCard,
    GitBranch,
    HandCoins,
    Layers3,
    PackageSearch,
    Radio,
    Target,
    TriangleAlert,
    Users,
    WalletCards,
    type LucideIcon,
} from "lucide-react";

const ICONS: Record<string, LucideIcon> = {
    "badge-dollar-sign": BadgeDollarSign,
    "building-2": Building2,
    "calendar-check": CalendarCheck,
    "chart-no-axes-combined":
        ChartNoAxesCombined,
    "contact-round": ContactRound,
    "credit-card": CreditCard,
    "git-branch": GitBranch,
    "hand-coins": HandCoins,
    "layers-3": Layers3,
    "package-search": PackageSearch,
    radio: Radio,
    target: Target,
    "triangle-alert": TriangleAlert,
    users: Users,
    "wallet-cards": WalletCards,
    bell: Bell,
};

export function NotificationIcon({
    icon,
    priority,
}: {
    icon: string | null;
    priority: string;
}) {
    const Icon = ICONS[icon ?? "bell"] ?? Bell;

    const classes =
        priority === "critical"
            ? "bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-400"
            : priority === "high"
              ? "bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-400"
              : "bg-primary/10 text-primary";

    return (
        <span
            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${classes}`}
        >
            <Icon className="h-5 w-5" />
        </span>
    );
}
