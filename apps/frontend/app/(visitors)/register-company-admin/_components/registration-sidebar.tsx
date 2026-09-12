import {
    BadgeCheck,
    Banknote,
    Building2,
    GitBranch,
    ShieldCheck,
    Users,
} from "lucide-react";

const RESPONSIBILITIES = [
    {
        icon: Building2,
        title: "Manage the company",
        description:
            "Control company information, approval readiness and operational settings.",
    },
    {
        icon: GitBranch,
        title: "Manage branches",
        description:
            "Create branches and assign staff to the correct operating location.",
    },
    {
        icon: Users,
        title: "Manage roles",
        description:
            "Invite managers, loan officers, finance staff, collectors and auditors.",
    },
    {
        icon: Banknote,
        title: "Control lending",
        description:
            "Configure products, review requests, approve offers and oversee repayments.",
    },
];

export function RegistrationSidebar() {
    return (
        <aside className="relative overflow-hidden bg-slate-950 px-6 py-8 text-white lg:min-h-[760px] lg:px-8 lg:py-10">
            <div className="absolute -left-24 -top-24 h-72 w-72 rounded-full bg-primary/25 blur-3xl" />
            <div className="absolute -bottom-32 -right-20 h-80 w-80 rounded-full bg-blue-500/20 blur-3xl" />

            <div className="relative">
                <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-bold text-white/80 backdrop-blur">
                    <ShieldCheck className="h-4 w-4 text-emerald-400" />
                    Secure company onboarding
                </div>

                <div className="mt-8">
                    <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-slate-950 shadow-xl">
                        <Building2 className="h-7 w-7" />
                    </div>

                    <h1 className="mt-5 text-3xl font-black tracking-tight">
                        Become a LoanHub company owner
                    </h1>

                    <p className="mt-3 text-sm leading-7 text-white/65">
                        The first approved account becomes the
                        company owner. This role receives the
                        highest level of control inside the
                        company tenant.
                    </p>
                </div>

                <div className="mt-8 space-y-5">
                    {RESPONSIBILITIES.map(
                        ({
                            icon: Icon,
                            title,
                            description,
                        }) => (
                            <div
                                key={title}
                                className="flex gap-3"
                            >
                                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/10 text-white">
                                    <Icon className="h-5 w-5" />
                                </div>

                                <div>
                                    <h2 className="text-sm font-black">
                                        {title}
                                    </h2>

                                    <p className="mt-1 text-xs leading-5 text-white/55">
                                        {description}
                                    </p>
                                </div>
                            </div>
                        ),
                    )}
                </div>

                <div className="mt-10 rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur">
                    <div className="flex items-start gap-3">
                        <BadgeCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400" />

                        <div>
                            <p className="text-sm font-black">
                                What happens after registration?
                            </p>

                            <ol className="mt-3 space-y-2 text-xs leading-5 text-white/60">
                                <li>
                                    1. LoanHub verifies the
                                    company details.
                                </li>
                                <li>
                                    2. The company is approved
                                    or returned for correction.
                                </li>
                                <li>
                                    3. The owner selects a
                                    billing plan.
                                </li>
                                <li>
                                    4. Branches, staff and
                                    loan products can be added.
                                </li>
                            </ol>
                        </div>
                    </div>
                </div>
            </div>
        </aside>
    );
}
