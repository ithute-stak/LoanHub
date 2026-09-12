import type { SubscriptionPlan } from "@/types/billing";

export type PlanVisibilityFilter = "all" | "public" | "private";
export type PlanActivityFilter = "all" | "active" | "inactive";
export type PlanEditorMode = "create" | "edit";

export type PlanEditorState = {
    mode: PlanEditorMode;
    plan: SubscriptionPlan | null;
};

export type PlanPageStats = {
    totalPlans: number;
    activePlans: number;
    publicPlans: number;
    freePlans: number;
    payPerUnlockPlans: number;
    activeSubscriptions: number;
    subscriptionValue: number;
    averageTransactionFee: number;
};
