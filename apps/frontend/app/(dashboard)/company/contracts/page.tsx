"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { FileCheck2, FileSignature, MailCheck, RefreshCcw, ShieldCheck } from "lucide-react";

import { originationApi } from "@/api/origination";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { PageLoader } from "@/components/ui/page-loader";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatDate, titleCase } from "@/lib/format";
import type { LoanContract } from "@/types/origination";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";


type SigningMethod = "wet_ink" | "electronic" | "email_otp";

type EmailOtpStatus = {
  contract_id: string;
  borrower_name: string;
  masked_email: string;
  recipient_email_required: boolean;
  email_transport_ready: boolean;
  pending: boolean;
  expires_at: string | null;
  attempts_remaining: number;
};

type EmailOtpRequest = {
  status: "sent";
  contract_id: string;
  masked_email: string;
  expires_at: string;
  attempts_remaining: number;
};

function borrowerDetails(contract: LoanContract): { name: string; email: string | null } {
  const raw = contract.terms_snapshot?.borrower;
  const borrower = raw && typeof raw === "object" && !Array.isArray(raw)
    ? raw as Record<string, unknown>
    : {};
  const name = String(borrower.name ?? "Borrower").trim() || "Borrower";
  const emailValue = String(borrower.email ?? "").trim();
  return { name, email: emailValue || null };
}

function replaceContract(rows: LoanContract[], updated: LoanContract): LoanContract[] {
  return rows.map((item) => item.id === updated.id ? updated : item);
}

