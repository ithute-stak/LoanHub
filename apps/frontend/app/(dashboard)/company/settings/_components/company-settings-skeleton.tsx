export function CompanySettingsSkeleton() {
    return (
        <div className="space-y-6">
            <div className="h-40 animate-pulse rounded-3xl bg-muted" />

            <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
                <div className="h-[720px] animate-pulse rounded-3xl bg-muted" />
                <div className="space-y-6">
                    <div className="h-64 animate-pulse rounded-3xl bg-muted" />
                    <div className="h-48 animate-pulse rounded-3xl bg-muted" />
                </div>
            </div>
        </div>
    );
}
