"use client";

import Image from "next/image";
import {
    ArrowLeft,
    Building2,
    ShieldCheck,
    Users,
    Landmark,
    CheckCircle2,
} from "lucide-react";
import { useRouter } from "next/navigation";

import { CreateCompanyForm } from "@/components/CreateCompanyForm";

export default function LenderAccessPage() {
    const router = useRouter();

    return (
        <main className="h-screen overflow-hidden bg-background text-foreground">
            <div className="grid h-full lg:grid-cols-2">

                {/* LEFT SIDE */}
                <section className="relative hidden overflow-hidden bg-primary lg:flex">
                    <div className="absolute -left-32 -top-32 h-96 w-96 rounded-full bg-white/10 blur-3xl" />
                    <div className="absolute -bottom-32 -right-32 h-96 w-96 rounded-full bg-white/10 blur-3xl" />

                    <div className="relative z-10 flex h-full flex-col justify-center px-16 text-white">

                        <Image
                            src="/ithute-solutions-mark.png"
                            alt="LoanHub"
                            width={260}
                            height={180}
                            priority
                            className="mb-8 object-contain brightness-0 invert"
                        />

                        <h1 className="max-w-xl text-6xl font-black leading-tight">
                            Grow Your Lending Business.
                        </h1>

                        <p className="mt-6 max-w-xl text-lg leading-8 text-white/80">
                            Join LoanHub and connect directly with borrowers
                            across Lesotho. Manage applications, branches,
                            loan officers and customers from one platform.
                        </p>

                        <div className="mt-10 space-y-5">

                            <Feature
                                icon={Landmark}
                                text="Receive borrower applications in real-time"
                            />

                            <Feature
                                icon={Users}
                                text="Manage branches and loan officers"
                            />

                            <Feature
                                icon={ShieldCheck}
                                text="Secure approval workflows and compliance"
                            />

                            <Feature
                                icon={Building2}
                                text="Grow your customer base nationwide"
                            />

                        </div>

                        <div className="mt-12 rounded-3xl bg-white/10 p-6 backdrop-blur">
                            <p className="text-sm font-bold uppercase tracking-widest text-white/60">
                                Why LoanHub?
                            </p>

                            <p className="mt-3 text-lg leading-8 text-white/90">
                                LoanHub helps financial institutions
                                streamline borrower acquisition while
                                providing a professional digital experience.
                            </p>
                        </div>
                    </div>
                </section>

                {/* RIGHT SIDE */}
                <section className="relative flex h-full flex-col overflow-y-auto bg-background">

                    {/* Header */}
                    <div className="flex items-center justify-between border-b border-border px-8 py-5">
                        <button
                            type="button"
                            onClick={() => router.back()}
                            className="
                                flex
                                cursor-pointer
                                items-center
                                gap-2
                                rounded-2xl
                                border
                                border-border
                                px-4
                                py-2
                                text-sm
                                font-black
                                transition-all
                                hover:border-primary
                                hover:text-primary
                            "
                        >
                            <ArrowLeft className="h-4 w-4" />
                            Back
                        </button>

                        <div className="lg:hidden">
                            <Image
                                src="/ithute-solutions-mark.png"
                                alt="LoanHub"
                                width={120}
                                height={60}
                                priority
                            />
                        </div>
                    </div>

                    {/* Form */}
                    <div className="flex flex-1 items-center justify-center p-8">
                        <div className="w-full max-w-3xl">

                            <div className="mb-8">
                                <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-primary/10 px-4 py-2 text-xs font-black text-primary">
                                    <CheckCircle2 className="h-4 w-4" />
                                    Company Registration
                                </div>

                                <h2 className="text-4xl font-black">
                                    Register Your Institution
                                </h2>

                                <p className="mt-3 text-muted-foreground">
                                    Complete the form below and submit your
                                    application for review by the LoanHub
                                    SuperAdmin team.
                                </p>
                            </div>

                            <CreateCompanyForm />
                        </div>
                    </div>
                </section>

            </div>
        </main>
    );
}

function Feature({
                     icon: Icon,
                     text,
                 }: {
    icon: React.ElementType;
    text: string;
}) {
    return (
        <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/10">
                <Icon className="h-6 w-6" />
            </div>

            <p className="text-lg font-semibold">
                {text}
            </p>
        </div>
    );
}