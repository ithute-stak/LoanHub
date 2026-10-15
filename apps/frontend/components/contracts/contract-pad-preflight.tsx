"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
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

export function ContractPadPreflight({ contractId }: { contractId: string }) {
  const [check, setCheck] = useState<Preflight | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setCheck(null);
    setError(null);
    api.get<Preflight>(`/contract-signing/contracts/${contractId}/pad/preflight`)
      .then(({ data }) => {
        if (mounted) setCheck(data);
      })
      .catch(() => {
        if (mounted) setError("Could not verify signing permissions and contract state.");
      });
    return () => { mounted = false; };
  }, [contractId]);

  if (error) return <p role="alert" className="text-sm text-destructive">{error}</p>;
  if (!check) return <p className="text-sm text-muted-foreground">Checking contract signing eligibility...</p>;
  if (!check.ready) {
    return (
      <section className="rounded-2xl border p-4" role="status">
        <p className="font-semibold">Signature pad preview unavailable</p>
        <p className="text-sm text-muted-foreground">Contract registration requirements: {check.blockers.join(", ")}.</p>
      </section>
    );
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">
        Capture preview linked to {check.contract_number}, version {check.contract_version}.
        This does not verify identity, record consent, or sign the agreement.
      </p>
      <ContractSignatureCapture key={`${check.contract_id}:${check.contract_hash}`} contractId={check.contract_id} />
    </div>
  );
}
