"use client";


import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import {
    Eye,
    EyeOff,
} from "lucide-react";
import {
    type HTMLInputTypeAttribute,
    useState,
} from "react";

type BaseProps = {
    label: string;
    name: string;
    error?: string;
    hint?: string;
    required?: boolean;
};

type TextFieldProps = BaseProps & {
    value: string;
    onChange: (value: string) => void;
    type?: HTMLInputTypeAttribute;
    placeholder?: string;
    autoComplete?: string;
    minLength?: number;
};

export function TextField({
    label,
    name,
    value,
    onChange,
    type = "text",
    placeholder,
    autoComplete,
    error,
    hint,
    required = false,
    minLength,
}: TextFieldProps) {
    const [showPassword, setShowPassword] =
        useState(false);

    const isPassword =
        type === "password";

    const inputType =
        isPassword && showPassword
            ? "text"
            : type;

    const describedBy = [
        hint ? `${name}-hint` : "",
        error ? `${name}-error` : "",
    ]
        .filter(Boolean)
        .join(" ");

    return (
        <label
            htmlFor={name}
            className="block"
        >
            <span className="mb-2 flex items-center gap-1 text-sm font-bold text-foreground">
                {label}

                {required && (
                    <span
                        className="text-red-500"
                        aria-hidden="true"
                    >
                        *
                    </span>
                )}
            </span>

            <div className="relative">
                <Input
                    id={name}
                    name={name}
                    type={inputType}
                    required={required}
                    minLength={minLength}
                    value={value}
                    autoComplete={autoComplete}
                    placeholder={placeholder}
                    aria-invalid={Boolean(error)}
                    aria-describedby={
                        describedBy || undefined
                    }
                    onChange={(event) =>
                        onChange(
                            event.target.value,
                        )
                    }
                    className={`h-12 w-full rounded-xl border bg-background px-4 text-sm outline-none transition placeholder:text-muted-foreground/70 focus:ring-2 ${
                        error
                            ? "border-red-500 focus:border-red-500 focus:ring-red-500/20"
                            : "focus:border-primary focus:ring-primary/20"
                    } ${
                        isPassword
                            ? "pr-12"
                            : ""
                    }`}
                />

                {isPassword && (
                    <button
                        type="button"
                        onClick={() =>
                            setShowPassword(
                                (current) =>
                                    !current,
                            )
                        }
                        className="absolute right-3 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground"
                        aria-label={
                            showPassword
                                ? "Hide password"
                                : "Show password"
                        }
                    >
                        {showPassword ? (
                            <EyeOff className="h-4 w-4" />
                        ) : (
                            <Eye className="h-4 w-4" />
                        )}
                    </button>
                )}
            </div>

            {hint && !error && (
                <p
                    id={`${name}-hint`}
                    className="mt-1.5 text-xs leading-5 text-muted-foreground"
                >
                    {hint}
                </p>
            )}

            {error && (
                <p
                    id={`${name}-error`}
                    className="mt-1.5 text-xs font-semibold text-red-600 dark:text-red-400"
                >
                    {error}
                </p>
            )}
        </label>
    );
}

type SelectFieldProps = BaseProps & {
    value: string;
    onChange: (value: string) => void;
    options: readonly string[];
};

export function SelectField({
    label,
    name,
    value,
    onChange,
    options,
    error,
    hint,
    required = false,
}: SelectFieldProps) {
    return (
        <label
            htmlFor={name}
            className="block"
        >
            <span className="mb-2 flex items-center gap-1 text-sm font-bold">
                {label}

                {required && (
                    <span className="text-red-500">
                        *
                    </span>
                )}
            </span>

            <NativeSelect
                id={name}
                name={name}
                value={value}
                required={required}
                aria-invalid={Boolean(error)}
                onChange={(event) =>
                    onChange(
                        event.target.value,
                    )
                }
                className={`h-12 w-full rounded-xl border bg-background px-4 text-sm outline-none transition focus:ring-2 ${
                    error
                        ? "border-red-500 focus:ring-red-500/20"
                        : "focus:border-primary focus:ring-primary/20"
                }`}
            >
                {options.map((option) => (
                    <option
                        key={option}
                        value={option}
                    >
                        {option}
                    </option>
                ))}
            </NativeSelect>

            {hint && !error && (
                <p className="mt-1.5 text-xs text-muted-foreground">
                    {hint}
                </p>
            )}

            {error && (
                <p className="mt-1.5 text-xs font-semibold text-red-600 dark:text-red-400">
                    {error}
                </p>
            )}
        </label>
    );
}
