"use client";

import {
    Activity,
    BadgeCheck,
    Building2,
    CalendarDays,
    Copy,
    MapPin,
} from "lucide-react";
import { toast } from "@/utils/toast";

function formatDate(value?: string | null): string {
    if (!value) return "Not available";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return "Not available";
    }

    return new Intl.DateTimeFormat("en-LS", {
        day: "2-digit",
        month: "short",
        year: "numeric",
    }).format(date);
}

type Props = {
    company: {
        id: string;
        name?: string | null;
        status?: string | null;
        is_active?: boolean | null;
        district?: string | null;
        created_at?: string | null;
    };
    completion: number;
    branding?: {
        left_logo_file?: { original_name: string } | null;
        right_logo_file?: { original_name: string } | null;
    } | null;
};

export function CompanySettingsSidebar({
    company,
    completion,
    branding,
}: Props) {
    async function copyId() {
        try {
            await navigator.clipboard.writeText(company.id);
            toast.success("Company ID copied.");
        } catch {
            toast.error("Company ID could not be copied.");
        }
    }

    const status = String(company.status ?? "unknown")
        .replaceAll("_", " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());

    return (
        <aside className="space-y-6">
            <article className="rounded-3xl border bg-card p-5 shadow-sm">
                <div className="flex items-start gap-3">
                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                        <Building2 className="h-5 w-5" />
                    </div>

                    <div className="min-w-0">
                        <p className="truncate text-lg font-black">
                            {company.name ?? "Unnamed company"}
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                            Active tenant profile
                        </p>
                    </div>
                </div>

                <div className="mt-5 space-y-3 text-sm">
                    <InfoRow
                        icon={Activity}
                        label="Status"
                        value={status}
                    />
                    <InfoRow
                        icon={MapPin}
                        label="District"
                        value={company.district ?? "Not set"}
                    />
                    <InfoRow
                        icon={CalendarDays}
                        label="Registered"
                        value={formatDate(company.created_at)}
                    />
                </div>

                <button
                    type="button"
                    onClick={() => void copyId()}
                    className="mt-5 inline-flex h-10 w-full items-center justify-center gap-2 rounded-xl border bg-background text-xs font-black transition hover:border-primary hover:text-primary"
                >
                    <Copy className="h-3.5 w-3.5" />
                    Copy company ID
                </button>
            </article>



            <article className="rounded-3xl border bg-card p-5 shadow-sm">
                <p className="text-sm font-black">Document branding</p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">Generated loan documents now support both the system logo and your company logo.</p>
                <div className="mt-4 space-y-3 text-sm">
                    <InfoRow
                        icon={Building2}
                        label="Left logo"
                        value={branding?.left_logo_file?.original_name ?? "System logo only"}
                    />
                    <InfoRow
                        icon={BadgeCheck}
                        label="Right logo"
                        value={branding?.right_logo_file?.original_name ?? "Not uploaded"}
                    />
                </div>
            </article>
            <article className="rounded-3xl border bg-card p-5 shadow-sm">
                <div className="flex items-start justify-between gap-4">
                    <div>
                        <p className="text-sm font-black">
                            Profile completeness
                        </p>
                        <p className="mt-1 text-xs leading-5 text-muted-foreground">
                            Complete details improve verification
                            and marketplace trust.
                        </p>
                    </div>

                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                        <BadgeCheck className="h-5 w-5" />
                    </div>
                </div>

                <div className="mt-5 flex items-end justify-between">
                    <span className="text-3xl font-black">
                        {completion}%
                    </span>
                    <span className="text-xs font-bold text-muted-foreground">
                        {completion === 100
                            ? "Complete"
                            : "Needs attention"}
                    </span>
                </div>

                <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-muted">
                    <div
                        className="h-full rounded-full bg-primary transition-all"
                        style={{ width: `${completion}%` }}
                    />
                </div>
            </article>
        </aside>
    );
}

function InfoRow({
    icon: Icon,
    label,
    value,
}: {
    icon: typeof Activity;
    label: string;
    value: string;
}) {
    return (
        <div className="flex items-center justify-between gap-4">
            <span className="inline-flex items-center gap-2 text-muted-foreground">
                <Icon className="h-4 w-4" />
                {label}
            </span>
            <span className="text-right font-black">{value}</span>
        </div>
    );
}
