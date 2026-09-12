"use client";

import { Printer } from "lucide-react";

export function PrintManualButton() {
    return (
        <button
            type="button"
            onClick={() => window.print()}
            className="inline-flex items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white px-5 py-3 text-sm font-black text-slate-900 shadow-sm transition hover:border-emerald-300 hover:bg-emerald-50 dark:border-slate-700 dark:bg-slate-900 dark:text-white dark:hover:border-emerald-800 dark:hover:bg-emerald-950/40 print:hidden"
        >
            <Printer className="h-4 w-4" />
            Print / save as PDF
        </button>
    );
}
