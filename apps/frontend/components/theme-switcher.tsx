"use client";

import { Laptop, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";
import { Button } from "@/components/ui/button";

const options = [
    { value: "light", label: "Light", icon: Sun },
    { value: "dark", label: "Dark", icon: Moon },
    { value: "system", label: "System", icon: Laptop },
] as const;

export function ThemeSwitcher({ compact = true }: { compact?: boolean }) {
    const { theme, setTheme } = useTheme();
    const mounted = useSyncExternalStore(
        () => () => undefined,
        () => true,
        () => false,
    );
    if (!mounted) return <div className="h-10 w-10" aria-hidden />;
    if (compact) {
        const currentIndex = Math.max(0, options.findIndex((item) => item.value === theme));
        const next = options[(currentIndex + 1) % options.length];
        const CurrentIcon = options[currentIndex]?.icon ?? Laptop;
        return (
            <Button type="button" variant="outline" size="icon-lg" onClick={() => setTheme(next.value)} title={`Theme: ${theme ?? "system"}. Switch to ${next.label}`} aria-label={`Switch to ${next.label} theme`} className="h-10 w-10 rounded-xl">
                <CurrentIcon className="h-5 w-5" />
            </Button>
        );
    }
    return (
        <div className="grid grid-cols-3 gap-2 rounded-2xl border p-2">
            {options.map(({ value, label, icon: Icon }) => (
                <Button key={value} type="button" variant={theme === value ? "default" : "ghost"} onClick={() => setTheme(value)} className="rounded-xl px-3 py-2 text-xs font-black">
                    <Icon className="h-4 w-4" />{label}
                </Button>
            ))}
        </div>
    );
}
