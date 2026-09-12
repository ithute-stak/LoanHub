"use client";

import {
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
    CompaniesPageModel,
} from "../_hooks/use-companies-page";

type Props =
    CompaniesPageModel["deleteDialog"];

export function CompanyDeleteDialog({
                                        company,
                                        isDeleting,
                                        onOpenChange,
                                        onConfirm,
                                    }: Props) {
    return (
        <AlertDialog
            open={Boolean(company)}
            onOpenChange={onOpenChange}
        >
            <AlertDialogContent className="rounded-3xl">
                <AlertDialogHeader>
                    <AlertDialogTitle>
                        Delete company?
                    </AlertDialogTitle>

                    <AlertDialogDescription>
                        You are about to delete{" "}
                        <strong>
                            {company?.name}
                        </strong>
                        . This may affect branches,
                        staff assignments and other
                        connected records.
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
                                Delete company
                            </>
                        )}
                    </AlertDialogAction>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    );
}