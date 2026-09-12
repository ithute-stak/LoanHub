"use client";

import Link from "next/link";
import {
    ArrowLeft,
} from "lucide-react";

import {
    RegistrationForm,
} from "./_components/registration-form";
import {
    RegistrationSidebar,
} from "./_components/registration-sidebar";
import {
    RegistrationSuccess,
} from "./_components/registration-success";
import {
    useCompanyRegistration,
} from "./_hooks/use-company-registration";

export default function RegisterCompanyOwnerPage() {
    const registration =
        useCompanyRegistration();

    if (registration.complete) {
        return <RegistrationSuccess />;
    }

    return (
        <main className="min-h-screen bg-muted/20 px-4 py-5 sm:px-6 sm:py-8 lg:px-8">
            <div className="mx-auto max-w-7xl">
                <Link
                    href="/choose-account-type"
                    className="mb-5 inline-flex items-center gap-2 text-sm font-bold text-muted-foreground transition hover:text-foreground"
                >
                    <ArrowLeft className="h-4 w-4" />
                    Back to account types
                </Link>

                <div className="overflow-hidden rounded-3xl border bg-card shadow-2xl lg:grid lg:grid-cols-[0.85fr_1.4fr]">
                    <RegistrationSidebar />

                    <RegistrationForm
                        {...registration}
                    />
                </div>
            </div>
        </main>
    );
}
