"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ContractSignatureCapture } from "@/components/contracts/contract-signature-capture";

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

/**
 * Operator-only signing preparation. Never interprets local hardware status
 * or a browser stroke preview as signer identity, consent or legal signing.
 */
export function ContractPadPreflight({ contractId }: { contractId: string }) {
  const [check, setCheck] = useState<Preflight | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [session, setSession] = useState<PadSession | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let mounted = true;
    setCheck(null);
    setError(null);
    setSession(null);
    api.get<Preflight>(`/contract-signing/contracts/${contractId}/pad/preflight`)
      .then(({ data }) => { if (mounted) setCheck(data); })
      .catch(() => { if (mounted) setError("Could not verify signing permissions and contract state."); });
    return () => { mounted = false; };
  }, [contractId]);

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
      {session && <p role="status" className="text-xs text-muted-foreground">
        Session {session.session_id} ({session.status}), expires {new Date(session.expires_at).toLocaleString()}.
        Hardware signing remains disabled until identity, consent and secured evidence capture are implemented.
      </p>}
      <ContractSignatureCapture
        key={`${check.contract_id}:${check.contract_hash}`}
        contractId={check.contract_id}
        disabled={busy}
      />
    </section>
  );
}
