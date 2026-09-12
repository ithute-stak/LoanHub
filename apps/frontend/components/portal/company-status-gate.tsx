"use client";

import { Building2, Clock3, Loader2, LogOut, ShieldAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { useAppData } from "@/provider/appDataProvider";
import { useAppDispatch } from "@/store/hooks";
import { logoutUser } from "@/store/slices/authSlice";

export function CompanyStatusGate({ children }: { children: ReactNode }) {
    const router = useRouter();
    const dispatch = useAppDispatch();
    const {
        currentCompany,
        companies,
        isCompaniesLoading,
        errors,
        refreshAllData,
    } = useAppData();

    if (isCompaniesLoading && companies.length === 0) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-background">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
        );
    }

    if (!currentCompany) {
        return (
            <StatusScreen
                icon={ShieldAlert}
                title="Company workspace unavailable"
                message={errors.companies ?? "No company is currently assigned to this account."}
                actionLabel="Retry"
                onAction={() => void refreshAllData()}
                onLogout={async () => {
                    await dispatch(logoutUser());
                    router.replace("/login");
                }}
            />
        );
    }

    if (String(currentCompany.status).toLowerCase() !== "approved") {
        return (
            <StatusScreen
                icon={Clock3}
                title={
                    String(currentCompany.status).toLowerCase() === "rejected"
                        ? "Company registration was not approved"
                        : "Company registration is under review"
                }
                message={
                    String(currentCompany.status).toLowerCase() === "rejected"
                        ? "Contact the LoanHub platform administrator to review the registration requirements."
                        : "Your company account was created successfully. The platform administrator must verify and approve it before the operational workspace is enabled."
                }
                onLogout={async () => {
                    await dispatch(logoutUser());
                    router.replace("/login");
                }}
            />
        );
    }

    if (!currentCompany.is_active) {
        return (
            <StatusScreen
                icon={ShieldAlert}
                title="Company account is suspended"
                message="The company has been approved but is currently inactive. Contact the LoanHub platform administrator for assistance."
                onLogout={async () => {
                    await dispatch(logoutUser());
                    router.replace("/login");
                }}
            />
        );
    }

    return children;
}

function StatusScreen({
    icon: Icon,
    title,
    message,
    actionLabel,
    onAction,
    onLogout,
}: {
    icon: typeof Building2;
    title: string;
    message: string;
    actionLabel?: string;
    onAction?: () => void;
    onLogout: () => Promise<void>;
}) {
    return (
        <div className="flex min-h-screen items-center justify-center bg-muted/20 p-4">
            <section className="w-full max-w-xl rounded-3xl border bg-card p-8 text-center shadow-xl">
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-primary/10 text-primary">
                    <Icon className="h-8 w-8" />
                </div>
                <h1 className="mt-6 text-2xl font-black">{title}</h1>
                <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-muted-foreground">
                    {message}
                </p>
                <div className="mt-7 flex flex-col justify-center gap-3 sm:flex-row">
                    {onAction && actionLabel && (
                        <button
                            type="button"
                            onClick={onAction}
                            className="h-11 rounded-xl bg-primary px-5 text-sm font-black text-primary-foreground"
                        >
                            {actionLabel}
                        </button>
                    )}
                    <button
                        type="button"
                        onClick={() => void onLogout()}
                        className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border px-5 text-sm font-black"
                    >
                        <LogOut className="h-4 w-4" />
                        Logout
                    </button>
                </div>
            </section>
        </div>
    );
}
