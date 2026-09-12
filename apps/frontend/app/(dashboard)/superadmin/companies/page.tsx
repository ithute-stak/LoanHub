"use client";

import {
    CompaniesOverview,
} from "./_components/companies-overview";

import {
    CompaniesTable,
} from "./_components/companies-table";

import {
    CompanyDeleteDialog,
} from "./_components/company-delete-dialog";

import { CompanyEditDialog } from "./_components/company-edit-dialog";
import { CompanyOwnerAccessDialog } from "./_components/company-owner-access-dialog";

import {
    useCompaniesPage,
} from "./_hooks/use-companies-page";

export default function AllCompaniesPage() {
    const {
        overview,
        table,
        editDialog,
        ownerAccessDialog,
        deleteDialog,
    } = useCompaniesPage();

    return (
        <main className="space-y-6">
            <CompaniesOverview
                {...overview}
            />

            <CompaniesTable
                {...table}
            />

            <CompanyDeleteDialog
                {...deleteDialog}
            />

            <CompanyEditDialog
                {...editDialog}
            />

            <CompanyOwnerAccessDialog
                {...ownerAccessDialog}
            />
        </main>
    );
}
