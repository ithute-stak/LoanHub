"use client";

import {
    Activity,
    BadgeCheck,
    Building2,
    CalendarDays,
    Check,
    ChevronRight,
    CircleUserRound,
    Clock3,
    Copy,
    Eye,
    EyeOff,
    KeyRound,
    Laptop2,
    LockKeyhole,
    LogOut,
    Mail,
    RefreshCw,
    Save,
    ShieldCheck,
    Smartphone,
    UserRound,
    type LucideIcon,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

import {
    changeAccountPassword,
    getAccountOverview,
    listAccountActivity,
    listAccountSessions,
    listMyNationalIdChangeRequests,
    decideMyNationalIdChangeRequest,
    revokeAccountSession,
    revokeAllAccountSessions,
    revokeOtherAccountSessions,
    updateAccountContact,
    updateAccountProfile,
} from "@/api/account";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { LoadingButton } from "@/components/ui/loading-button";
import { NativeSelect } from "@/components/ui/native-select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { formatDate, formatDateTime, titleCase } from "@/lib/format";
import { useAppDispatch } from "@/store/hooks";
import { fetchCurrentUser, logoutUser, replaceAuthUser } from "@/store/slices/authSlice";
import type { CompanyClientNationalIdChangeRequest } from "@/types/companyClient";
import type {
    AccountActivity as AccountActivityType,
    AccountOverview,
    AccountProfileUpdate,
    AccountSession,
} from "@/types/account";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";
import { MFAControlCard } from "@/components/account/mfa-control-card";

const emptyProfile: AccountProfileUpdate = {
    first_name: "",
    middle_name: "",
    last_name: "",
    gender: null,
    date_of_birth: null,
    national_id: "",
    passport_number: "",
    marital_status: null,
    nationality: "Mosotho",
    district: "",
    town_or_village: "",
    physical_address: "",
};

type PortalKind = "company" | "borrower" | "platform" | "superadmin";

export function AccountProfilePage({ portal }: { portal: PortalKind }) {
    const dispatch = useAppDispatch();
    const router = useRouter();
    const [overview, setOverview] = useState<AccountOverview | null>(null);
    const [sessions, setSessions] = useState<AccountSession[]>([]);
    const [activity, setActivity] = useState<AccountActivityType[]>([]);
    const [identityRequests, setIdentityRequests] = useState<CompanyClientNationalIdChangeRequest[]>([]);
    const [profile, setProfile] = useState<AccountProfileUpdate>(emptyProfile);
    const [contact, setContact] = useState({ email: "", phone: "", current_password: "" });
    const [password, setPassword] = useState({ current_password: "", new_password: "", confirm_password: "" });
    const [loading, setLoading] = useState(true);
    const [savingProfile, setSavingProfile] = useState(false);
    const [savingContact, setSavingContact] = useState(false);
    const [savingPassword, setSavingPassword] = useState(false);
    const [sessionAction, setSessionAction] = useState<string | null>(null);
    const [showCurrentPassword, setShowCurrentPassword] = useState(false);
    const [showNewPassword, setShowNewPassword] = useState(false);
    const [identityAction, setIdentityAction] = useState<string | null>(null);
    const [identityRejectionReason, setIdentityRejectionReason] = useState("");

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const account = await getAccountOverview();
            const [accountSessions, accountActivity, nationalIdRequests] = await Promise.all([
                account.security.can_manage_security ? listAccountSessions() : Promise.resolve([]),
                account.security.can_manage_security ? listAccountActivity() : Promise.resolve([]),
                listMyNationalIdChangeRequests().catch(() => []),
            ]);
            setOverview(account);
            setSessions(accountSessions);
            setActivity(accountActivity);
            setIdentityRequests(nationalIdRequests);
            const person = account.user.person;
            setProfile({
                first_name: person?.first_name ?? "",
                middle_name: person?.middle_name ?? "",
                last_name: person?.last_name ?? "",
                gender: person?.gender ?? null,
                date_of_birth: person?.date_of_birth ?? null,
                national_id: person?.national_id ?? "",
                passport_number: person?.passport_number ?? "",
                marital_status: person?.marital_status ?? null,
                nationality: person?.nationality ?? "Mosotho",
                district: person?.district ?? "",
                town_or_village: person?.town_or_village ?? "",
                physical_address: person?.physical_address ?? "",
            });
            setContact({
                email: account.user.email ?? "",
                phone: account.user.phone,
                current_password: "",
            });
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not load your account profile."));
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void load();
    }, [load]);

    const displayName = useMemo(() => {
        const person = overview?.user.person;
        return person?.full_name || [person?.first_name, person?.last_name].filter(Boolean).join(" ") || overview?.user.email || overview?.user.phone || "LoanHub user";
    }, [overview]);

    const initials = useMemo(() => {
        const parts = displayName.trim().split(/\s+/).filter(Boolean);
        return (parts.slice(0, 2).map((part) => part[0]?.toUpperCase()).join("") || "LU").slice(0, 2);
    }, [displayName]);

    async function saveProfile(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setSavingProfile(true);
        try {
            const editableProfile = { ...profile };
            delete editableProfile.national_id;
            await updateAccountProfile(editableProfile);
            await dispatch(fetchCurrentUser()).unwrap();
            await load();
            toast.success("Personal profile updated.");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not update your personal profile."));
        } finally {
            setSavingProfile(false);
        }
    }

    async function decideIdentityRequest(requestId: string, approve: boolean) {
        if (!approve && !identityRejectionReason.trim()) {
            toast.warning("Enter a rejection reason first.");
            return;
        }
        setIdentityAction(requestId);
        try {
            const updated = await decideMyNationalIdChangeRequest(requestId, {
                approve,
                reason: approve ? null : identityRejectionReason.trim(),
            });
            setIdentityRequests((current) => current.map((item) => item.id === updated.id ? updated : item));
            setIdentityRejectionReason("");
            await dispatch(fetchCurrentUser()).unwrap();
            await load();
            toast.success(approve ? "National ID change approved." : "National ID change rejected.");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "The National ID decision could not be recorded."));
        } finally {
            setIdentityAction(null);
        }
    }

    async function saveContact(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!contact.current_password) {
            toast.error("Enter your current password to confirm contact changes.");
            return;
        }
        setSavingContact(true);
        try {
            const user = await updateAccountContact({
                email: contact.email.trim() || null,
                phone: contact.phone.trim(),
                current_password: contact.current_password,
            });
            dispatch(replaceAuthUser(user));
            setContact((current) => ({ ...current, current_password: "" }));
            await load();
            toast.success("Contact details updated. Verification was reset for security.");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not update your contact details."));
        } finally {
            setSavingContact(false);
        }
    }

    async function savePassword(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setSavingPassword(true);
        try {
            const result = await changeAccountPassword(password);
            toast.success(result.message);
            await dispatch(logoutUser());
            router.replace("/login?password_changed=1");
            router.refresh();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not change your password."));
        } finally {
            setSavingPassword(false);
        }
    }

    async function revokeSession(sessionId: string) {
        setSessionAction(sessionId);
        try {
            const result = await revokeAccountSession(sessionId);
            toast.success(result.message);
            setSessions(await listAccountSessions());
            setActivity(await listAccountActivity());
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not revoke that session."));
        } finally {
            setSessionAction(null);
        }
    }

    async function revokeOthers() {
        setSessionAction("others");
        try {
            const result = await revokeOtherAccountSessions();
            toast.success(`${result.message} ${result.revoked_count} session(s) affected.`);
            setSessions(await listAccountSessions());
            setActivity(await listAccountActivity());
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not sign out other sessions."));
        } finally {
            setSessionAction(null);
        }
    }

    async function revokeAll() {
        setSessionAction("all");
        try {
            const result = await revokeAllAccountSessions();
            toast.success(result.message);
            await dispatch(logoutUser());
            router.replace("/login");
            router.refresh();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not sign out all sessions."));
        } finally {
            setSessionAction(null);
        }
    }

    function copyUserId() {
        if (!overview?.user.id) return;
        void navigator.clipboard.writeText(overview.user.id);
        toast.success("User ID copied.");
    }

    if (loading && !overview) {
        return <AccountSkeleton />;
    }

    if (!overview) {
        return (
            <Alert variant="destructive" className="rounded-3xl p-5">
                <AlertTitle>Account profile unavailable</AlertTitle>
                <AlertDescription>LoanHub could not load the authenticated account.</AlertDescription>
                <Button className="mt-4" variant="outline" onClick={() => void load()}><RefreshCw className="h-4 w-4" />Retry</Button>
            </Alert>
        );
    }

    const activeSessions = sessions.filter((session) => session.is_active);
    const passwordChecks = passwordStrength(password.new_password);

    return (
        <div className="space-y-6">
            <section className="overflow-hidden rounded-[2rem] border bg-card shadow-sm">
                <div className="bg-gradient-to-br from-primary/10 via-background to-emerald-500/10 p-6 sm:p-8">
                    <div className="flex flex-col justify-between gap-6 lg:flex-row lg:items-center">
                        <div className="flex min-w-0 items-center gap-4">
                            <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-[1.6rem] border bg-primary text-2xl font-black text-primary-foreground shadow-lg">{initials}</div>
                            <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-2">
                                    <h1 className="truncate text-2xl font-black sm:text-3xl">{displayName}</h1>
                                    <Badge variant={overview.security.is_verified ? "default" : "secondary"}>{overview.security.is_verified ? "Verified" : "Verification pending"}</Badge>
                                    <Badge variant={overview.security.is_active ? "outline" : "destructive"}>{overview.security.is_active ? "Active" : "Inactive"}</Badge>
                                </div>
                                <p className="mt-2 text-sm text-muted-foreground">Manage the identity, contact details, password and signed-in sessions for this authenticated LoanHub account.</p>
                                <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                                    <span className="rounded-full border bg-background/80 px-3 py-1.5">{overview.user.email ?? "No email recorded"}</span>
                                    <span className="rounded-full border bg-background/80 px-3 py-1.5">{overview.user.phone}</span>
                                    <span className="rounded-full border bg-background/80 px-3 py-1.5">Primary: {titleCase(overview.user.role)}</span>
                                </div>
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:min-w-[390px]">
                            <MetricCard label="Active sessions" value={String(overview.security.active_sessions)} icon={Laptop2} />
                            <MetricCard label="Role assignments" value={String(overview.memberships.filter((item) => item.is_active).length || 1)} icon={ShieldCheck} />
                            <MetricCard label="Member since" value={formatDate(overview.security.account_created_at)} icon={CalendarDays} className="col-span-2 sm:col-span-1" />
                        </div>
                    </div>
                </div>
            </section>

            {overview.security.is_impersonated ? (
                <Alert variant="destructive" className="rounded-3xl p-5">
                    <ShieldCheck />
                    <AlertTitle>Read-only impersonation session</AlertTitle>
                    <AlertDescription>Profile edits, password changes, session details and security history are hidden while a platform administrator is acting through an impersonation session. End impersonation and sign in directly to manage this account.</AlertDescription>
                </Alert>
            ) : null}

            <Tabs defaultValue="overview" className="space-y-5">
                <TabsList className="grid h-auto w-full grid-cols-2 gap-1 rounded-2xl p-1 sm:grid-cols-4">
                    <TabsTrigger value="overview" className="min-h-10 rounded-xl">Overview</TabsTrigger>
                    <TabsTrigger value="personal" className="min-h-10 rounded-xl">Personal details</TabsTrigger>
                    <TabsTrigger value="security" className="min-h-10 rounded-xl">Security</TabsTrigger>
                    <TabsTrigger value="activity" className="min-h-10 rounded-xl">Sessions & activity</TabsTrigger>
                </TabsList>

                <TabsContent value="overview" className="space-y-5">
                    <div className="grid gap-5 xl:grid-cols-[1.05fr_0.95fr]">
                        <section className="rounded-3xl border bg-card p-5 shadow-sm sm:p-6">
                            <SectionHeading icon={CircleUserRound} title="Account identity" description="Core details used to identify the authenticated user." />
                            <div className="mt-5 grid gap-3 sm:grid-cols-2">
                                <InfoCard label="Full name" value={displayName} icon={UserRound} />
                                <InfoCard label="Phone" value={overview.user.phone} icon={Smartphone} />
                                <InfoCard label="Email" value={overview.user.email ?? "Not recorded"} icon={Mail} />
                                <InfoCard label="Last seen" value={formatDateTime(overview.security.last_seen_at)} icon={Clock3} />
                            </div>
                            <button type="button" onClick={copyUserId} className="mt-4 flex w-full items-center justify-between rounded-2xl border bg-muted/20 p-4 text-left transition hover:bg-muted/50">
                                <span className="min-w-0"><span className="block text-xs font-bold uppercase text-muted-foreground">LoanHub user ID</span><span className="mt-1 block truncate font-mono text-xs">{overview.user.id}</span></span>
                                <Copy className="h-4 w-4 shrink-0 text-primary" />
                            </button>
                        </section>

                        <section className="rounded-3xl border bg-card p-5 shadow-sm sm:p-6">
                            <SectionHeading icon={Building2} title="Companies and assigned roles" description="One account may hold several roles without creating duplicate users." />
                            <div className="mt-5 space-y-3">
                                {overview.memberships.length === 0 ? (
                                    <div className="rounded-2xl border border-dashed p-5 text-sm text-muted-foreground">No company memberships are assigned to this account.</div>
                                ) : overview.memberships.map((membership) => (
                                    <div key={membership.id} className="rounded-2xl border p-4">
                                        <div className="flex flex-wrap items-start justify-between gap-3">
                                            <div>
                                                <p className="font-black">{membership.company_name}</p>
                                                <p className="mt-1 text-xs text-muted-foreground">{membership.branch_name ?? "Company-wide access"}</p>
                                            </div>
                                            <div className="flex flex-wrap gap-2">
                                                <Badge variant={membership.is_active ? "outline" : "destructive"}>{titleCase(membership.role)}</Badge>
                                                {membership.is_primary ? <Badge>Primary</Badge> : null}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </section>
                    </div>

                    <section className="rounded-3xl border bg-card p-5 shadow-sm sm:p-6">
                        <SectionHeading icon={BadgeCheck} title="Account status" description="Security and lifecycle information controlled by LoanHub." />
                        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                            <StatusCard label="Account access" value={overview.security.is_active ? "Active" : "Inactive"} good={overview.security.is_active} />
                            <StatusCard label="Verification" value={overview.security.is_verified ? "Verified" : "Pending"} good={overview.security.is_verified} />
                            <StatusCard label="Current portal" value={titleCase(portal)} good />
                            <StatusCard label="Last account update" value={formatDateTime(overview.security.account_updated_at)} good />
                        </div>
                    </section>
                </TabsContent>

                <TabsContent value="personal" className="space-y-5">
                    {identityRequests.filter((item) => item.status === "pending").map((request) => (
                        <section key={request.id} className="rounded-3xl border border-amber-500/30 bg-amber-500/5 p-5 shadow-sm sm:p-6">
                            <div className="flex flex-wrap items-start justify-between gap-3">
                                <div>
                                    <div className="flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-amber-600" /><h2 className="text-lg font-black">National ID change approval</h2></div>
                                    <p className="mt-2 text-sm text-muted-foreground">Request {request.reference} · expires {formatDateTime(request.expires_at)}</p>
                                </div>
                                <Badge variant="outline">Awaiting approvals</Badge>
                            </div>
                            <div className="mt-5 grid gap-3 sm:grid-cols-2">
                                <div className="rounded-2xl border bg-background p-4"><p className="text-xs font-bold text-muted-foreground">Current National ID</p><p className="mt-1 font-mono text-lg font-black">{request.current_national_id || "Not recorded"}</p></div>
                                <div className="rounded-2xl border bg-background p-4"><p className="text-xs font-bold text-muted-foreground">Proposed National ID</p><p className="mt-1 font-mono text-lg font-black">{request.proposed_national_id}</p></div>
                            </div>
                            <div className="mt-4 rounded-2xl border bg-background p-4"><p className="text-xs font-bold text-muted-foreground">Reason supplied by the company</p><p className="mt-2 whitespace-pre-wrap text-sm leading-6">{request.reason}</p></div>
                            <Alert className="mt-4"><LockKeyhole /><AlertTitle>Confirm carefully</AlertTitle><AlertDescription>Approving does not change the ID immediately. An active company owner must also approve. When both approvals exist, LoanHub changes the ID, resets identity verification and records a high-severity audit event.</AlertDescription></Alert>
                            {!request.borrower_approved_at ? (
                                <div className="mt-4 space-y-3">
                                    <Textarea value={identityRejectionReason} onChange={(event) => setIdentityRejectionReason(event.target.value)} rows={2} placeholder="Reason required only when rejecting" />
                                    <div className="flex flex-wrap justify-end gap-2">
                                        <LoadingButton variant="outline" loading={identityAction === request.id} onClick={() => void decideIdentityRequest(request.id, false)}>Reject request</LoadingButton>
                                        <LoadingButton loading={identityAction === request.id} onClick={() => void decideIdentityRequest(request.id, true)}><Check className="h-4 w-4" />Approve ID change</LoadingButton>
                                    </div>
                                </div>
                            ) : <p className="mt-4 text-sm font-bold text-emerald-700">Your approval was recorded {formatDateTime(request.borrower_approved_at)}. Waiting for the company owner.</p>}
                        </section>
                    ))}
                    <form onSubmit={saveProfile} className="rounded-3xl border bg-card p-5 shadow-sm sm:p-6">
                        <SectionHeading icon={UserRound} title="Personal details" description="Update your own identity and address. Sensitive identity changes remain audit logged." />
                        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                            <Field label="First name"><Input required value={profile.first_name ?? ""} onChange={(event) => setProfile((current) => ({ ...current, first_name: event.target.value }))} /></Field>
                            <Field label="Middle name"><Input value={profile.middle_name ?? ""} onChange={(event) => setProfile((current) => ({ ...current, middle_name: event.target.value }))} /></Field>
                            <Field label="Last name"><Input required value={profile.last_name ?? ""} onChange={(event) => setProfile((current) => ({ ...current, last_name: event.target.value }))} /></Field>
                            <Field label="Gender"><NativeSelect value={profile.gender ?? ""} onChange={(event) => setProfile((current) => ({ ...current, gender: (event.target.value || null) as AccountProfileUpdate["gender"] }))}><option value="">Not specified</option><option value="male">Male</option><option value="female">Female</option><option value="other">Other</option></NativeSelect></Field>
                            <Field label="Date of birth"><Input type="date" value={profile.date_of_birth ?? ""} onChange={(event) => setProfile((current) => ({ ...current, date_of_birth: event.target.value || null }))} /></Field>
                            <Field label="Marital status"><NativeSelect value={profile.marital_status ?? ""} onChange={(event) => setProfile((current) => ({ ...current, marital_status: (event.target.value || null) as AccountProfileUpdate["marital_status"] }))}><option value="">Not specified</option><option value="single">Single</option><option value="married">Married</option><option value="divorced">Divorced</option><option value="widowed">Widowed</option></NativeSelect></Field>
                            <Field label="National ID"><Input readOnly value={profile.national_id ?? ""} className="bg-muted/40" /><p className="text-xs text-muted-foreground">Protected identity field. A lender must request a change and both you and a company owner must approve it.</p></Field>
                            <Field label="Passport number"><Input value={profile.passport_number ?? ""} onChange={(event) => setProfile((current) => ({ ...current, passport_number: event.target.value }))} /></Field>
                            <Field label="Nationality"><Input value={profile.nationality ?? ""} onChange={(event) => setProfile((current) => ({ ...current, nationality: event.target.value }))} /></Field>
                            <Field label="District"><Input value={profile.district ?? ""} onChange={(event) => setProfile((current) => ({ ...current, district: event.target.value }))} /></Field>
                            <Field label="Town or village"><Input value={profile.town_or_village ?? ""} onChange={(event) => setProfile((current) => ({ ...current, town_or_village: event.target.value }))} /></Field>
                            <Field label="Physical address" className="sm:col-span-2 lg:col-span-3"><Textarea value={profile.physical_address ?? ""} onChange={(event) => setProfile((current) => ({ ...current, physical_address: event.target.value }))} /></Field>
                        </div>
                        <div className="mt-6 flex justify-end"><LoadingButton type="submit" loading={savingProfile} loadingText="Saving profile..." disabled={!overview.security.can_manage_security}><Save className="h-4 w-4" />Save personal details</LoadingButton></div>
                    </form>

                    <form onSubmit={saveContact} className="rounded-3xl border bg-card p-5 shadow-sm sm:p-6">
                        <SectionHeading icon={Mail} title="Contact and sign-in identity" description="Phone and email changes require the current password and reset verification status." />
                        <Alert className="mt-5 rounded-2xl p-4"><LockKeyhole /><AlertTitle>Security confirmation required</AlertTitle><AlertDescription>LoanHub never asks for a provider PIN or OTP here. Enter only your current LoanHub password.</AlertDescription></Alert>
                        <div className="mt-5 grid gap-4 md:grid-cols-2">
                            <Field label="Email address"><Input type="email" value={contact.email} onChange={(event) => setContact((current) => ({ ...current, email: event.target.value }))} /></Field>
                            <Field label="Phone number"><Input required value={contact.phone} onChange={(event) => setContact((current) => ({ ...current, phone: event.target.value }))} /></Field>
                            <Field label="Current password" className="md:col-span-2"><PasswordField value={contact.current_password} visible={showCurrentPassword} onToggle={() => setShowCurrentPassword((value) => !value)} onChange={(value) => setContact((current) => ({ ...current, current_password: value }))} autoComplete="current-password" /></Field>
                        </div>
                        <div className="mt-6 flex justify-end"><LoadingButton type="submit" loading={savingContact} loadingText="Updating contact..." disabled={!overview.security.can_manage_security}><Save className="h-4 w-4" />Update contact details</LoadingButton></div>
                    </form>
                </TabsContent>

                <TabsContent value="security" className="space-y-5">
                    <MFAControlCard />
                    <form onSubmit={savePassword} className="rounded-3xl border bg-card p-5 shadow-sm sm:p-6">
                        <SectionHeading icon={KeyRound} title="Change password" description="A successful password change signs out every device and requires a fresh login." />
                        <div className="mt-6 grid gap-4 lg:grid-cols-[1fr_0.9fr]">
                            <div className="space-y-4">
                                <Field label="Current password"><PasswordField value={password.current_password} visible={showCurrentPassword} onToggle={() => setShowCurrentPassword((value) => !value)} onChange={(value) => setPassword((current) => ({ ...current, current_password: value }))} autoComplete="current-password" /></Field>
                                <Field label="New password"><PasswordField value={password.new_password} visible={showNewPassword} onToggle={() => setShowNewPassword((value) => !value)} onChange={(value) => setPassword((current) => ({ ...current, new_password: value }))} autoComplete="new-password" /></Field>
                                <Field label="Confirm new password"><PasswordField value={password.confirm_password} visible={showNewPassword} onToggle={() => setShowNewPassword((value) => !value)} onChange={(value) => setPassword((current) => ({ ...current, confirm_password: value }))} autoComplete="new-password" /></Field>
                            </div>
                            <div className="rounded-3xl border bg-muted/20 p-5">
                                <p className="font-black">Password requirements</p>
                                <div className="mt-4 space-y-3">
                                    {passwordChecks.map((check) => <Requirement key={check.label} met={check.met} label={check.label} />)}
                                    <Requirement met={Boolean(password.new_password && password.new_password === password.confirm_password)} label="Both new-password fields match" />
                                </div>
                                <p className="mt-5 text-xs leading-5 text-muted-foreground">Avoid names, phone numbers, email names and passwords used on other services.</p>
                            </div>
                        </div>
                        <div className="mt-6 flex justify-end"><LoadingButton type="submit" loading={savingPassword} loadingText="Changing password..." disabled={!overview.security.can_manage_security || !password.current_password || !password.new_password || !password.confirm_password}><KeyRound className="h-4 w-4" />Change password</LoadingButton></div>
                    </form>

                    <section className="rounded-3xl border border-red-200 bg-red-50/40 p-5 shadow-sm dark:border-red-900 dark:bg-red-950/10 sm:p-6">
                        <SectionHeading icon={LogOut} title="Emergency sign-out" description="Use this when a phone, computer or browser may no longer be trusted." />
                        <div className="mt-5 flex flex-col gap-3 sm:flex-row">
                            <LoadingButton variant="outline" loading={sessionAction === "others"} loadingText="Signing out others..." disabled={!overview.security.can_manage_security} onClick={() => void revokeOthers()}><Laptop2 className="h-4 w-4" />Sign out other devices</LoadingButton>
                            <LoadingButton variant="destructive" loading={sessionAction === "all"} loadingText="Signing out all..." disabled={!overview.security.can_manage_security} onClick={() => void revokeAll()}><LogOut className="h-4 w-4" />Sign out every device</LoadingButton>
                        </div>
                    </section>
                </TabsContent>

                <TabsContent value="activity" className="space-y-5">
                    <section className="rounded-3xl border bg-card p-5 shadow-sm sm:p-6">
                        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                            <SectionHeading icon={Laptop2} title="Signed-in sessions" description="Review and revoke refresh sessions linked to this account." />
                            <Badge variant="outline">{activeSessions.length} active</Badge>
                        </div>
                        <div className="mt-5 space-y-3">
                            {sessions.length === 0 ? <EmptyState text="No refresh sessions were found." /> : sessions.map((session) => (
                                <div key={session.id} className="flex flex-col justify-between gap-4 rounded-2xl border p-4 sm:flex-row sm:items-center">
                                    <div className="flex min-w-0 items-start gap-3">
                                        <div className={`mt-0.5 rounded-xl p-2 ${session.is_current ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"}`}><Laptop2 className="h-4 w-4" /></div>
                                        <div className="min-w-0">
                                            <div className="flex flex-wrap items-center gap-2"><p className="font-black">{session.is_current ? "Current browser session" : "LoanHub session"}</p><Badge variant={session.is_active ? "outline" : "secondary"}>{titleCase(session.status)}</Badge>{session.is_current ? <Badge>Current</Badge> : null}</div>
                                            <p className="mt-1 text-xs text-muted-foreground">Created {formatDateTime(session.created_at)} · Expires {formatDateTime(session.expires_at)}</p>
                                        </div>
                                    </div>
                                    {!session.is_current && session.is_active ? <LoadingButton variant="destructive" size="sm" loading={sessionAction === session.id} loadingText="Revoking..." onClick={() => void revokeSession(session.id)}>Revoke</LoadingButton> : null}
                                </div>
                            ))}
                        </div>
                    </section>

                    <section className="rounded-3xl border bg-card p-5 shadow-sm sm:p-6">
                        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                            <SectionHeading icon={Activity} title="Account security activity" description="Recent login, logout, profile, password and session events." />
                            <Button variant="outline" onClick={() => void load()}><RefreshCw className="h-4 w-4" />Refresh</Button>
                        </div>
                        <div className="mt-5 space-y-3">
                            {activity.length === 0 ? <EmptyState text="No account-security activity has been recorded yet." /> : activity.map((event) => (
                                <div key={event.id} className="rounded-2xl border p-4">
                                    <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                                        <div className="min-w-0">
                                            <div className="flex flex-wrap items-center gap-2"><p className="font-black">{titleCase(event.action.replace(/^auth\.|^account\./, ""))}</p><Badge variant={event.status === "success" ? "outline" : "destructive"}>{titleCase(event.status)}</Badge></div>
                                            <p className="mt-1 text-sm text-muted-foreground">{event.description ?? "Security event recorded."}</p>
                                            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground"><span>{formatDateTime(event.created_at)}</span>{event.ip_address ? <span>IP: {event.ip_address}</span> : null}</div>
                                        </div>
                                        <ChevronRight className="hidden h-4 w-4 text-muted-foreground sm:block" />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </section>
                </TabsContent>
            </Tabs>
        </div>
    );
}

function passwordStrength(value: string) {
    return [
        { label: "At least 10 characters", met: value.length >= 10 },
        { label: "Contains an uppercase letter", met: /[A-Z]/.test(value) },
        { label: "Contains a lowercase letter", met: /[a-z]/.test(value) },
        { label: "Contains a number", met: /\d/.test(value) },
        { label: "Contains a special character", met: /[^A-Za-z0-9]/.test(value) },
    ];
}

function Requirement({ met, label }: { met: boolean; label: string }) {
    return <div className={`flex items-center gap-2 text-sm ${met ? "text-emerald-700 dark:text-emerald-400" : "text-muted-foreground"}`}><span className={`flex h-5 w-5 items-center justify-center rounded-full border ${met ? "border-emerald-500 bg-emerald-500 text-white" : "border-muted-foreground/30"}`}>{met ? <Check className="h-3 w-3" /> : null}</span>{label}</div>;
}

function PasswordField({ value, visible, onToggle, onChange, autoComplete }: { value: string; visible: boolean; onToggle: () => void; onChange: (value: string) => void; autoComplete: string }) {
    return <div className="relative"><Input type={visible ? "text" : "password"} value={value} onChange={(event) => onChange(event.target.value)} autoComplete={autoComplete} className="pr-11" /><button type="button" aria-label={visible ? "Hide password" : "Show password"} onClick={onToggle} className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-foreground">{visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button></div>;
}

function Field({ label, children, className = "" }: { label: string; children: React.ReactNode; className?: string }) {
    return <label className={`block ${className}`}><span className="mb-2 block text-sm font-bold">{label}</span>{children}</label>;
}

function SectionHeading({ icon: Icon, title, description }: { icon: LucideIcon; title: string; description: string }) {
    return <div className="flex items-start gap-3"><div className="rounded-2xl bg-primary/10 p-3 text-primary"><Icon className="h-5 w-5" /></div><div><h2 className="text-lg font-black">{title}</h2><p className="mt-1 text-sm text-muted-foreground">{description}</p></div></div>;
}

function MetricCard({ label, value, icon: Icon, className = "" }: { label: string; value: string; icon: LucideIcon; className?: string }) {
    return <div className={`rounded-2xl border bg-background/80 p-4 ${className}`}><div className="flex items-center justify-between gap-2"><p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">{label}</p><Icon className="h-4 w-4 text-primary" /></div><p className="mt-2 text-lg font-black">{value}</p></div>;
}

function InfoCard({ label, value, icon: Icon }: { label: string; value: string; icon: LucideIcon }) {
    return <div className="rounded-2xl border bg-muted/20 p-4"><div className="flex items-center gap-2 text-xs font-bold uppercase text-muted-foreground"><Icon className="h-4 w-4" />{label}</div><p className="mt-2 break-words font-black">{value}</p></div>;
}

function StatusCard({ label, value, good }: { label: string; value: string; good: boolean }) {
    return <div className="rounded-2xl border p-4"><div className="flex items-center gap-2"><span className={`h-2.5 w-2.5 rounded-full ${good ? "bg-emerald-500" : "bg-amber-500"}`} /><p className="text-xs font-bold uppercase text-muted-foreground">{label}</p></div><p className="mt-2 font-black">{value}</p></div>;
}

function EmptyState({ text }: { text: string }) {
    return <div className="rounded-2xl border border-dashed p-8 text-center text-sm text-muted-foreground">{text}</div>;
}

function AccountSkeleton() {
    return <div className="space-y-5"><div className="h-52 animate-pulse rounded-[2rem] bg-muted" /><div className="h-12 animate-pulse rounded-2xl bg-muted" /><div className="grid gap-5 lg:grid-cols-2"><div className="h-80 animate-pulse rounded-3xl bg-muted" /><div className="h-80 animate-pulse rounded-3xl bg-muted" /></div></div>;
}
