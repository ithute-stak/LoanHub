"use client";

import {
    Check,
    Loader2,
    Search,
    Shield,
    UserRoundCog,
    Users,
} from "lucide-react";
import { useRouter } from "next/navigation";
import {
    useEffect,
    useMemo,
    useRef,
    useState,
} from "react";

import {
    listImpersonationTargets,
    startImpersonation,
} from "@/api/auth";
import { Button } from "@/components/ui/button";
import { DialogFooter } from "@/components/ui/dialog";
import { CustomDialog } from "@/components/ui/custom-dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { getDashboardRoute } from "@/lib/role-redirect";
import {
    StorageKeys,
    setStoredJson,
    setStoredValue,
} from "@/lib/storage";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { replaceAuthSession } from "@/store/slices/authSlice";
import type { ImpersonationTarget } from "@/types/auth";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

const DEFAULT_REASON =
    "Platform support and role workflow testing";

function getTargetKey(
    target: ImpersonationTarget,
): string {
    return [
        target.id,
        target.company_id ?? "platform",
        target.branch_id ?? "all-branches",
        target.role,
    ].join(":");
}

function formatRole(role: string): string {
    return role
        .replaceAll("_", " ")
        .replace(/\b\w/g, (letter) =>
            letter.toUpperCase(),
        );
}

