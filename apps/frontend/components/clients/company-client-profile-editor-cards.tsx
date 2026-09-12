"use client";

import { useState, type ReactNode } from "react";
import {
  BadgeCheck,
  BriefcaseBusiness,
  Check,
  CircleX,
  IdCard,
  Landmark,
  MapPin,
  Pencil,
  Save,
  ShieldCheck,
  X,
} from "lucide-react";

import {
  decideCompanyClientNationalIdChangeAsOwner,
  getCompanyClientProfile,
  requestCompanyClientNationalIdChange,
  updateCompanyClientProfile,
} from "@/api/companyClients";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import {
  BANK_NAMES,
  DEFAULT_BANK_BRANCH,
  bankAccountPrefixHint,
  bankAccountValidationMessage,
  bankDetails,
  isBankName,
} from "@/lib/banking";
import { formatDate, formatDateTime, formatMoney, titleCase } from "@/lib/format";
import type {
  CompanyClientProfile,
  CompanyClientProfileUpdate,
} from "@/types/companyClient";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

type EditSection = "personal" | "contact" | "employment" | "banking";

function valueOrDash(value: string | number | null | undefined) {
  return value === null || value === undefined || value === "" ? "—" : value;
}

function EditableRow({
  label,
  value,
  editable = false,
  actionLabel = "Edit field",
  onEdit,
}: {
  label: string;
  value: string | number | null | undefined;
  editable?: boolean;
  actionLabel?: string;
  onEdit?: () => void;
}) {
  return (
    <div className="grid min-h-11 grid-cols-[minmax(100px,150px)_1fr_auto] items-center gap-3 border-b py-2.5 last:border-b-0">
      <span className="text-xs font-semibold text-muted-foreground">{label}</span>
      <span className="min-w-0 break-words text-sm font-semibold">{valueOrDash(value)}</span>
      {editable && onEdit ? (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-8 w-8 shrink-0"
          aria-label={`${actionLabel}: ${label}`}
          title={`${actionLabel}: ${label}`}
          onClick={onEdit}
        >
          <Pencil className="h-3.5 w-3.5" />
        </Button>
      ) : <span className="w-8" aria-hidden />}
    </div>
  );
}

function Field({ label, children, className = "" }: { label: string; children: ReactNode; className?: string }) {
  return (
    <div className={`space-y-1.5 ${className}`}>
      <Label>{label}</Label>
      {children}
    </div>
  );
}

function CardHeading({
  icon: Icon,
  title,
  editing,
  canEdit,
  onEdit,
  onCancel,
}: {
  icon: typeof IdCard;
  title: string;
  editing: boolean;
  canEdit: boolean;
  onEdit: () => void;
  onCancel: () => void;
}) {
  return (
    <CardHeader className="pb-3">
      <div className="flex items-center justify-between gap-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Icon className="h-4 w-4 text-primary" />{title}
        </CardTitle>
        {canEdit ? (
          <Button type="button" variant="ghost" size="sm" onClick={editing ? onCancel : onEdit}>
            {editing ? <X className="h-4 w-4" /> : <Pencil className="h-4 w-4" />}
            {editing ? "Cancel" : "Edit"}
          </Button>
        ) : null}
      </div>
    </CardHeader>
  );
}

