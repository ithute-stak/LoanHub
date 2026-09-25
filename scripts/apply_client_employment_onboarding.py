from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one match in {path}, found {count}: {old[:100]!r}")
    p.write_text(text.replace(old, new, 1))


replace_once(
    "apps/frontend/types/companyClient.ts",
    '    employment_status: "employed" | "self_employed" | "unemployed" | "student" | "pensioner";\n    employer_name?: string | null;',
    '    employment_status: "employed" | "self_employed" | "unemployed" | "student" | "pensioner";\n    employment_type?: string | null;\n    cdas_employee_number?: string | null;\n    employer_name?: string | null;',
)

Path("apps/frontend/components/clients/employer-group-registration-field.tsx").write_text(r'''"use client";

import { useEffect, useMemo, useState } from "react";

import { listEmployerGroups } from "@/api/employerGroups";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SuggestionSearch } from "@/components/ui/suggestion-search";
import type { EmployerGroup, EmployerGroupCreate } from "@/types/employerGroup";

type EmploymentStatus = "employed" | "self_employed" | "unemployed" | "student" | "pensioner";

type Selection = {
  employer_group_id?: string | null;
  employer_name?: string | null;
  new_employer_group?: EmployerGroupCreate | null;
  employment_type?: string | null;
  cdas_employee_number?: string | null;
};

type Props = {
  employmentStatus: EmploymentStatus;
  employmentType?: string | null;
  cdasEmployeeNumber?: string | null;
  employerGroupId?: string | null;
  employerName?: string | null;
  newEmployerGroup?: EmployerGroupCreate | null;
  onChange: (selection: Selection) => void;
  required?: boolean;
};

const CREATE_PREFIX = "__create_work_group__:";

function display(group: Pick<EmployerGroup, "code" | "name">): string {
  return `${group.code} — ${group.name}`;
}

function workGroupCode(name: string): string {
  const code = name
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);
  return code || "WORK-GROUP";
}

export function EmployerGroupRegistrationField({
  employmentStatus,
  employmentType,
  cdasEmployeeNumber,
  employerGroupId,
  employerName,
  newEmployerGroup,
  onChange,
  required = false,
}: Props) {
  const [groups, setGroups] = useState<EmployerGroup[]>([]);
  const [search, setSearch] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void listEmployerGroups()
      .then((rows) => {
        if (!cancelled) {
          setGroups(rows);
          setLoadError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setLoadError("Work groups could not be loaded. Try again.");
      });
    return () => { cancelled = true; };
  }, []);

  const selected = useMemo(
    () => groups.find((group) => group.id === employerGroupId) ?? null,
    [employerGroupId, groups],
  );

  useEffect(() => {
    if (employmentStatus !== "employed") {
      setSearch("");
      return;
    }
    if (selected) {
      setSearch(display(selected));
      return;
    }
    if (newEmployerGroup) {
      setSearch(display(newEmployerGroup));
      return;
    }
    setSearch(employerName ?? "");
  }, [employerName, employmentStatus, newEmployerGroup, selected]);

  const suggestions = useMemo(() => {
    const existing = groups.map((group) => ({
      value: group.id,
      label: display(group),
      description: "Existing work group",
      keywords: [group.code, group.name],
    }));
    const query = search.trim();
    if (query.length < 2 || selected || newEmployerGroup) return existing;
    const normalized = query.toLocaleLowerCase();
    const exact = groups.some((group) =>
      group.code.toLocaleLowerCase() === normalized
      || group.name.toLocaleLowerCase() === normalized
      || display(group).toLocaleLowerCase() === normalized,
    );
    if (exact) return existing;
    return [...existing, {
      value: `${CREATE_PREFIX}${query}`,
      label: `Add “${query}”`,
      description: "Create this work group when the borrower account is opened",
      keywords: [query, "add", "new", "work group"],
    }];
  }, [groups, newEmployerGroup, search, selected]);

  if (employmentStatus === "self_employed") {
    return (
      <div className="rounded-2xl border border-border/50 bg-muted/[0.22] p-3.5">
        <div className="mb-2.5 space-y-1">
          <Label className="text-xs font-black tracking-[0.01em] text-foreground/90">
            Work type / business activity<span className="ml-1 text-destructive">*</span>
          </Label>
          <p className="text-[11px] leading-4 text-muted-foreground/90">
            Describe the borrower&apos;s trade, profession or main business activity. A work group is not required for self-employed clients.
          </p>
        </div>
        <Input
          className="h-11"
          value={employmentType ?? ""}
          onChange={(event) => onChange({
            employment_type: event.target.value,
            employer_group_id: null,
            employer_name: null,
            new_employer_group: null,
            cdas_employee_number: null,
          })}
          placeholder="e.g. Retail shop, construction, farming, consulting"
        />
      </div>
    );
  }

  if (employmentStatus !== "employed") {
    return (
      <div className="rounded-2xl border border-dashed bg-muted/15 p-4 text-xs leading-5 text-muted-foreground">
        No employer or work-group details are required for this employment status.
      </div>
    );
  }

  const governmentEmployee = employmentType === "government";

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-border/50 bg-muted/[0.22] p-3.5">
          <div className="mb-2.5 space-y-1">
            <Label className="text-xs font-black tracking-[0.01em] text-foreground/90">
              Employment type<span className="ml-1 text-destructive">*</span>
            </Label>
            <p className="text-[11px] leading-4 text-muted-foreground/90">
              Government employment enables capture of the payroll identity used for CDAS verification.
            </p>
          </div>
          <Select
            value={employmentType ?? ""}
            onValueChange={(value) => onChange({
              employment_type: value,
              cdas_employee_number: value === "government" ? cdasEmployeeNumber ?? null : null,
            })}
          >
            <SelectTrigger className="h-11 w-full"><SelectValue placeholder="Select employment type" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="government">Government</SelectItem>
              <SelectItem value="private">Private sector</SelectItem>
              <SelectItem value="ngo">NGO / non-profit</SelectItem>
              <SelectItem value="other">Other employer</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {governmentEmployee ? (
          <div className="rounded-2xl border border-primary/20 bg-primary/[0.04] p-3.5">
            <div className="mb-2.5 space-y-1">
              <Label className="text-xs font-black tracking-[0.01em] text-foreground/90">Employee No.</Label>
              <p className="text-[11px] leading-4 text-muted-foreground/90">
                Optional at registration. This prepares an unverified CDAS payroll profile; CDAS is not selected automatically as the loan collection method.
              </p>
            </div>
            <Input
              className="h-11"
              value={cdasEmployeeNumber ?? ""}
              onChange={(event) => onChange({ cdas_employee_number: event.target.value })}
              placeholder="Government employee / payroll number"
              autoComplete="off"
            />
          </div>
        ) : null}
      </div>

      <div className="rounded-2xl border border-border/50 bg-muted/[0.22] p-3.5">
        <div className="mb-2.5 space-y-1">
          <Label className="text-xs font-black tracking-[0.01em] text-foreground/90">
            Work group{required ? <span className="ml-1 text-destructive">*</span> : null}
          </Label>
          <p className="text-[11px] leading-4 text-muted-foreground/90">
            Search existing work groups. If the borrower&apos;s group is missing, type its name and choose the Add option in the popover.
          </p>
        </div>
        <SuggestionSearch
          value={search}
          onValueChange={(value) => {
            setSearch(value);
            onChange({ employer_group_id: null, employer_name: value.trim() || null, new_employer_group: null });
          }}
          suggestions={suggestions}
          placeholder="Search L/GOV, LMPS, ministry, company…"
          emptyMessage="Type at least two characters to add a new work group."
          suggestionLabel="Work groups"
          maxSuggestions={14}
          showSuggestionsOnFocus
          onSuggestionSelect={(suggestion) => {
            if (suggestion.value.startsWith(CREATE_PREFIX)) {
              const name = suggestion.value.slice(CREATE_PREFIX.length).trim();
              const staged = { code: workGroupCode(name), name };
              setSearch(display(staged));
              onChange({ employer_group_id: null, employer_name: name, new_employer_group: staged });
              return;
            }
            const group = groups.find((row) => row.id === suggestion.value);
            if (!group) return;
            setSearch(display(group));
            onChange({ employer_group_id: group.id, employer_name: group.name, new_employer_group: null });
          }}
        />
        {newEmployerGroup ? (
          <p className="mt-2 text-xs font-semibold text-primary">
            New work group staged: {newEmployerGroup.code} — {newEmployerGroup.name}
          </p>
        ) : null}
        {loadError ? <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">{loadError}</p> : null}
      </div>
    </div>
  );
}
''')

