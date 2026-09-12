"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
    Award,
    BriefcaseBusiness,
    Clock3,
    FileChartColumn,
    FileCheck2,
    FilePenLine,
    FilePlus2,
    FileText,
    FolderOpen,
    LayoutTemplate,
    Loader2,
    LockKeyhole,
    MoreHorizontal,
    NotebookTabs,
    ReceiptText,
    ScrollText,
    Search,
    Trash2,
    UsersRound,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { listCompanyClients } from "@/api/companyClients";
import { listLoans } from "@/api/loans";
import {
    createWorkspaceDocument,
    deleteWorkspaceDocument,
    listWorkspaceDocuments,
} from "@/api/workspaceDocuments";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { CustomDialog } from "@/components/ui/custom-dialog";
import { DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import type { CompanyClient } from "@/types/companyClient";
import type { Loan } from "@/types/loan";
import type {
    DocumentStyleKey,
    DocumentVisibility,
    WorkspaceDocument,
} from "@/types/workspaceDocuments";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

type StudioMode = "company" | "borrower" | "superadmin" | "platform";
type TemplateCategory = "Popular" | "Client Letters" | "Business" | "Management" | "Proposals" | "Contracts" | "CVs" | "Legal" | "Personal";

type DocumentTemplate = {
    key: string;
    title: string;
    description: string;
    category: TemplateCategory;
    icon: typeof FileText;
    style: DocumentStyleKey;
    badge?: string;
};

const templates: DocumentTemplate[] = [
    { key: "blank", title: "Blank document", description: "A clean page with the complete Word-like ribbon, branding, cover pages and signature tools.", category: "Popular", icon: FilePlus2, style: "modern_blue", badge: "Start fresh" },
    { key: "formal_letter", title: "Formal letter", description: "Recipient, subject, salutation, positioned addresses and professional closing.", category: "Popular", icon: FilePenLine, style: "classic_word", badge: "Most used" },
    { key: "client_confirmation_letter", title: "Client confirmation letter", description: "No-arrears confirmation auto-filled from the selected company client and current LoanHub account state.", category: "Client Letters", icon: FileCheck2, style: "classic_word", badge: "Customer" },
    { key: "good_standing_confirmation_letter", title: "Good standing confirmation", description: "Professional client-in-good-standing letter with current no-arrears verification.", category: "Client Letters", icon: FileCheck2, style: "classic_word", badge: "Customer" },
    { key: "paid_up_letter", title: "Paid-up letter", description: "Settlement-in-full confirmation for a selected loan. LoanHub blocks creation while a balance remains.", category: "Client Letters", icon: ReceiptText, style: "classic_word", badge: "Verified" },
    { key: "settlement_letter", title: "Settlement letter", description: "Current balance, installment and no-arrears confirmation for a selected live loan, valid for 30 days.", category: "Client Letters", icon: ScrollText, style: "legal_monochrome", badge: "Verified" },
    { key: "memo", title: "Memorandum", description: "Internal communication with purpose, background, decisions and actions.", category: "Popular", icon: NotebookTabs, style: "modern_blue" },
    { key: "loan_agreement", title: "Loan agreement", description: "Editable LoanHub lending agreement based on the approved Filizwa-style draft, with cost terms, repayment, default and signature sections.", category: "Popular", icon: FileCheck2, style: "legal_monochrome", badge: "LoanHub" },
    { key: "loan_agreement_filizwa_style", title: "Loan agreement (Filizwa style)", description: "Two-page agreement template matching the structure of the last two pages of the Filizwa PDF, including borrower details, loan conditions, cost elements, bank deduction details and acceptance sections.", category: "Contracts", icon: FileCheck2, style: "legal_monochrome", badge: "New" },
    { key: "business_letter", title: "Business letter", description: "Commercial correspondence with sender and recipient blocks.", category: "Business", icon: BriefcaseBusiness, style: "executive_navy" },
    { key: "invoice", title: "Invoice", description: "Customer, line items, totals, payment details and terms.", category: "Business", icon: ReceiptText, style: "classic_word" },
    { key: "meeting_minutes", title: "Meeting minutes", description: "Attendance, agenda, resolutions, action owners and deadlines.", category: "Management", icon: UsersRound, style: "minimal_clean" },
    { key: "project_report", title: "Project report", description: "Executive summary, deliverables, risks, findings and recommendations.", category: "Management", icon: FileChartColumn, style: "executive_navy" },
    { key: "policy", title: "Policy document", description: "Version-controlled policy structure with responsibilities, controls and approval.", category: "Legal", icon: FileCheck2, style: "legal_monochrome" },
    { key: "proposal", title: "Professional proposal", description: "General-purpose proposal with problem, solution, scope, implementation and pricing.", category: "Proposals", icon: ScrollText, style: "modern_blue" },
    { key: "business_proposal", title: "Business proposal", description: "Executive business case, commercial model, milestones, pricing and acceptance.", category: "Proposals", icon: BriefcaseBusiness, style: "executive_navy", badge: "Cover page" },
    { key: "technical_proposal", title: "Technical proposal", description: "Architecture, requirements, methodology, deliverables, assumptions and implementation plan.", category: "Proposals", icon: FileChartColumn, style: "modern_blue", badge: "Cover page" },
    { key: "tender_proposal", title: "Tender / bid proposal", description: "Tender response, compliance matrix, capability, programme and commercial offer.", category: "Proposals", icon: FileCheck2, style: "executive_navy", badge: "Cover page" },
    { key: "funding_proposal", title: "Funding proposal", description: "Need, objectives, impact, budget, sustainability and monitoring framework.", category: "Proposals", icon: ScrollText, style: "elegant_green", badge: "Cover page" },
    { key: "partnership_proposal", title: "Partnership proposal", description: "Strategic fit, responsibilities, value exchange, governance and next steps.", category: "Proposals", icon: UsersRound, style: "warm_professional", badge: "Cover page" },
    { key: "contract", title: "General agreement", description: "Parties, obligations, payment, termination, dispute terms and signature fields.", category: "Contracts", icon: FileCheck2, style: "legal_monochrome" },
    { key: "service_agreement", title: "Service agreement", description: "Services, service levels, fees, responsibilities, confidentiality and termination.", category: "Contracts", icon: FileCheck2, style: "legal_monochrome" },
    { key: "employment_contract", title: "Employment contract", description: "Appointment, duties, remuneration, leave, conduct, confidentiality and termination.", category: "Contracts", icon: BriefcaseBusiness, style: "legal_monochrome" },
    { key: "nda", title: "Non-disclosure agreement", description: "Confidential information, permitted use, exclusions, return and remedies.", category: "Contracts", icon: LockKeyhole, style: "legal_monochrome" },
    { key: "consultancy_agreement", title: "Consultancy agreement", description: "Scope, deliverables, fees, independence, intellectual property and termination.", category: "Contracts", icon: FileCheck2, style: "classic_word" },
    { key: "partnership_agreement", title: "Partnership agreement", description: "Contributions, ownership, management, profit sharing, exit and disputes.", category: "Contracts", icon: UsersRound, style: "legal_monochrome" },
    { key: "resume", title: "Classic CV / résumé", description: "Clean profile, skills, experience, education and references.", category: "CVs", icon: BriefcaseBusiness, style: "minimal_clean" },
    { key: "executive_cv", title: "Executive CV", description: "Leadership profile, board-level achievements, strategic impact and career history.", category: "CVs", icon: BriefcaseBusiness, style: "executive_navy" },
    { key: "software_cv", title: "Software developer CV", description: "Technical stack, projects, engineering experience, tools and education.", category: "CVs", icon: FileText, style: "modern_blue" },
    { key: "graduate_cv", title: "Graduate CV", description: "Education-first CV with projects, skills, placements and achievements.", category: "CVs", icon: FileText, style: "elegant_green" },
    { key: "academic_cv", title: "Academic CV", description: "Research, teaching, publications, conferences, awards and service.", category: "CVs", icon: FileText, style: "classic_word" },
    { key: "skills_cv", title: "Skills-based CV", description: "Competency-led CV for career changes, contractors and practical experience.", category: "CVs", icon: FileText, style: "warm_professional" },
    { key: "certificate", title: "Certificate", description: "A polished achievement or completion certificate.", category: "Personal", icon: Award, style: "elegant_green" },
];

const categories: Array<"All" | TemplateCategory> = [
    "All",
    "Popular",
    "Client Letters",
    "Business",
    "Management",
    "Proposals",
    "Contracts",
    "CVs",
    "Legal",
    "Personal",
];

export function DocumentStudioHome({
    basePath,
    mode,
}: {
    basePath: string;
    mode: StudioMode;
}) {
    const router = useRouter();
    const [documents, setDocuments] = useState<WorkspaceDocument[]>([]);
    const [loading, setLoading] = useState(true);
    const [creating, setCreating] = useState<string | null>(null);
    const [search, setSearch] = useState("");
    const [statusFilter, setStatusFilter] = useState("all");
    const [templateCategory, setTemplateCategory] = useState<(typeof categories)[number]>("All");
    const [deleteTarget, setDeleteTarget] = useState<WorkspaceDocument | null>(null);
    const [deleting, setDeleting] = useState(false);
    const [companyClients, setCompanyClients] = useState<CompanyClient[]>([]);
    const [companyLoans, setCompanyLoans] = useState<Loan[]>([]);
    const [clientDataLoading, setClientDataLoading] = useState(false);
    const [pendingClientTemplate, setPendingClientTemplate] = useState<DocumentTemplate | null>(null);
    const [selectedClientId, setSelectedClientId] = useState("");
    const [selectedLoanId, setSelectedLoanId] = useState("");
    const [signerName, setSignerName] = useState("");
    const [signerTitle, setSignerTitle] = useState("");
    const [companyBankAccounts, setCompanyBankAccounts] = useState("");

    async function load() {
        setLoading(true);
        try {
            const response = await listWorkspaceDocuments({ limit: 300 });
            setDocuments(response.items);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not load the document studio."));
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        void load();
    }, []);

    useEffect(() => {
        if (mode !== "company") return;
        let cancelled = false;
        setClientDataLoading(true);
        Promise.all([listCompanyClients(), listLoans()])
            .then(([clientRows, loanRows]) => {
                if (cancelled) return;
                setCompanyClients(clientRows);
                setCompanyLoans(loanRows);
                const params = new URLSearchParams(window.location.search);
                const clientId = params.get("client") || "";
                const loanId = params.get("loan") || "";
                if (clientId && clientRows.some((row) => row.id === clientId)) {
                    setSelectedClientId(clientId);
                    setTemplateCategory("Client Letters");
                }
                if (loanId && loanRows.some((row) => row.id === loanId)) {
                    setSelectedLoanId(loanId);
                }
            })
            .catch((error: unknown) => {
                if (!cancelled) {
                    toast.error(getErrorMessage(error, "Could not load company clients and loans for document autofill."));
                }
            })
            .finally(() => {
                if (!cancelled) setClientDataLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [mode]);

    const visible = useMemo(() => {
        const token = search.trim().toLowerCase();
        return documents.filter((document) => {
            const matchesStatus = statusFilter === "all" || document.status === statusFilter;
            const matchesSearch =
                !token ||
                `${document.title} ${document.reference} ${document.owner_display_name} ${document.plain_text}`
                    .toLowerCase()
                    .includes(token);
            return matchesStatus && matchesSearch;
        });
    }, [documents, search, statusFilter]);

    const visibleTemplates = useMemo(
        () => templates.filter((template) => {
            if (template.category === "Client Letters" && mode !== "company") return false;
            return templateCategory === "All" || template.category === templateCategory;
        }),
        [mode, templateCategory],
    );

    const visibleCategories = useMemo(
        () => categories.filter((category) => category !== "Client Letters" || mode === "company"),
        [mode],
    );

    const selectedClient = useMemo(
        () => companyClients.find((client) => client.id === selectedClientId) ?? null,
        [companyClients, selectedClientId],
    );

    const selectedClientLoans = useMemo(
        () => selectedClient
            ? companyLoans.filter((loan) => loan.borrower_id === selectedClient.borrower_id)
            : [],
        [companyLoans, selectedClient],
    );

    const clientLetterNeedsLoan = pendingClientTemplate
        ? ["paid_up_letter", "settlement_letter"].includes(pendingClientTemplate.key)
        : false;

    const defaultVisibility: DocumentVisibility =
        mode === "company" ? "company" : mode === "superadmin" ? "platform" : "private";
    const filesPath =
        mode === "company"
            ? "/company/files"
            : mode === "borrower"
              ? "/borrower/files"
              : mode === "superadmin"
                ? "/superadmin/files"
                : null;

    async function create(
        template: DocumentTemplate,
        context?: {
            company_client_id?: string | null;
            loan_id?: string | null;
            signer_name?: string | null;
            signer_title?: string | null;
            company_bank_accounts?: string | null;
        },
    ) {
        setCreating(template.key);
        try {
            const client = context?.company_client_id
                ? companyClients.find((row) => row.id === context.company_client_id) ?? null
                : null;
            const created = await createWorkspaceDocument({
                title: template.key === "blank"
                    ? "Untitled document"
                    : client
                      ? `${template.title} - ${client.full_name}`
                      : `New ${template.title.toLowerCase()}`,
                template_key: template.key,
                visibility: defaultVisibility,
                include_brand_header: !["resume", "executive_cv", "software_cv", "graduate_cv", "academic_cv", "skills_cv", "certificate"].includes(template.key),
                include_footer: true,
                cover_page_enabled: ["business_proposal", "technical_proposal", "tender_proposal", "funding_proposal", "partnership_proposal"].includes(template.key),
                cover_page: {
                    title: template.title,
                    subtitle: template.category === "Proposals" ? "Professional proposal" : "",
                    prepared_for: client?.full_name ?? "",
                    prepared_by: signerName,
                    document_date: new Intl.DateTimeFormat(undefined, { dateStyle: "long" }).format(new Date()),
                    version_label: "Version 1",
                    confidentiality_note: "",
                    show_logo: true,
                    show_reference: true,
                },
                style_key: template.style,
                default_font_family:
                    template.style === "legal_monochrome" ? "Times New Roman" :
                    template.style === "elegant_green" ? "Georgia" : "Arial",
                default_font_size_pt: 11,
                default_line_height_percent: 115,
                ...context,
            });
            setPendingClientTemplate(null);
            router.push(`${basePath}/${created.id}`);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not create the document."));
        } finally {
            setCreating(null);
        }
    }

    function startTemplate(template: DocumentTemplate) {
        if (template.category === "Client Letters") {
            setPendingClientTemplate(template);
            if (selectedLoanId && !selectedClientLoans.some((loan) => loan.id === selectedLoanId)) {
                setSelectedLoanId("");
            }
            return;
        }
        void create(template);
    }

    function createClientLetter() {
        if (!pendingClientTemplate) return;
        if (!selectedClientId) {
            toast.warning("Select a company client before creating this letter.");
            return;
        }
        if (clientLetterNeedsLoan && !selectedLoanId) {
            toast.warning("Select the loan that this letter relates to.");
            return;
        }
        void create(pendingClientTemplate, {
            company_client_id: selectedClientId,
            loan_id: selectedLoanId || null,
            signer_name: signerName.trim() || null,
            signer_title: signerTitle.trim() || null,
            company_bank_accounts: companyBankAccounts.trim() || null,
        });
    }

    async function removeConfirmed() {
        if (!deleteTarget) return;
        setDeleting(true);
        try {
            await deleteWorkspaceDocument(deleteTarget.id);
            setDocuments((current) => current.filter((item) => item.id !== deleteTarget.id));
            toast.success("Document removed");
            setDeleteTarget(null);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not remove the document."));
        } finally {
            setDeleting(false);
        }
    }

    return (
        <main className="space-y-6">
            <section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8">
                <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-primary/10 blur-3xl" />
                <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <div className="flex items-center gap-2 text-primary">
                            <LayoutTemplate className="h-5 w-5" />
                            <span className="text-xs font-black uppercase tracking-[0.16em]">LoanHub document studio</span>
                        </div>
                        <h1 className="mt-2 text-3xl font-black tracking-tight">Create documents with a Word-like editor</h1>
                        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                            Use professional templates, rich styles, tables, images, page layouts and drag-and-drop signature fields. Autosave, collaborate securely, export to Word or PDF, print, and share controlled copies.
                        </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        {filesPath && <Button asChild variant="outline" className="h-11"><Link href={filesPath}><FolderOpen />Open file library</Link></Button>}
                        <Button type="button" className="h-11" onClick={() => startTemplate(templates[0])} disabled={Boolean(creating)}>
                            {creating === "blank" ? <Loader2 className="animate-spin" /> : <FilePlus2 />}
                            Blank document
                        </Button>
                    </div>
                </div>
            </section>

            <section className="rounded-3xl border bg-card p-5 shadow-sm">
                <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                    <div><h2 className="text-lg font-black">Template gallery</h2><p className="mt-1 text-sm text-muted-foreground">Choose a starting structure, then customise every detail. Customer letters can auto-fill from a selected company client and loan.</p></div>
                    <div className="flex flex-wrap gap-2">
                        {visibleCategories.map((category) => (
                            <button key={category} type="button" onClick={() => setTemplateCategory(category)} className={`rounded-full border px-3 py-1.5 text-xs font-black transition ${templateCategory === category ? "border-primary bg-primary text-primary-foreground" : "hover:border-primary hover:text-primary"}`}>{category}</button>
                        ))}
                    </div>
                </div>
                <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                    {visibleTemplates.map((template) => {
                        const Icon = template.icon;
                        return (
                            <button key={template.key} type="button" onClick={() => startTemplate(template)} disabled={Boolean(creating)} className="group relative overflow-hidden rounded-3xl border bg-background p-5 text-left transition hover:-translate-y-0.5 hover:border-primary hover:shadow-md disabled:opacity-60">
                                <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-primary via-primary/60 to-transparent opacity-0 transition group-hover:opacity-100" />
                                <div className="flex items-start justify-between gap-3">
                                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary transition group-hover:bg-primary group-hover:text-primary-foreground"><Icon className="h-6 w-6" /></div>
                                    <div className="flex items-center gap-2">{template.badge && <span className="rounded-full bg-primary/10 px-2 py-1 text-[10px] font-black uppercase text-primary">{template.badge}</span>}{creating === template.key && <Loader2 className="h-5 w-5 animate-spin text-primary" />}</div>
                                </div>
                                <h3 className="mt-4 font-black">{template.title}</h3>
                                <p className="mt-1 min-h-10 text-xs leading-5 text-muted-foreground">{template.description}</p>
                                <p className="mt-3 text-[10px] font-black uppercase tracking-wide text-muted-foreground">{template.category}</p>
                            </button>
                        );
                    })}
                </div>
            </section>

            <section className="overflow-hidden rounded-3xl border bg-card shadow-sm">
                <div className="border-b p-5">
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                        <div><h2 className="text-lg font-black">My documents and shared work</h2><p className="mt-1 text-sm text-muted-foreground">Private, company, platform and directly shared documents.</p></div>
                        <div className="grid gap-2 sm:grid-cols-[260px_170px]">
                            <div className="relative"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" /><Input value={search} onChange={(event) => setSearch(event.target.value)} className="pl-9" placeholder="Search documents..." /></div>
                            <NativeSelect value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} className="h-9 rounded-lg border bg-background px-3"><option value="all">All statuses</option><option value="draft">Drafts</option><option value="final">Final</option><option value="archived">Archived</option></NativeSelect>
                        </div>
                    </div>
                </div>

                {loading ? <div className="flex justify-center p-12"><Loader2 className="h-7 w-7 animate-spin text-primary" /></div> : (
                    <div className="grid gap-4 p-4 md:grid-cols-2 2xl:grid-cols-3">
                        {visible.map((document) => (
                            <article key={document.id} className="rounded-2xl border bg-muted/10 p-4 transition hover:border-primary hover:shadow-sm">
                                <div className="flex items-start gap-3">
                                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary"><FilePenLine className="h-5 w-5" /></div>
                                    <div className="min-w-0 flex-1"><Link href={`${basePath}/${document.id}`} className="line-clamp-2 font-black hover:text-primary">{document.title}</Link><p className="mt-1 font-mono text-[11px] text-muted-foreground">{document.reference}</p></div>
                                    <MoreHorizontal className="h-5 w-5 text-muted-foreground" />
                                </div>
                                <p className="mt-3 line-clamp-3 min-h-14 text-xs leading-5 text-muted-foreground">{document.plain_text || "Empty document"}</p>
                                <div className="mt-4 flex flex-wrap gap-2 text-[11px] font-bold">
                                    <span className="rounded-full bg-primary/10 px-2.5 py-1 text-primary">{document.status}</span>
                                    {document.visibility === "private" ? <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-1"><LockKeyhole className="h-3 w-3" />Private</span> : <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-1"><UsersRound className="h-3 w-3" />{document.visibility}</span>}
                                    {document.signature_field_count > 0 && <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-emerald-800">{document.signature_field_count} fields</span>}
                                </div>
                                <div className="mt-4 flex items-center justify-between gap-3 border-t pt-3 text-[11px] text-muted-foreground">
                                    <span className="inline-flex items-center gap-1"><Clock3 className="h-3.5 w-3.5" />{new Date(document.updated_at).toLocaleString()}</span>
                                    <div className="flex items-center gap-1"><Button asChild size="sm" variant="ghost"><Link href={`${basePath}/${document.id}`}>Open</Link></Button>{document.can_manage && <Button type="button" size="icon" variant="ghost" onClick={() => setDeleteTarget(document)} title="Remove document"><Trash2 className="text-red-600" /></Button>}</div>
                                </div>
                            </article>
                        ))}
                        {visible.length === 0 && <div className="col-span-full p-12 text-center"><FileText className="mx-auto h-10 w-10 text-muted-foreground" /><p className="mt-3 font-black">No documents found</p><p className="mt-1 text-sm text-muted-foreground">Create your first document from the template gallery.</p></div>}
                    </div>
                )}
            </section>

            <CustomDialog
                open={Boolean(pendingClientTemplate)}
                onOpenChange={(open) => {
                    if (!open && !creating) setPendingClientTemplate(null);
                }}
                title={pendingClientTemplate?.title ?? "Customer letter"}
                description="Select the customer and, where required, the loan. LoanHub fills verified account data and uses the active company's current document branding."
                contentClassName="sm:max-w-2xl"
            >
                <div className="grid gap-5 py-2">
                    <div className="grid gap-2">
                        <Label htmlFor="client-letter-customer">Customer</Label>
                        <NativeSelect
                            id="client-letter-customer"
                            value={selectedClientId}
                            disabled={clientDataLoading || Boolean(creating)}
                            onChange={(event) => {
                                setSelectedClientId(event.target.value);
                                setSelectedLoanId("");
                            }}
                        >
                            <option value="">Select customer...</option>
                            {companyClients.map((client) => (
                                <option key={client.id} value={client.id}>
                                    {client.full_name} · {client.account_reference}
                                </option>
                            ))}
                        </NativeSelect>
                        {selectedClient && (
                            <p className="text-xs text-muted-foreground">
                                ID {selectedClient.national_id || selectedClient.passport_number || "not recorded"} · {selectedClient.phone}
                            </p>
                        )}
                    </div>

                    <div className="grid gap-2">
                        <Label htmlFor="client-letter-loan">
                            Loan {clientLetterNeedsLoan ? "(required)" : "(optional)"}
                        </Label>
                        <NativeSelect
                            id="client-letter-loan"
                            value={selectedLoanId}
                            disabled={!selectedClientId || clientDataLoading || Boolean(creating)}
                            onChange={(event) => setSelectedLoanId(event.target.value)}
                        >
                            <option value="">No specific loan</option>
                            {selectedClientLoans.map((loan) => (
                                <option key={loan.id} value={loan.id}>
                                    {loan.loan_reference} · {loan.status} · balance LSL {Number(loan.balance || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                </option>
                            ))}
                        </NativeSelect>
                        {pendingClientTemplate?.key === "paid_up_letter" && (
                            <p className="text-xs text-muted-foreground">Paid-up letters are accepted only when the selected loan has no remaining ledger balance or unpaid installments.</p>
                        )}
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2">
                        <div className="grid gap-2">
                            <Label htmlFor="client-letter-signer">Signatory name</Label>
                            <Input id="client-letter-signer" value={signerName} onChange={(event) => setSignerName(event.target.value)} placeholder="Defaults to the logged-in staff member" />
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="client-letter-title">Signatory title</Label>
                            <Input id="client-letter-title" value={signerTitle} onChange={(event) => setSignerTitle(event.target.value)} placeholder="Manager, Director, Loan Officer..." />
                        </div>
                    </div>

                    {pendingClientTemplate?.key === "settlement_letter" && (
                        <div className="grid gap-2">
                            <Label htmlFor="client-letter-bank-accounts">Company bank account details</Label>
                            <Textarea
                                id="client-letter-bank-accounts"
                                value={companyBankAccounts}
                                onChange={(event) => setCompanyBankAccounts(event.target.value)}
                                rows={5}
                                placeholder={"First National Bank — Branch: Pioneer — Account: ...\nStandard Bank — Branch: City — Account: ..."}
                            />
                            <p className="text-xs text-muted-foreground">The current LoanHub company model does not store structured company bank accounts, so enter the approved account block here when required.</p>
                        </div>
                    )}

                    <div className="rounded-xl border bg-muted/30 p-3 text-xs leading-5 text-muted-foreground">
                        Client confirmation and good-standing letters are blocked when LoanHub currently shows arrears. Settlement letters require a live balance with no arrears. Stronger historical claims such as “never missed a payment” remain for staff review rather than being asserted automatically.
                    </div>
                </div>
                <DialogFooter>
                    <Button type="button" variant="outline" onClick={() => setPendingClientTemplate(null)} disabled={Boolean(creating)}>Cancel</Button>
                    <Button type="button" onClick={createClientLetter} disabled={Boolean(creating) || clientDataLoading}>
                        {creating === pendingClientTemplate?.key ? <Loader2 className="animate-spin" /> : <FilePlus2 />}
                        Create auto-filled letter
                    </Button>
                </DialogFooter>
            </CustomDialog>

            <ConfirmDialog open={Boolean(deleteTarget)} onOpenChange={(open) => !open && !deleting && setDeleteTarget(null)} title="Remove document?" description={`Remove ${deleteTarget?.title ?? "this document"}? Published Word or PDF copies in the file library are not removed.`} confirmLabel="Remove document" destructive loading={deleting} onConfirm={removeConfirmed} />
        </main>
    );
}
