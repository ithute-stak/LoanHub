"use client";

import { useEffect, useState } from "react";
import { WacomStrokePreview } from "./wacom-stroke-preview";
import {
  useWacomSignatureSocket,
  type AuthorizedWacomPreview,
} from "./use-wacom-signature-socket";

export type WacomSignatureFieldProps = {
  fieldId: string;
  sessionKey: string;
  disabled?: boolean;
  /** Caller must verify operator, borrower consent, field, session and
   * document hash, and obtain an approved workstation preview ticket. */
  authorize: (fieldId: string, sessionKey: string) => Promise<AuthorizedWacomPreview>;
};

export function WacomSignatureField({
  fieldId, sessionKey, disabled = false, authorize,
}: WacomSignatureFieldProps) {
  const { status, strokes, start, cancel } = useWacomSignatureSocket(sessionKey);
  const [focused, setFocused] = useState(false);
  const [requesting, setRequesting] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    setFocused(false);
    setRequesting(false);
    setMessage("");
  }, [fieldId, sessionKey]);

  async function begin() {
    if (disabled || !focused || requesting || status === "capturing" || status === "authorizing") return;
    setRequesting(true);
    setMessage("");
    try {
      const approval = await authorize(fieldId, sessionKey);
      if (approval.fieldId !== fieldId || approval.sessionKey !== sessionKey || !start(approval)) {
        setMessage("Preview authorization failed.");
      }
    } catch {
      setMessage("Preview not authorized. Please try again.");
    } finally {
      setRequesting(false);
    }
  }

  return (
    <section data-signature-field-id={fieldId} aria-label="Wacom signature preview field" className="space-y-3">
      <button
        type="button"
        disabled={disabled}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        aria-label="Select signature field"
        className="rounded-lg border px-3 py-2"
      >
        Signature field: {fieldId}
      </button>
      <div className="flex gap-2">
        <button type="button" onMouseDown={(event) => event.preventDefault()}
          disabled={disabled || !focused || requesting || status === "capturing" || status === "authorizing"}
          onClick={begin} className="rounded-lg border px-3 py-2">
          {requesting ? "Authorizing…" : "Start test handwriting preview"}
        </button>
        <button type="button" onClick={() => cancel()} className="rounded-lg border px-3 py-2">
          Cancel and clear
        </button>
      </div>
      <p role="status" className="text-sm">{message || `Preview status: ${status}`}</p>
      <WacomStrokePreview strokes={strokes} sessionKey={sessionKey}
        active={!disabled && (status === "capturing" || status === "complete")} />
      <p className="text-xs">Test preview only — no contract is signed or submitted.</p>
    </section>
  );
}
