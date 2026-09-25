"use client";

import { useEffect, useState } from "react";
import { MailCheck } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { LoanContract } from "@/types/origination";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";


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

type Props = {
  contract: LoanContract;
  borrowerEmail?: string | null;
  disabled?: boolean;
  onVerified: () => void | Promise<void>;
};

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function EmailOtpSigningPanel({ contract, borrowerEmail, disabled = false, onVerified }: Props) {
  const [status, setStatus] = useState<EmailOtpStatus | null>(null);
  const [recipientEmail, setRecipientEmail] = useState(borrowerEmail ?? "");
  const [otpCode, setOtpCode] = useState("");
  const [working, setWorking] = useState<"status" | "request" | "verify" | null>(null);

  useEffect(() => {
    setRecipientEmail(borrowerEmail ?? "");
    setOtpCode("");
    setStatus(null);

    let cancelled = false;
    const loadStatus = async () => {
      setWorking("status");
      try {
        const response = await api.get<EmailOtpStatus>(
          `/contract-signing/contracts/${contract.id}/email-otp/status`,
        );
        if (!cancelled) setStatus(response.data);
      } catch (error: unknown) {
        if (!cancelled) {
          toast.error(getErrorMessage(error, "Email + OTP signing status could not be loaded."));
        }
      } finally {
        if (!cancelled) setWorking(null);
      }
    };

    void loadStatus();
    return () => {
      cancelled = true;
    };
  }, [borrowerEmail, contract.id]);

  const emailRequired = Boolean(status?.recipient_email_required && !status.pending);
  const cleanedEmail = recipientEmail.trim().toLowerCase();
  const validFallbackEmail = EMAIL_PATTERN.test(cleanedEmail);
  const sendDisabled = disabled
    || working !== null
    || status?.email_transport_ready === false
    || (emailRequired && !validFallbackEmail);

  async function requestCode() {
    if (emailRequired && !validFallbackEmail) {
      toast.warning("Enter a valid borrower email address.");
      return;
    }

    setWorking("request");
    try {
      const response = await api.post<EmailOtpRequest>(
        `/contract-signing/contracts/${contract.id}/email-otp/request`,
        emailRequired ? { recipient_email: cleanedEmail } : {},
      );
      setOtpCode("");
      setStatus({
        contract_id: response.data.contract_id,
        borrower_name: status?.borrower_name ?? "Borrower",
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

  async function verifyCode() {
    const code = otpCode.trim();
    if (!/^\d{6}$/.test(code)) {
      toast.warning("Enter the six-digit code sent to the borrower.");
      return;
    }

    setWorking("verify");
    try {
      await api.post(`/contract-signing/contracts/${contract.id}/email-otp/verify`, { otp: code });
      setOtpCode("");
      setStatus(null);
      toast.success("Email + OTP signature verified", {
        description: "The borrower signature evidence was recorded and the contract PDF refreshed.",
      });
      await onVerified();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The signing code could not be verified."));
      try {
        const response = await api.get<EmailOtpStatus>(
          `/contract-signing/contracts/${contract.id}/email-otp/status`,
        );
        setStatus(response.data);
      } catch {
        // Keep the original verification error visible; status refresh is best effort.
      }
    } finally {
      setWorking(null);
    }
  }

  return (
    <div className="space-y-4 rounded-2xl border bg-background p-4 sm:col-span-2">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="flex items-center gap-2 font-black"><MailCheck className="h-4 w-4 text-primary" />Email verification</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {status?.masked_email || borrowerEmail || (emailRequired ? "No borrower email found" : "Checking borrower email…")}
          </p>
        </div>
        <LoadingButton
          type="button"
          variant="outline"
          loading={working === "request" || working === "status"}
          loadingText={working === "status" ? "Finding email…" : "Sending…"}
          disabled={sendDisabled}
          onClick={() => void requestCode()}
        >
          {status?.pending ? "Send new code" : "Send signing code"}
        </LoadingButton>
      </div>

      {status && !status.email_transport_ready ? (
        <Alert variant="destructive">
          <AlertTitle>Email delivery is not configured</AlertTitle>
          <AlertDescription>Configure the company Email integration or production contract-email SMTP settings before using Email + OTP.</AlertDescription>
        </Alert>
      ) : null}

      {emailRequired ? (
        <div className="space-y-2">
          <Label>Borrower email</Label>
          <Input
            type="email"
            autoComplete="email"
            value={recipientEmail}
            disabled={disabled || working !== null}
            onChange={(event) => setRecipientEmail(event.target.value)}
            placeholder="borrower@example.com"
          />
          <p className="text-xs leading-5 text-muted-foreground">
            LoanHub could not find an email on the client profile or contract. Confirm the address with the borrower and enter it for this signing request. The OTP evidence stores only a masked address and cryptographic hash.
          </p>
        </div>
      ) : null}

      {status?.pending ? (
        <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
          <div className="space-y-2">
            <Label>Six-digit code</Label>
            <Input
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={otpCode}
              disabled={disabled || working !== null}
              onChange={(event) => setOtpCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
              placeholder="000000"
            />
            <p className="text-xs text-muted-foreground">
              {status.attempts_remaining} attempt(s) remaining
              {status.expires_at ? ` · expires ${formatDate(status.expires_at)}` : ""}
            </p>
          </div>
          <LoadingButton
            type="button"
            loading={working === "verify"}
            loadingText="Verifying…"
            disabled={disabled || working !== null || otpCode.length !== 6}
            onClick={() => void verifyCode()}
          >
            Verify & sign
          </LoadingButton>
        </div>
      ) : null}
    </div>
  );
}
