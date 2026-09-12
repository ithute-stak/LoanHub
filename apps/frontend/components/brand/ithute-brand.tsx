import Image from "next/image";
import Link from "next/link";

/** LoanHub is the product. Ithute Solutions is credited separately as developer. */
export function IthuteBrand({
    href = "/",
    compact = false,
    subtitle = "Lesotho loan marketplace",
}: {
    href?: string;
    compact?: boolean;
    subtitle?: string;
}) {
    return (
        <Link href={href} className="flex min-w-0 items-center gap-3" aria-label="LoanHub home">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-2xl border bg-white shadow-sm">
                <Image src="/loanhub-app-icon.png" alt="LoanHub" width={48} height={48} className="h-full w-full object-contain" priority />
            </div>
            {!compact && (
                <div className="min-w-0">
                    <Image src="/loanhub-horizontal-logo.png" alt="LoanHub — Lesotho Loan Marketplace" width={190} height={52} className="h-9 w-auto max-w-full object-contain object-left" priority />
                    <p className="mt-1 truncate text-[11px] font-semibold text-muted-foreground">{subtitle}</p>
                </div>
            )}
        </Link>
    );
}

export function IthutePoweredBy() {
    return (
        <div className="flex items-center gap-2 text-[10px] font-bold text-muted-foreground">
            <Image src="/ithute-solutions-developer-logo.png" alt="Ithute Solutions" width={28} height={28} className="h-7 w-7 rounded-lg border bg-white object-contain p-0.5" />
            <span>Software engineering by Ithute Solutions</span>
        </div>
    );
}
