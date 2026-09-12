import { resolveDocumentGenerationBrand } from "@/lib/document-generation-overlay";
import { formatDate, formatDateTime, formatMoney, titleCase } from "@/lib/format";
import type {
  CompanyClientExistingLoanCheck,
  CompanyClientProfile,
} from "@/types/companyClient";

export type BorrowerHistoryCompanyContext = {
  id: string | null;
  name: string;
  licenseNumber?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  branchName?: string | null;
};

export type BorrowerHistoryReportInput = {
  lookup: CompanyClientExistingLoanCheck;
  profile: CompanyClientProfile | null;
  company: BorrowerHistoryCompanyContext;
};

function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function textOrDash(value: unknown): string {
  const text = String(value ?? "").trim();
  return text || "—";
}

function reportReference(lookup: CompanyClientExistingLoanCheck): string {
  const timestamp = new Date(lookup.checked_at);
  const stamp = Number.isNaN(timestamp.getTime())
    ? new Date().toISOString()
    : timestamp.toISOString();
  return `BH${stamp.replace(/\D/g, "").slice(2, 14)}`;
}

function metricCard(label: string, value: string, danger = false): string {
  return `<div class="metric${danger ? " danger" : ""}">
    <div class="metric-label">${escapeHtml(label)}</div>
    <div class="metric-value">${escapeHtml(value)}</div>
  </div>`;
}

function detailRow(label: string, value: unknown): string {
  return `<div class="detail-row"><span>${escapeHtml(label)}</span><strong>${escapeHtml(textOrDash(value))}</strong></div>`;
}