page = "apps/frontend/app/(dashboard)/company/clients/page.tsx"
replace_once(page, '  employment_status: "employed",\n  employer_name: null,', '  employment_status: "employed",\n  employment_type: null,\n  cdas_employee_number: null,\n  employer_name: null,')
replace_once(page, '      if (clientForm.employment_status === "employed" && !clientForm.employer_group_id && !clientForm.new_employer_group) {\n        errors.push("Select the borrower’s employer/work group or add a new group.");\n      }', '      if (clientForm.employment_status === "employed" && !clientForm.employment_type) {\n        errors.push("Select whether the borrower works for government, the private sector, an NGO or another employer.");\n      }\n      if (clientForm.employment_status === "employed" && !clientForm.employer_group_id && !clientForm.new_employer_group) {\n        errors.push("Select the borrower’s employer/work group or add a new group.");\n      }\n      if (clientForm.employment_status === "self_employed" && !String(clientForm.employment_type ?? "").trim()) {\n        errors.push("Enter the self-employed borrower’s work type or main business activity.");\n      }')
replace_once(page, '        employer_name: optional(clientForm.employer_name),\n        job_title: optional(clientForm.job_title),', '        employment_type: optional(clientForm.employment_type),\n        cdas_employee_number: clientForm.employment_status === "employed" && clientForm.employment_type === "government"\n          ? optional(clientForm.cdas_employee_number)\n          : null,\n        employer_group_id: clientForm.employment_status === "employed" ? clientForm.employer_group_id : null,\n        new_employer_group: clientForm.employment_status === "employed" ? clientForm.new_employer_group : null,\n        employer_name: clientForm.employment_status === "employed" ? optional(clientForm.employer_name) : null,\n        job_title: ["employed", "self_employed"].includes(clientForm.employment_status) ? optional(clientForm.job_title) : null,')
replace_once(page, '        contentClassName="w-[calc(100%-0.75rem)] sm:max-w-6xl"', '        contentClassName="w-[calc(100%-0.75rem)] max-w-[calc(100%-0.75rem)] sm:w-[85vw] sm:max-w-[85vw]"')
replace_once(page, '<Select value={clientForm.employment_status} onValueChange={(value) => updateClient("employment_status", value as AssistedCompanyClientCreate["employment_status"])}>', '<Select value={clientForm.employment_status} onValueChange={(value) => {\n                            const employmentStatus = value as AssistedCompanyClientCreate["employment_status"];\n                            setClientStepErrors([]);\n                            setClientForm((current) => ({\n                              ...current,\n                              employment_status: employmentStatus,\n                              employment_type: null,\n                              cdas_employee_number: null,\n                              employer_group_id: null,\n                              employer_name: null,\n                              new_employer_group: null,\n                              job_title: ["employed", "self_employed"].includes(employmentStatus) ? current.job_title : null,\n                            }));\n                          }}>')
replace_once(page, '                          <EmployerGroupRegistrationField\n                            employerGroupId={clientForm.employer_group_id}\n                            employerName={clientForm.employer_name}\n                            newEmployerGroup={clientForm.new_employer_group}\n                            required={clientForm.employment_status === "employed"}', '                          <EmployerGroupRegistrationField\n                            employmentStatus={clientForm.employment_status}\n                            employmentType={clientForm.employment_type}\n                            cdasEmployeeNumber={clientForm.cdas_employee_number}\n                            employerGroupId={clientForm.employer_group_id}\n                            employerName={clientForm.employer_name}\n                            newEmployerGroup={clientForm.new_employer_group}\n                            required={clientForm.employment_status === "employed"}')
replace_once(page, '                        <Field label="Job title">\n                          <Input className="h-11" value={clientForm.job_title ?? ""} onChange={(event) => updateClient("job_title", event.target.value)} />\n                        </Field>', '                        {["employed", "self_employed"].includes(clientForm.employment_status) ? (\n                          <Field label={clientForm.employment_status === "self_employed" ? "Role / trade" : "Job title"}>\n                            <Input className="h-11" value={clientForm.job_title ?? ""} onChange={(event) => updateClient("job_title", event.target.value)} />\n                          </Field>\n                        ) : null}')
replace_once(page, '                            <ReviewItem label="Employment" value={titleCase(clientForm.employment_status)} />\n                            <ReviewItem label="Employer / work group" value={clientForm.new_employer_group ? `${clientForm.new_employer_group.code} — ${clientForm.new_employer_group.name}` : (clientForm.employer_name || "Not supplied")} />\n                            <ReviewItem label="Income / pay day" value={clientForm.income_day ? `Day ${clientForm.income_day} of each month` : "Not supplied"} />', '                            <ReviewItem label="Employment" value={titleCase(clientForm.employment_status)} />\n                            {clientForm.employment_status === "employed" ? (\n                              <>\n                                <ReviewItem label="Employment type" value={clientForm.employment_type ? titleCase(clientForm.employment_type) : "Not supplied"} />\n                                <ReviewItem label="Employer / work group" value={clientForm.new_employer_group ? `${clientForm.new_employer_group.code} — ${clientForm.new_employer_group.name}` : (clientForm.employer_name || "Not supplied")} />\n                                {clientForm.employment_type === "government" ? <ReviewItem label="Employee No." value={clientForm.cdas_employee_number || "Not supplied — CDAS cannot be enabled yet"} /> : null}\n                              </>\n                            ) : clientForm.employment_status === "self_employed" ? (\n                              <ReviewItem label="Work type" value={clientForm.employment_type || "Not supplied"} />\n                            ) : null}\n                            {["employed", "self_employed"].includes(clientForm.employment_status) ? <ReviewItem label="Job / role" value={clientForm.job_title || "Not supplied"} /> : null}\n                            <ReviewItem label="Income / pay day" value={clientForm.income_day ? `Day ${clientForm.income_day} of each month` : "Not supplied"} />')

