"use client";

import { ArrowLeft, CalendarDays, FileText, HandCoins, ShieldAlert, Timer, UserRound } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

import { displayReference } from "@/lib/display-reference";
import { formatMoney } from "@/lib/format";
import { useAppData } from "@/provider/appDataProvider";
import { StatusBadge } from "@/components/portal/status-badge";

export default function LoanRequestDetailPage() {
    const params = useParams<{ id: string }>();
    const router = useRouter();
    const { loanRequests, isLoanRequestsLoading, refreshAllData, getBorrowerById } = useAppData();
    const request = loanRequests.find((item) => item.id === params.id);

    useEffect(() => {
        if (request) return;
        const timer = window.setTimeout(() => void refreshAllData(), 0);
        return () => window.clearTimeout(timer);
    }, [refreshAllData, request]);

    if (isLoanRequestsLoading && !request) return <div className="flex min-h-[55vh] items-center justify-center text-sm text-muted-foreground">Loading loan request...</div>;
    if (!request) return <main className="flex min-h-[55vh] items-center justify-center"><section className="max-w-lg rounded-3xl border bg-card p-8 text-center shadow-sm"><ShieldAlert className="mx-auto h-10 w-10 text-amber-600" /><h1 className="mt-4 text-2xl font-black">Loan request unavailable</h1><p className="mt-2 text-sm text-muted-foreground">This request may have been removed or is outside the current platform view.</p><button type="button" onClick={() => router.push("/superadmin/loans")} className="mt-5 h-11 rounded-xl bg-primary px-5 text-sm font-black text-primary-foreground">Return to loan portfolio</button></section></main>;

    const borrower = getBorrowerById(request.borrower_id);
    const reference = displayReference("REQ", request.id, request.created_at);

    return <main className="space-y-6"><button type="button" onClick={() => router.push("/superadmin/loans")} className="inline-flex items-center gap-2 text-sm font-black text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" /> Back to loan portfolio</button><section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8"><div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-primary/10 blur-3xl" /><div className="relative flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-xs font-black uppercase tracking-[0.16em] text-primary">Loan request</p><h1 className="mt-2 text-3xl font-black">{reference}</h1><p className="mt-2 text-sm text-muted-foreground">A human-friendly reference is shown instead of the internal database identifier.</p></div><StatusBadge value={request.status} /></div></section><section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Card icon={HandCoins} label="Requested amount" value={formatMoney(request.requested_amount)} /><Card icon={Timer} label="Preferred term" value={request.preferred_term_months ? `${request.preferred_term_months} months` : "Flexible"} /><Card icon={CalendarDays} label="Submitted" value={new Date(request.created_at).toLocaleDateString("en-LS")} /><Card icon={UserRound} label="Borrower profile" value={borrower ? "Registered borrower" : "Protected marketplace profile"} /></section><section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_330px]"><article className="rounded-3xl border bg-card p-6 shadow-sm"><div className="flex items-center gap-2"><FileText className="h-5 w-5 text-primary" /><h2 className="text-lg font-black">Purpose and request information</h2></div><p className="mt-4 rounded-2xl bg-muted/40 p-5 text-sm leading-7 text-muted-foreground">{request.loan_purpose || "The borrower did not provide an additional purpose description."}</p></article><aside className="rounded-3xl border bg-card p-6 shadow-sm"><h2 className="font-black">Platform oversight</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">Use notifications, audit history and the company marketplace records to investigate activity. Internal UUIDs remain available only in API and technical logs.</p></aside></section></main>;
}

function Card({ icon: Icon, label, value }: { icon: typeof HandCoins; label: string; value: string }) {
    return <article className="rounded-2xl border bg-card p-5 shadow-sm"><Icon className="h-5 w-5 text-primary" /><p className="mt-3 text-xs font-bold uppercase tracking-wide text-muted-foreground">{label}</p><p className="mt-2 text-xl font-black">{value}</p></article>;
}
