"use client";

import { api } from "@/lib/api";
import {
  markDocumentGenerationFailed,
  markDocumentGenerationReady,
  prepareDocumentGenerationWindow,
} from "@/lib/document-generation-overlay";

type ReceiptPdfRequest = {
  loanId: string;
  paymentId: string;
  receiptNumber?: string | null;
  companyId?: string | null;
};

function safePdfFileName(value: string | null | undefined): string {
  const base = (value || "LoanHub-payment-receipt")
    .trim()
    .replace(/[^A-Za-z0-9._-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return `${base || "LoanHub-payment-receipt"}.pdf`;
}

function directReceiptPath({ loanId, paymentId }: ReceiptPdfRequest): string {
  return `/loans/${encodeURIComponent(loanId)}/payment-slips/by-payment/${encodeURIComponent(paymentId)}.pdf`;
}

async function fetchReceiptPdf(request: ReceiptPdfRequest): Promise<Blob> {
  const response = await api.get<Blob>(directReceiptPath(request), {
    responseType: "blob",
    headers: {
      Accept: "application/pdf",
    },
  });

  const contentType = String(response.headers["content-type"] || "").toLowerCase();
  if (contentType && !contentType.includes("application/pdf")) {
    throw new Error("The server did not return a PDF receipt.");
  }

  return response.data;
}

/**
 * Download a freshly rendered receipt from FastAPI.
 *
 * This deliberately does not use receipt_file / ManagedFile because those
 * historical files may be unavailable after a restore or container rebuild.
 * The backend renders the current Filizwa-style slip directly from the
 * authoritative payment ledger using payment_id.
 */
export async function downloadPaymentReceiptPdf(request: ReceiptPdfRequest): Promise<void> {
  const blob = await fetchReceiptPdf(request);
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");

  try {
    anchor.href = objectUrl;
    anchor.download = safePdfFileName(request.receiptNumber);
    anchor.rel = "noopener";
    document.body.appendChild(anchor);
    anchor.click();
  } finally {
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1_000);
  }
}

/**
 * Open the freshly rendered receipt in a dedicated PDF window and invoke the
 * browser print flow. The window is created before awaiting the API request so
 * popup blockers still recognise the action as originating from the click.
 */
export async function printPaymentReceiptPdf(request: ReceiptPdfRequest): Promise<void> {
  const popup = window.open("", "_blank", "width=900,height=900");
  if (!popup) {
    throw new Error("The print window was blocked. Allow pop-ups for LoanHub and try again.");
  }

  prepareDocumentGenerationWindow(popup, {
    title: `Preparing ${request.receiptNumber ?? "payment receipt"}`,
    description: "Please wait while LoanHub renders the current payment receipt for printing.",
    companyId: request.companyId,
  });

  let objectUrl: string | null = null;
  try {
    const blob = await fetchReceiptPdf(request);
    objectUrl = URL.createObjectURL(blob);
    markDocumentGenerationReady(popup);
    popup.location.replace(objectUrl);
    popup.focus();

    // Chrome/Edge normally switch to the built-in PDF viewer. Give it a short
    // moment to attach before requesting print. If a browser ignores the
    // automatic request, the fully rendered PDF remains open and printable.
    window.setTimeout(() => {
      try {
        if (!popup.closed) {
          popup.focus();
          popup.print();
        }
      } catch {
        // The PDF viewer remains open even when a browser disallows scripted
        // printing from its internal viewer.
      }
    }, 1_200);

    const urlToRevoke = objectUrl;
    window.setTimeout(() => URL.revokeObjectURL(urlToRevoke), 120_000);
  } catch (error) {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    markDocumentGenerationFailed(popup);
    throw error;
  }
}
