import type {
    LoanCompany,
} from "@/store/slices/companiesSlice";

export function normalizeCompanyStatus(
    value: unknown,
): string {
    return String(value ?? "")
        .trim()
        .toLowerCase();
}

export function formatCompanyDate(
    value: string | null | undefined,
): string {
    if (!value) {
        return "Not available";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return "Not available";
    }

    return new Intl.DateTimeFormat("en-LS", {
        day: "2-digit",
        month: "short",
        year: "numeric",
    }).format(date);
}

export function getPercentage(
    value: number,
    total: number,
): number {
    if (total <= 0) {
        return 0;
    }

    return (value / total) * 100;
}

export function formatPercentage(
    value: number,
): string {
    if (!Number.isFinite(value)) {
        return "0%";
    }

    return `${Math.round(value)}%`;
}

export function getRequestError(
    error: unknown,
): string {
    if (typeof error === "string") {
        return error;
    }

    if (
        typeof error === "object" &&
        error !== null &&
        "message" in error &&
        typeof error.message === "string"
    ) {
        return error.message;
    }

    return "The requested action could not be completed";
}

export function getTimestamp(
    value: string | null | undefined,
): number {
    if (!value) {
        return 0;
    }

    const timestamp = new Date(value).getTime();

    return Number.isNaN(timestamp)
        ? 0
        : timestamp;
}

export function countByCompany<
    T extends {
        company_id: string;
    },
>(
    records: T[],
    predicate?: (record: T) => boolean,
): Map<string, number> {
    const result = new Map<string, number>();

    for (const record of records) {
        if (predicate && !predicate(record)) {
            continue;
        }

        result.set(
            record.company_id,
            (result.get(record.company_id) ?? 0) + 1,
        );
    }

    return result;
}

function escapeCsvValue(
    value: unknown,
): string {
    const text = String(value ?? "");

    return `"${text.replaceAll('"', '""')}"`;
}

export function exportCompaniesToCsv({
                                         companies,
                                         branchesByCompany,
                                         staffByCompany,
                                     }: {
    companies: LoanCompany[];
    branchesByCompany: Map<string, number>;
    staffByCompany: Map<string, number>;
}) {
    const headings = [
        "Company",
        "Registration Number",
        "License Number",
        "Email",
        "Phone",
        "Website",
        "District",
        "Address",
        "Status",
        "Active",
        "Branches",
        "Staff",
        "Created At",
    ];

    const rows = companies.map((company) => [
        company.name,
        company.registration_number,
        company.license_number,
        company.email,
        company.phone,
        company.website,
        company.district,
        company.address,
        company.status,
        company.is_active ? "Yes" : "No",
        branchesByCompany.get(company.id) ?? 0,
        staffByCompany.get(company.id) ?? 0,
        company.created_at,
    ]);

    const csv = [
        headings,
        ...rows,
    ]
        .map((row) =>
            row
                .map(escapeCsvValue)
                .join(","),
        )
        .join("\n");

    const blob = new Blob([csv], {
        type: "text/csv;charset=utf-8",
    });

    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");

    anchor.href = url;
    anchor.download =
        `loanhub-companies-${new Date()
            .toISOString()
            .slice(0, 10)}.csv`;

    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();

    URL.revokeObjectURL(url);
}