"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import {
    ArrowRight,
    BadgeCheck,
    Building2,
    Landmark,
    ShieldCheck,
    User,
    WalletCards,
} from "lucide-react";

export default function ChooseAccountTypePage() {
    const router = useRouter();

    return (
        <main className="relative h-screen overflow-hidden bg-background text-foreground">
            <div className="absolute left-[-160px] top-[-160px] h-[360px] w-[360px] rounded-full bg-primary/15 blur-3xl" />
            <div className="absolute bottom-[-180px] right-[-140px] h-[420px] w-[420px] rounded-full bg-primary/10 blur-3xl" />

            <div className="relative z-10 container mx-auto flex h-screen items-center justify-center px-6">
                <div className="w-full max-w-6xl">
                    <div className="mb-8 flex flex-col items-center text-center">
                        <Image
                            src="/ithute-solutions-mark.png"
                            alt="LoanHub by Ithute Solutions"
                            width={230}
                            height={120}
                            priority
                            className="object-contain"
                        />

                        <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-xs font-semibold text-muted-foreground shadow-sm">
                            <BadgeCheck className="h-4 w-4 text-primary" />
                            Trusted Loan Marketplace
                        </div>

                        <h1 className="mt-4 text-3xl font-black tracking-tight md:text-5xl">
                            Choose how you want to use LoanHub
                        </h1>

                        <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground md:text-base">
                            LoanHub connects borrowers, loan companies and financial
                            institutions across Lesotho through one secure marketplace.
                        </p>
                    </div>

                    <div className="grid gap-6 lg:grid-cols-2">
                        <AccountTypeCard
                            icon={<User className="h-7 w-7" />}
                            title="Borrower"
                            description="Apply once and receive loan offers from multiple approved lenders throughout Lesotho."
                            features={[
                                "Create one borrower profile",
                                "Submit loan requests online",
                                "Compare lender offers",
                            ]}
                            action="Continue as Borrower"
                            onClick={() => router.push("/borrower-registration")}
                        />

                        <AccountTypeCard
                            icon={<Building2 className="h-7 w-7" />}
                            title="Loan Company"
                            description="Register your institution, manage branches, review applications and grow your lending portfolio."
                            features={[
                                "Register company profile",
                                "Manage branches and staff",
                                "Receive borrower requests",
                            ]}
                            action="Continue as Loan Company"
                            onClick={() => router.push("/register-company-admin")}
                        />
                    </div>

                    <div className="mt-6 flex flex-col items-center gap-2 text-center">
                        <button
                            type="button"
                            onClick={() => router.push("/login")}
                            className="cursor-pointer text-sm font-bold text-primary transition-all duration-200 hover:underline hover:opacity-80"
                        >
                            Already have an account? Login
                        </button>

                        <p className="max-w-2xl text-xs leading-5 text-muted-foreground">
                            Secure access for borrowers, company admins, branch managers,
                            loan officers and platform administrators.
                        </p>
                    </div>
                </div>
            </div>
        </main>
    );
}

function AccountTypeCard({
                             icon,
                             title,
                             description,
                             features,
                             action,
                             onClick,
                         }: {
    icon: React.ReactNode;
    title: string;
    description: string;
    features: string[];
    action: string;
    onClick: () => void;
}) {
    return (
        <button
            type="button"
            onClick={onClick}
            className="group h-full cursor-pointer rounded-[1.75rem] border border-border bg-card p-6 text-left shadow-sm transition-all duration-300 hover:-translate-y-1 hover:border-primary hover:shadow-2xl active:scale-[0.98]"
        >
            <div className="flex items-start justify-between gap-6">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-primary transition-all duration-300 group-hover:bg-primary group-hover:text-primary-foreground">
                    {icon}
                </div>

                <ArrowRight className="h-5 w-5 text-muted-foreground transition-all duration-300 group-hover:translate-x-1 group-hover:text-primary" />
            </div>

            <h2 className="mt-5 text-2xl font-black text-card-foreground">
                {title}
            </h2>

            <p className="mt-3 text-sm leading-6 text-muted-foreground">
                {description}
            </p>

            <div className="mt-5 space-y-2.5">
                {features.map((feature) => (
                    <div key={feature} className="flex items-center gap-3">
                        <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-primary">
                            <ShieldCheck className="h-3.5 w-3.5" />
                        </div>

                        <span className="text-sm font-semibold text-card-foreground">
              {feature}
            </span>
                    </div>
                ))}
            </div>

            <div className="mt-5 flex items-center justify-between rounded-2xl border border-border bg-background px-4 py-3">
                <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
                        {title === "Borrower" ? (
                            <WalletCards className="h-4.5 w-4.5" />
                        ) : (
                            <Landmark className="h-4.5 w-4.5" />
                        )}
                    </div>

                    <span className="text-sm font-black text-primary">
            {action}
          </span>
                </div>

                <ArrowRight className="h-4.5 w-4.5 text-primary transition-transform duration-300 group-hover:translate-x-1" />
            </div>
        </button>
    );
}