"use client";

import {
    ShieldCheck,
} from "lucide-react";

import {
    CompanyAdminTable,
} from "./_components/adminTable";

export default function CompanyAdminsPage() {
    return (
        <main className="space-y-6">
            <section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8">
                <div className="absolute -right-20 -top-24 h-64 w-64 rounded-full bg-primary/10 blur-3xl" />

                <div className="relative flex items-start gap-4">
                    <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                        <ShieldCheck className="h-7 w-7" />
                    </div>

                    <div>
                        <p className="text-xs font-black uppercase tracking-[0.16em] text-primary">
                            Platform access control
                        </p>

                        <h1 className="mt-1 text-3xl font-black tracking-tight">
                            Company administrators
                        </h1>

                        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
                            Review company administrator profiles, account status and tenant assignments from one place.
                        </p>
                    </div>
                </div>
            </section>

            <CompanyAdminTable />
        </main>
    );
}
