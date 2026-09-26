"use client";

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
  employmentStatus?: EmploymentStatus;
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

function workGroupPlaceholder(employmentType?: string | null): string {
  switch (employmentType) {
    case "government":
      return "Search L/GOV, LMPS, ministry, department…";
    case "private":
      return "Search company or employer group…";
    case "ngo":
      return "Search NGO or organisation…";
    case "other":
      return "Search employer or work group…";
    default:
      return "Choose employer sector first";
  }
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
  const resolvedEmploymentStatus = employmentStatus ?? "employed";
  const enhancedEmploymentFlow = employmentStatus !== undefined;

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
    if (resolvedEmploymentStatus !== "employed") {
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
  }, [employerName, newEmployerGroup, resolvedEmploymentStatus, selected]);

  const suggestions = useMemo(() => {
    const existing = groups.map((group) => ({
      value: group.id,
      label: display(group),
      description: "Existing employer / work group",
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
      description: "Create this employer / work group when the borrower account is opened",
      keywords: [query, "add", "new", "employer", "work group"],
    }];
  }, [groups, newEmployerGroup, search, selected]);

  if (resolvedEmploymentStatus === "self_employed") {
    return (
      <div className="rounded-2xl border border-border/50 bg-muted/[0.22] p-3.5">
        <div className="mb-2.5 space-y-1">
          <Label className="text-xs font-black tracking-[0.01em] text-foreground/90">
            Work type / business activity<span className="ml-1 text-destructive">*</span>
          </Label>
          <p className="text-[11px] leading-4 text-muted-foreground/90">
            Describe the borrower&apos;s trade, profession or main business activity. An employer / work group is not required for self-employed clients.
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
          maxLength={50}
        />
      </div>
    );
  }

  if (resolvedEmploymentStatus !== "employed") {
    return (
      <div className="rounded-2xl border border-dashed bg-muted/15 p-4 text-xs leading-5 text-muted-foreground">
        No employer or work-group details are required for this employment status.
      </div>
    );
  }

  const governmentEmployee = enhancedEmploymentFlow && employmentType === "government";
  const employerSectorChosen = !enhancedEmploymentFlow || Boolean(employmentType);

  return (
    <div className="rounded-2xl border border-border/50 bg-muted/[0.22] p-4">
      {enhancedEmploymentFlow ? (
        <div className="mb-4 space-y-1">
          <Label className="text-sm font-black tracking-[0.01em] text-foreground/90">
            Employer details
          </Label>
          <p className="text-[11px] leading-4 text-muted-foreground/90">
            First classify the employer sector, then select the actual employer / work group. The sector is a category; the work group is the organisation that employs or pays the borrower.
          </p>
        </div>
      ) : null}

      {enhancedEmploymentFlow ? (
        <div className={`grid gap-4 ${governmentEmployee ? "md:grid-cols-2" : "md:grid-cols-1"}`}>
          <div className="space-y-2">
            <div className="space-y-1">
              <Label className="text-xs font-black tracking-[0.01em] text-foreground/90">
                Employer sector<span className="ml-1 text-destructive">*</span>
              </Label>
              <p className="text-[11px] leading-4 text-muted-foreground/90">
                Classify who employs the borrower. Government enables capture of the payroll identity used for CDAS verification.
              </p>
            </div>
            <Select
              value={employmentType ?? ""}
              onValueChange={(value) => {
                setSearch("");
                onChange({
                  employment_type: value,
                  cdas_employee_number: value === "government" ? cdasEmployeeNumber ?? null : null,
                  employer_group_id: null,
                  employer_name: null,
                  new_employer_group: null,
                });
              }}
            >
              <SelectTrigger className="h-11 w-full"><SelectValue placeholder="Select employer sector" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="government">Government</SelectItem>
                <SelectItem value="private">Private company</SelectItem>
                <SelectItem value="ngo">NGO / non-profit</SelectItem>
                <SelectItem value="other">Other organisation</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {governmentEmployee ? (
            <div className="space-y-2 rounded-xl border border-primary/20 bg-primary/[0.04] p-3">
              <div className="space-y-1">
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
      ) : null}

      <div className={enhancedEmploymentFlow ? "mt-4 border-t border-border/50 pt-4" : ""}>
        <div className="mb-2.5 space-y-1">
          <Label className="text-xs font-black tracking-[0.01em] text-foreground/90">
            Employer / work group{required ? <span className="ml-1 text-destructive">*</span> : null}
          </Label>
          <p className="text-[11px] leading-4 text-muted-foreground/90">
            {employerSectorChosen
              ? "Select the actual organisation that employs or pays the borrower. Search the existing list, or type a missing employer and choose Add."
              : "Choose the employer sector above first. The employer / work group search will then become available."}
          </p>
        </div>
        <SuggestionSearch
          value={search}
          onValueChange={(value) => {
            setSearch(value);
            onChange({ employer_group_id: null, employer_name: value.trim() || null, new_employer_group: null });
          }}
          suggestions={suggestions}
          placeholder={workGroupPlaceholder(employmentType)}
          emptyMessage="Type at least two characters to add a new employer / work group."
          suggestionLabel="Employers / work groups"
          maxSuggestions={14}
          showSuggestionsOnFocus
          disabled={!employerSectorChosen}
          persistOpenUntilSelection={!selected && !newEmployerGroup}
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
            New employer / work group staged: {newEmployerGroup.code} — {newEmployerGroup.name}
          </p>
        ) : null}
        {loadError ? <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">{loadError}</p> : null}
      </div>
    </div>
  );
}
