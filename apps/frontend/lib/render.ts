import type { ReactNode } from "react";

export function displayText(value: unknown, fallback = "—"): string {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "string" || typeof value === "number" || typeof value === "bigint") return String(value);
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (value instanceof Date) return value.toLocaleString();
  try {
    return JSON.stringify(value);
  } catch {
    return fallback;
  }
}

export function renderValue(value: unknown, fallback: ReactNode = "—"): ReactNode {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "string" || typeof value === "number" || typeof value === "bigint") return String(value);
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return displayText(value, typeof fallback === "string" ? fallback : "—");
}
