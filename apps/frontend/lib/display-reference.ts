function compact(value: string): string {
    return value.replaceAll("-", "").slice(-8).toUpperCase();
}

export function displayReference(
    prefix: string,
    id: string | null | undefined,
    createdAt?: string | null,
): string {
    if (!id) return `${prefix}-PENDING`;

    const year = createdAt
        ? new Date(createdAt).getFullYear()
        : new Date().getFullYear();

    return `${prefix}-${Number.isNaN(year) ? new Date().getFullYear() : year}-${compact(id)}`;
}

export function shortReference(value: string | null | undefined): string {
    return value ? compact(value) : "Not available";
}
