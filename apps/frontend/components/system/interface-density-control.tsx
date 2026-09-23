"use client";

import { useEffect, useState } from "react";
import { AlignJustify, Rows3 } from "lucide-react";

type InterfaceDensity = "comfortable" | "compact";

const STORAGE_KEY = "loanhub.ui-density";

function applyDensity(value: InterfaceDensity) {
    document.documentElement.dataset.loanhubDensity = value;
    document.documentElement.dataset.loanhubDensityAuto = "false";
    localStorage.setItem(STORAGE_KEY, value);
}

export function InterfaceDensityControl() {
    const [density, setDensity] = useState<InterfaceDensity>("comfortable");

    useEffect(() => {
        const rootDensity = document.documentElement.dataset.loanhubDensity;
        const storedDensity = localStorage.getItem(STORAGE_KEY);
        const resolved = storedDensity === "compact" || storedDensity === "comfortable"
            ? storedDensity
            : rootDensity === "compact"
                ? "compact"
                : "comfortable";
        setDensity(resolved);
    }, []);

    function selectDensity(value: InterfaceDensity) {
        applyDensity(value);
        setDensity(value);
    }

    return (
        <div
            className="inline-flex min-w-0 items-center rounded-xl border bg-background p-1 shadow-sm"
            role="group"
            aria-label="Dashboard density"
        >
            <button
                type="button"
                onClick={() => selectDensity("comfortable")}
                aria-pressed={density === "comfortable"}
                title="Comfortable dashboard density"
                className={`inline-flex h-8 min-w-0 items-center justify-center gap-1.5 rounded-lg px-2.5 text-xs font-bold transition sm:px-3 ${
                    density === "comfortable"
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground"
                }`}
            >
                <Rows3 className="h-3.5 w-3.5 shrink-0" />
                <span className="hidden sm:inline">Comfortable</span>
            </button>
            <button
                type="button"
                onClick={() => selectDensity("compact")}
                aria-pressed={density === "compact"}
                title="Compact dashboard density"
                className={`inline-flex h-8 min-w-0 items-center justify-center gap-1.5 rounded-lg px-2.5 text-xs font-bold transition sm:px-3 ${
                    density === "compact"
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground"
                }`}
            >
                <AlignJustify className="h-3.5 w-3.5 shrink-0" />
                <span className="hidden sm:inline">Compact</span>
            </button>
        </div>
    );
}
