import type {
    Branch,
    BranchCreatePayload,
} from "@/types/branch";

export const LESOTHO_DISTRICTS = [
    "Berea",
    "Butha-Buthe",
    "Leribe",
    "Mafeteng",
    "Maseru",
    "Mohale's Hoek",
    "Mokhotlong",
    "Qacha's Nek",
    "Quthing",
    "Thaba-Tseka",
] as const;

export type BranchFormValues = {
    company_id: string;
    name: string;
    district: string;
    town: string;
    address: string;
    phone: string;
    email: string;
    is_active: boolean;
};

export type BranchFormErrors =
    Partial<Record<keyof BranchFormValues, string>>;

export function createBranchFormValues(
    branch?: Branch | null,
): BranchFormValues {
    return {
        company_id: branch?.company_id ?? "",
        name: branch?.name ?? "",
        district: branch?.district ?? "",
        town: branch?.town ?? "",
        address: branch?.address ?? "",
        phone: branch?.phone ?? "",
        email: branch?.email ?? "",
        is_active: branch?.is_active ?? true,
    };
}

export function validateBranchForm(
    values: BranchFormValues,
): BranchFormErrors {
    const errors: BranchFormErrors = {};

    if (!values.company_id.trim()) {
        errors.company_id =
            "Select the company that owns this branch";
    }

    if (values.name.trim().length < 2) {
        errors.name =
            "Branch name must contain at least 2 characters";
    }

    if (!values.district.trim()) {
        errors.district =
            "Select the branch district";
    }

    if (values.town.trim().length < 2) {
        errors.town =
            "Town or village must contain at least 2 characters";
    }

    if (values.address.trim().length < 4) {
        errors.address =
            "Enter a clear physical address";
    }

    const normalizedPhone =
        values.phone.replace(/\s+/g, "");

    if (!normalizedPhone) {
        errors.phone =
            "Phone number is required";
    } else if (
        !/^\+?[0-9]{7,15}$/.test(
            normalizedPhone,
        )
    ) {
        errors.phone =
            "Enter a valid phone number";
    }

    if (
        values.email.trim() &&
        !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(
            values.email.trim(),
        )
    ) {
        errors.email =
            "Enter a valid email address";
    }

    return errors;
}

export function toBranchPayload(
    values: BranchFormValues,
): BranchCreatePayload {
    return {
        company_id: values.company_id.trim(),
        name: values.name.trim(),
        district: values.district.trim(),
        town: values.town.trim(),
        address: values.address.trim(),
        phone: values.phone.trim(),
        email: values.email.trim(),
        is_active: values.is_active,
    };
}

export function formatBranchDate(
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
    fallback = "The requested action could not be completed",
): string {
    if (typeof error === "string") {
        return error;
    }

    if (
        typeof error === "object" &&
        error !== null &&
        "response" in error
    ) {
        const responseError = error as {
            response?: {
                data?: {
                    detail?:
                        | string
                        | Array<{
                              msg?: string;
                          }>;
                };
            };
        };

        const detail =
            responseError.response?.data?.detail;

        if (typeof detail === "string") {
            return detail;
        }

        if (Array.isArray(detail)) {
            const messages = detail
                .map((item) => item.msg)
                .filter(
                    (
                        message,
                    ): message is string =>
                        Boolean(message),
                );

            if (messages.length > 0) {
                return messages.join(", ");
            }
        }
    }

    if (error instanceof Error) {
        return error.message;
    }

    return fallback;
}

function escapeCsvValue(
    value: unknown,
): string {
    const text = String(value ?? "");

    return `"${text.replace(/"/g, '""')}"`;
}

export function exportBranchesToCsv({
    branches,
    getCompanyName,
    staffByBranch,
}: {
    branches: Branch[];
    getCompanyName: (
        companyId: string,
    ) => string;
    staffByBranch: Map<string, number>;
}) {
    const headings = [
        "Branch",
        "Company",
        "District",
        "Town",
        "Address",
        "Phone",
        "Email",
        "Status",
        "Assigned Staff",
        "Created At",
        "Updated At",
    ];

    const rows = branches.map((branch) => [
        branch.name,
        getCompanyName(branch.company_id),
        branch.district,
        branch.town,
        branch.address,
        branch.phone,
        branch.email,
        branch.is_active
            ? "Active"
            : "Inactive",
        staffByBranch.get(branch.id) ?? 0,
        branch.created_at ?? "",
        branch.updated_at ?? "",
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

    const url =
        URL.createObjectURL(blob);

    const anchor =
        document.createElement("a");

    anchor.href = url;
    anchor.download =
        `loanhub-branches-${new Date()
            .toISOString()
            .slice(0, 10)}.csv`;

    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();

    URL.revokeObjectURL(url);
}
