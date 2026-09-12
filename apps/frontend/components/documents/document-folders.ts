export type DocumentFolderKey =
    | "all"
    | "letters"
    | "contracts"
    | "reports"
    | "spreadsheets"
    | "receipts"
    | "finance"
    | "compliance"
    | "people"
    | "branding"
    | "general";

export function documentFolderForCategory(category: string | null | undefined): DocumentFolderKey {
    const value = String(category ?? "general").trim().toLowerCase();

    if (/spreadsheet|workbook|excel|\.xlsx|\.csv/.test(value)) return "spreadsheets";
    if (/letter_document|workspace_document|correspondence|letter/.test(value)) return "letters";
    if (/contract|agreement|credit_agreement/.test(value)) return "contracts";
    if (/report|submission|statement/.test(value)) return "reports";
    if (/receipt|payment_slip|disbursement_slip|slip/.test(value)) return "receipts";
    if (/finance|account|treasury|journal|expense/.test(value)) return "finance";
    if (/compliance|kyc|identity|licen[cs]e|risk/.test(value)) return "compliance";
    if (/employee|staff|human_resource|\bhr\b|performance/.test(value)) return "people";
    if (/logo|brand/.test(value)) return "branding";
    return "general";
}

export function documentFolderLabel(key: DocumentFolderKey): string {
    const labels: Record<DocumentFolderKey, string> = {
        all: "All documents",
        letters: "Letters & correspondence",
        contracts: "Contracts & agreements",
        reports: "Reports & statements",
        spreadsheets: "Spreadsheets & workbooks",
        receipts: "Receipts & slips",
        finance: "Finance & accounting",
        compliance: "Compliance & KYC",
        people: "People & HR",
        branding: "Brand assets",
        general: "General records",
    };
    return labels[key];
}
