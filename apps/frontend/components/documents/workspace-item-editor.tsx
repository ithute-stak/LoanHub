"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft, Laptop2, Loader2 } from "lucide-react";

import { getWorkspaceDocument } from "@/api/workspaceDocuments";
import { RichLetterEditor } from "@/components/documents/rich-letter-editor";
import { SpreadsheetEditor } from "@/components/documents/spreadsheet-editor";
import { isSpreadsheetDocument } from "@/types/workspaceSpreadsheets";
import type { WorkspaceDocument } from "@/types/workspaceDocuments";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

type StudioMode = "company" | "borrower" | "superadmin" | "platform";

export function WorkspaceItemEditor({
    documentId,
    basePath,
    mode,
}: {
    documentId: string;
    basePath: string;
    mode: StudioMode;
}) {
    const [document, setDocument] = useState<WorkspaceDocument | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        getWorkspaceDocument(documentId)
            .then((value) => {
                if (!cancelled) setDocument(value);
            })
            .catch((error: unknown) => {
                if (!cancelled) toast.error(getErrorMessage(error, "Could not open this workspace item."));
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [documentId]);

    if (loading) {
        return <div className="flex min-h-[60vh] items-center justify-center"><Loader2 className="h-7 w-7 animate-spin text-primary" /></div>;
    }
    if (!document) {
        return <div className="rounded-3xl border bg-card p-8 text-center text-sm text-muted-foreground">Workspace item unavailable.</div>;
    }
    if (isSpreadsheetDocument(document)) {
        return <SpreadsheetEditor documentId={documentId} basePath={basePath} />;
    }
    return (
        <>
            <div className="hidden md:block">
                <RichLetterEditor documentId={documentId} basePath={basePath} mode={mode} />
            </div>
            <main className="flex min-h-[70dvh] items-center justify-center p-5 md:hidden">
                <section className="w-full max-w-md rounded-3xl border bg-card p-7 text-center shadow-sm">
                    <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                        <Laptop2 className="h-7 w-7" />
                    </div>
                    <h1 className="mt-5 text-xl font-black">Document Studio uses a larger workspace</h1>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">
                        For reliable page layout, tables, signatures and print-accurate editing, open this document on a tablet, laptop or desktop. Spreadsheet Studio remains available on smaller screens.
                    </p>
                    <Link href={basePath} className="mt-6 inline-flex h-10 items-center gap-2 rounded-xl border px-4 text-sm font-black hover:border-primary hover:text-primary">
                        <ArrowLeft className="h-4 w-4" /> Back to documents
                    </Link>
                </section>
            </main>
        </>
    );
}
