"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Banknote,
  BookOpenCheck,
  Camera,
  CheckCircle2,
  Clock3,
  Download,
  FileText,
  FolderOpen,
  Gauge,
  Plus,
  RefreshCcw,
  Scale,
  ShieldCheck,
  Upload,
  UserRound,
  WalletCards,
} from "lucide-react";

import {
  downloadCompanyClientFile,
  getCompanyClientProfile,
  loadCompanyClientFileObjectUrl,
  uploadCompanyClientDocument,
  uploadCompanyClientProfileImage,
} from "@/api/companyClients";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { CompanyClientProfileEditorCards } from "@/components/clients/company-client-profile-editor-cards";
import { ExternalDebtTracker } from "@/components/clients/external-debt-tracker";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { formatDate, formatMoney, titleCase } from "@/lib/format";
import type {
  CompanyClient,
  CompanyClientProfile,
  CompanyClientProfileDocument,
} from "@/types/companyClient";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

const DOCUMENT_TYPES = [
  ["national_id", "National ID"],
  ["passport", "Passport"],
  ["payslip", "Payslip"],
  ["bank_statement", "Bank statement"],
  ["proof_of_residence", "Proof of residence"],
  ["employment_letter", "Employment letter"],
  ["loan_agreement", "Loan agreement"],
  ["other", "Other document"],
] as const;

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "BR";
}

function fileSize(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function ratingClass(score: number | null) {
  if (score === null) return "border-muted bg-muted/40 text-muted-foreground";
  if (score >= 80) return "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
  if (score >= 65) return "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300";
  return "border-destructive/30 bg-destructive/10 text-destructive";
}

function InfoRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="grid min-w-0 gap-1 border-b py-3 last:border-b-0 sm:grid-cols-[minmax(120px,0.75fr)_minmax(0,1.25fr)] sm:gap-4">
      <span className="text-xs font-semibold text-muted-foreground">{label}</span>
      <span className="min-w-0 break-words text-sm font-semibold leading-5">{value === null || value === undefined || value === "" ? "—" : value}</span>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  note,
}: {
  icon: typeof Gauge;
  label: string;
  value: string;
  note: string;
}) {
  return (
    <Card className="min-w-0 rounded-2xl border-border/70 shadow-none">
      <CardContent className="flex min-h-28 items-start gap-3 p-4 sm:p-5">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Icon className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-bold text-muted-foreground">{label}</p>
          <p className="mt-1 break-words text-lg font-black leading-tight sm:text-xl">{value}</p>
          <p className="mt-1.5 text-xs leading-5 text-muted-foreground">{note}</p>
        </div>
      </CardContent>
    </Card>
  );
}

