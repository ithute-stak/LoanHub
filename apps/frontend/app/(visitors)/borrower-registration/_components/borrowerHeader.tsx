"use client";

import Image from "next/image";
import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";

export function BorrowerHeader() {
    const router = useRouter();

    return (
        <div className="flex items-center justify-between border-b border-border px-8 py-5">

            <button
                onClick={() => router.back()}
                className="
                    flex
                    items-center
                    gap-2
                    rounded-2xl
                    border
                    border-border
                    px-4
                    py-2
                    text-sm
                    font-black
                    transition
                    hover:border-primary
                    hover:text-primary
                "
            >
                <ArrowLeft className="h-4 w-4"/>
                Back
            </button>

            <div className="lg:hidden">
                <Image
                    src="/ithute-solutions-mark.png"
                    alt="LoanHub"
                    width={120}
                    height={60}
                />
            </div>

        </div>
    );
}