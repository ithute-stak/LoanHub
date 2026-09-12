"use client";

import {
    BranchAnalytics,
} from "./_components/branch-analytics";
import {
    BranchDeleteDialog,
} from "./_components/branch-delete-dialog";
import {
    BranchFormDialog,
} from "./_components/branch-form-dialog";
import {
    BranchTable,
} from "./_components/branch-table";
import {
    BranchViewDialog,
} from "./_components/branch-view-dialog";
import {
    BranchesHeader,
} from "./_components/branches-header";
import {
    useBranchesPage,
} from "./_hooks/use-branches-page";

export default function BranchesPage() {
    const {
        header,
        overview,
        table,
        formDialog,
        viewDialog,
        deleteDialog,
    } = useBranchesPage();

    return (
        <main className="space-y-6">
            <BranchesHeader
                {...header}
            />

            <BranchAnalytics
                {...overview}
            />

            <BranchTable
                {...table}
            />

            <BranchFormDialog
                {...formDialog}
            />

            <BranchViewDialog
                {...viewDialog}
            />

            <BranchDeleteDialog
                {...deleteDialog}
            />
        </main>
    );
}
