import { createUuid } from "@/lib/uuid";

export function formatMoney(value: number | string | null | undefined, currency = "LSL"): string {
    const amount = Number(value ?? 0);
    return new Intl.NumberFormat("en-LS", {
        style: "currency",
        currency,
        maximumFractionDigits: 2,
    }).format(Number.isFinite(amount) ? amount : 0);
}

export function formatDate(value: string | null | undefined): string {
    if (!value) return "Not available";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Not available";
    return new Intl.DateTimeFormat("en-LS", {
        day: "2-digit",
        month: "short",
        year: "numeric",
    }).format(date);
}

export function formatDateTime(value: string | null | undefined): string {
    if (!value) return "Not available";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Not available";
    return new Intl.DateTimeFormat("en-LS", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    }).format(date);
}

export function titleCase(value: string | null | undefined): string {
    return String(value ?? "")
        .replaceAll("_", " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function createIdempotencyKey(prefix: string): string {
    return `${prefix}-${createUuid()}`;
}
