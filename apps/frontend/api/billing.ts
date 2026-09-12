import { api } from "@/lib/api";
import type {
    CompanySubscription,
    SubscriptionCheckoutPayload,
    SubscriptionCheckoutResponse,
    SubscriptionPlan,
    SubscriptionPlanCreatePayload,
    SubscriptionPlanUpdatePayload,
} from "@/types/billing";

export async function listSubscriptionPlans(): Promise<SubscriptionPlan[]> {
    const response = await api.get<SubscriptionPlan[]>("/billing/plans");
    return response.data;
}

export async function listAdminSubscriptionPlans(): Promise<SubscriptionPlan[]> {
    const response = await api.get<SubscriptionPlan[]>("/billing/plans/admin");
    return response.data;
}

export async function createSubscriptionPlan(
    payload: SubscriptionPlanCreatePayload,
): Promise<SubscriptionPlan> {
    const response = await api.post<SubscriptionPlan>("/billing/plans", payload);
    return response.data;
}

export async function updateSubscriptionPlan(
    planId: string,
    payload: SubscriptionPlanUpdatePayload,
): Promise<SubscriptionPlan> {
    const response = await api.put<SubscriptionPlan>(
        `/billing/plans/${planId}`,
        payload,
    );
    return response.data;
}

export async function deleteSubscriptionPlan(planId: string): Promise<void> {
    await api.delete(`/billing/plans/${planId}`);
}

export async function listSubscriptions(): Promise<CompanySubscription[]> {
    const response = await api.get<CompanySubscription[]>("/billing/subscriptions", {
        params: { limit: 500 },
    });
    return response.data;
}

export async function getCurrentSubscription(): Promise<CompanySubscription | null> {
    const response = await api.get<CompanySubscription | null>(
        "/billing/subscriptions/current",
    );
    return response.data;
}

export async function checkoutSubscription(
    payload: SubscriptionCheckoutPayload,
): Promise<SubscriptionCheckoutResponse> {
    const response = await api.post<SubscriptionCheckoutResponse>(
        "/billing/subscriptions/checkout",
        payload,
    );
    return response.data;
}

export async function cancelSubscription(
    subscriptionId: string,
): Promise<CompanySubscription> {
    const response = await api.post<CompanySubscription>(
        `/billing/subscriptions/${subscriptionId}/cancel`,
    );
    return response.data;
}