replace_once("apps/backend/database/schemas/company_clients.py", '    employment_status: EmploymentStatus\n    employer_name: str | None = Field(default=None, max_length=200)', '    employment_status: EmploymentStatus\n    employment_type: str | None = Field(default=None, max_length=100)\n    cdas_employee_number: str | None = Field(default=None, max_length=100)\n    employer_name: str | None = Field(default=None, max_length=200)')

Path("apps/backend/services/employer_group_service.py").write_text(r'''from __future__ import annotations

import re
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from database.models.employer_group import EmployerGroup
from database.schemas.employer_group import EmployerGroupCreate
from utils.work_group_policy import WORK_GROUP_CODES, WORK_GROUP_POLICY, work_group_policy_for


_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9 /._&-]{0,39}$")


def ensure_central_work_groups(db: Session) -> tuple[int, int]:
    """Persist LoanHub's canonical work-group catalogue idempotently."""
    existing_groups = db.query(EmployerGroup).filter(EmployerGroup.code.in_(WORK_GROUP_CODES)).all()
    groups_by_code = {group.code: group for group in existing_groups}
    created_count = 0
    updated_count = 0
    for policy in WORK_GROUP_POLICY:
        group = groups_by_code.get(policy.code)
        if group is None:
            group = EmployerGroup(code=policy.code, name=policy.name, is_active=True)
            db.add(group)
            groups_by_code[policy.code] = group
            created_count += 1
            continue
        changed = False
        if group.name != policy.name:
            group.name = policy.name
            changed = True
        if not group.is_active:
            group.is_active = True
            changed = True
        if changed:
            updated_count += 1
    if created_count or updated_count:
        db.commit()
    return created_count, updated_count


def normalize_employer_group_code(value: str) -> str:
    code = re.sub(r"\s+", " ", str(value or "").strip()).upper()
    if not code or not _CODE_PATTERN.fullmatch(code):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Work-group code must contain letters, numbers or the supported separators / . _ & - and be at most 40 characters.")
    policy = work_group_policy_for(code)
    return policy.code if policy is not None else code


def normalize_employer_group_name(value: str) -> str:
    name = re.sub(r"\s+", " ", str(value or "").strip())
    if len(name) < 2 or len(name) > 200:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Work-group name must be between 2 and 200 characters.")
    return name


def resolve_employer_group(db: Session, *, employer_group_id: UUID | None = None, new_employer_group: EmployerGroupCreate | None = None) -> EmployerGroup | None:
    """Resolve an active work group, creating a new custom group when requested."""
    if employer_group_id and new_employer_group is not None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Select one work group, not both.")
    if employer_group_id:
        group = db.query(EmployerGroup).filter(EmployerGroup.id == employer_group_id, EmployerGroup.is_active.is_(True)).first()
        if group is None:
            raise HTTPException(status_code=422, detail="The selected work group is not available.")
        return group
    if new_employer_group is None:
        return None
    name = normalize_employer_group_name(new_employer_group.name)
    central_policy = work_group_policy_for(new_employer_group.code) or work_group_policy_for(name)
    code = central_policy.code if central_policy is not None else normalize_employer_group_code(new_employer_group.code)
    existing = db.query(EmployerGroup).filter(EmployerGroup.code == code).first()
    if existing is not None:
        if central_policy is not None:
            existing.name = central_policy.name
        if not existing.is_active:
            existing.is_active = True
        db.flush()
        return existing
    if central_policy is not None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Central work group {central_policy.code} is not available. Contact a LoanHub administrator.")
    group = EmployerGroup(code=code, name=name, is_active=True)
    db.add(group)
    db.flush()
    return group
''')

