import {
    Building2,
    RefreshCcw,
} from "lucide-react";

type Props = {
    companyName?: string | null;
    refreshing: boolean;
    onRefresh: () => void;
};

export function CompanySettingsHeader({
    companyName,
    refreshing,
    onRefresh,
}: Props) {
    return (
        <section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8">
            <div className="absolute -right-20 -top-24 h-64 w-64 rounded-full bg-primary/10 blur-3xl" />

            <div className="relative flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-start gap-4">
                    <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                        <Building2 className="h-7 w-7" />
                    </div>

                    <div>
                        <p className="text-xs font-black uppercase tracking-[0.16em] text-primary">
                            Tenant administration
                        </p>

                        <h1 className="mt-1 text-3xl font-black tracking-tight">
                            Company settings
                        </h1>

                        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
                            Maintain legal, contact and operating
                            information for{" "}
                            <strong className="text-foreground">
                                {companyName ?? "the active company"}
                            </strong>
                            .
                        </p>
                    </div>
                </div>

                <button
                    type="button"
                    onClick={onRefresh}
                    disabled={refreshing}
                    className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border bg-background px-4 text-sm font-black transition hover:border-primary hover:text-primary disabled:opacity-50"
                >
                    <RefreshCcw
                        className={`h-4 w-4 ${
                            refreshing ? "animate-spin" : ""
                        }`}
                    />
                    Refresh
                </button>
            </div>
        </section>
    );
}
