import Link from "next/link";
import {
    ArrowRight,
    CheckCircle2,
    Clock3,
    MailCheck,
    ShieldCheck,
} from "lucide-react";

export function RegistrationSuccess() {
    return (
        <main className="flex min-h-screen items-center justify-center bg-muted/20 p-4 sm:p-8">
            <section className="w-full max-w-2xl overflow-hidden rounded-3xl border bg-card shadow-2xl">
                <div className="bg-gradient-to-br from-emerald-500/15 via-background to-primary/10 p-8 text-center sm:p-10">
                    <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-emerald-100 text-emerald-700 shadow-lg dark:bg-emerald-950/50 dark:text-emerald-400">
                        <CheckCircle2 className="h-10 w-10" />
                    </div>

                    <h1 className="mt-6 text-3xl font-black tracking-tight sm:text-4xl">
                        Application submitted
                    </h1>

                    <p className="mx-auto mt-3 max-w-xl text-sm leading-7 text-muted-foreground">
                        The company and owner account
                        were created successfully. The
                        company remains pending until
                        LoanHub completes verification.
                    </p>
                </div>

                <div className="grid gap-3 border-t p-6 sm:grid-cols-3 sm:p-8">
                    {[
                        {
                            icon: MailCheck,
                            title: "Account created",
                            text: "Use the owner phone or email to sign in.",
                        },
                        {
                            icon: ShieldCheck,
                            title: "Verification",
                            text: "LoanHub reviews the company application.",
                        },
                        {
                            icon: Clock3,
                            title: "Activation",
                            text: "Lending tools open after approval.",
                        },
                    ].map(
                        ({
                            icon: Icon,
                            title,
                            text,
                        }) => (
                            <div
                                key={title}
                                className="rounded-2xl border bg-muted/20 p-4"
                            >
                                <Icon className="h-5 w-5 text-primary" />

                                <p className="mt-3 text-sm font-black">
                                    {title}
                                </p>

                                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                                    {text}
                                </p>
                            </div>
                        ),
                    )}
                </div>

                <div className="border-t p-6 sm:p-8">
                    <Link
                        href="/login"
                        className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-primary px-5 text-sm font-black text-primary-foreground transition hover:bg-primary/90"
                    >
                        Continue to login
                        <ArrowRight className="h-4 w-4" />
                    </Link>
                </div>
            </section>
        </main>
    );
}
