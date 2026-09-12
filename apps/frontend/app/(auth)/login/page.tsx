"use client";

import Image from "next/image";
import Link from "next/link";
import {
    ArrowRight,
    Eye,
    EyeOff,
    Globe2,
    Loader2,
    Lock,
    KeyRound,
    Phone,
    ShieldCheck,
    Sparkles,
    Workflow,
} from "lucide-react";
import { useMemo, useState, type FormEvent, type ReactNode } from "react";
import { useRouter } from "next/navigation";

import { Input } from "@/components/ui/input";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { loginUser } from "@/store/slices/authSlice";
import { getDashboardRoute } from "@/lib/role-redirect";

function normalisePhone(value: string) {
    return value.replace(/\s+/g, "").replace(/^\+266/, "").replace(/^266/, "");
}

export default function LoginPage() {
    const router = useRouter();
    const dispatch = useAppDispatch();
    const { loading, error } = useAppSelector((state) => state.auth);

    const [showPassword, setShowPassword] = useState(false);
    const [phone, setPhone] = useState("");
    const [password, setPassword] = useState("");
    const [secondFactor, setSecondFactor] = useState("");

    const cleanedPhone = useMemo(() => normalisePhone(phone), [phone]);
    const formReady = cleanedPhone.trim().length >= 8 && password.trim().length > 0;

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();

        const result = await dispatch(
            loginUser({
                phone: cleanedPhone,
                password: password.trim(),
                otp: /^\d{6}$/.test(secondFactor.trim()) ? secondFactor.trim() : null,
                recovery_code: secondFactor.trim() && !/^\d{6}$/.test(secondFactor.trim()) ? secondFactor.trim() : null,
                device_name: typeof navigator === "undefined" ? "LoanHub web" : `${navigator.platform || "Web"} browser`,
            }),
        );

        if (loginUser.fulfilled.match(result)) {
            router.replace(
                result.payload.user.must_change_password
                    ? "/change-password"
                    : getDashboardRoute(result.payload.user.role),
            );
        }
    };

    return (
        <main className="min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top_left,rgba(30,97,185,0.12),transparent_26%),radial-gradient(circle_at_bottom_right,rgba(34,197,94,0.10),transparent_24%),linear-gradient(180deg,#f7fbff_0%,#f3f7fc_52%,#eef4fb_100%)] text-foreground">
            <div className="grid min-h-screen lg:grid-cols-[1.02fr_0.98fr]">
                <section className="relative hidden overflow-hidden border-r border-border/70 lg:flex">
                    <div className="absolute inset-0 bg-[linear-gradient(135deg,#ebf5ff_0%,#f7fbff_48%,#eef9f1_100%)]" />
                    <div className="absolute left-[-120px] top-[-120px] h-[320px] w-[320px] rounded-full bg-[#1e61b9]/16 blur-3xl" />
                    <div className="absolute right-[-80px] top-[12%] h-[240px] w-[240px] rounded-full bg-[#22c55e]/14 blur-3xl" />
                    <div className="absolute bottom-[-100px] left-[18%] h-[260px] w-[260px] rounded-full bg-[#facc15]/10 blur-3xl" />
                    <div className="absolute bottom-[-90px] right-[-60px] h-[220px] w-[220px] rounded-full bg-[#14b8a6]/10 blur-3xl" />

                    <div className="relative z-10 flex w-full items-center justify-center px-12 py-10 xl:px-16">
                        <div className="w-full max-w-xl">
                            <div className="inline-flex items-center gap-2 rounded-full border border-primary/15 bg-white/80 px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-primary shadow-sm backdrop-blur">
                                <Sparkles className="h-4 w-4" />
                                LoanHub by Ithute Solutions
                            </div>

                            <h1 className="mt-7 max-w-lg text-5xl font-black leading-[1.02] tracking-tight text-slate-950 xl:text-[3.65rem]">
                                Welcome to a smarter way to manage lending.
                            </h1>

                            <p className="mt-4 max-w-lg text-lg leading-8 text-slate-600">
                                Secure, simple loan operations for approvals, repayments, contracts, collections and daily business control.
                            </p>

                            <div className="mt-6 flex flex-wrap gap-3">
                                <MiniPill icon={<ShieldCheck className="h-4 w-4" />} text="Secure access" />
                                <MiniPill icon={<Workflow className="h-4 w-4" />} text="Simple workflow" />
                                <MiniPill icon={<Globe2 className="h-4 w-4" />} text="Built for Lesotho" />
                            </div>

                            <div className="mt-8 overflow-hidden rounded-[2rem] border border-white/85 bg-white/74 p-5 shadow-[0_28px_90px_-48px_rgba(15,23,42,0.42)] backdrop-blur xl:p-6">
                                <div className="grid items-center gap-5 xl:grid-cols-[1fr_0.9fr]">
                                    <div className="relative overflow-hidden rounded-[1.75rem] border border-white/50 bg-[radial-gradient(circle_at_20%_18%,rgba(255,255,255,0.42),transparent_16%),radial-gradient(circle_at_80%_20%,rgba(250,204,21,0.22),transparent_20%),radial-gradient(circle_at_72%_82%,rgba(34,197,94,0.22),transparent_26%),linear-gradient(135deg,#0f418b_0%,#1e61b9_48%,#0f9f72_100%)] p-6 text-white shadow-[0_22px_60px_-30px_rgba(15,23,42,0.55)]">
                                        <div className="inline-flex rounded-full border border-white/20 bg-white/10 px-3 py-1.5 text-[11px] font-black uppercase tracking-[0.16em] text-white/95 backdrop-blur">
                                            LoanHub platform
                                        </div>

                                        <h2 className="mt-5 max-w-xs text-3xl font-black leading-tight tracking-tight text-white">
                                            Clean, modern lending operations.
                                        </h2>

                                        <p className="mt-3 max-w-sm text-sm leading-7 text-white/85">
                                            One workspace for borrower records, approvals, schedules and recovery.
                                        </p>

                                        <div className="mt-8 flex justify-center">
                                            <div className="flex h-40 w-40 items-center justify-center rounded-[2rem] border border-white/25 bg-white/15 backdrop-blur-lg">
                                                <div className="flex h-28 w-28 items-center justify-center rounded-[1.4rem] bg-white shadow-[0_18px_40px_-22px_rgba(15,23,42,0.65)]">
                                                    <Image
                                                        src="/burner.png"
                                                        alt="LoanHub by Ithute Solutions"
                                                        width={160}
                                                        height={160}
                                                        priority
                                                        className="h-auto w-[90px] object-contain"
                                                    />
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="space-y-3">
                                        <InfoCard
                                            icon={<ShieldCheck className="h-5 w-5" />}
                                            title="Protected access"
                                            text="Secure sign-in with authenticated sessions and role-based access."
                                        />
                                        <InfoCard
                                            icon={<Workflow className="h-5 w-5" />}
                                            title="Operational workflow"
                                            text="Manage requests, approvals, documents, payments and collections from one place."
                                        />
                                        <InfoCard
                                            icon={<Globe2 className="h-5 w-5" />}
                                            title="Professional workspace"
                                            text="A cleaner system experience designed to feel simple, business-ready and reliable."
                                        />
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                <section className="relative flex items-center justify-center px-5 py-8 sm:px-8 sm:py-10 lg:px-10 xl:px-14">
                    <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(255,255,255,0.38),transparent)] lg:hidden" />
                    <div className="relative z-10 w-full max-w-lg">
                        <div className="mb-8 flex flex-col items-center text-center lg:hidden">
                            <div className="rounded-[1.8rem] border border-white/80 bg-white/85 p-5 shadow-[0_24px_70px_-40px_rgba(15,23,42,0.45)] backdrop-blur">
                                <Image
                                    src="/burner.png"
                                    alt="LoanHub by Ithute Solutions"
                                    width={160}
                                    height={160}
                                    priority
                                    className="object-contain"
                                />
                            </div>
                            <h1 className="mt-5 text-3xl font-black tracking-tight text-slate-950">
                                Welcome to LoanHub
                            </h1>
                            <p className="mt-2 max-w-md text-sm leading-6 text-slate-600">
                                Secure lending operations for companies and borrowers across Lesotho.
                            </p>
                        </div>

                        <div className="rounded-[2rem] border border-white/80 bg-white/88 p-6 shadow-[0_30px_90px_-45px_rgba(15,23,42,0.45)] backdrop-blur sm:p-8">
                            <div className="mb-7">
                                <div className="inline-flex items-center gap-2 rounded-full border border-primary/15 bg-primary/5 px-4 py-2 text-sm font-semibold text-primary shadow-sm">
                                    <Sparkles className="h-4 w-4" />
                                    LoanHub secure login
                                </div>

                                <h2 className="mt-5 text-4xl font-black tracking-tight text-slate-950">
                                    Welcome back
                                </h2>

                                <p className="mt-3 max-w-md leading-7 text-slate-600">
                                    Sign in to continue managing your LoanHub account, loan operations and company workspace.
                                </p>
                            </div>

                            {error ? (
                                <div className="mb-6 rounded-2xl border border-destructive/25 bg-destructive/10 px-4 py-3 text-sm font-semibold text-destructive shadow-sm">
                                    {error}
                                </div>
                            ) : null}

                            <form onSubmit={handleSubmit} className="space-y-5">
                                <div className="space-y-2.5">
                                    <div className="flex items-center justify-between gap-2">
                                        <label htmlFor="login-phone" className="text-sm font-black text-slate-800">
                                            Phone number
                                        </label>
                                        <span className="text-xs font-semibold text-slate-500">
                                            Use your registered LoanHub number
                                        </span>
                                    </div>

                                    <div className="group flex min-h-16 items-center rounded-2xl border border-slate-200 bg-slate-50/80 px-4 shadow-sm transition-all duration-200 focus-within:border-primary/60 focus-within:bg-white focus-within:ring-4 focus-within:ring-primary/10">
                                        <div className="flex items-center gap-3 pr-3">
                                            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                                                <Phone className="h-5 w-5" />
                                            </div>
                                            <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-black tracking-wide text-slate-600">
                                                +266
                                            </span>
                                        </div>

                                        <Input
                                            id="login-phone"
                                            type="tel"
                                            value={phone}
                                            onChange={(event) => setPhone(normalisePhone(event.target.value))}
                                            placeholder="59000000"
                                            autoComplete="tel"
                                            inputMode="numeric"
                                            disabled={loading}
                                            className="h-14 w-full border-0 bg-transparent px-0 text-base font-semibold shadow-none outline-none ring-0 placeholder:font-normal placeholder:text-slate-400 focus-visible:ring-0 disabled:cursor-not-allowed disabled:opacity-60"
                                        />
                                    </div>
                                </div>

                                <div className="space-y-2.5">
                                    <div className="flex items-center justify-between gap-2">
                                        <label htmlFor="login-password" className="text-sm font-black text-slate-800">
                                            Password
                                        </label>
                                        <Link
                                            href="/forgot-password"
                                            className="text-xs font-bold text-primary transition-all hover:underline hover:opacity-80"
                                        >
                                            Forgot password?
                                        </Link>
                                    </div>

                                    <div className="group flex min-h-16 items-center rounded-2xl border border-slate-200 bg-slate-50/80 px-4 shadow-sm transition-all duration-200 focus-within:border-primary/60 focus-within:bg-white focus-within:ring-4 focus-within:ring-primary/10">
                                        <div className="mr-3 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                                            <Lock className="h-5 w-5" />
                                        </div>

                                        <Input
                                            id="login-password"
                                            type={showPassword ? "text" : "password"}
                                            value={password}
                                            onChange={(event) => setPassword(event.target.value)}
                                            placeholder="Enter password"
                                            autoComplete="current-password"
                                            disabled={loading}
                                            className="h-14 w-full border-0 bg-transparent px-0 text-base font-semibold shadow-none outline-none ring-0 placeholder:font-normal placeholder:text-slate-400 focus-visible:ring-0 disabled:cursor-not-allowed disabled:opacity-60"
                                        />

                                        <button
                                            type="button"
                                            onClick={() => setShowPassword((current) => !current)}
                                            disabled={loading}
                                            className="ml-3 inline-flex h-10 w-10 items-center justify-center rounded-xl text-slate-500 transition-all hover:bg-primary/10 hover:text-primary disabled:cursor-not-allowed disabled:opacity-60"
                                            aria-label={showPassword ? "Hide password" : "Show password"}
                                        >
                                            {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                                        </button>
                                    </div>
                                </div>

                                <div className="space-y-2.5">
                                    <div className="flex items-center justify-between gap-2">
                                        <label htmlFor="login-second-factor" className="text-sm font-black text-slate-800">
                                            Authenticator or recovery code
                                        </label>
                                        <span className="text-xs font-semibold text-slate-500">Only required when MFA is enabled</span>
                                    </div>
                                    <div className="group flex min-h-16 items-center rounded-2xl border border-slate-200 bg-slate-50/80 px-4 shadow-sm transition-all duration-200 focus-within:border-primary/60 focus-within:bg-white focus-within:ring-4 focus-within:ring-primary/10">
                                        <div className="mr-3 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary"><KeyRound className="h-5 w-5" /></div>
                                        <Input id="login-second-factor" value={secondFactor} onChange={(event) => setSecondFactor(event.target.value.replace(/\s+/g, ""))} placeholder="6-digit code or recovery code" autoComplete="one-time-code" disabled={loading} className="h-14 w-full border-0 bg-transparent px-0 text-base font-semibold tracking-widest shadow-none outline-none ring-0 focus-visible:ring-0" />
                                    </div>
                                </div>

                                <div className="rounded-2xl border border-slate-200/80 bg-slate-50/80 px-4 py-3 text-xs leading-6 text-slate-500">
                                    Use your registered phone number and password. If your password was recently changed, log in again using the new one.
                                </div>

                                <button
                                    type="submit"
                                    disabled={loading || !formReady}
                                    className="group flex h-14 w-full cursor-pointer items-center justify-center gap-2 rounded-2xl bg-primary font-black text-primary-foreground shadow-[0_20px_40px_-22px_rgba(30,97,185,0.85)] transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_22px_46px_-20px_rgba(30,97,185,0.9)] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
                                >
                                    {loading ? (
                                        <>
                                            <Loader2 className="h-5 w-5 animate-spin" />
                                            Logging in...
                                        </>
                                    ) : (
                                        <>
                                            Login to LoanHub
                                            <ArrowRight className="h-5 w-5 transition-transform duration-300 group-hover:translate-x-1" />
                                        </>
                                    )}
                                </button>
                            </form>

                            <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50/85 p-5 text-center shadow-sm">
                                <p className="text-sm text-slate-500">
                                    New to LoanHub?
                                </p>

                                <button
                                    type="button"
                                    onClick={() => router.push("/choose-account-type")}
                                    className="mt-2 cursor-pointer text-sm font-black text-primary transition-all hover:underline hover:opacity-80"
                                >
                                    Create a borrower account
                                </button>
                                <div className="mt-3 border-t border-slate-200 pt-3">
                                    <Link
                                        href="/register-institution"
                                        className="text-sm font-black text-primary transition-all hover:underline hover:opacity-80"
                                    >
                                        Register a bank or lending institution
                                    </Link>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>
            </div>
        </main>
    );
}

function MiniPill({ icon, text }: { icon: ReactNode; text: string }) {
    return (
        <div className="inline-flex items-center gap-2 rounded-full border border-white/80 bg-white/72 px-4 py-3 text-sm font-semibold text-slate-700 shadow-sm backdrop-blur">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary">
                {icon}
            </span>
            {text}
        </div>
    );
}

function InfoCard({ icon, title, text }: { icon: ReactNode; title: string; text: string }) {
    return (
        <div className="flex items-start gap-4 rounded-2xl border border-white/80 bg-white/72 p-4 shadow-sm backdrop-blur">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                {icon}
            </div>

            <div>
                <h3 className="font-black text-slate-900">{title}</h3>
                <p className="mt-1 text-sm leading-6 text-slate-600">{text}</p>
            </div>
        </div>
    );
}
