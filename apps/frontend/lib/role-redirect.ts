import type { UserRole } from "@/types/auth";
import { isCompanyRole, isPlatformRole } from "@/types/auth";

export function getDashboardRoute(role: UserRole): string {
    if (role === "superadmin") {
        return "/superadmin";
    }
    if (isPlatformRole(role)) {
        return "/platform";
    }
    if (role === "borrower") {
        return "/borrower";
    }
    if (isCompanyRole(role)) {
        return "/company";
    }
    return "/login";
}
