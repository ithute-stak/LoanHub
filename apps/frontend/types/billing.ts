import type { PaymentProvider, PaymentTransaction } from "@/types/payment";
import type { PaymentMethod } from "@/types/expenseManagement";

export type BillingCycle = "monthly" | "annual" | "pay_per_transaction";
export type SubscriptionStatus = "active" | "expired" | "cancelled" | "pending" | "suspended";

export type SubscriptionPlanFeatures = {
    marketplace_full_access: boolean;
    advanced_analytics: boolean;
    custom_branding: boolean;
    api_access: boolean;
    priority_support: boolean;
    audit_exports: boolean;
    [key: string]: boolean | string | number | null | undefined;
};

export type SubscriptionPlanLimits = {
    branches: number;
    staff: number;
    products: number;
    [key: string]: number | string | boolean | null | undefined;
};

export type SubscriptionPlan = {
    id: string;
    code: string;
    name: string;
    description: string | null;
    monthly_price: number;
    annual_price: number;
    marketplace_unlock_fee: number;
    transaction_fee_percent: number;
    features: SubscriptionPlanFeatures;
    limits: SubscriptionPlanLimits;
    is_active: boolean;
    is_public: boolean;
    created_at: string;
    updated_at: string;
};

export type SubscriptionPlanCreatePayload = {
    code: string;
    name: string;
    description: string | null;
    monthly_price: number;
    annual_price: number;
    marketplace_unlock_fee: number;
    transaction_fee_percent: number;
    features: SubscriptionPlanFeatures;
    limits: SubscriptionPlanLimits;
    is_active: boolean;
    is_public: boolean;
};

export type SubscriptionPlanUpdatePayload = Omit<
    SubscriptionPlanCreatePayload,
    "code"
>;

export type CompanySubscription = {
    id: string;
    company_id: string;
    plan_id: string | null;
    plan_name: string;
    amount: number;
    start_date: string;
    end_date: string;
    billing_cycle: BillingCycle;
    status: SubscriptionStatus;
    auto_renew: boolean;
    payment_provider: PaymentProvider | null;
    external_reference: string | null;
    created_at: string;
    updated_at: string;
    plan: SubscriptionPlan | null;
};

export type SubscriptionCheckoutPayload = {
    plan_id: string;
    billing_cycle: BillingCycle;
    payment_method: PaymentMethod;
    proof_reference?: string | null;
    proof_url?: string | null;
    proof_notes?: string | null;
    auto_renew: boolean;
};

export type SubscriptionCheckoutResponse = {
    subscription: CompanySubscription;
    payment: PaymentTransaction | null;
};
