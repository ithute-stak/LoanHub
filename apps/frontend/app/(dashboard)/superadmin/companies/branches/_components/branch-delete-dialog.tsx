"use client";

import {
    AlertTriangle,
    Loader2,
    Trash2,
} from "lucide-react";

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

import type {
    BranchesPageModel,
} from "../_hooks/use-branches-page";

type Props =
    BranchesPageModel["deleteDialog"];

export function BranchDeleteDialog({
    branch,
    companyName,
    isDeleting,
    onOpenChange,
    onConfirm,
}: Props) {
    return (
        <AlertDialog
            open={Boolean(branch)}
            onOpenChange={
                onOpenChange
            }
        >
            <AlertDialogContent className="rounded-3xl">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-red-100 text-red-600 dark:bg-red-950/40 dark:text-red-400">
                    <AlertTriangle className="h-6 w-6" />
                </div>

                <AlertDialogHeader>
                    <AlertDialogTitle>
                        Delete branch?
                    </AlertDialogTitle>

                    <AlertDialogDescription>
                        You are about to delete{" "}
                        <strong>
                            {branch?.name}
                        </strong>{" "}
                        from{" "}
                        <strong>
                            {companyName}
                        </strong>
                        . Staff assignments and records
                        connected to this branch may also be
                        affected.
                    </AlertDialogDescription>
                </AlertDialogHeader>

                <AlertDialogFooter>
                    <AlertDialogCancel
                        disabled={isDeleting}
                    >
                        Cancel
                    </AlertDialogCancel>

                    <AlertDialogAction
                        onClick={(event) => {
                            event.preventDefault();
                            void onConfirm();
                        }}
                        disabled={isDeleting}
                        className="bg-red-600 text-white hover:bg-red-700"
                    >
                        {isDeleting ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                Deleting...
                            </>
                        ) : (
                            <>
                                <Trash2 className="mr-2 h-4 w-4" />
                                Delete branch
                            </>
                        )}
                    </AlertDialogAction>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    );
}
