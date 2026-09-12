type UnknownRecord = Record<string, unknown>;

type ApiErrorLike = {
    response?: {
        data?: unknown;
        status?: number;
    };
    message?: unknown;
};

const LOCATION_PREFIXES = new Set([
    "body",
    "query",
    "path",
    "header",
    "cookie",
]);

function isRecord(value: unknown): value is UnknownRecord {
    return typeof value === "object" && value !== null;
}

function formatLocation(value: unknown): string {
    if (!Array.isArray(value)) {
        return "";
    }

    return value
        .filter(
            (item) =>
                typeof item === "string" ||
                typeof item === "number",
        )
        .map(String)
        .filter((item) => !LOCATION_PREFIXES.has(item))
        .join(".");
}

function formatValidationIssue(value: UnknownRecord): string {
    const message =
        typeof value.msg === "string"
            ? value.msg.trim()
            : typeof value.message === "string"
              ? value.message.trim()
              : "";

    if (!message) {
        return "";
    }

    const location = formatLocation(value.loc);

    return location
        ? `${location}: ${message}`
        : message;
}

function extractMessage(
    value: unknown,
    seen: Set<unknown>,
): string {
    if (value === null || value === undefined) {
        return "";
    }

    if (typeof value === "string") {
        return value.trim();
    }

    if (
        typeof value === "number" ||
        typeof value === "bigint" ||
        typeof value === "boolean"
    ) {
        return String(value);
    }

    if (value instanceof Error) {
        const errorWithResponse = value as Error & ApiErrorLike;
        const responseMessage = extractMessage(
            errorWithResponse.response?.data,
            seen,
        );

        if (responseMessage) {
            return responseMessage;
        }

        return value.message.trim();
    }

    if (typeof value !== "object") {
        return "";
    }

    if (seen.has(value)) {
        return "";
    }

    seen.add(value);

    if (Array.isArray(value)) {
        const messages = value
            .map((item) => extractMessage(item, seen))
            .filter(Boolean);

        return [...new Set(messages)].join("; ");
    }

    const record = value as UnknownRecord;
    const validationMessage = formatValidationIssue(record);

    if (validationMessage) {
        return validationMessage;
    }

    for (const key of [
        "detail",
        "message",
        "error",
        "errors",
        "reason",
        "title",
    ]) {
        if (!(key in record)) {
            continue;
        }

        const message = extractMessage(record[key], seen);

        if (message) {
            return message;
        }
    }

    return "";
}

/**
 * Converts API errors, FastAPI validation details, arrays and unknown values
 * into safe user-facing text. It never returns an object or React child.
 */
export function toDisplayMessage(
    value: unknown,
    fallback = "Something went wrong.",
): string {
    const message = extractMessage(value, new Set());

    return message || fallback;
}

export function getErrorMessage(
    error: unknown,
    fallback: string,
): string {
    if (isRecord(error) && "response" in error) {
        const apiError = error as ApiErrorLike;
        const responseMessage = toDisplayMessage(
            apiError.response?.data,
            "",
        );

        if (responseMessage) {
            return responseMessage;
        }
    }

    return toDisplayMessage(error, fallback);
}