function buildCompanyProfileSections(profile: CompanyClientProfile): string {
  const { client, stats, payment_rating: rating } = profile;
  const loanRows = profile.loans.map((loan) => `
    <tr>
      <td class="mono">${escapeHtml(loan.loan_reference)}</td>
      <td>${escapeHtml(titleCase(loan.status))}</td>
      <td>${escapeHtml(formatDate(loan.disbursed_at ?? loan.approved_at))}</td>
      <td>${escapeHtml(formatMoney(loan.principal_amount))}</td>
      <td>${escapeHtml(formatMoney(loan.total_repayable))}</td>
      <td>${escapeHtml(formatMoney(loan.amount_paid))}</td>
      <td class="${loan.balance > 0 ? "danger-text" : ""}">${escapeHtml(formatMoney(loan.balance))}</td>
      <td>${escapeHtml(formatMoney(loan.installment_amount))}</td>
      <td>${escapeHtml(formatDate(loan.maturity_date))}</td>
      <td>${loan.is_overdue ? `${loan.overdue_installment_count} overdue` : "Current"}</td>
    </tr>
  `).join("");

  const documentRows = profile.documents.map((document) => `
    <tr>
      <td>${escapeHtml(titleCase(document.document_type))}</td>
      <td>${escapeHtml(document.original_name)}</td>
      <td>${escapeHtml(document.reference)}</td>
      <td>${escapeHtml(formatDateTime(document.created_at))}</td>
      <td>${document.is_confidential ? "Confidential" : "Internal"}</td>
    </tr>
  `).join("");

  const activityRows = profile.recent_case_entries.map((entry) => `
    <tr>
      <td>${escapeHtml(formatDateTime(entry.created_at))}</td>
      <td>${escapeHtml(titleCase(entry.entry_type))}</td>
      <td>${escapeHtml(entry.title || titleCase(entry.category))}</td>
      <td>${escapeHtml(entry.body)}</td>
      <td>${escapeHtml(titleCase(entry.status))}</td>
      <td>${entry.amount == null ? "—" : escapeHtml(formatMoney(entry.amount, entry.currency))}</td>
      <td>${escapeHtml(entry.reference_number || "—")}</td>
    </tr>
  `).join("");

  return `
    <section class="section page-break-avoid">
      <div class="section-heading">
        <div><span class="eyebrow">Active company record</span><h2>Borrower profile</h2></div>
        <span class="pill">${escapeHtml(client.account_reference)}</span>
      </div>
      <div class="two-column">
        <div class="detail-card">
          <h3>Identity and contact</h3>
          ${detailRow("Full name", client.full_name)}
          ${detailRow("National ID", client.national_id)}
          ${detailRow("Date of birth", formatDate(client.date_of_birth))}
          ${detailRow("Gender", titleCase(client.gender))}
          ${detailRow("Phone", client.phone)}
          ${detailRow("Email", client.email)}
          ${detailRow("Address", [client.physical_address, client.town_or_village, client.district].filter(Boolean).join(", "))}
        </div>
        <div class="detail-card">
          <h3>Employment and affordability</h3>
          ${detailRow("Employment", titleCase(client.employment_status))}
          ${detailRow("Employer", client.employer_name)}
          ${detailRow("Job title", client.job_title)}
          ${detailRow("Monthly income", client.monthly_income == null ? "—" : formatMoney(client.monthly_income))}
          ${detailRow("Salary date", client.salary_date)}
          ${detailRow("Bank", client.bank_name)}
          ${detailRow("Bank account", client.masked_bank_account)}
        </div>
      </div>
    </section>

    <section class="section page-break-avoid">
      <div class="section-heading">
        <div><span class="eyebrow">Repayment performance</span><h2>Payment rating</h2></div>
        <span class="rating rating-${escapeHtml(rating.grade.toLowerCase())}">${escapeHtml(rating.grade)} · ${escapeHtml(rating.label)}</span>
      </div>
      <div class="metrics six">
        ${metricCard("Score", rating.score == null ? "NR" : `${rating.score}/100`)}
        ${metricCard("On-time rate", `${rating.on_time_rate.toFixed(1)}%`)}
        ${metricCard("Completion rate", `${rating.completion_rate.toFixed(1)}%`)}
        ${metricCard("Paid installments", `${rating.paid_installments}/${rating.total_due_installments}`)}
        ${metricCard("Overdue installments", String(rating.overdue_installments), rating.overdue_installments > 0)}
        ${metricCard("Average days late", rating.average_days_late.toFixed(1), rating.average_days_late > 0)}
      </div>
      <div class="notice compact"><strong>Rating explanation:</strong> ${escapeHtml(rating.explanation)}</div>
      <div class="subtle">Last repayment: ${escapeHtml(formatDateTime(rating.last_payment_at))} · Total due: ${escapeHtml(formatMoney(rating.total_due_amount))} · Total paid: ${escapeHtml(formatMoney(rating.total_paid_amount))}</div>
    </section>

    <section class="section">
      <div class="section-heading">
        <div><span class="eyebrow">Company portfolio</span><h2>Loan history</h2></div>
        <span class="pill">${stats.total_loans} loan${stats.total_loans === 1 ? "" : "s"}</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Loan</th><th>Status</th><th>Started</th><th>Principal</th><th>Repayable</th><th>Paid</th><th>Balance</th><th>Installment</th><th>Maturity</th><th>Arrears</th></tr></thead>
          <tbody>${loanRows || '<tr><td colspan="10">No company loan history is recorded.</td></tr>'}</tbody>
        </table>
      </div>
    </section>

    <section class="section">
      <div class="section-heading">
        <div><span class="eyebrow">Supporting records</span><h2>Documents register</h2></div>
        <span class="pill">${profile.documents.length} document${profile.documents.length === 1 ? "" : "s"}</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Type</th><th>File name</th><th>Reference</th><th>Added</th><th>Access</th></tr></thead>
          <tbody>${documentRows || '<tr><td colspan="5">No borrower documents are registered for this company.</td></tr>'}</tbody>
        </table>
      </div>
      <p class="subtle">The report lists document metadata only. Protected document contents are not embedded.</p>
    </section>

    <section class="section">
      <div class="section-heading">
        <div><span class="eyebrow">Current company only</span><h2>Comments and legal activity</h2></div>
        <span class="pill">Latest ${profile.recent_case_entries.length}</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Date</th><th>Type</th><th>Title</th><th>Details</th><th>Status</th><th>Amount</th><th>Reference</th></tr></thead>
          <tbody>${activityRows || '<tr><td colspan="7">No comments or legal activity are recorded.</td></tr>'}</tbody>
        </table>
      </div>
    </section>
  `;
}

