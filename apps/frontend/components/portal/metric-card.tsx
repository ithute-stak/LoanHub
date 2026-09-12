import type { LucideIcon } from "lucide-react";

export function MetricCard({
    title,
    value,
    description,
    icon: Icon,
}: {
    title: string;
    value: string;
    description: string;
    icon: LucideIcon;
}) {
    return (
        <article className="rounded-3xl border bg-card p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-md">
            <div className="flex items-start justify-between gap-4">
                <div>
                    <p className="text-sm font-semibold text-muted-foreground">{title}</p>
                    <p className="mt-3 text-3xl font-black tracking-tight">{value}</p>
                    <p className="mt-2 text-xs leading-5 text-muted-foreground">{description}</p>
                </div>
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                    <Icon className="h-6 w-6" />
                </div>
            </div>
        </article>
    );
}
