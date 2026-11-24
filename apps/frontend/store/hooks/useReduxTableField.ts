"use client";

import { useCallback, type Dispatch, type SetStateAction } from "react";
import { useTenant } from "@/provider/tenantProvider";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { tableViewFieldSet } from "@/store/slices/tableViewsSlice";

/**
 * Redux-backed equivalent of useState for table-only UI preferences.
 * Scope includes the signed-in user, company, branch and role, preventing
 * search/filter/pagination preferences leaking across tenant switches.
 *
 * Do not use for sensitive row content, form drafts, authorization or financial
 * data. API rows continue to use the existing scoped Redux HTTP cache.
 */
export function useReduxTableField<T>(
    table: string,
    field: string,
    initialValue: T,
): [T, Dispatch<SetStateAction<T>>] {
    const dispatch = useAppDispatch();
    const userId = useAppSelector((state) => state.auth.user?.id ?? null);
    const { activeCompanyId, activeBranchId, activeRole } = useTenant();
    const scope = [
        userId ?? "anonymous",
        activeCompanyId ?? "platform",
        activeBranchId ?? "all-branches",
        activeRole ?? "no-role",
        table,
    ].join(":");
    const stored = useAppSelector((state) => state.tableViews.byScope[scope]?.[field]);
    const value = stored === undefined ? initialValue : (stored as T);

    const setValue: Dispatch<SetStateAction<T>> = useCallback(
        (nextValue) => {
            const resolved =
                typeof nextValue === "function"
                    ? (nextValue as (previous: T) => T)(value)
                    : nextValue;
            dispatch(tableViewFieldSet({ scope, field, value: resolved }));
        },
        [dispatch, field, scope, value],
    );
    return [value, setValue];
}
