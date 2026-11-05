"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { WacomSignatureField } from "./wacom-signature-field";
import type { AuthorizedWacomPreview } from "./use-wacom-signature-socket";

/**
 * Explicit, operator-driven TEST exchange, not legal signature capture.
 * The enrolled Ed25519 key is never exposed to JS. Challenge signing is
 * performed by the separate local Go CLI. No arbitrary local sign API.
 */
type Challenge = {
  challenge_id: string;
  workstation_id: string;
  session_id: string;
  nonce: string;
  issued_at: string;
  expires_at: string;
  capture_enabled: false;
};
type Proof = {
  challenge_id: string;
  workstation_id: string;
  signature_base64: string;
};
type Ticket = {
  preview_ticket: string;
  session_id: string;
  workstation_id: string;
  expires_in_seconds_max: number;
  capture_enabled: false;
  contract_signed: false;
};
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const SIGNATURE = /^[A-Za-z0-9+/]{86}==$/;

export function WacomTestAuthorizationPanel({
  contractId, contractHash, sessionId, eligible,
}: {
  contractId: string;
  contractHash: string;
  sessionId: string;
  eligible: boolean;
}) {
  const [workstation, setWorkstation] = useState("");
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [proofText, setProofText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [approved, setApproved] = useState<AuthorizedWacomPreview | null>(null);
  const generation = useRef(0);
  const issued = useRef(false);
  const currentBinding = useRef({ contractId, contractHash, sessionId, eligible });
  currentBinding.current = { contractId, contractHash, sessionId, eligible };

  useEffect(() => {
    generation.current++;
    issued.current = false;
    setApproved(null);
    setChallenge(null);
    setProofText("");
    setError("");
    return () => { generation.current++; };
  }, [contractId, contractHash, sessionId]);

  useEffect(() => {
    if (!eligible) {
      generation.current++;
      issued.current = false;
      setChallenge(null);
      setApproved(null);
      setProofText("");
    }
  }, [eligible]);

  const base = `/contract-signing/contracts/${encodeURIComponent(contractId)}/pad/sessions/${encodeURIComponent(sessionId)}`;
  const validSession = eligible && UUID.test(contractId) && UUID.test(sessionId)
    && /^[0-9a-f]{64}$/.test(contractHash);

  async function requestChallenge() {
    if (!validSession || busy || !UUID.test(workstation)) return;
    const requestID = ++generation.current;
    issued.current = false;
    setApproved(null);
    setChallenge(null);
    setProofText("");
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post<Challenge>(`${base}/workstation-challenges`, {
        workstation_id: workstation,
      });
      if (generation.current !== requestID || !currentBinding.current.eligible) return;
      if (data.workstation_id !== workstation || data.session_id !== sessionId ||
          data.capture_enabled !== false || !UUID.test(data.challenge_id) ||
          !Number.isFinite(Date.parse(data.expires_at)) ||
          Date.parse(data.expires_at) <= Date.now()) throw new Error("Invalid backend challenge");
      setChallenge(data);
    } catch {
      if (generation.current === requestID) setError("Workstation challenge unavailable. Check enrollment and session.");
    } finally {
      if (generation.current === requestID) setBusy(false);
    }
  }

  async function verifyProof() {
    if (!validSession || busy || !challenge ||
        Date.parse(challenge.expires_at) <= Date.now()) return;
    let proof: Proof;
    try {
      const raw: unknown = JSON.parse(proofText);
      if (!raw || typeof raw !== "object") throw new Error("Invalid proof");
      const candidate = raw as Record<string, unknown>;
      if (Object.keys(candidate).sort().join(",") !==
          "challenge_id,signature_base64,workstation_id") throw new Error("Unexpected proof");
      if (candidate.challenge_id !== challenge.challenge_id ||
          candidate.workstation_id !== challenge.workstation_id ||
          typeof candidate.signature_base64 !== "string" ||
          !SIGNATURE.test(candidate.signature_base64)) throw new Error("Proof does not match");
      proof = candidate as Proof;
    } catch {
      setError("Invalid local proof. It must match the current challenge and workstation.");
      return;
    }
    const requestID = ++generation.current;
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post<Ticket>(`${base}/preview-tickets`, proof);
      if (generation.current !== requestID || !currentBinding.current.eligible) return;
      if (data.workstation_id !== challenge.workstation_id ||
          data.session_id !== sessionId || data.capture_enabled !== false ||
          data.contract_signed !== false ||
          !Number.isInteger(data.expires_in_seconds_max) ||
          data.expires_in_seconds_max <= 0 ||
          data.expires_in_seconds_max > 30 ||
          typeof data.preview_ticket !== "string" ||
          data.preview_ticket.length < 64 || data.preview_ticket.length > 3500) {
        throw new Error("Untrusted backend ticket response");
      }
      // Ephemeral browser memory only; never localStorage, query params or logs.
      issued.current = false;
      setChallenge(null);
      setProofText("");
      setApproved({
        ticket: data.preview_ticket,
        endpoint: "ws://127.0.0.1:8765/v1/preview/stream",
        fieldId: "borrower_signature",
        sessionKey: sessionId,
        expiresAt: Date.now() + Math.min(25, data.expires_in_seconds_max) * 1000,
      });
    } catch {
      if (generation.current === requestID) setError("Backend rejected the proof or ticket issuance is disabled.");
    } finally {
      if (generation.current === requestID) setBusy(false);
    }
  }

  async function authorize(fieldId: string, sessionKey: string): Promise<AuthorizedWacomPreview> {
    if (!eligible || !approved || issued.current ||
        fieldId !== approved.fieldId || sessionKey !== approved.sessionKey ||
        approved.expiresAt <= Date.now()) throw new Error("Preview ticket unavailable");
    issued.current = true;
    const result = approved;
    setApproved(null);
    return result;
  }

  return (
    <section className="space-y-3 rounded-2xl border border-dashed p-4" aria-label="Wacom workstation test authorization">
      <p className="text-sm font-semibold">Wacom STU-540 — protected test preview</p>
      <p className="text-xs text-muted-foreground">
        A backend challenge must be signed by the enrolled Go workstation CLI.
        This test flow cannot sign or submit a contract. Challenges expire after 30 seconds.
      </p>
      <label className="block text-sm">
        Enrolled workstation UUID
        <input className="mt-1 w-full rounded border p-2 font-mono text-xs"
          value={workstation} onChange={(event) => {
            generation.current++;
            issued.current = false;
            setWorkstation(event.target.value.trim().toLowerCase());
            setChallenge(null); setProofText(""); setApproved(null);
          }} placeholder="Workstation UUID" maxLength={36} autoComplete="off" />
      </label>
      <button type="button" className="rounded border px-3 py-2 text-sm"
        disabled={!validSession || busy || !UUID.test(workstation)}
        onClick={() => void requestChallenge()}>
        {busy ? "Verifying…" : "Request backend challenge"}
      </button>
      {challenge && (
        <div className="space-y-2">
          <p className="text-xs">Pass this JSON to the enrolled local Go CLI using its protected stdin mode.</p>
          <textarea readOnly aria-label="Backend-issued workstation challenge"
            className="w-full rounded border p-2 font-mono text-xs" rows={5}
            value={JSON.stringify(challenge)} />
          <label className="block text-xs">
            Paste local CLI proof JSON (not the private key)
            <textarea aria-label="Local workstation proof JSON" rows={3} maxLength={2048}
              className="mt-1 w-full rounded border p-2 font-mono text-xs"
              value={proofText} onChange={(event) => setProofText(event.target.value)} />
          </label>
          <button type="button" className="rounded border px-3 py-2 text-sm"
            disabled={busy || !validSession || Date.parse(challenge.expires_at) <= Date.now() || !proofText}
            onClick={() => void verifyProof()}>Verify proof and request preview ticket</button>
        </div>
      )}
      {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
      <WacomSignatureField
        key={`${contractId}:${contractHash}:${sessionId}`}
        fieldId="borrower_signature"
        sessionKey={sessionId}
        disabled={!validSession || busy || !approved || approved.expiresAt <= Date.now()}
        authorize={authorize}
      />
      <p className="text-xs text-muted-foreground">Test only — no signing evidence or contract PDF changes.</p>
    </section>
  );
}