export function CompanyClientProfileDialog({
  open,
  client,
  onOpenChange,
  onStartLoan,
}: {
  open: boolean;
  client: CompanyClient | null;
  onOpenChange: (open: boolean) => void;
  onStartLoan: (client: CompanyClient) => void;
}) {
  const [profile, setProfile] = useState<CompanyClientProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [profileImageUrl, setProfileImageUrl] = useState<string | null>(null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imageUploading, setImageUploading] = useState(false);
  const [imageInputKey, setImageInputKey] = useState(0);
  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState("national_id");
  const [documentDescription, setDocumentDescription] = useState("");
  const [documentConfidential, setDocumentConfidential] = useState(true);
  const [documentUploading, setDocumentUploading] = useState(false);
  const [documentInputKey, setDocumentInputKey] = useState(0);
  const [downloadingFileId, setDownloadingFileId] = useState<string | null>(null);

  const loadProfile = useCallback(async () => {
    if (!client) return;
    setLoading(true);
    setError(null);
    try {
      setProfile(await getCompanyClientProfile(client.id));
    } catch (loadError: unknown) {
      const message = getErrorMessage(loadError, "The borrower profile could not be loaded.");
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    if (!open || !client) return;
    const timer = window.setTimeout(() => void loadProfile(), 0);
    return () => window.clearTimeout(timer);
  }, [client, loadProfile, open]);

  useEffect(() => {
    let active = true;
    let createdUrl: string | null = null;
    const imageId = profile?.profile_image?.id;
    const accountId = profile?.client.id;
    const timer = window.setTimeout(() => {
      if (!open || !imageId || !accountId) {
        setProfileImageUrl(null);
        return;
      }
      void loadCompanyClientFileObjectUrl(accountId, imageId)
        .then((url) => {
          if (!active) {
            URL.revokeObjectURL(url);
            return;
          }
          createdUrl = url;
          setProfileImageUrl(url);
        })
        .catch(() => {
          if (active) setProfileImageUrl(null);
        });
    }, 0);

    return () => {
      active = false;
      window.clearTimeout(timer);
      if (createdUrl) URL.revokeObjectURL(createdUrl);
    };
  }, [open, profile?.client.id, profile?.profile_image?.id]);

  const currentClient = profile?.client ?? client;
  const rating = profile?.payment_rating;
  const ratingScore = rating?.score ?? null;
  async function uploadImage() {
    if (!client || !imageFile) {
      toast.warning("Choose a profile image first.");
      return;
    }
    if (!imageFile.type.startsWith("image/")) {
      toast.error("The profile image must be an image file.");
      return;
    }
    setImageUploading(true);
    try {
      await uploadCompanyClientProfileImage(client.id, imageFile);
      setImageFile(null);
      setImageInputKey((value) => value + 1);
      await loadProfile();
      toast.success("Borrower profile image updated.");
    } catch (uploadError: unknown) {
      toast.error(getErrorMessage(uploadError, "The profile image could not be uploaded."));
    } finally {
      setImageUploading(false);
    }
  }

  async function uploadDocument() {
    if (!client || !documentFile) {
      toast.warning("Choose a borrower document first.");
      return;
    }
    setDocumentUploading(true);
    try {
      await uploadCompanyClientDocument(client.id, {
        file: documentFile,
        documentType,
        description: documentDescription,
        isConfidential: documentConfidential,
      });
      setDocumentFile(null);
      setDocumentDescription("");
      setDocumentInputKey((value) => value + 1);
      await loadProfile();
      toast.success("Borrower document uploaded.");
    } catch (uploadError: unknown) {
      toast.error(getErrorMessage(uploadError, "The borrower document could not be uploaded."));
    } finally {
      setDocumentUploading(false);
    }
  }

  async function downloadDocument(file: CompanyClientProfileDocument) {
    if (!client) return;
    setDownloadingFileId(file.id);
    try {
      await downloadCompanyClientFile(client.id, file);
    } catch (downloadError: unknown) {
      toast.error(getErrorMessage(downloadError, "The borrower document could not be downloaded."));
    } finally {
      setDownloadingFileId(null);
    }
  }

  function startQuickRequest() {
    if (!currentClient) return;
    onOpenChange(false);
    onStartLoan(currentClient);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[calc(100dvh-1rem)] w-[calc(100vw-1rem)] max-w-none flex-col gap-0 overflow-hidden rounded-2xl p-0 sm:h-[92vh] sm:w-[96vw] sm:max-w-[96vw] sm:rounded-3xl sm:p-0 xl:max-w-[88rem]">
        <DialogHeader className="shrink-0 border-b bg-gradient-to-r from-primary/10 via-background to-sky-500/10 px-4 py-4 pr-14 sm:px-6 sm:py-5 lg:px-8">
          <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-center">
            <div className="flex min-w-0 items-start gap-3 sm:items-center sm:gap-5">
              <Avatar className="h-16 w-16 shrink-0 border-4 border-background shadow-lg sm:h-24 sm:w-24">
                {profileImageUrl ? <AvatarImage src={profileImageUrl} alt={`${currentClient?.full_name ?? "Borrower"} profile`} /> : null}
                <AvatarFallback className="text-lg font-black sm:text-2xl">{initials(currentClient?.full_name ?? "Borrower")}</AvatarFallback>
              </Avatar>
              <div className="min-w-0 flex-1">
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  <DialogTitle className="min-w-0 break-words text-xl font-black leading-tight sm:text-3xl">{currentClient?.full_name ?? "Borrower profile"}</DialogTitle>
                  {currentClient ? <Badge variant={currentClient.status === "active" ? "default" : "secondary"}>{titleCase(currentClient.status)}</Badge> : null}
                  {rating ? <Badge variant="outline" className={ratingClass(rating.score)}>Rating {rating.grade} · {rating.label}</Badge> : null}
                </div>
                <DialogDescription className="mt-2 flex min-w-0 flex-wrap gap-2 text-xs sm:text-sm">
                  <span className="max-w-full break-all rounded-full border bg-background/70 px-2.5 py-1 font-mono">{currentClient?.account_reference ?? "Loading account..."}</span>
                  <span className="max-w-full break-all rounded-full border bg-background/70 px-2.5 py-1">ID: {currentClient?.national_id || currentClient?.passport_number || "Not recorded"}</span>
                  {currentClient?.phone ? <span className="rounded-full border bg-background/70 px-2.5 py-1">{currentClient.phone}</span> : null}
                </DialogDescription>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:items-center xl:justify-end">
              <Button className="w-full sm:w-auto" variant="outline" size="sm" disabled={loading || !client} onClick={() => void loadProfile()}>
                <RefreshCcw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh
              </Button>
              {currentClient ? (
                <>
                  <Button className="w-full sm:w-auto" variant="outline" size="sm" asChild>
                    <Link href={`/company/documents?client=${currentClient.id}`}><FileText className="h-4 w-4" />Letters</Link>
                  </Button>
                  <Button className="w-full sm:w-auto" variant="outline" size="sm" asChild disabled={currentClient.status !== "active"}>
                    <Link href={`/company/origination/new?borrower=${currentClient.borrower_id}`}><BookOpenCheck className="h-4 w-4" />Assessment</Link>
                  </Button>
                  <Button className="w-full sm:w-auto" size="sm" disabled={currentClient.status !== "active"} onClick={startQuickRequest}>
                    <Plus className="h-4 w-4" />Quick request
                  </Button>
                </>
              ) : null}
            </div>
          </div>
        </DialogHeader>

        {error ? (
          <div className="p-5">
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Profile unavailable</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          </div>
        ) : null}

        <Tabs defaultValue="overview" className="flex min-h-0 flex-1 flex-col">
          <div className="shrink-0 overflow-x-auto border-b bg-background/95 px-3 py-2 backdrop-blur sm:px-6 lg:px-8">
            <TabsList className="grid h-auto min-w-[560px] grid-cols-4 gap-1 sm:min-w-0">
              <TabsTrigger className="min-h-10 gap-2" value="overview"><UserRound className="h-4 w-4" />Overview</TabsTrigger>
              <TabsTrigger className="min-h-10 gap-2" value="payments"><Gauge className="h-4 w-4" />Payments & loans</TabsTrigger>
              <TabsTrigger className="min-h-10 gap-2" value="documents"><FolderOpen className="h-4 w-4" />Documents</TabsTrigger>
              <TabsTrigger className="min-h-10 gap-2" value="activity"><Scale className="h-4 w-4" />Activity</TabsTrigger>
            </TabsList>
          </div>

          <ScrollArea className="min-h-0 flex-1 bg-muted/15">
            <div className="mx-auto w-full max-w-[84rem] p-4 sm:p-6 lg:p-8">
              {loading && !profile ? (
                <div className="flex min-h-80 items-center justify-center text-sm text-muted-foreground">Loading complete borrower profile...</div>
              ) : null}

              <TabsContent value="overview" className="mt-0 space-y-5">
                {profile ? (
                  <>
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                      <StatCard icon={Gauge} label="Payment rating" value={ratingScore === null ? "Not rated" : `${ratingScore}/100`} note={rating?.label ?? "No payment history"} />
                      <StatCard icon={WalletCards} label="Outstanding" value={formatMoney(profile.stats.outstanding_balance)} note={`${profile.stats.active_loans} active loan${profile.stats.active_loans === 1 ? "" : "s"}`} />
                      <StatCard icon={Banknote} label="Lifetime paid" value={formatMoney(profile.stats.lifetime_paid_total)} note={`From ${profile.stats.total_loans} total loan${profile.stats.total_loans === 1 ? "" : "s"}`} />
                      <StatCard icon={Clock3} label="Overdue position" value={String(profile.payment_rating.overdue_installments)} note={`${profile.stats.defaulted_loans} defaulted loan${profile.stats.defaulted_loans === 1 ? "" : "s"}`} />
                    </div>

                    <CompanyClientProfileEditorCards
                      profile={profile}
                      onUpdated={setProfile}
                    />
                  </>
                ) : null}
              </TabsContent>

              <TabsContent value="payments" className="mt-0 space-y-5">
                {profile ? (
                  <>
                    <div className="grid min-w-0 gap-5 xl:grid-cols-[340px_minmax(0,1fr)]">
                      <Card className="rounded-2xl shadow-none">
                        <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Gauge className="h-4 w-4 text-primary" />Payment rating</CardTitle></CardHeader>
                        <CardContent className="space-y-5">
                          <div className={`rounded-2xl border p-5 text-center ${ratingClass(profile.payment_rating.score)}`}>
                            <p className="text-xs font-black uppercase tracking-[0.16em]">Grade {profile.payment_rating.grade}</p>
                            <p className="mt-2 text-5xl font-black">{profile.payment_rating.score ?? "NR"}</p>
                            <p className="mt-1 font-bold">{profile.payment_rating.label}</p>
                          </div>
                          <Progress value={profile.payment_rating.score ?? 0} className="h-3" />
                          <p className="text-sm leading-6 text-muted-foreground">{profile.payment_rating.explanation}</p>
                          <Separator />
                          <InfoRow label="On-time rate" value={`${Math.round(profile.payment_rating.on_time_rate * 100)}%`} />
                          <InfoRow label="Completion rate" value={`${Math.round(profile.payment_rating.completion_rate * 100)}%`} />
                          <InfoRow label="Average days late" value={profile.payment_rating.average_days_late} />
                          <InfoRow label="Last payment" value={formatDateTime(profile.payment_rating.last_payment_at)} />
                        </CardContent>
                      </Card>

                      <div className="grid min-w-0 content-start gap-3 md:grid-cols-2 2xl:grid-cols-3">
                        <StatCard icon={CheckCircle2} label="Paid installments" value={String(profile.payment_rating.paid_installments)} note={`${profile.payment_rating.on_time_installments} paid on time`} />
                        <StatCard icon={Clock3} label="Late installments" value={String(profile.payment_rating.late_installments)} note={`${profile.payment_rating.average_days_late} average days late`} />
                        <StatCard icon={AlertTriangle} label="Overdue installments" value={String(profile.payment_rating.overdue_installments)} note={`${profile.stats.overdue_loans} affected loans`} />
                        <StatCard icon={Banknote} label="Installments paid" value={formatMoney(profile.payment_rating.total_paid_amount)} note={`Against ${formatMoney(profile.payment_rating.total_due_amount)} due`} />
                        <StatCard icon={WalletCards} label="Lifetime borrowed" value={formatMoney(profile.stats.lifetime_principal_total)} note={`${profile.stats.completed_loans} completed loans`} />
                        <StatCard icon={ShieldCheck} label="Legal position" value={String(profile.stats.open_legal_action_count)} note={`${profile.stats.legal_action_count} total legal actions`} />
                      </div>
                    </div>

                    <ExternalDebtTracker
                      accountId={profile.client.id}
                      debts={profile.external_debts}
                      canEdit={profile.permissions.can_edit_profile}
                      onChanged={(externalDebts) => {
                        const activeStatuses = new Set(["active", "defaulted", "restructured", "unknown"]);
                        const activeExternalDebts = externalDebts.filter((row) => activeStatuses.has(row.status) && Number(row.current_balance || 0) > 0);
                        const externalBalance = activeExternalDebts.reduce((sum, row) => sum + Number(row.current_balance || 0), 0);
                        setProfile((current) => current ? {
                          ...current,
                          external_debts: externalDebts,
                          client: {
                            ...current.client,
                            has_existing_loans: externalBalance > 0 || current.client.active_loan_count > 0,
                            existing_loan_total: externalBalance,
                          },
                        } : current);
                      }}
                    />

                    <Card className="overflow-hidden rounded-2xl shadow-none">
                      <CardHeader><CardTitle className="text-base">Loan history</CardTitle></CardHeader>
                      <CardContent className="p-0">
                        <div className="overflow-x-auto">
                          <table className="w-full min-w-[900px] text-sm">
                            <thead className="border-y bg-muted/30 text-left text-xs text-muted-foreground">
                              <tr><th className="px-4 py-3">Reference</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Principal</th><th className="px-4 py-3">Paid</th><th className="px-4 py-3">Balance</th><th className="px-4 py-3">Installment</th><th className="px-4 py-3">Maturity</th></tr>
                            </thead>
                            <tbody className="divide-y">
                              {profile.loans.map((loan) => (
                                <tr key={loan.id}>
                                  <td className="px-4 py-3"><p className="font-mono font-bold">{loan.loan_reference}</p><p className="text-xs text-muted-foreground">{titleCase(loan.repayment_type)} · {loan.repayment_period} periods</p></td>
                                  <td className="px-4 py-3"><div className="flex flex-wrap gap-1"><Badge variant={loan.is_overdue ? "destructive" : "outline"}>{titleCase(loan.status)}</Badge><Badge variant="secondary">{titleCase(loan.risk_level)} risk</Badge></div>{loan.overdue_installment_count > 0 ? <p className="mt-1 text-xs text-destructive">{loan.overdue_installment_count} overdue</p> : null}</td>
                                  <td className="px-4 py-3 font-semibold">{formatMoney(loan.principal_amount)}</td>
                                  <td className="px-4 py-3 font-semibold">{formatMoney(loan.amount_paid)}</td>
                                  <td className="px-4 py-3 font-black">{formatMoney(loan.balance)}</td>
                                  <td className="px-4 py-3">{formatMoney(loan.installment_amount)}</td>
                                  <td className="px-4 py-3">{loan.maturity_date ? formatDate(loan.maturity_date) : "—"}</td>
                                </tr>
                              ))}
                              {profile.loans.length === 0 ? <tr><td colSpan={7} className="h-36 px-4 text-center text-muted-foreground">No loan history is available for this borrower in the active company.</td></tr> : null}
                            </tbody>
                          </table>
                        </div>
                      </CardContent>
                    </Card>
                  </>
                ) : null}
              </TabsContent>

              <TabsContent value="documents" className="mt-0 space-y-5">
                {profile ? (
                  <div className="grid min-w-0 gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
                    <div className="space-y-5">
                      <Card className="rounded-2xl shadow-none">
                        <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Camera className="h-4 w-4 text-primary" />Profile image</CardTitle></CardHeader>
                        <CardContent className="space-y-4">
                          <div className="flex justify-center">
                            <Avatar className="h-36 w-36 border-4 border-muted shadow-lg">
                              {profileImageUrl ? <AvatarImage src={profileImageUrl} alt={`${profile.client.full_name} profile`} /> : null}
                              <AvatarFallback className="text-3xl font-black">{initials(profile.client.full_name)}</AvatarFallback>
                            </Avatar>
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="borrower-profile-image">Choose profile image</Label>
                            <Input key={imageInputKey} id="borrower-profile-image" type="file" accept="image/png,image/jpeg,image/webp,image/gif" onChange={(event) => setImageFile(event.target.files?.[0] ?? null)} />
                            <p className="text-xs text-muted-foreground">Use a clear head-and-shoulders photograph. The latest upload becomes the active profile image.</p>
                          </div>
                          <LoadingButton className="w-full" loading={imageUploading} loadingText="Uploading image..." onClick={() => void uploadImage()}>
                            <Camera className="h-4 w-4" />Update profile image
                          </LoadingButton>
                        </CardContent>
                      </Card>

                      <Card className="rounded-2xl shadow-none">
                        <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Upload className="h-4 w-4 text-primary" />Upload document</CardTitle></CardHeader>
                        <CardContent className="space-y-4">
                          <div className="space-y-2">
                            <Label htmlFor="borrower-document-type">Document type</Label>
                            <Select value={documentType} onValueChange={setDocumentType}>
                              <SelectTrigger id="borrower-document-type"><SelectValue /></SelectTrigger>
                              <SelectContent>{DOCUMENT_TYPES.map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent>
                            </Select>
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="borrower-document-file">File</Label>
                            <Input key={documentInputKey} id="borrower-document-file" type="file" accept=".pdf,.png,.jpg,.jpeg,.webp,.doc,.docx,.xls,.xlsx,.csv,.txt" onChange={(event) => setDocumentFile(event.target.files?.[0] ?? null)} />
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="borrower-document-description">Description</Label>
                            <Textarea id="borrower-document-description" value={documentDescription} onChange={(event) => setDocumentDescription(event.target.value)} rows={3} placeholder="Optional notes about this document" />
                          </div>
                          <label className="flex items-start gap-3 rounded-xl border p-3 text-sm">
                            <Checkbox checked={documentConfidential} onCheckedChange={(checked) => setDocumentConfidential(checked === true)} />
                            <span><span className="font-bold">Confidential document</span><span className="mt-0.5 block text-xs text-muted-foreground">Restrict access to authorised borrower-profile users.</span></span>
                          </label>
                          <LoadingButton className="w-full" loading={documentUploading} loadingText="Uploading document..." onClick={() => void uploadDocument()}>
                            <Upload className="h-4 w-4" />Upload document
                          </LoadingButton>
                        </CardContent>
                      </Card>
                    </div>

                    <Card className="rounded-2xl shadow-none">
                      <CardHeader>
                        <div className="flex items-center justify-between gap-3"><CardTitle className="flex items-center gap-2 text-base"><FolderOpen className="h-4 w-4 text-primary" />Borrower documents</CardTitle><Badge variant="outline">{profile.documents.length}</Badge></div>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        {profile.documents.map((file) => (
                          <div key={file.id} className="flex flex-col gap-3 rounded-xl border p-4 sm:flex-row sm:items-center sm:justify-between">
                            <div className="flex min-w-0 items-start gap-3">
                              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary"><FileText className="h-5 w-5" /></div>
                              <div className="min-w-0">
                                <p className="truncate font-bold">{file.original_name}</p>
                                <div className="mt-1 flex flex-wrap gap-1.5"><Badge variant="secondary">{titleCase(file.document_type)}</Badge>{file.is_confidential ? <Badge variant="outline"><ShieldCheck className="h-3 w-3" />Confidential</Badge> : null}</div>
                                <p className="mt-1 text-xs text-muted-foreground">{fileSize(file.size_bytes)} · {formatDateTime(file.created_at)}</p>
                                {file.description ? <p className="mt-1 text-xs text-muted-foreground">{file.description}</p> : null}
                              </div>
                            </div>
                            <Button variant="outline" size="sm" disabled={downloadingFileId === file.id} onClick={() => void downloadDocument(file)}>
                              <Download className="h-4 w-4" />{downloadingFileId === file.id ? "Downloading..." : "Download"}
                            </Button>
                          </div>
                        ))}
                        {profile.documents.length === 0 ? <div className="flex min-h-64 flex-col items-center justify-center rounded-2xl border border-dashed text-center"><FolderOpen className="h-10 w-10 text-muted-foreground" /><p className="mt-3 font-black">No borrower documents yet</p><p className="mt-1 max-w-md text-sm text-muted-foreground">Upload identity, income, residence, employment and agreement records from the panel on the left.</p></div> : null}
                      </CardContent>
                    </Card>
                  </div>
                ) : null}
              </TabsContent>

              <TabsContent value="activity" className="mt-0 space-y-5">
                {profile ? (
                  <>
                    <div className="grid gap-3 md:grid-cols-3">
                      <StatCard icon={FileText} label="Comments" value={String(profile.stats.comment_count)} note="Internal borrower notes" />
                      <StatCard icon={Scale} label="Legal actions" value={String(profile.stats.legal_action_count)} note={`${profile.stats.open_legal_action_count} currently open`} />
                      <StatCard icon={FolderOpen} label="Documents" value={String(profile.stats.document_count)} note="Company-owned borrower records" />
                    </div>
                    <Card className="rounded-2xl shadow-none">
                      <CardHeader><CardTitle className="text-base">Recent comments and legal activity</CardTitle></CardHeader>
                      <CardContent className="space-y-3">
                        {profile.recent_case_entries.map((entry) => (
                          <div key={entry.id} className="grid gap-3 rounded-xl border p-4 md:grid-cols-[150px_1fr_180px]">
                            <div><Badge variant={entry.entry_type === "legal_action" ? "destructive" : "secondary"}>{entry.entry_type === "legal_action" ? "Legal action" : "Comment"}</Badge><p className="mt-2 text-xs font-bold">{titleCase(entry.category)}</p></div>
                            <div><p className="font-black">{entry.title || (entry.entry_type === "legal_action" ? "Legal action" : "Client comment")}</p><p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{entry.body}</p>{entry.reference_number ? <p className="mt-2 text-xs">Reference: <span className="font-mono font-bold">{entry.reference_number}</span></p> : null}</div>
                            <div className="md:text-right"><Badge variant="outline">{titleCase(entry.status)}</Badge><p className="mt-2 text-xs font-semibold">{entry.created_by_name || "Company user"}</p><p className="text-xs text-muted-foreground">{formatDateTime(entry.created_at)}</p></div>
                          </div>
                        ))}
                        {profile.recent_case_entries.length === 0 ? <div className="flex min-h-56 flex-col items-center justify-center rounded-2xl border border-dashed text-center"><Scale className="h-10 w-10 text-muted-foreground" /><p className="mt-3 font-black">No comments or legal activity</p><p className="mt-1 text-sm text-muted-foreground">This borrower has no recorded case activity in the active company.</p></div> : null}
                      </CardContent>
                    </Card>
                  </>
                ) : null}
              </TabsContent>
            </div>
          </ScrollArea>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