export function CompanyClientProfileEditorCards({
  profile,
  onUpdated,
}: {
  profile: CompanyClientProfile;
  onUpdated: (profile: CompanyClientProfile) => void;
}) {
  const client = profile.client;
  const permissions = profile.permissions;
  const [editing, setEditing] = useState<EditSection | null>(null);
  const [draft, setDraft] = useState<CompanyClientProfileUpdate>({});
  const [saving, setSaving] = useState(false);
  const [showNationalIdRequest, setShowNationalIdRequest] = useState(false);
  const [proposedNationalId, setProposedNationalId] = useState("");
  const [nationalIdReason, setNationalIdReason] = useState("");
  const [identityWorking, setIdentityWorking] = useState(false);
  const [ownerRejectionReason, setOwnerRejectionReason] = useState("");

  function startEditing(section: EditSection) {
    setEditing(section);
    if (section === "personal") {
      setDraft({
        first_name: client.first_name,
        middle_name: client.middle_name,
        last_name: client.last_name,
        gender: (client.gender || null) as CompanyClientProfileUpdate["gender"],
        date_of_birth: client.date_of_birth,
        passport_number: client.passport_number,
        marital_status: (client.marital_status || null) as CompanyClientProfileUpdate["marital_status"],
        nationality: client.nationality,
      });
    } else if (section === "contact") {
      setDraft({
        email: client.email,
        phone: client.phone,
        district: client.district,
        town_or_village: client.town_or_village,
        physical_address: client.physical_address,
        is_login_active: client.is_login_active,
      });
    } else if (section === "employment") {
      setDraft({
        employment_status: client.employment_status as CompanyClientProfileUpdate["employment_status"],
        employer_name: client.employer_name,
        job_title: client.job_title,
        monthly_income: client.monthly_income,
        salary_date: client.salary_date,
      });
    } else {
      const details = bankDetails(client.bank_name);
      setDraft({
        account_status: client.status as CompanyClientProfileUpdate["account_status"],
        bank_account: {
          account_holder: client.bank_account_holder || client.full_name,
          bank_name: details?.name ?? client.bank_name ?? null,
          branch_name: details?.branch ?? client.bank_branch_name ?? DEFAULT_BANK_BRANCH,
          branch_code: details?.code ?? client.bank_branch_code ?? null,
          account_type: client.bank_account_type || "savings",
          currency: client.bank_currency || "LSL",
          account_number: null,
          salary_account: client.salary_account,
        },
      });
    }
  }

  async function saveSection() {
    if (!editing) return;
    const payload: CompanyClientProfileUpdate = { ...draft };
    if (editing === "contact") {
      if (!permissions.can_edit_contact) {
        delete payload.email;
        delete payload.phone;
      }
      if (!permissions.can_edit_account_status) delete payload.is_login_active;
    }
    if (editing === "banking") {
      if (!permissions.can_edit_banking) {
        delete payload.bank_account;
      } else if (payload.bank_account) {
        const bankName = payload.bank_account.bank_name;
        const accountNumber = payload.bank_account.account_number;
        const legacyBankUnchanged = Boolean(
          client.has_bank_account
          && client.bank_name
          && !isBankName(client.bank_name)
          && bankName === client.bank_name
          && !String(accountNumber || "").trim(),
        );

        if (!legacyBankUnchanged) {
          if (!bankName || !isBankName(bankName)) {
            toast.warning("Select FNB, PB, STD or NB before saving banking details.");
            return;
          }
          if (!client.has_bank_account && !String(accountNumber || "").trim()) {
            toast.warning("Enter the bank account number before creating the banking profile.");
            return;
          }
          if (client.has_bank_account && client.bank_name !== bankName && !String(accountNumber || "").trim()) {
            toast.warning("Changing the bank also requires the matching new account number.");
            return;
          }
          const accountError = bankAccountValidationMessage(bankName, accountNumber);
          if (accountError) {
            toast.warning(accountError);
            return;
          }
          const details = bankDetails(bankName);
          payload.bank_account = {
            ...payload.bank_account,
            bank_name: bankName,
            branch_name: details?.branch ?? DEFAULT_BANK_BRANCH,
            branch_code: details?.code ?? null,
          };
        }
      }
      if (!permissions.can_edit_account_status) delete payload.account_status;
    }
    setSaving(true);
    try {
      const updated = await updateCompanyClientProfile(client.id, payload);
      onUpdated(updated);
      setEditing(null);
      toast.success("Borrower profile updated and audit logged.");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The borrower profile could not be updated."));
    } finally {
      setSaving(false);
    }
  }

  async function submitNationalIdRequest() {
    if (!proposedNationalId.trim() || nationalIdReason.trim().length < 10) {
      toast.warning("Enter the proposed National ID and a clear reason of at least 10 characters.");
      return;
    }
    setIdentityWorking(true);
    try {
      await requestCompanyClientNationalIdChange(client.id, {
        proposed_national_id: proposedNationalId.trim(),
        reason: nationalIdReason.trim(),
      });
      onUpdated(await getCompanyClientProfile(client.id));
      setShowNationalIdRequest(false);
      setProposedNationalId("");
      setNationalIdReason("");
      toast.success("National ID change request created. Borrower and company-owner approvals are required.");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The National ID change request could not be created."));
    } finally {
      setIdentityWorking(false);
    }
  }

  async function ownerDecision(approve: boolean) {
    const request = profile.latest_national_id_change_request;
    if (!request) return;
    if (!approve && !ownerRejectionReason.trim()) {
      toast.warning("Enter a rejection reason first.");
      return;
    }
    setIdentityWorking(true);
    try {
      await decideCompanyClientNationalIdChangeAsOwner(client.id, request.id, {
        approve,
        reason: approve ? null : ownerRejectionReason.trim(),
      });
      onUpdated(await getCompanyClientProfile(client.id));
      setOwnerRejectionReason("");
      toast.success(approve ? "Company-owner approval recorded." : "National ID change request rejected.");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The owner decision could not be recorded."));
    } finally {
      setIdentityWorking(false);
    }
  }

  const identityRequest = profile.latest_national_id_change_request;
  const pendingIdentityRequest = identityRequest?.status === "pending" ? identityRequest : null;
  const draftBankName = draft.bank_account?.bank_name ?? null;
  const draftAccountNumber = draft.bank_account?.account_number ?? null;
  const draftBankError = bankAccountValidationMessage(draftBankName, draftAccountNumber);
  const legacyDraftBank = draftBankName && !isBankName(draftBankName) ? draftBankName : null;

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card className="rounded-2xl shadow-none">
        <CardHeading icon={IdCard} title="Personal profile" editing={editing === "personal"} canEdit={permissions.can_edit_profile} onEdit={() => startEditing("personal")} onCancel={() => setEditing(null)} />
        <CardContent className="pt-0">
          {editing === "personal" ? (
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="First name"><Input value={draft.first_name ?? ""} onChange={(event) => setDraft((current) => ({ ...current, first_name: event.target.value }))} /></Field>
                <Field label="Middle name"><Input value={draft.middle_name ?? ""} onChange={(event) => setDraft((current) => ({ ...current, middle_name: event.target.value }))} /></Field>
                <Field label="Last name"><Input value={draft.last_name ?? ""} onChange={(event) => setDraft((current) => ({ ...current, last_name: event.target.value }))} /></Field>
                <Field label="Passport"><Input value={draft.passport_number ?? ""} onChange={(event) => setDraft((current) => ({ ...current, passport_number: event.target.value }))} /></Field>
                <Field label="Date of birth"><Input type="date" value={draft.date_of_birth ?? ""} onChange={(event) => setDraft((current) => ({ ...current, date_of_birth: event.target.value || null }))} /></Field>
                <Field label="Gender"><NativeSelect value={draft.gender ?? ""} onChange={(event) => setDraft((current) => ({ ...current, gender: (event.target.value || null) as CompanyClientProfileUpdate["gender"] }))}><option value="">Not specified</option><option value="male">Male</option><option value="female">Female</option><option value="other">Other</option></NativeSelect></Field>
                <Field label="Marital status"><NativeSelect value={draft.marital_status ?? ""} onChange={(event) => setDraft((current) => ({ ...current, marital_status: (event.target.value || null) as CompanyClientProfileUpdate["marital_status"] }))}><option value="">Not specified</option><option value="single">Single</option><option value="married">Married</option><option value="divorced">Divorced</option><option value="widowed">Widowed</option></NativeSelect></Field>
                <Field label="Nationality"><Input value={draft.nationality ?? ""} onChange={(event) => setDraft((current) => ({ ...current, nationality: event.target.value }))} /></Field>
              </div>
              <LoadingButton className="w-full" loading={saving} loadingText="Saving personal details..." onClick={() => void saveSection()}><Save className="h-4 w-4" />Save personal details</LoadingButton>
            </div>
          ) : (
            <>
              <EditableRow label="First name" value={client.first_name} editable={permissions.can_edit_profile} onEdit={() => startEditing("personal")} />
              <EditableRow label="Middle name" value={client.middle_name} editable={permissions.can_edit_profile} onEdit={() => startEditing("personal")} />
              <EditableRow label="Last name" value={client.last_name} editable={permissions.can_edit_profile} onEdit={() => startEditing("personal")} />
              <EditableRow label="National ID" value={client.national_id} editable={permissions.can_request_national_id_change && !pendingIdentityRequest} actionLabel="Request change" onEdit={() => setShowNationalIdRequest((value) => !value)} />
              <EditableRow label="Passport" value={client.passport_number} editable={permissions.can_edit_profile} onEdit={() => startEditing("personal")} />
              <EditableRow label="Date of birth" value={client.date_of_birth ? formatDate(client.date_of_birth) : null} editable={permissions.can_edit_profile} onEdit={() => startEditing("personal")} />
              <EditableRow label="Gender" value={client.gender ? titleCase(client.gender) : null} editable={permissions.can_edit_profile} onEdit={() => startEditing("personal")} />
              <EditableRow label="Marital status" value={client.marital_status ? titleCase(client.marital_status) : null} editable={permissions.can_edit_profile} onEdit={() => startEditing("personal")} />
              <EditableRow label="Nationality" value={client.nationality} editable={permissions.can_edit_profile} onEdit={() => startEditing("personal")} />
            </>
          )}

          {showNationalIdRequest && !pendingIdentityRequest ? (
            <div className="mt-4 space-y-3 rounded-2xl border border-amber-500/30 bg-amber-500/5 p-4">
              <div className="flex items-start gap-3"><ShieldCheck className="mt-0.5 h-5 w-5 text-amber-600" /><div><p className="font-black">Protected National ID change</p><p className="text-xs leading-5 text-muted-foreground">The change is applied only after the borrower and an active company owner approve it. Identity verification will be reset.</p></div></div>
              <Field label="Proposed National ID"><Input value={proposedNationalId} onChange={(event) => setProposedNationalId(event.target.value)} /></Field>
              <Field label="Reason for change"><Textarea rows={3} value={nationalIdReason} onChange={(event) => setNationalIdReason(event.target.value)} placeholder="Explain the correction and the evidence checked" /></Field>
              <div className="flex justify-end gap-2"><Button variant="outline" onClick={() => setShowNationalIdRequest(false)}>Cancel</Button><LoadingButton loading={identityWorking} loadingText="Submitting..." onClick={() => void submitNationalIdRequest()}><ShieldCheck className="h-4 w-4" />Request dual approval</LoadingButton></div>
            </div>
          ) : null}

          {identityRequest ? (
            <div className={`mt-4 rounded-2xl border p-4 ${pendingIdentityRequest ? "border-primary/30 bg-primary/5" : "bg-muted/20"}`}>
              <div className="flex flex-wrap items-center justify-between gap-2"><div><p className="font-black">National ID request {identityRequest.reference}</p><p className="text-xs text-muted-foreground">{identityRequest.current_national_id || "Not recorded"} → {identityRequest.proposed_national_id}</p></div><Badge variant={identityRequest.status === "rejected" ? "destructive" : "outline"}>{titleCase(identityRequest.status)}</Badge></div>
              <p className="mt-3 text-sm leading-6">{identityRequest.reason}</p>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <div className="flex items-center gap-2 rounded-xl border bg-background p-3 text-xs"><BadgeCheck className={`h-4 w-4 ${identityRequest.borrower_approved_at ? "text-emerald-600" : "text-muted-foreground"}`} /><span>Borrower: {identityRequest.borrower_approved_at ? `Approved ${formatDateTime(identityRequest.borrower_approved_at)}` : "Awaiting approval"}</span></div>
                <div className="flex items-center gap-2 rounded-xl border bg-background p-3 text-xs"><ShieldCheck className={`h-4 w-4 ${identityRequest.company_owner_approved_at ? "text-emerald-600" : "text-muted-foreground"}`} /><span>Company owner: {identityRequest.company_owner_approved_at ? `Approved ${formatDateTime(identityRequest.company_owner_approved_at)}` : "Awaiting approval"}</span></div>
              </div>
              {pendingIdentityRequest && permissions.can_approve_national_id_change && !identityRequest.company_owner_approved_at ? (
                <div className="mt-3 space-y-2">
                  <Textarea rows={2} value={ownerRejectionReason} onChange={(event) => setOwnerRejectionReason(event.target.value)} placeholder="Rejection reason (required only when rejecting)" />
                  <div className="flex flex-wrap justify-end gap-2"><LoadingButton variant="outline" loading={identityWorking} onClick={() => void ownerDecision(false)}><CircleX className="h-4 w-4" />Reject</LoadingButton><LoadingButton loading={identityWorking} onClick={() => void ownerDecision(true)}><Check className="h-4 w-4" />Approve as company owner</LoadingButton></div>
                </div>
              ) : null}
              {identityRequest.rejection_reason ? <p className="mt-3 text-xs text-destructive">Rejection: {identityRequest.rejection_reason}</p> : null}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card className="rounded-2xl shadow-none">
        <CardHeading icon={MapPin} title="Contact & address" editing={editing === "contact"} canEdit={permissions.can_edit_profile || permissions.can_edit_contact} onEdit={() => startEditing("contact")} onCancel={() => setEditing(null)} />
        <CardContent className="pt-0">
          {editing === "contact" ? (
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Phone"><Input disabled={!permissions.can_edit_contact} value={draft.phone ?? ""} onChange={(event) => setDraft((current) => ({ ...current, phone: event.target.value }))} /></Field>
                <Field label="Email"><Input disabled={!permissions.can_edit_contact} type="email" value={draft.email ?? ""} onChange={(event) => setDraft((current) => ({ ...current, email: event.target.value }))} /></Field>
                <Field label="District"><Input disabled={!permissions.can_edit_profile} value={draft.district ?? ""} onChange={(event) => setDraft((current) => ({ ...current, district: event.target.value }))} /></Field>
                <Field label="Town / village"><Input disabled={!permissions.can_edit_profile} value={draft.town_or_village ?? ""} onChange={(event) => setDraft((current) => ({ ...current, town_or_village: event.target.value }))} /></Field>
                <Field label="Physical address" className="sm:col-span-2"><Textarea disabled={!permissions.can_edit_profile} rows={3} value={draft.physical_address ?? ""} onChange={(event) => setDraft((current) => ({ ...current, physical_address: event.target.value }))} /></Field>
                {permissions.can_edit_account_status ? <label className="flex items-center gap-3 rounded-xl border p-3 sm:col-span-2"><Checkbox checked={draft.is_login_active === true} onCheckedChange={(checked) => setDraft((current) => ({ ...current, is_login_active: checked === true }))} /><span className="text-sm font-bold">Borrower login access active</span></label> : null}
              </div>
              <LoadingButton className="w-full" loading={saving} loadingText="Saving contact details..." onClick={() => void saveSection()}><Save className="h-4 w-4" />Save contact and address</LoadingButton>
            </div>
          ) : (
            <>
              <EditableRow label="Phone" value={client.phone} editable={permissions.can_edit_contact} onEdit={() => startEditing("contact")} />
              <EditableRow label="Email" value={client.email} editable={permissions.can_edit_contact} onEdit={() => startEditing("contact")} />
              <EditableRow label="District" value={client.district} editable={permissions.can_edit_profile} onEdit={() => startEditing("contact")} />
              <EditableRow label="Town / village" value={client.town_or_village} editable={permissions.can_edit_profile} onEdit={() => startEditing("contact")} />
              <EditableRow label="Physical address" value={[client.physical_address, client.town_or_village, client.district].filter(Boolean).join(", ")} editable={permissions.can_edit_profile} onEdit={() => startEditing("contact")} />
              <EditableRow label="Login access" value={client.is_login_active ? "Active" : "Disabled"} editable={permissions.can_edit_account_status} onEdit={() => startEditing("contact")} />
            </>
          )}
        </CardContent>
      </Card>

      <Card className="rounded-2xl shadow-none">
        <CardHeading icon={BriefcaseBusiness} title="Employment & affordability" editing={editing === "employment"} canEdit={permissions.can_edit_profile} onEdit={() => startEditing("employment")} onCancel={() => setEditing(null)} />
        <CardContent className="pt-0">
          {editing === "employment" ? (
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Employment"><NativeSelect value={draft.employment_status ?? "employed"} onChange={(event) => setDraft((current) => ({ ...current, employment_status: event.target.value as CompanyClientProfileUpdate["employment_status"] }))}><option value="employed">Employed</option><option value="self_employed">Self-employed</option><option value="unemployed">Unemployed</option><option value="student">Student</option><option value="pensioner">Pensioner</option></NativeSelect></Field>
                <Field label="Employer"><Input value={draft.employer_name ?? ""} onChange={(event) => setDraft((current) => ({ ...current, employer_name: event.target.value }))} /></Field>
                <Field label="Job title"><Input value={draft.job_title ?? ""} onChange={(event) => setDraft((current) => ({ ...current, job_title: event.target.value }))} /></Field>
                <Field label="Monthly income"><Input type="number" min="0" step="0.01" value={draft.monthly_income ?? ""} onChange={(event) => setDraft((current) => ({ ...current, monthly_income: event.target.value === "" ? null : Number(event.target.value) }))} /></Field>
                <Field label="Salary date"><Input value={draft.salary_date ?? ""} onChange={(event) => setDraft((current) => ({ ...current, salary_date: event.target.value }))} placeholder="e.g. 25 or 2026-08-25" /></Field>
                <Alert className="sm:col-span-2"><Landmark className="h-4 w-4" /><AlertTitle>External loans are tracked separately</AlertTitle><AlertDescription>Use Payments & loans to add, review or record payments against each external obligation. This prevents a single total from losing the installment history.</AlertDescription></Alert>
              </div>
              <LoadingButton className="w-full" loading={saving} loadingText="Saving employment details..." onClick={() => void saveSection()}><Save className="h-4 w-4" />Save employment details</LoadingButton>
            </div>
          ) : (
            <>
              <EditableRow label="Employment" value={titleCase(client.employment_status)} editable={permissions.can_edit_profile} onEdit={() => startEditing("employment")} />
              <EditableRow label="Employer" value={client.employer_name} editable={permissions.can_edit_profile} onEdit={() => startEditing("employment")} />
              <EditableRow label="Job title" value={client.job_title} editable={permissions.can_edit_profile} onEdit={() => startEditing("employment")} />
              <EditableRow label="Monthly income" value={client.monthly_income === null ? null : formatMoney(client.monthly_income)} editable={permissions.can_edit_profile} onEdit={() => startEditing("employment")} />
              <EditableRow label="Salary date" value={client.salary_date} editable={permissions.can_edit_profile} onEdit={() => startEditing("employment")} />
              <EditableRow label="Next payday" value={client.next_salary_pay_date ? formatDate(client.next_salary_pay_date) : null} />
              <EditableRow label="Tracked external debt" value={client.has_existing_loans ? formatMoney(client.existing_loan_total) : "None recorded"} />
            </>
          )}
        </CardContent>
      </Card>

      <Card className="rounded-2xl shadow-none">
        <CardHeading icon={Landmark} title="Banking & company account" editing={editing === "banking"} canEdit={permissions.can_edit_banking || permissions.can_edit_account_status} onEdit={() => startEditing("banking")} onCancel={() => setEditing(null)} />
        <CardContent className="pt-0">
          {editing === "banking" ? (
            <div className="space-y-4">
              {permissions.can_edit_banking ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="Account holder"><Input value={draft.bank_account?.account_holder ?? ""} onChange={(event) => setDraft((current) => ({ ...current, bank_account: { ...(current.bank_account ?? {}), account_holder: event.target.value } }))} /></Field>
                  <Field label="Bank">
                    <NativeSelect
                      value={draft.bank_account?.bank_name ?? ""}
                      onChange={(event) => {
                        const bankName = event.target.value;
                        const details = bankDetails(bankName);
                        setDraft((current) => ({
                          ...current,
                          bank_account: {
                            ...(current.bank_account ?? {}),
                            bank_name: details?.name ?? null,
                            branch_name: details?.branch ?? DEFAULT_BANK_BRANCH,
                            branch_code: details?.code ?? null,
                          },
                        }));
                      }}
                    >
                      <option value="">Select bank</option>
                      {legacyDraftBank ? <option value={legacyDraftBank}>Legacy: {legacyDraftBank}</option> : null}
                      {BANK_NAMES.map((bankName) => <option key={bankName} value={bankName}>{bankName}</option>)}
                    </NativeSelect>
                  </Field>
                  <Field label="Branch"><Input value={draft.bank_account?.branch_name ?? DEFAULT_BANK_BRANCH} readOnly /></Field>
                  <Field label="Bank code"><Input value={draft.bank_account?.branch_code ?? ""} readOnly placeholder="Select a bank" /></Field>
                  <Field label="Account type"><Input value={draft.bank_account?.account_type ?? "savings"} onChange={(event) => setDraft((current) => ({ ...current, bank_account: { ...(current.bank_account ?? {}), account_type: event.target.value } }))} /></Field>
                  <Field label="Currency"><Input maxLength={3} value={draft.bank_account?.currency ?? "LSL"} onChange={(event) => setDraft((current) => ({ ...current, bank_account: { ...(current.bank_account ?? {}), currency: event.target.value.toUpperCase() } }))} /></Field>
                  <Field label={client.has_bank_account ? "New account number (leave blank to keep current)" : "Account number"} className="sm:col-span-2">
                    <Input
                      autoComplete="off"
                      inputMode="numeric"
                      value={draft.bank_account?.account_number ?? ""}
                      aria-invalid={draftBankError ? true : undefined}
                      onChange={(event) => setDraft((current) => ({ ...current, bank_account: { ...(current.bank_account ?? {}), account_number: event.target.value } }))}
                    />
                    <p className="text-xs text-muted-foreground">
                      {legacyDraftBank
                        ? "Historical bank remains unchanged until you select FNB, PB, STD or NB and enter a matching new account number."
                        : bankAccountPrefixHint(draftBankName)}
                    </p>
                    {draftBankError ? <p className="text-xs font-semibold text-destructive">{draftBankError}</p> : null}
                  </Field>
                  <label className="flex items-center gap-3 rounded-xl border p-3 sm:col-span-2"><Checkbox checked={draft.bank_account?.salary_account === true} onCheckedChange={(checked) => setDraft((current) => ({ ...current, bank_account: { ...(current.bank_account ?? {}), salary_account: checked === true } }))} /><span className="text-sm font-bold">Salary is paid into this account</span></label>
                </div>
              ) : null}
              {permissions.can_edit_account_status ? <Field label="Company client status"><NativeSelect value={draft.account_status ?? "active"} onChange={(event) => setDraft((current) => ({ ...current, account_status: event.target.value as CompanyClientProfileUpdate["account_status"] }))}><option value="active">Active</option><option value="inactive">Inactive</option><option value="suspended">Suspended</option><option value="closed">Closed</option></NativeSelect></Field> : null}
              <Alert><ShieldCheck /><AlertTitle>Bank verification reset</AlertTitle><AlertDescription>Changing banking details marks the bank profile unverified until the company completes verification again.</AlertDescription></Alert>
              <LoadingButton className="w-full" loading={saving} loadingText="Saving banking details..." onClick={() => void saveSection()}><Save className="h-4 w-4" />Save banking and account details</LoadingButton>
            </div>
          ) : (
            <>
              <EditableRow label="Account holder" value={client.bank_account_holder} editable={permissions.can_edit_banking} onEdit={() => startEditing("banking")} />
              <EditableRow label="Bank" value={client.bank_name} editable={permissions.can_edit_banking} onEdit={() => startEditing("banking")} />
              <EditableRow label="Branch" value={[client.bank_branch_name, client.bank_branch_code].filter(Boolean).join(" · ")} editable={permissions.can_edit_banking} onEdit={() => startEditing("banking")} />
              <EditableRow label="Account" value={client.masked_bank_account} editable={permissions.can_edit_banking} onEdit={() => startEditing("banking")} />
              <EditableRow label="Account type" value={client.bank_account_type ? titleCase(client.bank_account_type) : null} editable={permissions.can_edit_banking} onEdit={() => startEditing("banking")} />
              <EditableRow label="Salary account" value={client.salary_account ? "Yes" : "No"} editable={permissions.can_edit_banking} onEdit={() => startEditing("banking")} />
              <EditableRow label="Bank verification" value={client.bank_verification_status ? titleCase(client.bank_verification_status) : null} />
              <EditableRow label="Client status" value={titleCase(client.status)} editable={permissions.can_edit_account_status} onEdit={() => startEditing("banking")} />
              <EditableRow label="Account opened" value={formatDate(client.created_at)} />
              <EditableRow label="Credit-check consent" value={client.consent_to_credit_checks ? "Recorded" : "Not recorded"} />
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}