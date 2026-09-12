import {LucideIcon, TrendingUp} from "lucide-react";

export function Activity({
                      icon: Icon,
                      title,
                      text,
                      time,
                      type,
                  }: {
    icon: LucideIcon;
    title: string;
    text: string;
    time: string;
    type: "company" | "user" | "request" | "revenue" | "system";
}) {
    const styles = {
        company: "bg-primary/10 text-primary",
        user: "bg-green-500/10 text-green-600",
        request: "bg-blue-500/10 text-blue-600",
        revenue: "bg-yellow-500/10 text-yellow-600",
        system: "bg-muted text-muted-foreground",
    };

    return (
        <div className="group relative flex cursor-pointer gap-4 rounded-2xl border border-border bg-background p-4 transition-all duration-300 hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md">
            <div
                className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl transition-all duration-300 group-hover:scale-105 ${styles[type]}`}
            >
                <Icon className="h-5 w-5" />
            </div>

            <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-3">
                    <p className="truncate font-black">{title}</p>

                    <span className="shrink-0 rounded-full bg-card px-2.5 py-1 text-[11px] font-black text-muted-foreground">
            {time}
          </span>
                </div>

                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                    {text}
                </p>
            </div>
        </div>
    );
}

export function StatCard({
                      title,
                      value,
                      trend,
                      icon: Icon,
                  }: {
    title: string;
    value?: string;
    trend: string;
    icon: LucideIcon;
}) {

    return (
        <div className="group cursor-pointer rounded-[2rem] border border-border bg-card p-6 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:border-primary/40 hover:shadow-2xl">
            <div className="flex items-center justify-between">
                <div className="rounded-2xl bg-primary/10 p-4 text-primary transition-all duration-300 group-hover:bg-primary group-hover:text-primary-foreground">
                    <Icon className="h-6 w-6" />
                </div>

                <div className="flex items-center gap-1 rounded-full bg-primary/10 px-3 py-1 text-xs font-black text-primary">
                    <TrendingUp className="h-3.5 w-3.5" />
                    {trend}
                </div>
            </div>

            <p className="mt-5 text-sm font-bold text-muted-foreground">{title}</p>
            <h3 className="mt-2 text-4xl font-black tracking-tight">{value}</h3>
        </div>
    );
}
