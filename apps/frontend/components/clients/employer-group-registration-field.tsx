"use client";

import { useEffect, useMemo, useState } from "react";

import { listEmployerGroups } from "@/api/employerGroups";
import { Label } from "@/components/ui/label";
import { SuggestionSearch } from "@/components/ui/suggestion-search";
import type { EmployerGroup, EmployerGroupCreate } from "@/types/employerGroup";

type Selection = {
  employer_group_id: string | null;
  employer_name: string | null;
  new_employer_group: EmployerGroupCreate | null;
};

type Props = {
  employerGroupId?: string | null;
  employerName?: string | null;
  newEmployerGroup?: EmployerGroupCreate | null;
  onChange: (selection: Selection) => void;
  required?: boolean;
};

function display(group: Pick<EmployerGroup, "code" | "name">): string {
  return `${group.code} — ${group.name}`;
}

export function EmployerGroupRegistrationField({
  employerGroupId,
  employerName,
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
        if (!cancelled) {
          setLoadError("Work groups could not be loaded. Try again.");
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const selected = useMemo(
    () => groups.find((group) => group.id === employerGroupId) ?? null,
    [employerGroupId, groups],
  );

  useEffect(() => {
    if (selected) {
      setSearch(display(selected));
      return;
    }

    if (employerName) {
      setSearch((current) => current || employerName);
    }
  }, [employerName, selected]);

  const suggestions = useMemo(
    () =>
      groups.map((group) => ({
        value: group.id,
        label: display(group),
        description: group.name,
        keywords: [group.code, group.name],
      })),
    [groups],
  );

  function clearSelection(nextSearch = "") {
    setSearch(nextSearch);
    onChange({
      employer_group_id: null,
      employer_name: nextSearch.trim() || null,
      new_employer_group: null,
    });
  }

  return (
    <div className="space-y-2">
      <div className="space-y-0.5">
        <Label className="text-sm font-bold">
          Work group
          {required ? <span className="ml-1 text-destructive">*</span> : null}
        </Label>
        <p className="text-[11px] leading-4 text-muted-foreground">
          Search and select one of LoanHub&apos;s centrally supported work groups.
        </p>
      </div>

      <SuggestionSearch
        value={search}
        onValueChange={(value) => clearSelection(value)}
        suggestions={suggestions}
        placeholder="Search L/GOV, LMPS, LCS, LDF…"
        emptyMessage="No matching supported work group."
        suggestionLabel="Work groups"
        maxSuggestions={12}
        showSuggestionsOnFocus
        onSuggestionSelect={(suggestion) => {
          const group = groups.find((row) => row.id === suggestion.value);
          if (!group) return;

          setSearch(display(group));
          onChange({
            employer_group_id: group.id,
            employer_name: group.name,
            new_employer_group: null,
          });
        }}
      />

      {loadError ? (
        <p className="text-xs text-amber-700 dark:text-amber-300">{loadError}</p>
      ) : null}
    </div>
  );
}
