export const GLOBAL_BORROWER_LOOKUP_EVENT = "loanhub:global-borrower-lookup";

export type GlobalBorrowerLookupAction = "new" | "link" | "history";

export type GlobalBorrowerLookupDetail = {
  action: GlobalBorrowerLookupAction;
  nationalId: string;
};

export function borrowerLookupHref(detail: GlobalBorrowerLookupDetail): string {
  const params = new URLSearchParams({
    action: detail.action,
    national_id: detail.nationalId,
  });
  return `/company/clients?${params.toString()}`;
}

export function dispatchGlobalBorrowerLookup(detail: GlobalBorrowerLookupDetail): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent<GlobalBorrowerLookupDetail>(GLOBAL_BORROWER_LOOKUP_EVENT, {
      detail,
    }),
  );
}
