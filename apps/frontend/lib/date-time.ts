import { formatDistanceToNow } from "date-fns";

const TIME_ZONE_SUFFIX = /(?:Z|[+-]\d{2}:?\d{2})$/i;

/**
 * Parse a timestamp returned by the LoanHub API.
 *
 * PostgreSQL/FastAPI timestamps can be serialized without an explicit
 * timezone suffix even though they represent UTC. Browsers interpret such
 * strings as local time, which makes UTC timestamps appear two hours old in
 * Lesotho (UTC+02:00). Preserve timestamps that already contain a timezone
 * and treat timezone-less API timestamps as UTC.
 */
export function parseApiDateTime(value: string | Date): Date {
    if (value instanceof Date) {
        return value;
    }

    const timestamp = value.trim();
    if (!timestamp) {
        return new Date(Number.NaN);
    }

    return new Date(
        TIME_ZONE_SUFFIX.test(timestamp)
            ? timestamp
            : `${timestamp}Z`,
    );
}

export function formatApiRelativeTime(
    value: string | Date,
): string {
    const parsed = parseApiDateTime(value);

    if (Number.isNaN(parsed.getTime())) {
        return "";
    }

    return formatDistanceToNow(parsed, {
        addSuffix: true,
    });
}