Path("apps/backend/routers/employer_groups.py").write_text(r'''from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database.models.employer_group import EmployerGroup
from database.schemas.employer_group import EmployerGroupRead
from database.session import get_db
from utils.work_group_policy import work_group_sort_key

router = APIRouter(prefix="/employer-groups", tags=["Employer Groups"])

@router.get("", response_model=list[EmployerGroupRead])
def list_employer_groups(search: str | None = Query(default=None, max_length=120), limit: int = Query(default=250, ge=1, le=500), db: Session = Depends(get_db)):
    query = db.query(EmployerGroup).filter(EmployerGroup.is_active.is_(True))
    term = str(search or "").strip()
    if term:
        value = f"%{term}%"
        query = query.filter(or_(EmployerGroup.code.ilike(value), EmployerGroup.name.ilike(value)))
    groups = query.all()
    groups.sort(key=lambda group: (work_group_sort_key(group.code), str(group.name).casefold(), str(group.code).casefold()))
    return groups[:limit]
''')

service = "apps/backend/services/company_client_service.py"
replace_once(service, 'from database.models.enums import LoanStatus, UserRole\nfrom database.models.origination import (', 'from database.models.enums import LoanStatus, UserRole\nfrom database.models.lending_operations import CDASPayrollProfile\nfrom database.models.origination import (')
replace_once(service, 'def clean_optional(value: str | None) -> str | None:\n    if value is None:\n        return None\n    cleaned = str(value).strip()\n    return cleaned or None\n\n\n', '''def clean_optional(value: str | None) -> str | None:\n    if value is None:\n        return None\n    cleaned = str(value).strip()\n    return cleaned or None\n\n\ndef _employment_status_value(value) -> str:\n    return str(getattr(value, "value", value) or "").strip().lower()\n\n\ndef _save_assisted_cdas_payroll_profile(\n    db: Session,\n    *,\n    borrower: Borrower,\n    company_id: UUID,\n    branch_id: UUID | None,\n    employee_number: str | None,\n    employer_group,\n) -> CDASPayrollProfile | None:\n    """Capture payroll identity for later CDAS verification without enabling CDAS on a loan."""\n    number = clean_optional(employee_number)\n    if not number:\n        return None\n    duplicate = (\n        db.query(CDASPayrollProfile)\n        .filter(\n            CDASPayrollProfile.company_id == company_id,\n            func.lower(func.trim(CDASPayrollProfile.employee_number)) == number.casefold(),\n            CDASPayrollProfile.borrower_id != borrower.id,\n        )\n        .first()\n    )\n    if duplicate is not None:\n        raise HTTPException(status_code=409, detail="This CDAS employee number is already linked to another borrower in the active company.")\n    profile = (\n        db.query(CDASPayrollProfile)\n        .filter(CDASPayrollProfile.company_id == company_id, CDASPayrollProfile.borrower_id == borrower.id)\n        .first()\n    )\n    group_code = clean_optional(getattr(employer_group, "code", None))\n    group_name = clean_optional(getattr(employer_group, "name", None))\n    if profile is None:\n        profile = CDASPayrollProfile(\n            company_id=company_id, borrower_id=borrower.id, branch_id=branch_id, employee_number=number,\n            payroll_group=group_code, ministry_department=group_name, employment_status="active", verified=False,\n            verification_notes="Captured during assisted borrower registration; CDAS verification is required before deductions.",\n        )\n        db.add(profile)\n    else:\n        changed = (str(profile.employee_number or "").strip().casefold() != number.casefold() or (profile.payroll_group or None) != group_code or (profile.ministry_department or None) != group_name)\n        profile.branch_id = branch_id\n        profile.employee_number = number\n        profile.payroll_group = group_code\n        profile.ministry_department = group_name\n        profile.employment_status = "active"\n        if changed:\n            profile.verified = False\n            profile.verified_at = None\n            profile.verified_by_user_id = None\n            profile.verification_reference = None\n            profile.verification_notes = "Payroll identity updated during assisted borrower registration; CDAS re-verification is required."\n    db.flush()\n    return profile\n\n\n''')
replace_once(service, '    fee_config = active_company_account_opening_fee_configuration(\n        db,\n        company_id=context.company_id,\n    )\n\n    existing_person = find_person_by_national_id(db, national_id)', '    fee_config = active_company_account_opening_fee_configuration(\n        db,\n        company_id=context.company_id,\n    )\n    employment_status_value = _employment_status_value(payload.employment_status)\n    is_employed = employment_status_value == "employed"\n    is_self_employed = employment_status_value == "self_employed"\n    employment_type = clean_optional(getattr(payload, "employment_type", None))\n    if is_employed and employment_type:\n        employment_type = employment_type.lower()\n    elif not is_self_employed:\n        employment_type = None\n\n    existing_person = find_person_by_national_id(db, national_id)')
old_resolve = '''        employer_group = resolve_employer_group(\n            db,\n            employer_group_id=payload.employer_group_id,\n            new_employer_group=payload.new_employer_group,\n        )'''
new_resolve = '''        employer_group = (\n            resolve_employer_group(\n                db,\n                employer_group_id=payload.employer_group_id,\n                new_employer_group=payload.new_employer_group,\n            )\n            if is_employed\n            else None\n        )'''
p = Path(service)
text = p.read_text()
if text.count(old_resolve) != 2:
    raise SystemExit(f"Expected two employer-group resolution blocks, found {text.count(old_resolve)}")
