"use client";

import { useMemo, useState } from "react";
import { toast } from "@/utils/toast";

import { useAppData } from "@/provider/appDataProvider";
import type {
    SubscriptionPlan,
    SubscriptionPlanCreatePayload,
    SubscriptionPlanUpdatePayload,
} from "@/types/billing";
import { getErrorMessage } from "@/utils/apiError";

import type {
    PlanActivityFilter,
    PlanEditorState,
    PlanPageStats,
    PlanVisibilityFilter,
} from "../_types/plan-page";

export function usePlansPage() {
    const {
        subscriptionPlans,
        subscriptions,
        isBillingLoading,
        errors,
        refreshBilling,
        createSubscriptionPlan,
        updateSubscriptionPlan,
        deleteSubscriptionPlan,
    } = useAppData();

    const [search, setSearch] = useState("");
    const [activityFilter, setActivityFilter] = useState<PlanActivityFilter>("all");
    const [visibilityFilter, setVisibilityFilter] = useState<PlanVisibilityFilter>("all");
    const [editor, setEditor] = useState<PlanEditorState | null>(null);
    const [planToDelete, setPlanToDelete] = useState<SubscriptionPlan | null>(null);
    const [saving, setSaving] = useState(false);
    const [deleting, setDeleting] = useState(false);

    const subscriptionCounts = useMemo(() => {
        const counts = new Map<string, number>();
        for (const subscription of subscriptions) {
            if (!subscription.plan_id) continue;
            counts.set(subscription.plan_id, (counts.get(subscription.plan_id) ?? 0) + 1);
        }
        return counts;
    }, [subscriptions]);

    const stats = useMemo<PlanPageStats>(() => {
        const activeSubscriptions = subscriptions.filter((item) => item.status === "active");
        const transactionFees = subscriptionPlans.map((plan) => Number(plan.transaction_fee_percent));
        return {
            totalPlans: subscriptionPlans.length,
            activePlans: subscriptionPlans.filter((plan) => plan.is_active).length,
            publicPlans: subscriptionPlans.filter((plan) => plan.is_public).length,
            freePlans: subscriptionPlans.filter((plan) => Number(plan.monthly_price) === 0 && Number(plan.annual_price) === 0).length,
            payPerUnlockPlans: subscriptionPlans.filter((plan) => Number(plan.marketplace_unlock_fee) > 0).length,
            activeSubscriptions: activeSubscriptions.length,
            subscriptionValue: activeSubscriptions.reduce((sum, item) => sum + Number(item.amount), 0),
            averageTransactionFee: transactionFees.length > 0
                ? transactionFees.reduce((sum, value) => sum + value, 0) / transactionFees.length
                : 0,
        };
    }, [subscriptionPlans, subscriptions]);

    const filteredPlans = useMemo(() => {
        const query = search.trim().toLowerCase();
        return subscriptionPlans.filter((plan) => {
            const matchesSearch = !query || [plan.name, plan.code, plan.description]
                .some((value) => String(value ?? "").toLowerCase().includes(query));
            const matchesActivity = activityFilter === "all" ||
                (activityFilter === "active" && plan.is_active) ||
                (activityFilter === "inactive" && !plan.is_active);
            const matchesVisibility = visibilityFilter === "all" ||
                (visibilityFilter === "public" && plan.is_public) ||
                (visibilityFilter === "private" && !plan.is_public);
            return matchesSearch && matchesActivity && matchesVisibility;
        });
    }, [activityFilter, search, subscriptionPlans, visibilityFilter]);

    async function submitPlan(
        payload: SubscriptionPlanCreatePayload | SubscriptionPlanUpdatePayload,
    ) {
        if (!editor) return;
        setSaving(true);
        try {
            if (editor.mode === "create") {
                await createSubscriptionPlan(payload as SubscriptionPlanCreatePayload);
                toast.success("Subscription plan created");
            } else if (editor.plan) {
                await updateSubscriptionPlan(editor.plan.id, payload as SubscriptionPlanUpdatePayload);
                toast.success("Subscription plan updated");
            }
            setEditor(null);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Unable to save subscription plan"));
        } finally {
            setSaving(false);
        }
    }

    async function confirmDelete() {
        if (!planToDelete) return;
        setDeleting(true);
        try {
            await deleteSubscriptionPlan(planToDelete.id);
            toast.success("Subscription plan deleted");
            setPlanToDelete(null);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Unable to delete subscription plan"));
        } finally {
            setDeleting(false);
        }
    }

    return {
        plans: filteredPlans,
        allPlans: subscriptionPlans,
        subscriptions,
        stats,
        subscriptionCounts,
        loading: isBillingLoading,
        error: errors.billing,
        search,
        activityFilter,
        visibilityFilter,
        editor,
        planToDelete,
        saving,
        deleting,
        setSearch,
        setActivityFilter,
        setVisibilityFilter,
        openCreate: () => setEditor({ mode: "create", plan: null }),
        openEdit: (plan: SubscriptionPlan) => setEditor({ mode: "edit", plan }),
        closeEditor: () => {
            if (!saving) setEditor(null);
        },
        setPlanToDelete,
        submitPlan,
        confirmDelete,
        refreshBilling,
    };
}
