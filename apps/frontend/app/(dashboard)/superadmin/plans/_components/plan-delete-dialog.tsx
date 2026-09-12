"use client";

import { Loader2, Trash2 } from "lucide-react";

import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import type { SubscriptionPlan } from "@/types/billing";

type Props = {
    plan: SubscriptionPlan | null;
    subscriptionCount: number;
    deleting: boolean;
    onOpenChange: (open: boolean) => void;
    onConfirm: () => Promise<void>;
};

export function PlanDeleteDialog({
    plan,
    subscriptionCount,
    deleting,
    onOpenChange,
    onConfirm,
}: Props) {
    const protectedPlan = plan?.code === "STARTER";
    const inUse = subscriptionCount > 0;
    const blocked = protectedPlan || inUse;

    return (
        <AlertDialog open={Boolean(plan)} onOpenChange={onOpenChange}>
            <AlertDialogContent className="rounded-3xl">
                <AlertDialogHeader>
                    <AlertDialogTitle>Delete pricing plan?</AlertDialogTitle>
                    <AlertDialogDescription>
                        {protectedPlan
                            ? "STARTER is LoanHub's fallback configuration and cannot be deleted."
                            : inUse
                              ? `${plan?.name ?? "This plan"} is referenced by ${subscriptionCount} subscription record(s). Make it inactive and private instead.`
                              : `Delete ${plan?.name ?? "this plan"}? This action cannot be undone.`}
                    </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                    <AlertDialogCancel disabled={deleting}>Close</AlertDialogCancel>
                    {!blocked && (
                        <AlertDialogAction
                            onClick={(event) => {
                                event.preventDefault();
                                void onConfirm();
                            }}
                            disabled={deleting}
                            className="bg-red-600 text-white hover:bg-red-700"
                        >
                            {deleting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Trash2 className="mr-2 h-4 w-4" />}
                            {deleting ? "Deleting..." : "Delete plan"}
                        </AlertDialogAction>
                    )}
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    );
}