p.write_text(text.replace(old_resolve, new_resolve))
replace_once(service, '        borrower.employment_status = payload.employment_status\n        borrower.employer_group_id = employer_group.id if employer_group is not None else None\n        borrower.employer_name = (\n            employer_group.name if employer_group is not None else clean_optional(payload.employer_name)\n        )\n        borrower.income_day = payload.income_day\n        borrower.job_title = clean_optional(payload.job_title)', '        borrower.employment_status = payload.employment_status\n        borrower.employment_type = employment_type\n        borrower.employer_group_id = employer_group.id if employer_group is not None else None\n        borrower.employer_name = employer_group.name if employer_group is not None else None\n        borrower.income_day = payload.income_day\n        borrower.job_title = clean_optional(payload.job_title) if (is_employed or is_self_employed) else None')
replace_once(service, '            _save_assisted_banking_profile(\n                db,\n                borrower=borrower,\n                company_id=context.company_id,\n                bank_input=payload.bank_account,\n            )\n            return _create_company_borrower_account(', '            _save_assisted_banking_profile(\n                db,\n                borrower=borrower,\n                company_id=context.company_id,\n                bank_input=payload.bank_account,\n            )\n            if is_employed and employment_type == "government":\n                _save_assisted_cdas_payroll_profile(\n                    db, borrower=borrower, company_id=context.company_id, branch_id=branch_id,\n                    employee_number=getattr(payload, "cdas_employee_number", None), employer_group=employer_group,\n                )\n            return _create_company_borrower_account(')
replace_once(service, '        borrower = Borrower(\n            user_id=user.id,\n            employment_status=payload.employment_status,\n            employer_group_id=employer_group.id if employer_group is not None else None,\n            employer_name=(\n                employer_group.name if employer_group is not None else clean_optional(payload.employer_name)\n            ),\n            income_day=payload.income_day,\n            job_title=clean_optional(payload.job_title),', '        borrower = Borrower(\n            user_id=user.id,\n            employment_status=payload.employment_status,\n            employment_type=employment_type,\n            employer_group_id=employer_group.id if employer_group is not None else None,\n            employer_name=employer_group.name if employer_group is not None else None,\n            income_day=payload.income_day,\n            job_title=clean_optional(payload.job_title) if (is_employed or is_self_employed) else None,')
replace_once(service, '        _save_assisted_banking_profile(\n            db,\n            borrower=borrower,\n            company_id=context.company_id,\n            bank_input=payload.bank_account,\n        )\n        return _create_company_borrower_account(', '        _save_assisted_banking_profile(\n            db,\n            borrower=borrower,\n            company_id=context.company_id,\n            bank_input=payload.bank_account,\n        )\n        if is_employed and employment_type == "government":\n            _save_assisted_cdas_payroll_profile(\n                db, borrower=borrower, company_id=context.company_id, branch_id=branch_id,\n                employee_number=getattr(payload, "cdas_employee_number", None), employer_group=employer_group,\n            )\n        return _create_company_borrower_account(')

tests = "apps/backend/tests/test_work_group_policy.py"
replace_once(tests, 'from fastapi import HTTPException\n', '')
replace_once(tests, '''def test_arbitrary_employer_group_code_is_rejected():\n    with pytest.raises(HTTPException) as exc:\n        normalize_employer_group_code("ACME LTD")\n\n    assert exc.value.status_code == 422\n    assert "central work groups" in str(exc.value.detail)\n''', '''@pytest.mark.parametrize(\n    ("raw", "expected"),\n    [("ACME LTD", "ACME LTD"), (" acme   ltd ", "ACME LTD"), ("Ministry-X", "MINISTRY-X")],\n)\ndef test_custom_employer_group_code_is_normalized(raw: str, expected: str):\n    assert normalize_employer_group_code(raw) == expected\n''')

Path(".github/workflows/apply-client-employment-onboarding.yml").unlink(missing_ok=True)
Path("scripts/apply_client_employment_onboarding.py").unlink(missing_ok=True)
