"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ContractSignatureCapture } from "@/components/contracts/contract-signature-capture";
import { WacomSignatureField } from "@/components/contracts/wacom-signature-field";

// An opt-in UI affordance only. Hardware capture remains disabled until
// the separate enrolled-workstation challenge signer and backend approval
// workflow can supply the exact field/session-bound preview ticket.
const showWacomTestPreviewUI = process.env.NEXT_PUBLIC_LOANHUB_WACOM_PREVIEW_UI === "true";

async function unconfiguredWacomPreviewAuthorization(): Promise<never> {
  throw new Error("Wacom workstation authorization is not configured");
}

type Preflight = {
  contract_id: string;
  contract_number: string;
  contract_version: number;
  contract_hash: string;
  ready: boolean;
  blockers: string[];
  requires_identity_verification: boolean;
  requires_explicit_signer_consent: boolean;
  capture_is_signature: false;
};

type PadSession = {
  session_id: string;
  contract_id: string;
  contract_hash?: string;
  status: string;
  expires_at: string;
  capture_enabled: false;
  reason?: string;
};

type PadSessionStatus = {
  session_id: string;
  contract_id: string;
  status: string;
  expires_at: string;
  capture_enabled: false;
  preview_eligible: boolean;
  preview_blockers: string[];
  workstation_capture_authorized: false;
};

/**
 * Operator-only signing preparation. Never interprets local hardware status
 * or a browser stroke preview as signer identity, consent or legal signing.
 */
export function ContractPadPreflight({ contractId }: { contractId: string }) {
  const [check, setCheck] = useState<Preflight | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [session, setSession] = useState<PadSession | null>(null);
  const [sessionStatus, setSessionStatus] = useState<PadSessionStatus | null>(null);
  const [sessionStatusError, setSessionStatusError] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let mounted = true;
    setCheck(null);
    setError(null);
    setSession(null);
    setSessionStatus(null);
    setSessionStatusError(false);
    api.get<Preflight>(`/contract-signing/contracts/${contractId}/pad/preflight`)
      .then(({ data }) => { if (mounted) setCheck(data); })
      .catch(() => { if (mounted) setError("Could not verify signing permissions and contract state."); });
    return () => { mounted = false; };
  }, [contractId]);

  // Recheck persisted session eligibility while the operator is on this
  // contract. Errors fail closed; status is advisory and never authorizes
  // capture, upload, consent or signing.
  useEffect(() => {
    if (!session) {
      return;
    }
    let active = true;
    setSessionStatus(null);
    setSessionStatusError(false);
    const path = `/contract-signing/contracts/${encodeURIComponent(contractId)}/pad/sessions/${encodeURIComponent(session.session_id)}`;
    const refresh = async () => {
      try {
        const { data } = await api.get<PadSessionStatus>(path);
        if (!active) return;
        if (data.session_id !== session.session_id || data.contract_id !== contractId ||
            data.capture_enabled !== false || data.workstation_capture_authorized !== false ||
            typeof data.preview_eligible !== "boolean" ||
            !Array.isArray(data.preview_blockers) ||
            data.preview_blockers.some((reason) => typeof reason !== "string")) {
          setSessionStatus(null);
          setSessionStatusError(true);
          return;
        }
        setSessionStatus(data);
        setSessionStatusError(false);
      } catch {
        if (active) {
          setSessionStatus(null);
          setSessionStatusError(true);
        }
      }
    };
    void refresh();
    const interval = window.setInterval(() => { void refresh(); }, 5000);
    return () => { active = false; window.clearInterval(interval); };
  }, [contractId, session]);

  async function createSession() {
    if (!check?.ready || busy || session) return;
    setBusy(true);
    setError(null);
    try {
      const { data } = await api.post<PadSession>(
        `/contract-signing/contracts/${contractId}/pad/sessions`,
      );
      if (data.contract_hash !== check.contract_hash || data.contract_id !== contractId) {
        // Best-effort cleanup of an unusable session; never accept mismatched
        // evidence, even if the cancellation request also fails.
        try {
          await api.post(`/contract-signing/contracts/${encodeURIComponent(data.contract_id)}/pad/sessions/${encodeURIComponent(data.session_id)}/cancel`);
        } catch {
          // The server expires unconsumed preparation sessions after ten minutes.
        }
        setError("Signing preparation did not match the current contract. Reload the agreement.");
        return;
      }
      setSessionStatus(null);
      setSessionStatusError(false);
      setSession(data);
    } catch {
      setError("Unable to prepare a pad session. Check contract permissions and retry.");
    } finally {
      setBusy(false);
    }
  }

  async function cancelSession() {
    if (!session || busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.post(`/contract-signing/contracts/${contractId}/pad/sessions/${session.session_id}/cancel`);
      setSession(null);
      setSessionStatus(null);
      setSessionStatusError(false);
    } catch {
      setError("Could not close the signing session. Please refresh its state.");
    } finally {
      setBusy(false);
    }
  }

  if (!check) return <p role="status" className="text-sm text-muted-foreground">{error ?? "Checking contract signing eligibility..."}</p>;
  if (!check.ready) return (
    <section className="rounded-2xl border p-4" role="status">
      <p className="font-semibold">Signature pad preview unavailable</p>
      <p className="text-sm text-muted-foreground">Contract requirements: {check.blockers.join(", ")}.</p>
    </section>
  );

  return (
    <section className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Agreement {check.contract_number}, version {check.contract_version}.
        Hardware diagnostics and signature previews do not verify identity,
        establish consent, or sign this agreement.
      </p>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" variant="outline" onClick={() => void createSession()} disabled={busy || Boolean(session)}>
          {busy ? "Working..." : "Prepare signing session"}
        </Button>
        {session && <Button type="button" variant="outline" disabled={busy} onClick={() => void cancelSession()}>Cancel session</Button>}
      </div>
      {session && <div role="status" className="space-y-1 text-xs text-muted-foreground">
        <p>Session {session.session_id} ({sessionStatus?.status ?? session.status}), expires {new Date(session.expires_at).toLocaleString()}.</p>
        {sessionStatusError
          ? <p role="alert" className="text-destructive">Session verification unavailable. Temporary preview is disabled; retry or cancel the session.</p>
          : !sessionStatus
            ? <p>Verifying current contract and session status...</p>
            : !sessionStatus.preview_eligible
              ? <p role="alert" className="text-destructive">Temporary preview blocked: {sessionStatus.preview_blockers.join(", ") || "session no longer eligible"}.</p>
              : <p>Session remains eligible for test preview only. Wacom workstation capture is not authorized.</p>}
        <p>Hardware signing remains disabled until identity, consent and secured evidence capture are implemented.</p>
      </div>}
      {showWacomTestPreviewUI && session && (
        <div className="space-y-2 rounded-2xl border border-dashed p-4">
          <p className="text-sm font-semibold">Wacom STU-540 — test handwriting preview (inactive)</p>
          <p className="text-xs text-muted-foreground">
            Hardware handwriting requires a separately authenticated workstation proof and
            short-lived backend ticket. This preview cannot sign or update the contract.
          </p>
          <WacomSignatureField
            key={`${check.contract_id}:${check.contract_hash}:${session.session_id}`}
            fieldId="borrower_signature"
            sessionKey={session.session_id}
            disabled
            authorize={unconfiguredWacomPreviewAuthorization}
          />
        </div>
      )}
      <ContractSignatureCapture
        key={`${check.contract_id}:${check.contract_hash}`}
        contractId={check.contract_id}
        disabled={busy || Boolean(session && (!sessionStatus?.preview_eligible || sessionStatusError))}
      />
    </section>
  );
}