export default function ContractsPage() {
  const [contracts, setContracts] = useState<LoanContract[]>([]);
  const [selected, setSelected] = useState<LoanContract | null>(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState<string | null>(null);
  const [signatureMethod, setSignatureMethod] = useState<SigningMethod>("wet_ink");
  const [signatureName, setSignatureName] = useState("");
  const [witnessName, setWitnessName] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [otpStatus, setOtpStatus] = useState<EmailOtpStatus | null>(null);
  const [otpRecipientEmail, setOtpRecipientEmail] = useState("");

  const load = useCallback(async (preferredContractId?: string) => {
    setLoading((current) => current || contracts.length === 0);
    try {
      const rows = await originationApi.listContracts();
      setContracts(rows);
      if (preferredContractId) {
        setSelected(rows.find((item) => item.id === preferredContractId) ?? null);
      }
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Contracts could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [contracts.length]);

  useEffect(() => {
    void load();
  }, [load]);

  const metrics = useMemo(() => ({
    awaitingBorrower: contracts.filter((item) => !item.borrower_signed_at).length,
    awaitingCompany: contracts.filter((item) => item.borrower_signed_at && !item.company_signed_at).length,
    signed: contracts.filter((item) => item.status === "signed").length,
  }), [contracts]);

  async function openContract(contract: LoanContract) {
    setSelected(contract);
    const borrower = borrowerDetails(contract);
    setSignatureName(contract.borrower_signature_name ?? borrower.name);
    setWitnessName(contract.witness_name ?? "");
    setSignatureMethod("wet_ink");
    setOtpCode("");
    setOtpStatus(null);
    setOtpRecipientEmail(borrower.email ?? "");
  }

  async function refreshOtpStatus(contract: LoanContract) {
    setWorking(`status:${contract.id}`);
    try {
      const response = await api.get<EmailOtpStatus>(`/contract-signing/contracts/${contract.id}/email-otp/status`);
      setOtpStatus(response.data);
      return response.data;
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Email + OTP signing status could not be loaded."));
      return null;
    } finally {
      setWorking(null);
    }
  }

  async function changeSigningMethod(value: string) {
    const method = value as SigningMethod;
    setSignatureMethod(method);
    setOtpCode("");
    if (method === "email_otp" && selected && !selected.borrower_signed_at) {
      await refreshOtpStatus(selected);
    } else {
      setOtpStatus(null);
    }
  }

  async function signBorrower(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || selected.borrower_signed_at || signatureMethod === "email_otp") return;
    if (signatureName.trim().length < 2) {
      toast.warning("Enter the borrower signature name.");
      return;
    }
    setWorking(`borrower:${selected.id}`);
    try {
      const updated = await originationApi.borrowerSign(selected.id, {
        signature_name: signatureName.trim(),
        signature_method: signatureMethod,
        witness_name: witnessName.trim() || null,
      });
      setContracts((rows) => replaceContract(rows, updated));
      setSelected(updated);
      toast.success("Borrower signature recorded");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Borrower signature could not be recorded."));
    } finally {
      setWorking(null);
    }
  }

  async function requestEmailOtp() {
    if (!selected || selected.borrower_signed_at) return;
    const recipientEmail = otpRecipientEmail.trim().toLowerCase();
    const emailRequired = Boolean(otpStatus?.recipient_email_required && !otpStatus.pending);
    if (emailRequired && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(recipientEmail)) {
      toast.warning("Enter a valid borrower email address.");
      return;
    }
    setWorking(`otp-request:${selected.id}`);
    try {
      const response = await api.post<EmailOtpRequest>(
        `/contract-signing/contracts/${selected.id}/email-otp/request`,
        emailRequired ? { recipient_email: recipientEmail } : {},
      );
      setOtpStatus({
        contract_id: response.data.contract_id,
        borrower_name: borrowerDetails(selected).name,
        masked_email: response.data.masked_email,
        recipient_email_required: false,
        email_transport_ready: true,
        pending: true,
        expires_at: response.data.expires_at,
        attempts_remaining: response.data.attempts_remaining,
      });
      toast.success("Signing code sent", {
        description: `A one-time code was sent to ${response.data.masked_email}.`,
      });
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The signing code could not be sent."));
    } finally {
      setWorking(null);
    }
  }

  async function verifyEmailOtp() {
    if (!selected || selected.borrower_signed_at) return;
    if (!/^\d{6}$/.test(otpCode.trim())) {
      toast.warning("Enter the six-digit code sent to the borrower.");
      return;
    }
    setWorking(`otp-verify:${selected.id}`);
    try {
      await api.post(`/contract-signing/contracts/${selected.id}/email-otp/verify`, { otp: otpCode.trim() });
      setOtpCode("");
      setOtpStatus(null);
      await load(selected.id);
      toast.success("Email + OTP signature verified", {
        description: "The borrower signature evidence has been recorded and the contract PDF refreshed.",
      });
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The signing code could not be verified."));
      await refreshOtpStatus(selected);
    } finally {
      setWorking(null);
    }
  }

  async function companySign() {
    if (!selected || selected.company_signed_at) return;
    setWorking(`company:${selected.id}`);
    try {
      const updated = await originationApi.companySign(selected.id, "electronic");
      setContracts((rows) => replaceContract(rows, updated));
      setSelected(updated);
      toast.success(updated.status === "signed" ? "Contract fully signed and locked" : "Company signature recorded");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Company signature could not be recorded."));
    } finally {
      setWorking(null);
    }
  }

  async function openPdf(contract: LoanContract) {
    const popup = window.open("", "_blank", "width=1100,height=850");
    setWorking(`pdf:${contract.id}`);
    try {
      await originationApi.openContractForPrinting(contract, popup);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The contract PDF could not be opened."));
    } finally {
      setWorking(null);
    }
  }

  if (loading && contracts.length === 0) return <PageLoader rows={8} />;

  const selectedBorrower = selected ? borrowerDetails(selected) : null;
  const otpBusy = Boolean(selected && working?.includes(selected.id));

  return (
    <main className="loanhub-page space-y-6">
      <section className="loanhub-hero p-6 sm:p-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.24em] text-primary">Secure contract execution</p>
            <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Contract signing centre</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
              Review agreements, record in-person signatures, or send a single-use Email + OTP challenge to the borrower. Disbursement remains blocked until the required contract is fully signed.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void load(selected?.id)}><RefreshCcw className="h-4 w-4" />Refresh</Button>
            <Button asChild><Link href="/company/loans?tab=contracts"><FileSignature className="h-4 w-4" />Loan workspace</Link></Button>
          </div>
        </div>
      </section>

      <div className="grid gap-4 sm:grid-cols-3">
        <Metric label="Awaiting borrower" value={metrics.awaitingBorrower} icon={MailCheck} />
        <Metric label="Awaiting company" value={metrics.awaitingCompany} icon={ShieldCheck} />
        <Metric label="Fully signed" value={metrics.signed} icon={FileCheck2} />
      </div>

      <Card className="overflow-hidden rounded-3xl">
        <CardHeader>
          <CardTitle>Loan contracts</CardTitle>
          <CardDescription>Select a contract to review its PDF and complete the permitted signing flow.</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader><TableRow><TableHead>Contract</TableHead><TableHead>Borrower</TableHead><TableHead>Email</TableHead><TableHead>Status</TableHead><TableHead>Created</TableHead><TableHead className="text-right">Action</TableHead></TableRow></TableHeader>
              <TableBody>
                {contracts.length === 0 ? <TableRow><TableCell colSpan={6} className="h-32 text-center text-muted-foreground">No contracts have been generated.</TableCell></TableRow> : contracts.map((contract) => {
                  const borrower = borrowerDetails(contract);
                  return <TableRow key={contract.id}>
                    <TableCell><p className="font-mono text-xs font-black text-primary">{contract.contract_number}</p><p className="text-xs text-muted-foreground">Version {contract.version}</p></TableCell>
                    <TableCell className="font-bold">{borrower.name}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{borrower.email ?? "No email"}</TableCell>
                    <TableCell><Badge variant={contract.status === "signed" ? "default" : "secondary"}>{titleCase(contract.status)}</Badge></TableCell>
                    <TableCell>{formatDate(contract.created_at)}</TableCell>
                    <TableCell className="text-right"><Button size="sm" onClick={() => void openContract(contract)}>Open signing</Button></TableCell>
                  </TableRow>;
                })}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {selected ? (
        <Card className="rounded-3xl border-primary/20">
          <CardHeader>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div><CardTitle>{selected.contract_number}</CardTitle><CardDescription>{selectedBorrower?.name} · {selectedBorrower?.email ?? "No borrower email"}</CardDescription></div>
              <Badge variant={selected.status === "signed" ? "default" : "secondary"}>{titleCase(selected.status)}</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            <Alert><ShieldCheck className="h-4 w-4" /><AlertTitle>Signing control</AlertTitle><AlertDescription>Email + OTP codes are single-use, expire after 10 minutes, and are never stored in plaintext. A verified code records the borrower signature evidence and refreshes the contract PDF.</AlertDescription></Alert>

            <div className="grid gap-3 sm:grid-cols-3">
              <StatusValue label="Borrower" value={selected.borrower_signed_at ? `Signed ${formatDate(selected.borrower_signed_at)}` : "Pending"} />
              <StatusValue label="Company" value={selected.company_signed_at ? `Signed ${formatDate(selected.company_signed_at)}` : "Pending"} />
              <StatusValue label="Contract" value={selected.status === "signed" ? "Locked after both signatures" : "Open for permitted signatures"} />
            </div>

            {!selected.borrower_signed_at ? (
              <form onSubmit={signBorrower} className="space-y-5 rounded-3xl border bg-muted/10 p-5">
                <div className="grid gap-5 sm:grid-cols-2">
                  <div className="space-y-2"><Label>Borrower signing method</Label><Select value={signatureMethod} onValueChange={(value) => void changeSigningMethod(value)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="wet_ink">Wet ink</SelectItem><SelectItem value="electronic">Electronic</SelectItem><SelectItem value="email_otp">Email + OTP</SelectItem></SelectContent></Select></div>
                  {signatureMethod !== "email_otp" ? <div className="space-y-2"><Label>Witness name</Label><Input value={witnessName} onChange={(event) => setWitnessName(event.target.value)} /></div> : null}
                </div>

                {signatureMethod === "email_otp" ? (
                  <div className="space-y-4 rounded-2xl border bg-background p-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <div><p className="font-black">Email verification</p><p className="text-sm text-muted-foreground">{otpStatus?.masked_email ?? selectedBorrower?.email ?? "Borrower email"}</p></div>
                      <LoadingButton type="button" variant="outline" loading={working === `otp-request:${selected.id}`} onClick={() => void requestEmailOtp()}>{otpStatus?.pending ? "Send new code" : "Send signing code"}</LoadingButton>
                    </div>
                    {otpStatus && !otpStatus.email_transport_ready ? <Alert variant="destructive"><AlertTitle>Email delivery is not configured</AlertTitle><AlertDescription>Configure the company Email integration or the production SMTP environment before using Email + OTP.</AlertDescription></Alert> : null}
                    {otpStatus?.recipient_email_required && !otpStatus.pending ? <div className="space-y-2"><Label>Borrower email</Label><Input type="email" autoComplete="email" value={otpRecipientEmail} onChange={(event) => setOtpRecipientEmail(event.target.value)} placeholder="borrower@example.com" /><p className="text-xs leading-5 text-muted-foreground">LoanHub could not find an email on the client profile or contract. Confirm the address with the borrower and enter it for this signing request.</p></div> : null}
                    {otpStatus?.pending ? <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end"><div className="space-y-2"><Label>Six-digit code</Label><Input inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={otpCode} onChange={(event) => setOtpCode(event.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="000000" /><p className="text-xs text-muted-foreground">{otpStatus.attempts_remaining} attempt(s) remaining{otpStatus.expires_at ? ` · expires ${formatDate(otpStatus.expires_at)}` : ""}</p></div><LoadingButton type="button" loading={working === `otp-verify:${selected.id}`} onClick={() => void verifyEmailOtp()}>Verify & sign</LoadingButton></div> : null}
                  </div>
                ) : (
                  <div className="space-y-2"><Label>Borrower signature name</Label><Input value={signatureName} onChange={(event) => setSignatureName(event.target.value)} /></div>
                )}

                {signatureMethod !== "email_otp" ? <div className="flex justify-end"><LoadingButton loading={working === `borrower:${selected.id}`}>Record borrower signature</LoadingButton></div> : null}
              </form>
            ) : null}

            <div className="flex flex-wrap justify-end gap-2">
              <LoadingButton type="button" variant="outline" loading={working === `pdf:${selected.id}`} onClick={() => void openPdf(selected)}>Open PDF</LoadingButton>
              {!selected.company_signed_at ? <LoadingButton type="button" loading={working === `company:${selected.id}`} onClick={() => void companySign()}>Company sign electronically</LoadingButton> : null}
            </div>
          </CardContent>
        </Card>
      ) : null}
    </main>
  );
}

function Metric({ label, value, icon: Icon }: { label: string; value: number; icon: typeof MailCheck }) {
  return <Card className="rounded-3xl"><CardContent className="flex items-center gap-4 p-5"><div className="rounded-2xl bg-primary/10 p-3 text-primary"><Icon className="h-5 w-5" /></div><div><p className="text-2xl font-black">{value}</p><p className="text-sm text-muted-foreground">{label}</p></div></CardContent></Card>;
}

function StatusValue({ label, value }: { label: string; value: string }) {
  return <div className="rounded-2xl border p-4"><p className="text-xs font-black uppercase tracking-wide text-muted-foreground">{label}</p><p className="mt-1 text-sm font-bold">{value}</p></div>;
}
