"use client";

import { Check, ReceiptText, ShieldCheck, Sparkles } from "lucide-react";
import { FormEvent, useState } from "react";

import { LoadingButton } from "@/components/ui/loading-button";
import { DEFAULT_PAYMENT_METHOD_OPTIONS, EMPTY_PAYMENT_EVIDENCE, PaymentMethodFields, type PaymentEvidence } from "@/components/payments/payment-method-fields";
import { Button } from "@/components/ui/button";
import { CustomDialog } from "@/components/ui/custom-dialog";
import { DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatDate, formatMoney } from "@/lib/format";
import { useAppData } from "@/provider/appDataProvider";
import { useTenant } from "@/provider/tenantProvider";
import { COMPANY_MANAGEMENT_ROLES, hasRole } from "@/types/auth";
import type { BillingCycle, SubscriptionPlan } from "@/types/billing";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

export default function CompanyBillingPage() {
    const {
        subscriptionPlans,
        currentSubscription,
        checkoutSubscription,
        cancelSubscription,
        isBillingLoading,
    } = useAppData();
    const { activeRole } = useTenant();
    const [selectedPlan, setSelectedPlan] = useState<SubscriptionPlan | null>(null);
    const [cycle, setCycle] = useState<BillingCycle>("monthly");
    const [autoRenew, setAutoRenew] = useState(false);
    const [paymentEvidence, setPaymentEvidence] = useState<PaymentEvidence>(EMPTY_PAYMENT_EVIDENCE);
    const [submitting, setSubmitting] = useState(false);
    const [cancelling, setCancelling] = useState(false);
    const canManage = hasRole(activeRole, COMPANY_MANAGEMENT_ROLES);

    async function handleCheckout(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!selectedPlan) return;
        setSubmitting(true);
        try {
            const result = await checkoutSubscription({
                plan_id: selectedPlan.id,
                billing_cycle: cycle,
                payment_method: paymentEvidence.payment_method,
                proof_reference: paymentEvidence.proof_reference.trim() || null,
                proof_url: paymentEvidence.proof_url.trim() || null,
                proof_notes: paymentEvidence.proof_notes.trim() || null,
                auto_renew: autoRenew,
            });
            toast.success(
                result.payment
                    ? `Subscription payment recorded: ${result.payment.provider_reference ?? result.payment.id}`
                    : "Subscription activated successfully",
            );
            setPaymentEvidence(EMPTY_PAYMENT_EVIDENCE);
            setSelectedPlan(null);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not activate the subscription"));
        } finally {
            setSubmitting(false);
        }
    }

    async function handleCancel() {
        if (!currentSubscription) return;
        setCancelling(true);
        try {
            await cancelSubscription(currentSubscription.id);
            toast.success("Subscription cancelled");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not cancel the subscription"));
        } finally {
            setCancelling(false);
        }
    }

    return (
        <div className="loanhub-page space-y-6">
            <section className="loanhub-hero">
                <div className="relative z-10 max-w-3xl">
                    <p className="text-xs font-black uppercase tracking-[0.24em] text-white/70">Company subscription</p>
                    <h1 className="mt-3 text-3xl font-black text-white sm:text-4xl">Choose the LoanHub plan that fits your operation</h1>
                    <p className="mt-3 text-sm leading-6 text-white/75">
                        Paid plans may be settled through any recognised payment channel. LoanHub records the selected method, proof, receipt, accounting entry and headquarters money register together.
                    </p>
                </div>
            </section>

            {currentSubscription && (
                <section className="loanhub-panel flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                        <div className="flex items-center gap-2">
                            <ShieldCheck className="h-5 w-5 text-primary" />
                            <h2 className="font-black">{currentSubscription.plan_name}</h2>
                            <StatusBadge value={currentSubscription.status} />
                        </div>
                        <p className="mt-2 text-sm text-muted-foreground">
                            Active period: {formatDate(currentSubscription.start_date)} – {formatDate(currentSubscription.end_date)}
                        </p>
                    </div>
                    {canManage && currentSubscription.status === "active" && (
                        <LoadingButton variant="outline" loading={cancelling} onClick={handleCancel}>
                            Cancel subscription
                        </LoadingButton>
                    )}
                </section>
            )}

            <section className="grid gap-5 lg:grid-cols-3">
                {subscriptionPlans.map((plan) => (
                    <article
                        key={plan.id}
                        className={`loanhub-panel relative flex flex-col p-6 ${
                            currentSubscription?.plan_id === plan.id ? "border-primary ring-2 ring-primary/15" : ""
                        }`}
                    >
                        {currentSubscription?.plan_id === plan.id && (
                            <span className="absolute right-4 top-4 rounded-full bg-primary px-3 py-1 text-xs font-black text-primary-foreground">
                                Current plan
                            </span>
                        )}
                        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/20 to-cyan-500/10 text-primary">
                            <Sparkles className="h-6 w-6" />
                        </div>
                        <h3 className="mt-5 text-2xl font-black">{plan.name}</h3>
                        <p className="mt-2 min-h-12 text-sm leading-6 text-muted-foreground">
                            {plan.description ?? "Flexible LoanHub access for growing lenders."}
                        </p>
                        <div className="mt-5 grid grid-cols-2 gap-3">
                            <Price label="Monthly" value={formatMoney(plan.monthly_price)} />
                            <Price label="Annual" value={formatMoney(plan.annual_price)} />
                        </div>
                        <div className="mt-5 space-y-3 text-sm">
                            <Feature text={`Marketplace unlock: ${formatMoney(plan.marketplace_unlock_fee)}`} />
                            <Feature text={`Transaction fee: ${plan.transaction_fee_percent}%`} />
                            {Object.keys(plan.features).slice(0, 4).map((feature) => (
                                <Feature key={feature} text={feature.replaceAll("_", " ")} />
                            ))}
                        </div>
                        <Button
                            type="button"
                            onClick={() => setSelectedPlan(plan)}
                            disabled={!canManage || currentSubscription?.plan_id === plan.id}
                            className="mt-6"
                        >
                            {canManage ? "Choose this plan" : "Owner/admin permission required"}
                        </Button>
                    </article>
                ))}
            </section>

            <CustomDialog
                open={Boolean(selectedPlan)}
                onOpenChange={(open) => !open && !submitting && setSelectedPlan(null)}
                title={`Activate ${selectedPlan?.name ?? "subscription plan"}`}
                description="Confirm the cycle, payment channel and supporting evidence before activating the plan."
                contentClassName="sm:max-w-lg"
            >
                <form onSubmit={handleCheckout} className="space-y-6 p-6 sm:p-8">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary"><ReceiptText className="h-5 w-5" /></div>
                    <div className="space-y-5">
                            <div className="space-y-2">
                                <Label htmlFor="billing-cycle">Billing cycle</Label>
                                <Select value={cycle} onValueChange={(value) => setCycle(value as BillingCycle)}>
                                    <SelectTrigger id="billing-cycle"><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="monthly">Monthly · {formatMoney(selectedPlan?.monthly_price ?? 0)}</SelectItem>
                                        <SelectItem value="annual">Annual · {formatMoney(selectedPlan?.annual_price ?? 0)}</SelectItem>
                                        <SelectItem value="pay_per_transaction">Pay per transaction</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>

                            <PaymentMethodFields
                                methods={DEFAULT_PAYMENT_METHOD_OPTIONS}
                                value={paymentEvidence}
                                onChange={setPaymentEvidence}
                            />

                            <div className="flex items-center justify-between gap-4 rounded-2xl border p-4">
                                <div>
                                    <Label htmlFor="auto-renew">Renewal reminder</Label>
                                    <p className="mt-1 text-xs text-muted-foreground">Keep the subscription marked for renewal; every renewal still requires a newly verified payment record.</p>
                                </div>
                                <Switch id="auto-renew" checked={autoRenew} onCheckedChange={setAutoRenew} />
                            </div>
                    </div>

                    <DialogFooter className="mx-0 mb-0">
                        <Button type="button" variant="outline" onClick={() => setSelectedPlan(null)} disabled={submitting}>
                            Cancel
                        </Button>
                        <LoadingButton type="submit" loading={submitting || isBillingLoading}>
                            Record payment and activate
                        </LoadingButton>
                    </DialogFooter>
                </form>
            </CustomDialog>
        </div>
    );
}

function Price({ label, value }: { label: string; value: string }) {
    return <div className="rounded-2xl bg-muted/50 p-3"><p className="text-xs font-bold text-muted-foreground">{label}</p><p className="mt-1 font-black">{value}</p></div>;
}

function Feature({ text }: { text: string }) {
    return <div className="flex items-center gap-2 capitalize"><Check className="h-4 w-4 text-emerald-600" />{text}</div>;
}
