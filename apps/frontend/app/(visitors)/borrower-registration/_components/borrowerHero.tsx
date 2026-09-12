"use client";

import Image from "next/image";
import {
    CreditCard,
    Wallet,
    ShieldCheck,
    CheckCircle2
} from "lucide-react";
import {BorrowerFeature} from "@/app/(visitors)/borrower-registration/_components/borrowerFeature";


export function BorrowerHero() {
    return (
        <section className="relative hidden overflow-hidden bg-primary lg:flex">

            <div className="absolute -left-32 -top-32 h-96 w-96 rounded-full bg-white/10 blur-3xl"/>
            <div className="absolute -bottom-32 -right-32 h-96 w-96 rounded-full bg-white/10 blur-3xl"/>

            <div className="relative z-10 flex h-full flex-col justify-center px-16 text-white">

                <Image
                    src="/ithute-solutions-mark.png"
                    alt="LoanHub"
                    width={250}
                    height={120}
                    className="mb-8 brightness-0 invert"
                />

                <h1 className="max-w-xl text-6xl font-black">
                    Access Loans Faster.
                </h1>

                <p className="mt-6 max-w-xl text-lg leading-8 text-white/80">
                    Apply for loans, manage your profile and
                    connect with lenders from one secure platform.
                </p>

                <div className="mt-10 space-y-5">

                    <BorrowerFeature
                        icon={Wallet}
                        text="Apply for loans online"
                    />

                    <BorrowerFeature
                        icon={CreditCard}
                        text="Track loan applications"
                    />

                    <BorrowerFeature
                        icon={ShieldCheck}
                        text="Secure profile management"
                    />

                    <BorrowerFeature
                        icon={CheckCircle2}
                        text="Connect with trusted lenders"
                    />

                </div>
            </div>
        </section>
    );
}