export async function renderBorrowerHistoryReport(
  popup: Window,
  input: BorrowerHistoryReportInput,
): Promise<void> {
  const { lookup, profile, company } = input;
  const brand = await resolveDocumentGenerationBrand(company.id, company.name);
  const reference = reportReference(lookup);
  const generatedAt = new Date();
  const adverse = lookup.defaulted_loan_count > 0 || lookup.overdue_loan_count > 0;
  const companyLogo = brand.companyLogoDataUrl
    ? `<img class="company-logo" src="${escapeHtml(brand.companyLogoDataUrl)}" alt="${escapeHtml(company.name)} logo" />`
    : `<div class="company-mark">${escapeHtml(company.name.split(/\s+/).slice(0, 2).map((word) => word[0]?.toUpperCase()).join("") || "CO")}</div>`;
  const loanHubHeaderLogo = `${window.location.origin}/loanhub-horizontal-logo.png`;
  const loanHubFooterLogo = `${window.location.origin}/loanhub-app-icon.png`;

  const companyDetails = [
    company.licenseNumber ? `Licence: ${company.licenseNumber}` : null,
    company.branchName,
    company.address,
    company.phone,
    company.email,
  ].filter(Boolean).map((value) => `<span>${escapeHtml(value)}</span>`).join("");

  const scopeText = profile
    ? "This report contains aggregate LoanHub history plus the active company's authorised borrower profile, repayment performance, loan register, document metadata, comments and legal activity. Other lenders' identities, documents, notes and internal records remain protected."
    : "This report contains aggregate LoanHub credit history only. The borrower is not linked to the active company, so lender identities, detailed loans, documents, notes and internal records are intentionally excluded.";

  popup.document.open();
  popup.document.write(`<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${escapeHtml(reference)} · Borrower History Report</title>
  <style>
    * { box-sizing: border-box; }
    @page { size: A4 landscape; margin: 10mm; }
    :root { --navy:#082f57; --blue:#0b69b7; --cyan:#eaf6ff; --ink:#14283d; --muted:#607286; --line:#cfdae6; --paper:#fff; --danger:#c62828; --success:#087f5b; }
    body { margin:0; background:#e8eef4; color:var(--ink); font-family:Inter,Arial,Helvetica,sans-serif; font-size:10px; }
    .sheet { width:277mm; min-height:190mm; margin:14px auto; background:var(--paper); padding:10mm; box-shadow:0 20px 50px rgba(8,47,87,.16); }
    .brand-header { display:grid; grid-template-columns:190px minmax(0,1fr) 118px; gap:18px; align-items:center; min-height:92px; padding:2px 0 12px; border-bottom:2px solid var(--navy); }
    .system-brand { width:190px; height:78px; display:flex; align-items:center; justify-content:flex-start; overflow:hidden; }
    .system-logo { width:100%; height:100%; object-fit:contain; transform:scale(1.45); transform-origin:center; }
    .company-brand { min-width:0; padding:0 8px; text-align:center; }
    .company-logo-wrap { min-width:0; display:flex; align-items:center; justify-content:flex-end; }
    .company-logo { width:108px; height:84px; object-fit:contain; object-position:right center; flex:0 0 auto; }
    .company-mark { width:82px; height:82px; border-radius:18px; display:grid; place-items:center; background:var(--navy); color:#fff; font-size:25px; font-weight:900; flex:0 0 auto; }
    .company-name { font-family:Georgia,"Times New Roman",serif; font-size:21px; font-weight:800; color:#101d33; line-height:1.12; overflow-wrap:anywhere; }
    .company-meta { display:flex; flex-wrap:wrap; justify-content:center; gap:4px 0; margin-top:7px; color:var(--muted); line-height:1.45; }
    .company-meta span { display:inline-flex; align-items:center; white-space:nowrap; }
    .company-meta span:not(:last-child)::after { content:"•"; margin:0 8px; color:#d62828; font-weight:900; }
    .report-meta { display:flex; flex-wrap:wrap; justify-content:flex-end; gap:4px 16px; margin-top:7px; color:var(--muted); line-height:1.5; font-size:8.5px; }
    .report-meta strong { color:var(--navy); }
    h1 { margin:11px 0 3px; color:var(--navy); font-size:25px; letter-spacing:-.03em; }
    h2 { margin:2px 0 0; color:var(--navy); font-size:16px; }
    h3 { margin:0 0 8px; color:var(--navy); font-size:12px; }
    .subtitle { color:var(--muted); font-size:11px; }
    .status-row { display:flex; flex-wrap:wrap; gap:8px; margin:12px 0; }
    .pill,.status { display:inline-flex; align-items:center; border:1px solid var(--line); border-radius:999px; padding:5px 9px; background:#f7fafc; font-weight:800; }
    .status.good { color:var(--success); border-color:#9fdfcc; background:#ecfbf6; }
    .status.bad { color:var(--danger); border-color:#f2b8b8; background:#fff2f2; }
    .notice { margin:12px 0; border-left:4px solid var(--blue); border-radius:8px; padding:10px 12px; background:var(--cyan); color:#29445f; line-height:1.55; }
    .notice.compact { margin:9px 0 6px; padding:8px 10px; }
    .metrics { display:grid; grid-template-columns:repeat(9,1fr); gap:7px; }
    .metrics.six { grid-template-columns:repeat(6,1fr); }
    .metric { min-width:0; border:1px solid var(--line); border-radius:10px; padding:9px; background:#f8fbfd; }
    .metric.danger { border-color:#efb0b0; background:#fff5f5; }
    .metric-label { color:var(--muted); font-size:7.5px; font-weight:900; text-transform:uppercase; letter-spacing:.11em; }
    .metric-value { margin-top:5px; color:var(--navy); font-size:15px; font-weight:900; overflow-wrap:anywhere; }
    .danger .metric-value,.danger-text { color:var(--danger); font-weight:900; }
    .section { margin-top:16px; }
    .section-heading { display:flex; align-items:end; justify-content:space-between; gap:14px; margin-bottom:8px; padding-bottom:6px; border-bottom:1px solid var(--line); }
    .eyebrow { color:var(--blue); font-size:7.5px; font-weight:900; letter-spacing:.13em; text-transform:uppercase; }
    .two-column { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
    .detail-card { border:1px solid var(--line); border-radius:12px; padding:10px 12px; background:#fbfdff; }
    .detail-row { display:grid; grid-template-columns:135px 1fr; gap:10px; padding:5px 0; border-bottom:1px solid #e5ecf2; }
    .detail-row:last-child { border-bottom:0; }
    .detail-row span { color:var(--muted); }
    .detail-row strong { text-align:right; overflow-wrap:anywhere; }
    .rating { border-radius:999px; padding:6px 10px; background:#e9f8f2; color:var(--success); font-weight:900; }
    .rating-d,.rating-e { background:#fff0f0; color:var(--danger); }
    .table-wrap { width:100%; overflow:hidden; border:1px solid var(--line); border-radius:10px; }
    table { width:100%; border-collapse:collapse; table-layout:auto; }
    th { background:var(--navy); color:#fff; padding:7px 6px; text-align:left; font-size:7px; text-transform:uppercase; letter-spacing:.08em; }
    td { padding:7px 6px; border-bottom:1px solid #e2e9f0; vertical-align:top; line-height:1.35; overflow-wrap:anywhere; }
    tbody tr:nth-child(even) { background:#f8fbfd; }
    .mono { font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-weight:800; }
    .subtle { margin-top:7px; color:var(--muted); line-height:1.45; }
    .footer { display:flex; align-items:center; justify-content:space-between; gap:20px; margin-top:18px; padding-top:9px; border-top:1px solid var(--line); color:var(--muted); font-size:8px; }
    .generated-by { display:inline-flex; align-items:center; gap:6px; font-weight:700; }
    .generated-by img { width:18px; height:18px; object-fit:contain; }
    .signature-grid { display:grid; grid-template-columns:1fr 1fr; gap:40px; margin-top:28px; }
    .signature-line { padding-top:22px; border-bottom:1px solid #50657a; }
    .page-break-avoid { break-inside:avoid; }
    @media print {
      body { background:#fff; }
      .sheet { width:auto; min-height:auto; margin:0; padding:0; box-shadow:none; }
      .section { break-inside:auto; }
      .page-break-avoid { break-inside:avoid; }
    }
  </style>
</head>
<body>
  <main class="sheet">
    <header class="brand-header">
      <div class="system-brand">
        <img class="system-logo" src="${escapeHtml(loanHubHeaderLogo)}" alt="LoanHub system logo" />
      </div>
      <div class="company-brand">
        <div class="company-name">${escapeHtml(company.name)}</div>
        <div class="company-meta">${companyDetails}</div>
      </div>
      <div class="company-logo-wrap">${companyLogo}</div>
    </header>
    <div class="report-meta">
      <span><strong>Report reference:</strong> ${escapeHtml(reference)}</span>
      <span><strong>Checked:</strong> ${escapeHtml(formatDateTime(lookup.checked_at))}</span>
      <span><strong>Generated:</strong> ${escapeHtml(generatedAt.toLocaleString("en-LS"))}</span>
    </div>

    <h1>Borrower History Report</h1>
    <div class="subtitle">National ID ${escapeHtml(lookup.national_id)} · LoanHub identity and credit-history verification</div>

    <div class="status-row">
      <span class="status good">Borrower identity found</span>
      <span class="status ${lookup.already_company_client ? "good" : ""}">${lookup.already_company_client ? "Linked to active company" : "Not linked to active company"}</span>
      <span class="status ${adverse ? "bad" : "good"}">${adverse ? "Adverse repayment status detected" : "No adverse LoanHub status"}</span>
    </div>

    <div class="notice"><strong>Report scope and privacy:</strong> ${escapeHtml(scopeText)}</div>

    <section class="section page-break-avoid">
      <div class="section-heading"><div><span class="eyebrow">LoanHub aggregate</span><h2>Credit history summary</h2></div><span class="pill">National ID verified</span></div>
      <div class="metrics">
        ${metricCard("All loans", String(lookup.total_loan_count))}
        ${metricCard("Open loans", String(lookup.active_loan_count))}
        ${metricCard("Completed", String(lookup.completed_loan_count))}
        ${metricCard("Defaulted", String(lookup.defaulted_loan_count), lookup.defaulted_loan_count > 0)}
        ${metricCard("Overdue", String(lookup.overdue_loan_count), lookup.overdue_loan_count > 0)}
        ${metricCard("Lenders", String(lookup.lender_count))}
        ${metricCard("Outstanding", formatMoney(lookup.loanhub_outstanding_total), lookup.loanhub_outstanding_total > 0)}
        ${metricCard("Lifetime borrowed", formatMoney(lookup.lifetime_principal_total))}
        ${metricCard("Lifetime paid", formatMoney(lookup.lifetime_paid_total))}
      </div>
      <div class="subtle">Latest LoanHub loan: ${escapeHtml(formatDate(lookup.latest_loan_at))} · Borrower-declared existing exposure: ${escapeHtml(formatMoney(lookup.declared_existing_loan_total))}</div>
    </section>

    ${profile ? buildCompanyProfileSections(profile) : ""}

    <section class="section page-break-avoid">
      <div class="notice"><strong>Operational use:</strong> This report reflects information recorded in LoanHub at the time shown above. Confirm identity, consent, affordability and original supporting documents before making a lending decision. This is not an external credit-bureau report.</div>
      <div class="signature-grid">
        <div><div class="signature-line"></div><div class="subtle">Prepared / reviewed by</div></div>
        <div><div class="signature-line"></div><div class="subtle">Date and signature</div></div>
      </div>
    </section>

    <footer class="footer"><span class="generated-by"><img src="${escapeHtml(loanHubFooterLogo)}" alt="" />Generated securely by LoanHub</span><span>${escapeHtml(reference)} · ${escapeHtml(company.name)}</span></footer>
  </main>
  <script>
    window.addEventListener("load", function () {
      var images = Array.from(document.images);
      Promise.all(images.map(function (image) {
        if (image.complete) return Promise.resolve();
        return new Promise(function (resolve) {
          image.addEventListener("load", resolve, { once: true });
          image.addEventListener("error", resolve, { once: true });
        });
      })).then(function () {
        window.setTimeout(function () { window.focus(); window.print(); }, 250);
      });
    });
  </script>
</body>
</html>`);
  popup.document.close();
}
