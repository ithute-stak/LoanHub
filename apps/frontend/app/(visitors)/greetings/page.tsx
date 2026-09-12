"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import {
    ArrowRight,
    BadgeCheck,
    Building2,
    ShieldCheck,
    Wallet,
} from "lucide-react";

import { StorageKeys } from "@/lib/storage";

export default function GreetingsPage() {
    const router = useRouter();

    const continueToNext = () => {
        localStorage.setItem(
            StorageKeys.hasSeenOnboarding,
            "true"
        );

        router.push("/choose-account-type");
    };

    return (
        <main className="relative min-h-screen overflow-hidden bg-background text-foreground">
            {/* Background Effects */}
            <div className="absolute left-[-150px] top-[-150px] h-96 w-96 rounded-full bg-primary/15 blur-3xl" />

            <div className="absolute bottom-[-180px] right-[-100px] h-[500px] w-[500px] rounded-full bg-primary/10 blur-3xl" />

            <div className="relative z-10 container mx-auto flex min-h-screen items-center justify-center px-6 py-12">
                <div className="max-w-6xl">
                    <div className="grid items-center gap-16 lg:grid-cols-2">
                        {/* LEFT */}
                        <div>
                            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-sm font-semibold shadow-sm">
                                <BadgeCheck className="h-4 w-4 text-primary" />
                                Trusted Financial Marketplace
                            </div>

                            <h1 className="mt-8 text-5xl font-black leading-tight md:text-7xl">
                                Welcome to{" "}
                                <span className="text-primary">
                                    LoanHub
                                </span>
                            </h1>

                            <p className="mt-8 text-lg leading-8 text-muted-foreground md:text-xl">
                                A modern platform connecting borrowers,
                                lenders and financial institutions
                                throughout Lesotho.
                            </p>

                            <div className="mt-10 grid gap-4">
                                <Benefit
                                    icon={<Wallet className="h-5 w-5" />}
                                    title="Compare Loan Offers"
                                    text="Apply once and receive offers from multiple lenders."
                                />

                                <Benefit
                                    icon={<Building2 className="h-5 w-5" />}
                                    title="Licensed Institutions"
                                    text="Work with approved and trusted financial providers."
                                />

                                <Benefit
                                    icon={<ShieldCheck className="h-5 w-5" />}
                                    title="Secure & Reliable"
                                    text="Protected accounts and secure communication."
                                />
                            </div>

                            <button
                                onClick={continueToNext}
                                className="
                                    group
                                    mt-10
                                    flex
                                    cursor-pointer
                                    items-center
                                    gap-3
                                    rounded-2xl
                                    bg-primary
                                    px-8
                                    py-4
                                    font-black
                                    text-primary-foreground
                                    shadow-xl
                                    transition-all
                                    duration-300
                                    hover:-translate-y-1
                                    hover:shadow-2xl
                                    active:scale-[0.98]
                                "
                            >
                                Get Started

                                <ArrowRight className="h-5 w-5 transition-transform duration-300 group-hover:translate-x-1" />
                            </button>
                        </div>

                        {/* RIGHT */}
                        <div className="flex justify-center">
                            <div className="rounded-[2rem] border border-border bg-card p-8 shadow-2xl">
                                <Image
                                    src="/ithute-solutions-mark.png"
                                    alt="LoanHub"
                                    width={420}
                                    height={420}
                                    priority
                                    className="object-contain"
                                />
                            </div>
                        </div>
                    </div>

                    <div className="mt-20 text-center">
                        <p className="text-sm text-muted-foreground">
                            LoanHub empowers borrowers and loan companies
                            to connect, collaborate and grow through one
                            secure marketplace.
                        </p>
                    </div>
                </div>
            </div>
        </main>
    );
}

function Benefit({
                     icon,
                     title,
                     text,
                 }: {
    icon: React.ReactNode;
    title: string;
    text: string;
}) {
    return (
        <div className="flex items-start gap-4 rounded-2xl border border-border bg-card p-4 shadow-sm">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                {icon}
            </div>

            <div>
                <h3 className="font-black">{title}</h3>

                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                    {text}
                </p>
            </div>
        </div>
    );
}