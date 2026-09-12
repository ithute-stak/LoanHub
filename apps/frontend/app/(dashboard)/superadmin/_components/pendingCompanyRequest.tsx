import {
    Building2,
    CheckCircle2,
    Loader2,
    XCircle,
} from "lucide-react";

import type {
    LoanCompany,
} from "@/store/slices/companiesSlice";

export default function PendingCompanyCard({company, loading, onApprove, onReject}: {
    company: LoanCompany;
    loading: boolean;
    onApprove: () => void;
    onReject: () => void;
}) {
    return (
        <div className="rounded-2xl border border-border bg-card p-5 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md">
            <div className="flex items-start gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                    <Building2 className="h-5 w-5" />
                </div>

                <div className="min-w-0 flex-1">
                    <h4 className="truncate font-black">
                        {company.name}
                    </h4>

                    <p className="mt-1 text-sm text-muted-foreground">
                        {company.email}
                    </p>

                    <div className="mt-3 grid gap-2 text-sm md:grid-cols-2">
                        <p>
                            <span className="font-black">District:</span>{" "}
                            {company.district}
                        </p>

                        <p>
                            <span className="font-black">Phone:</span>{" "}
                            {company.phone}
                        </p>

                        <p>
                            <span className="font-black">Reg:</span>{" "}
                            {company.registration_number}
                        </p>

                        <p>
                            <span className="font-black">License:</span>{" "}
                            {company.license_number}
                        </p>
                    </div>
                </div>
            </div>

            <div className="mt-5 flex justify-end gap-3">
                <button
                    type="button"
                    onClick={onReject}
                    disabled={loading}
                    className="flex cursor-pointer items-center gap-2 rounded-xl border border-destructive/30 px-4 py-2 text-sm font-black text-destructive transition-all hover:bg-destructive/10 disabled:cursor-not-allowed disabled:opacity-50"
                >
                    {loading ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                        <XCircle className="h-4 w-4" />
                    )}
                    Reject
                </button>

                <button
                    type="button"
                    onClick={onApprove}
                    disabled={loading}
                    className="flex cursor-pointer items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-black text-primary-foreground shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-50"
                >
                    {loading ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                        <CheckCircle2 className="h-4 w-4" />
                    )}
                    Approve
                </button>
            </div>
        </div>
    );
}