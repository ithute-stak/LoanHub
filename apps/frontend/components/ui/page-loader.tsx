import { Skeleton } from "@/components/ui/skeleton";

export function PageLoader({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-5" aria-label="Loading page">
      <div className="rounded-[1.75rem] border bg-gradient-to-br from-primary/15 via-background to-emerald-500/10 p-6">
        <Skeleton className="h-7 w-64" />
        <Skeleton className="mt-3 h-4 w-full max-w-xl" />
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        {[0, 1, 2].map((item) => <Skeleton key={item} className="h-28 rounded-3xl" />)}
      </div>
      <div className="rounded-3xl border bg-card p-5">
        {Array.from({ length: rows }).map((_, index) => (
          <div key={index} className="flex gap-4 border-b py-4 last:border-0">
            <Skeleton className="h-10 w-10 rounded-xl" />
            <div className="flex-1 space-y-2"><Skeleton className="h-4 w-1/3" /><Skeleton className="h-3 w-2/3" /></div>
          </div>
        ))}
      </div>
    </div>
  );
}
