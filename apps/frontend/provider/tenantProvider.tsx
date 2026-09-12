"use client";

import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useState,
    type ReactNode,
} from "react";

import {
    StorageKeys,
    getStoredValue,
    removeStoredValue,
    setStoredValue,
} from "@/lib/storage";
import { useAppSelector } from "@/store/hooks";
import { isCompanyRole, isPlatformRole, type CompanyMembership, type UserRole } from "@/types/auth";

export type TenantContextValue = {
    memberships: CompanyMembership[];
    companyMemberships: CompanyMembership[];
    availableRoles: CompanyMembership[];
    activeMembership: CompanyMembership | null;
    activeCompanyId: string | null;
    activeBranchId: string | null;
    activeRole: UserRole | null;
    hasMultipleCompanies: boolean;
    hasMultipleRoles: boolean;
    switchCompany: (companyId: string) => void;
    switchRole: (role: UserRole) => void;
    clearCompany: () => void;
};

const TenantContext = createContext<TenantContextValue | null>(null);

function chooseMembership(items: CompanyMembership[], requestedRole?: string | null): CompanyMembership | null {
    if (requestedRole) {
        const requested = items.find((item) => item.role === requestedRole);
        if (requested) return requested;
    }
    return items.find((item) => item.is_primary) ?? items[0] ?? null;
}

export function TenantProvider({ children }: { children: ReactNode }) {
    const user = useAppSelector((state) => state.auth.user);
    const [activeCompanyId, setActiveCompanyId] = useState<string | null>(null);
    const [activeRole, setActiveRole] = useState<UserRole | null>(null);

    const memberships = useMemo(
        () => (user?.memberships ?? []).filter((membership) => membership.is_active),
        [user?.memberships],
    );

    const companyMemberships = useMemo(() => {
        const seen = new Set<string>();
        return memberships.filter((membership) => {
            if (seen.has(membership.company_id)) return false;
            seen.add(membership.company_id);
            return true;
        });
    }, [memberships]);

    useEffect(() => {
        const timer = window.setTimeout(() => {
            if (!user || user.role === "borrower" || isPlatformRole(user.role) || !isCompanyRole(user.role)) {
                setActiveCompanyId(null);
                setActiveRole(user?.role ?? null);
                removeStoredValue(StorageKeys.activeCompanyId);
                removeStoredValue(StorageKeys.activeRole);
                return;
            }

            const storedCompanyId = getStoredValue(StorageKeys.activeCompanyId);
            const nextCompanyId = companyMemberships.some((item) => item.company_id === storedCompanyId)
                ? storedCompanyId
                : companyMemberships[0]?.company_id ?? null;
            const rolesForCompany = memberships.filter((item) => item.company_id === nextCompanyId);
            const selected = chooseMembership(rolesForCompany, getStoredValue(StorageKeys.activeRole));

            setActiveCompanyId(nextCompanyId);
            setActiveRole(selected?.role ?? user.role);
            if (nextCompanyId) setStoredValue(StorageKeys.activeCompanyId, nextCompanyId);
            if (selected?.role) setStoredValue(StorageKeys.activeRole, selected.role);
        }, 0);

        return () => window.clearTimeout(timer);
    }, [companyMemberships, memberships, user]);

    const availableRoles = useMemo(
        () => memberships.filter((membership) => membership.company_id === activeCompanyId),
        [activeCompanyId, memberships],
    );

    const activeMembership = useMemo(
        () => chooseMembership(availableRoles, activeRole),
        [activeRole, availableRoles],
    );

    const switchCompany = useCallback(
        (companyId: string) => {
            const roles = memberships.filter((item) => item.company_id === companyId);
            const selected = chooseMembership(roles);
            if (!selected) throw new Error("The selected company is not assigned to this account");
            setStoredValue(StorageKeys.activeCompanyId, companyId);
            setStoredValue(StorageKeys.activeRole, selected.role);
            setActiveCompanyId(companyId);
            setActiveRole(selected.role);
        },
        [memberships],
    );

    const switchRole = useCallback(
        (role: UserRole) => {
            const selected = availableRoles.find((item) => item.role === role);
            if (!selected) throw new Error("The selected role is not assigned for the active company");
            setStoredValue(StorageKeys.activeRole, role);
            setActiveRole(role);
        },
        [availableRoles],
    );

    const clearCompany = useCallback(() => {
        removeStoredValue(StorageKeys.activeCompanyId);
        removeStoredValue(StorageKeys.activeRole);
        setActiveCompanyId(null);
        setActiveRole(user?.role ?? null);
    }, [user?.role]);

    const value = useMemo<TenantContextValue>(() => ({
        memberships,
        companyMemberships,
        availableRoles,
        activeMembership,
        activeCompanyId,
        activeBranchId: activeMembership?.branch_id ?? null,
        activeRole: activeRole ?? user?.role ?? null,
        hasMultipleCompanies: companyMemberships.length > 1,
        hasMultipleRoles: availableRoles.length > 1,
        switchCompany,
        switchRole,
        clearCompany,
    }), [
        memberships,
        companyMemberships,
        availableRoles,
        activeMembership,
        activeCompanyId,
        activeRole,
        user?.role,
        switchCompany,
        switchRole,
        clearCompany,
    ]);

    return <TenantContext.Provider value={value}>{children}</TenantContext.Provider>;
}

export function useTenant(): TenantContextValue {
    const context = useContext(TenantContext);
    if (!context) throw new Error("useTenant must be used inside TenantProvider");
    return context;
}
