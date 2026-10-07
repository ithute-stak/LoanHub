export type SortableRecord = Record<string, unknown>;

const DATE_KEYS = [
    "updated_at",
    "updatedAt",
    "created_at",
    "createdAt",
    "submitted_at",
    "submittedAt",
    "occurred_at",
    "occurredAt",
    "effective_date",
    "effectiveDate",
    "date",
] as const;

const LABEL_KEYS = [
    "name",
    "title",
    "reference",
    "loan_reference",
    "application_reference",
    "request_reference",
    "invoice_number",
    "employee_number",
    "email",
    "id",
] as const;

function asTimestamp(value: unknown): number | null {
    if (typeof value !== "string" && typeof value !== "number" && !(value instanceof Date)) {
        return null;
    }
    const parsed = new Date(value).getTime();
    return Number.isFinite(parsed) ? parsed : null;
}

function textValue(record: SortableRecord): string {
    for (const key of LABEL_KEYS) {
        const value = record[key];
        if (value !== null && value !== undefined && String(value).trim()) {
            return String(value).trim();
        }
    }
    return "";
}

function timestampValue(record: SortableRecord): number | null {
    for (const key of DATE_KEYS) {
        const parsed = asTimestamp(record[key]);
        if (parsed !== null) {
            return parsed;
        }
    }
    return null;
}

/**
 * Deterministic UI ordering for live collections.
 *
 * 1. Records with timestamps sort newest first so a newly committed item appears
 *    where users expect after a realtime refresh.
 * 2. Records without useful dates fall back to a locale-aware human label.
 * 3. Original index is the final tie-breaker, so provider/business ordering is
 *    preserved when records have no sortable metadata.
 */
export function stableSmartSort<T extends object>(records: readonly T[]): T[] {
    return records
        .map((record, index) => ({ record, index }))
        .sort((left, right) => {
            const leftRecord = left.record as SortableRecord;
            const rightRecord = right.record as SortableRecord;
            const leftTime = timestampValue(leftRecord);
            const rightTime = timestampValue(rightRecord);

            if (leftTime !== null || rightTime !== null) {
                if (leftTime === null) return 1;
                if (rightTime === null) return -1;
                if (leftTime !== rightTime) return rightTime - leftTime;
            }

            const leftText = textValue(leftRecord);
            const rightText = textValue(rightRecord);
            if (leftText || rightText) {
                const compared = leftText.localeCompare(rightText, undefined, {
                    numeric: true,
                    sensitivity: "base",
                });
                if (compared !== 0) return compared;
            }

            return left.index - right.index;
        })
        .map(({ record }) => record);
}
