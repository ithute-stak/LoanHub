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
        <article className="min-w-0 rounded-2xl border bg-card p-4 shadow-sm transition hover:border-primary/30 2xl:rounded-3xl 2xl:p-5">
            <div className="flex min-w-0 items-start justify-between gap-3 2xl:gap-4">
                <div className="min-w-0">
                    <p className="text-xs font-semibold text-muted-foreground 2xl:text-sm">{title}</p>
                    <p className="mt-2 break-words text-2xl font-black tracking-tight 2xl:mt-3 2xl:text-3xl">{value}</p>
                    <p className="mt-1.5 text-[11px] leading-4 text-muted-foreground 2xl:mt-2 2xl:text-xs 2xl:leading-5">{description}</p>
                </div>
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary 2xl:h-12 2xl:w-12 2xl:rounded-2xl">
                    <Icon className="h-5 w-5 2xl:h-6 2xl:w-6" />
                </div>
            </div>
        </article>
    );
}
