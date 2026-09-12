import type {
    SubscriptionPlan,
    SubscriptionPlanFeatures,
    SubscriptionPlanLimits,
} from "@/types/billing";

export const KNOWN_FEATURE_KEYS = [
    "marketplace_full_access",
    "advanced_analytics",
    "custom_branding",
    "api_access",
    "priority_support",
    "audit_exports",
] as const;

export const KNOWN_LIMIT_KEYS = ["branches", "staff", "products"] as const;

export function formatLimit(value: unknown): string {
    const numberValue = Number(value);
    if (!Number.isFinite(numberValue)) return "Not set";
    if (numberValue < 0) return "Unlimited";
    return numberValue.toLocaleString();
}

export function formatFeatureName(value: string): string {
    return value
        .replaceAll("_", " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function getEnabledFeatures(plan: SubscriptionPlan): string[] {
    return Object.entries(plan.features ?? {})
        .filter(([, enabled]) => enabled === true)
        .map(([key]) => key);
}

export function getAnnualSavings(plan: SubscriptionPlan): number {
    const monthlyAnnualized = Number(plan.monthly_price) * 12;
    const annualPrice = Number(plan.annual_price);
    if (monthlyAnnualized <= 0 || annualPrice <= 0 || annualPrice >= monthlyAnnualized) {
        return 0;
    }
    return monthlyAnnualized - annualPrice;
}

export function getExtraJson(
    source: Record<string, unknown>,
    knownKeys: readonly string[],
): string {
    const extras = Object.fromEntries(
        Object.entries(source ?? {}).filter(([key]) => !knownKeys.includes(key)),
    );
    return Object.keys(extras).length > 0 ? JSON.stringify(extras, null, 2) : "{}";
}

export function parseJsonObject(value: string, label: string): Record<string, unknown> {
    const trimmed = value.trim();
    if (!trimmed) return {};
    const parsed: unknown = JSON.parse(trimmed);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error(`${label} must be a JSON object`);
    }
    return parsed as Record<string, unknown>;
}

export function normalizePlanCode(value: string): string {
    return value.trim().toUpperCase().replace(/[^A-Z0-9_]+/g, "_");
}

export function mergeFeatures(
    extras: Record<string, unknown>,
    known: SubscriptionPlanFeatures,
): SubscriptionPlanFeatures {
    return {
        ...extras,
        ...known,
    } as SubscriptionPlanFeatures;
}

export function mergeLimits(
    extras: Record<string, unknown>,
    known: SubscriptionPlanLimits,
): SubscriptionPlanLimits {
    return {
        ...extras,
        ...known,
    } as SubscriptionPlanLimits;
}
