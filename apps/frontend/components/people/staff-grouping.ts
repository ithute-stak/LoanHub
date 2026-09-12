import type { CompanyStaff } from "@/types/companyStuff";

export interface CompanyStaffPerson {
    userId: string;
    user: CompanyStaff["user"];
    memberships: CompanyStaff[];
    primaryMembership: CompanyStaff | null;
    fullName: string;
    contact: string;
    isVerified: boolean;
    userIsActive: boolean;
    activeMembershipCount: number;
}

function membershipOrder(left: CompanyStaff, right: CompanyStaff): number {
    if (left.is_primary !== right.is_primary) return left.is_primary ? -1 : 1;
    if (left.is_active !== right.is_active) return left.is_active ? -1 : 1;
    return left.role.localeCompare(right.role);
}

export function groupCompanyStaffByUser(
    memberships: CompanyStaff[],
): CompanyStaffPerson[] {
    const grouped = new Map<string, CompanyStaff[]>();

    for (const membership of memberships) {
        const current = grouped.get(membership.user_id) ?? [];
        current.push(membership);
        grouped.set(membership.user_id, current);
    }

    return Array.from(grouped.entries())
        .map(([userId, userMemberships]) => {
            const sortedMemberships = [...userMemberships].sort(membershipOrder);
            const representative = sortedMemberships[0];
            const person = representative.user?.person;
            const fullName =
                person?.full_name?.trim() ||
                [person?.first_name, person?.middle_name, person?.last_name]
                    .filter(Boolean)
                    .join(" ") ||
                representative.user?.email ||
                representative.user?.phone ||
                userId;

            return {
                userId,
                user: representative.user,
                memberships: sortedMemberships,
                primaryMembership:
                    sortedMemberships.find((membership) => membership.is_primary) ??
                    null,
                fullName,
                contact:
                    representative.user?.email ??
                    representative.user?.phone ??
                    userId,
                isVerified: Boolean(representative.user?.is_verified),
                userIsActive: Boolean(representative.user?.is_active),
                activeMembershipCount: sortedMemberships.filter(
                    (membership) => membership.is_active,
                ).length,
            } satisfies CompanyStaffPerson;
        })
        .sort((left, right) => left.fullName.localeCompare(right.fullName));
}