export function RoleSwitcher() {
    const router = useRouter();
    const dispatch = useAppDispatch();

    const user = useAppSelector(
        (state) => state.auth.user,
    );
    const accessToken = useAppSelector(
        (state) => state.auth.accessToken,
    );

    const [open, setOpen] = useState(false);
    const [search, setSearch] = useState("");
    const [targets, setTargets] = useState<
        ImpersonationTarget[]
    >([]);
    const [selectedKey, setSelectedKey] =
        useState<string | null>(null);
    const [reason, setReason] = useState(
        DEFAULT_REASON,
    );

    const [loadingTargets, setLoadingTargets] =
        useState(false);
    const [switching, setSwitching] =
        useState(false);

    /*
     * Prevent a slower previous search response from
     * replacing the results of a newer search.
     */
    const searchRequestRef = useRef(0);

    const selected = useMemo(
        () =>
            targets.find(
                (target) =>
                    getTargetKey(target) ===
                    selectedKey,
            ) ?? null,
        [selectedKey, targets],
    );

    const displayedTargets = useMemo(
        () => targets.slice(0, 200),
        [targets],
    );

    useEffect(() => {
        if (!open) {
            return;
        }

        const requestNumber =
            ++searchRequestRef.current;

        const timer = window.setTimeout(
            async () => {
                setLoadingTargets(true);

                try {
                    const result =
                        await listImpersonationTargets(
                            search.trim() || undefined,
                        );

                    if (
                        requestNumber !==
                        searchRequestRef.current
                    ) {
                        return;
                    }

                    setTargets(result);

                    /*
                     * Clear the selection when the chosen
                     * target is no longer in the result.
                     */
                    setSelectedKey(
                        (currentSelectedKey) => {
                            if (!currentSelectedKey) {
                                return null;
                            }

                            const stillExists =
                                result.some(
                                    (target) =>
                                        getTargetKey(
                                            target,
                                        ) ===
                                        currentSelectedKey,
                                );

                            return stillExists
                                ? currentSelectedKey
                                : null;
                        },
                    );
                } catch (error) {
                    if (
                        requestNumber !==
                        searchRequestRef.current
                    ) {
                        return;
                    }

                    setTargets([]);

                    toast.error(
                        getErrorMessage(
                            error,
                            "Could not load role-switch targets",
                        ),
                    );
                } finally {
                    if (
                        requestNumber ===
                        searchRequestRef.current
                    ) {
                        setLoadingTargets(false);
                    }
                }
            },
            300,
        );

        return () => {
            window.clearTimeout(timer);
        };
    }, [open, search]);

    if (user?.role !== "superadmin") {
        return null;
    }

    function handleOpenChange(
        nextOpen: boolean,
    ): void {
        if (switching) {
            return;
        }

        setOpen(nextOpen);

        if (!nextOpen) {
            setSearch("");
            setSelectedKey(null);
            setReason(DEFAULT_REASON);
            setTargets([]);
            setLoadingTargets(false);

            /*
             * Invalidates pending search responses.
             */
            searchRequestRef.current += 1;
        }
    }

    async function begin(): Promise<void> {
        const cleanReason = reason.trim();

        if (!selected) {
            toast.error(
                "Select the user role you want to test.",
            );
            return;
        }

        if (!accessToken || !user) {
            toast.error(
                "Your platform-owner session is no longer available. Sign in again.",
            );
            return;
        }

        if (cleanReason.length < 5) {
            toast.error(
                "Provide an audit reason of at least 5 characters.",
            );
            return;
        }

        setSwitching(true);

        try {
            const result =
                await startImpersonation({
                    target_user_id: selected.id,
                    company_id:
                        selected.company_id ??
                        undefined,
                    reason: cleanReason,
                    duration_minutes: 30,
                });

            /*
             * Preserve the original platform-owner
             * session before replacing Redux auth state.
             */
            setStoredValue(
                StorageKeys.originalAdminToken,
                accessToken,
            );

            setStoredJson(
                StorageKeys.originalAdminUser,
                user,
            );

            setStoredJson(
                StorageKeys.impersonation,
                {
                    expires_at: result.expires_at,
                    reason: result.reason,
                    target_name:
                    selected.display_name,
                    target_user_id: selected.id,
                    role: selected.role,
                    company_id:
                        result.company_id ??
                        selected.company_id ??
                        null,
                    company_name:
                        selected.company_name ??
                        null,
                    branch_name:
                        selected.branch_name ??
                        null,
                },
            );

            const activeCompanyId =
                result.company_id ??
                selected.company_id;

            if (activeCompanyId) {
                setStoredValue(
                    StorageKeys.activeCompanyId,
                    activeCompanyId,
                );
            }

            dispatch(
                replaceAuthSession({
                    accessToken:
                    result.access_token,
                    user: result.user,
                }),
            );

            toast.success(
                `Now viewing LoanHub as ${selected.display_name}`,
                {
                    description: `${formatRole(selected.role)}${
                        selected.company_name
                            ? ` at ${selected.company_name}`
                            : ""
                    }`,
                },
            );

            setOpen(false);

            const destinationRole =
                selected.role ||
                result.user.role;

            router.replace(
                getDashboardRoute(
                    destinationRole,
                ),
            );

            router.refresh();
        } catch (error) {
            toast.error(
                getErrorMessage(
                    error,
                    "Could not start the role-switch session",
                ),
            );
        } finally {
            setSwitching(false);
        }
    }

    return (
        <CustomDialog
            open={open}
            onOpenChange={handleOpenChange}
            trigger={
                <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-10 gap-2 rounded-xl px-3 text-xs font-black"
                    title="Test another role safely"
                >
                    <UserRoundCog className="h-4 w-4" />
                    <span className="hidden xl:inline">
                        Switch role
                    </span>
                </Button>
            }
            title="Switch into a user role"
            description="Start a time-limited and fully audited support session. Your original platform-owner session is preserved and can be restored."
            contentClassName="sm:max-w-2xl"
        >
            <div className="border-b border-border/60 bg-primary/5 px-5 py-3">
                <div className="flex items-center gap-2 text-primary">
                    <Shield className="h-5 w-5" />
                    <span className="text-xs font-black uppercase tracking-wider">
                        Platform owner testing
                    </span>
                </div>
            </div>
            <div className="space-y-5 p-5">
                <div className="space-y-2">
                    <label
                        htmlFor="role-switch-search"
                        className="text-sm font-black"
                    >
                        Find a user
                    </label>

                    <div className="relative">
                        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />

                        <Input
                            id="role-switch-search"
                            value={search}
                            onChange={(event) =>
                                setSearch(
                                    event.target
                                        .value,
                                )
                            }
                            placeholder="Search name, company, branch or role"
                            className="h-11 rounded-xl pl-10 pr-10"
                            autoComplete="off"
                        />

                        {loadingTargets && (
                            <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-muted-foreground" />
                        )}
                    </div>
                </div>

                <div className="overflow-hidden rounded-2xl border">
                    <div className="flex items-center justify-between border-b bg-muted/30 px-4 py-3">
                        <div className="flex items-center gap-2">
                            <Users className="h-4 w-4 text-muted-foreground" />

                            <span className="text-xs font-black uppercase tracking-wide text-muted-foreground">
                                Eligible users
                            </span>
                        </div>

                        <span className="text-xs font-semibold text-muted-foreground">
                            {displayedTargets.length}
                            {targets.length > 200
                                ? "+"
                                : ""}
                        </span>
                    </div>

                    <div className="max-h-80 divide-y overflow-y-auto">
                        {loadingTargets &&
                        displayedTargets.length ===
                        0 ? (
                            <div className="flex items-center justify-center gap-2 p-10 text-sm text-muted-foreground">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                Loading eligible
                                users...
                            </div>
                        ) : displayedTargets.length >
                        0 ? (
                            displayedTargets.map(
                                (target) => {
                                    const key =
                                        getTargetKey(
                                            target,
                                        );

                                    const isSelected =
                                        selectedKey ===
                                        key;

                                    return (
                                        <button
                                            key={
                                                key
                                            }
                                            type="button"
                                            onClick={() =>
                                                setSelectedKey(
                                                    key,
                                                )
                                            }
                                            className={[
                                                "flex w-full items-center gap-3 p-4 text-left transition-colors",
                                                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary",
                                                isSelected
                                                    ? "bg-primary/10"
                                                    : "hover:bg-muted/50",
                                            ].join(
                                                " ",
                                            )}
                                        >
                                            <span
                                                className={[
                                                    "flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-black",
                                                    isSelected
                                                        ? "bg-primary text-primary-foreground"
                                                        : "bg-muted text-foreground",
                                                ].join(
                                                    " ",
                                                )}
                                            >
                                                {isSelected ? (
                                                    <Check className="h-4 w-4" />
                                                ) : (
                                                    target.display_name
                                                        .charAt(
                                                            0,
                                                        )
                                                        .toUpperCase()
                                                )}
                                            </span>

                                            <span className="min-w-0 flex-1">
                                                <span className="block truncate text-sm font-black">
                                                    {
                                                        target.display_name
                                                    }
                                                </span>

                                                <span className="mt-1 block truncate text-xs text-muted-foreground">
                                                    {formatRole(
                                                        target.role,
                                                    )}

                                                    {" · "}

                                                    {target.company_name ??
                                                        "Platform / borrower"}

                                                    {target.branch_name
                                                        ? ` · ${target.branch_name}`
                                                        : ""}
                                                </span>
                                            </span>

                                            <span
                                                className={[
                                                    "h-4 w-4 shrink-0 rounded-full border-2",
                                                    isSelected
                                                        ? "border-primary bg-primary shadow-[inset_0_0_0_3px_hsl(var(--card))]"
                                                        : "border-muted-foreground/40",
                                                ].join(
                                                    " ",
                                                )}
                                                aria-hidden="true"
                                            />
                                        </button>
                                    );
                                },
                            )
                        ) : (
                            <div className="p-10 text-center">
                                <Users className="mx-auto h-8 w-8 text-muted-foreground/50" />

                                <p className="mt-3 text-sm font-black">
                                    No eligible active
                                    users found
                                </p>

                                <p className="mt-1 text-xs text-muted-foreground">
                                    Try another name,
                                    company, branch or
                                    role.
                                </p>
                            </div>
                        )}
                    </div>
                </div>

                {selected && (
                    <div className="rounded-2xl border border-primary/20 bg-primary/5 p-4">
                        <p className="text-xs font-black uppercase tracking-wide text-primary">
                            Selected session
                        </p>

                        <p className="mt-2 text-sm font-black">
                            {selected.display_name}
                        </p>

                        <p className="mt-1 text-xs text-muted-foreground">
                            {formatRole(
                                selected.role,
                            )}

                            {selected.company_name
                                ? ` · ${selected.company_name}`
                                : ""}

                            {selected.branch_name
                                ? ` · ${selected.branch_name}`
                                : ""}
                        </p>
                    </div>
                )}

                <div className="space-y-2">
                    <label
                        htmlFor="role-switch-reason"
                        className="text-sm font-black"
                    >
                        Audit reason
                    </label>

                    <Textarea
                        id="role-switch-reason"
                        value={reason}
                        onChange={(event) =>
                            setReason(
                                event.target.value,
                            )
                        }
                        minLength={5}
                        maxLength={500}
                        placeholder="Explain why this role-switch session is required"
                        className="min-h-24 resize-none rounded-xl"
                    />

                    <div className="flex justify-between text-xs text-muted-foreground">
                        <span>
                            Minimum 5 characters
                        </span>

                        <span>
                            {reason.length}/500
                        </span>
                    </div>
                </div>
            </div>

            <DialogFooter className="flex-row justify-end gap-3 border-t px-5 py-4 sm:space-x-0">
                <Button
                    type="button"
                    variant="outline"
                    onClick={() =>
                        handleOpenChange(false)
                    }
                    disabled={switching}
                    className="rounded-xl"
                >
                    Cancel
                </Button>

                <Button
                    type="button"
                    onClick={() => void begin()}
                    disabled={
                        !selected ||
                        reason.trim().length < 5 ||
                        switching
                    }
                    className="gap-2 rounded-xl font-black"
                >
                    {switching ? (
                        <>
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Switching...
                        </>
                    ) : (
                        <>
                            <UserRoundCog className="h-4 w-4" />
                            Start audited session
                        </>
                    )}
                </Button>
            </DialogFooter>
        </CustomDialog>
    );
}