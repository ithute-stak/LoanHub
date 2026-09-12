"use client";

import Link from "next/link";
import { KeyRound, LogIn } from "lucide-react";

import {BorrowerHero} from "@/app/(visitors)/borrower-registration/_components/borrowerHero";
import {BorrowerHeader} from "@/app/(visitors)/borrower-registration/_components/borrowerHeader";
import {CreateBorrowerForm} from "@/app/(visitors)/borrower-registration/_components/createBorrowerForm";

export default function BorrowerRegisterPage() {
    return (
        <main className="h-screen overflow-hidden bg-background">
            <div className="grid h-full lg:grid-cols-2">

                <BorrowerHero />

                <section className="flex flex-col overflow-y-auto">
                    <BorrowerHeader />

                    <div className="flex flex-1 items-center justify-center p-8">
                        <div className="w-full max-w-4xl">

                            <div className="mb-8">
                                <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-4 py-2 text-xs font-black text-primary">
                                    Borrower Registration
                                </div>

                                <h1 className="mt-4 text-4xl font-black">
                                    Create Borrower Account
                                </h1>

                                <p className="mt-3 text-muted-foreground">
                                    Complete your information to access loans,
                                    track applications and manage your profile.
                                </p>

                                <div className="mt-5 flex flex-wrap items-center gap-3 rounded-2xl border border-border/70 bg-muted/30 p-4 text-sm">
                                    <span className="font-medium text-foreground">
                                        Already have a LoanHub borrower account?
                                    </span>
                                    <Link
                                        href="/login"
                                        className="inline-flex items-center gap-2 rounded-xl bg-primary px-3 py-2 font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
                                    >
                                        <LogIn className="h-4 w-4" />
                                        Sign in
                                    </Link>
                                    <Link
                                        href="/forgot-password"
                                        className="inline-flex items-center gap-2 rounded-xl border border-input bg-background px-3 py-2 font-semibold text-foreground transition-colors hover:bg-accent"
                                    >
                                        <KeyRound className="h-4 w-4" />
                                        Forgot password
                                    </Link>
                                </div>
                            </div>

                            <CreateBorrowerForm />

                        </div>
                    </div>
                </section>

            </div>
        </main>
    );
}
