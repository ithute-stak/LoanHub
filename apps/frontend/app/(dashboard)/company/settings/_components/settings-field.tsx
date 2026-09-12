"use client";

import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import type { HTMLInputTypeAttribute } from "react";

type InputProps = {
    label: string;
    name: string;
    value: string;
    onChange: (value: string) => void;
    type?: HTMLInputTypeAttribute;
    inputMode?: "none" | "text" | "tel" | "url" | "email" | "numeric" | "decimal" | "search";
    placeholder?: string;
    hint?: string;
    error?: string;
    required?: boolean;
    disabled?: boolean;
    autoComplete?: string;
    className?: string;
};

export function SettingsInput({
    label,
    name,
    value,
    onChange,
    type = "text",
    inputMode,
    placeholder,
    hint,
    error,
    required = false,
    disabled = false,
    autoComplete,
    className = "",
}: InputProps) {
    return (
        <label htmlFor={name} className={`block ${className}`}>
            <span className="mb-2 flex items-center gap-1 text-sm font-black">
                {label}
                {required && <span className="text-red-500" aria-hidden="true">*</span>}
            </span>
            <Input
                id={name}
                name={name}
                type={type}
                inputMode={inputMode}
                value={value}
                onChange={(event) => onChange(event.target.value)}
                placeholder={placeholder}
                autoComplete={autoComplete}
                required={required}
                disabled={disabled}
                aria-invalid={Boolean(error)}
                className={`h-12 w-full rounded-xl border bg-background px-4 text-sm outline-none transition placeholder:text-muted-foreground/70 focus:ring-2 disabled:cursor-not-allowed disabled:bg-muted/50 disabled:opacity-70 ${error ? "border-red-500 focus:border-red-500 focus:ring-red-500/20" : "focus:border-primary focus:ring-primary/20"}`}
            />
            {hint && !error && <p className="mt-1.5 text-xs leading-5 text-muted-foreground">{hint}</p>}
            {error && <p className="mt-1.5 text-xs font-semibold text-red-600 dark:text-red-400">{error}</p>}
        </label>
    );
}

type SelectProps = {
    label: string;
    name: string;
    value: string;
    options: readonly string[];
    onChange: (value: string) => void;
    error?: string;
    required?: boolean;
    disabled?: boolean;
};

export function SettingsSelect({ label, name, value, options, onChange, error, required = false, disabled = false }: SelectProps) {
    return (
        <label htmlFor={name} className="block">
            <span className="mb-2 flex items-center gap-1 text-sm font-black">
                {label}
                {required && <span className="text-red-500">*</span>}
            </span>
            <NativeSelect
                id={name}
                name={name}
                value={value}
                onChange={(event) => onChange(event.target.value)}
                required={required}
                disabled={disabled}
                aria-invalid={Boolean(error)}
                className={`h-12 w-full rounded-xl border bg-background px-4 text-sm outline-none transition focus:ring-2 disabled:cursor-not-allowed disabled:bg-muted/50 disabled:opacity-70 ${error ? "border-red-500 focus:ring-red-500/20" : "focus:border-primary focus:ring-primary/20"}`}
            >
                <option value="">Select a district</option>
                {options.map((option) => <option key={option} value={option}>{option}</option>)}
            </NativeSelect>
            {error && <p className="mt-1.5 text-xs font-semibold text-red-600 dark:text-red-400">{error}</p>}
        </label>
    );
}
