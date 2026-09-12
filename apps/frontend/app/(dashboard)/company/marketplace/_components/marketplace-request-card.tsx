import {
    BriefcaseBusiness,
    CalendarDays,
    Eye,
    LockKeyhole,
    MapPin,
} from "lucide-react";

import { StatusBadge } from "@/components/portal/status-badge";
import { formatDate, formatMoney } from "@/lib/format";
import type { MarketplaceRequestCard } from "@/types/marketplace";

export function MarketplaceRequestCardView({
    request,
    onOpen,
}: {
    request: MarketplaceRequestCard;
    onOpen: (request: MarketplaceRequestCard) => void;
}) {
    return (
        <article className="flex h-full flex-col rounded-3xl border bg-card p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md">
            <div className="flex items-start justify-between gap-4">
                <div>
                    <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
                        Requested amount
                    </p>
                    <p className="mt-2 text-2xl font-black">{formatMoney(request.requested_amount)}</p>
                </div>
                <StatusBadge value={request.status} />
            </div>

            <div className="mt-5 grid gap-3 text-sm">
                <div className="flex items-center gap-3 rounded-2xl bg-muted/50 p-3">
                    <MapPin className="h-4 w-4 text-primary" />
                    <span>{request.borrower.district ?? "District not supplied"}</span>
                </div>
                <div className="flex items-center gap-3 rounded-2xl bg-muted/50 p-3">
                    <BriefcaseBusiness className="h-4 w-4 text-primary" />
                    <span>
                        {request.borrower.employment_status.replaceAll("_", " ")} · {request.borrower.monthly_income_band ?? "Income private"}
                    </span>
                </div>
                <div className="flex items-center gap-3 rounded-2xl bg-muted/50 p-3">
                    <CalendarDays className="h-4 w-4 text-primary" />
                    <span>
                        {request.preferred_term_months
                            ? `${request.preferred_term_months} months preferred`
                            : "Flexible repayment term"}
                    </span>
                </div>
            </div>

            <p className="mt-4 line-clamp-3 flex-1 text-sm leading-6 text-muted-foreground">
                {request.loan_purpose || "The borrower did not specify a loan purpose."}
            </p>

            <div className="mt-5 flex items-center justify-between gap-3 border-t pt-4">
                <div>
                    <p className="text-xs text-muted-foreground">Published {formatDate(request.created_at)}</p>
                    <p className="mt-1 text-xs font-bold text-primary">
                        {request.is_unlocked ? "Borrower profile unlocked" : `Unlock for ${formatMoney(request.unlock_price)}`}
                    </p>
                </div>
                <button
                    type="button"
                    onClick={() => onOpen(request)}
                    className="inline-flex h-10 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-bold text-primary-foreground"
                >
                    {request.is_unlocked ? <Eye className="h-4 w-4" /> : <LockKeyhole className="h-4 w-4" />}
                    {request.is_unlocked ? "View" : "Unlock"}
                </button>
            </div>
        </article>
    );
}
