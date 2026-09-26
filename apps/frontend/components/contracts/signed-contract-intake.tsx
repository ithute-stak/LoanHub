"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { FileCheck2, FileSearch, FolderCheck, Loader2, UploadCloud, X } from "lucide-react";
import { listCompanyClients } from "@/api/companyClients";
import {
  assignSignedContract,
  listSignedContractReviewQueue,
  openManagedFile,
  type SignedContractIntakeResult,
  type SignedContractReviewItem,
  uploadSignedContracts,
} from "@/api/signedContracts";
import type { CompanyClient } from "@/types/companyClient";

const ACCEPT = ".pdf,.jpg,.jpeg,.png,.webp";
const MAX_FILES = 20;

function readableSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function statusClass(status: SignedContractIntakeResult["status"]): string {
  if (status === "filed") return "border-emerald-200 bg-emerald-50 text-emerald-900";
  if (status === "review") return "border-amber-200 bg-amber-50 text-amber-900";
  if (status === "duplicate") return "border-sky-200 bg-sky-50 text-sky-900";
  return "border-rose-200 bg-rose-50 text-rose-900";
}

export function SignedContractIntake() {
  const [selected, setSelected] = useState<File[]>([]);
  const [results, setResults] = useState<SignedContractIntakeResult[]>([]);
  const [review, setReview] = useState<SignedContractReviewItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [reviewBusy, setReviewBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [clientSearch, setClientSearch] = useState("");
  const [clients, setClients] = useState<CompanyClient[]>([]);
  const [clientSearchBusy, setClientSearchBusy] = useState(false);
  const [assignment, setAssignment] = useState<Record<string, string>>({});
  const [assigning, setAssigning] = useState<string | null>(null);

  const loadReview = useCallback(async () => {
    setReviewBusy(true);
    try {
      setReview(await listSignedContractReviewQueue());
    } catch {
      setError("Could not load the signed-contract review queue.");
    } finally {
      setReviewBusy(false);
    }
  }, []);

  useEffect(() => {
    void loadReview();
  }, [loadReview]);

  const addFiles = useCallback((incoming: File[]) => {
    setError(null);
    setSelected((current) => {
      const known = new Set(current.map((file) => `${file.name}:${file.size}:${file.lastModified}`));
      const next = [...current];
      for (const file of incoming) {
        const key = `${file.name}:${file.size}:${file.lastModified}`;
        if (!known.has(key) && next.length < MAX_FILES) {
          known.add(key);
          next.push(file);
        }
      }
      return next;
    });
  }, []);

  const upload = async () => {
    if (!selected.length) return;
    setBusy(true);
    setError(null);
    try {
      const response = await uploadSignedContracts(selected);
      setResults(response);
      setSelected([]);
      await loadReview();
    } catch {
      setError("The signed contracts could not be uploaded. Nothing has been deliberately auto-filed from this failed batch.");
    } finally {
      setBusy(false);
    }
  };

  const searchClients = async () => {
    setClientSearchBusy(true);
    setError(null);
    try {
      setClients(await listCompanyClients({ search: clientSearch.trim() || undefined, limit: 20 }));
    } catch {
      setError("Could not search the client directory.");
    } finally {
      setClientSearchBusy(false);
    }
  };

  const fileManually = async (item: SignedContractReviewItem) => {
    const accountId = assignment[item.file_id];
    if (!accountId) return;
    setAssigning(item.file_id);
    setError(null);
    try {
      const result = await assignSignedContract(item.file_id, accountId);
      setResults((current) => [
        {
          file_id: result.file_id,
          original_name: item.original_name,
          status: "filed",
          client_account_id: result.client_account_id,
          client_name: result.client_name,
          evidence_types: ["manual_verification"],
          detail: "Manually verified and filed under Signed Contracts",
        },
        ...current,
      ]);
      setReview((current) => current.filter((row) => row.file_id !== item.file_id));
    } catch {
      setError("LoanHub could not file that contract under the selected client.");
    } finally {
      setAssigning(null);
    }
  };

  const resultCounts = useMemo(
    () => ({
      filed: results.filter((item) => item.status === "filed").length,
      review: results.filter((item) => item.status === "review").length,
      duplicate: results.filter((item) => item.status === "duplicate").length,
      rejected: results.filter((item) => item.status === "rejected").length,
    }),
    [results],
  );

  return (
    <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-6 p-4 md:p-6">
      <section className="rounded-2xl border bg-card p-5 shadow-sm">
        <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
          <div>
            <div className="flex items-center gap-2 text-xl font-semibold"><FolderCheck className="h-5 w-5" /> Global Signed Contract Upload</div>
            <p className="mt-1 max-w-4xl text-sm text-muted-foreground">
              Upload scanned wet-ink contracts here. LoanHub reads the scan locally and files the unchanged original under the matching client&apos;s <strong>Signed Contracts</strong> documents. A name alone is never enough for automatic filing.
            </p>
          </div>
          <div className="rounded-lg border px-3 py-2 text-xs text-muted-foreground">
            PDF · JPEG · PNG · WebP · up to {MAX_FILES} files per batch
          </div>
        </div>

        <label
          className="mt-5 flex min-h-48 cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed bg-muted/25 p-6 text-center transition hover:bg-muted/45"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            addFiles(Array.from(event.dataTransfer.files));
          }}
        >
          <UploadCloud className="mb-3 h-9 w-9" />
          <span className="font-medium">Drop signed contracts here or click to choose scans</span>
          <span className="mt-1 text-sm text-muted-foreground">The original scan is encrypted and checksum-verified. OCR is used only for routing.</span>
          <input
            className="hidden"
            type="file"
            multiple
            accept={ACCEPT}
            onChange={(event) => addFiles(Array.from(event.target.files || []))}
          />
        </label>

        {selected.length > 0 && (
          <div className="mt-4 space-y-2">
            {selected.map((file, index) => (
              <div key={`${file.name}-${file.lastModified}`} className="flex items-center justify-between rounded-lg border px-3 py-2 text-sm">
                <div className="min-w-0"><div className="truncate font-medium">{file.name}</div><div className="text-xs text-muted-foreground">{readableSize(file.size)}</div></div>
                <button type="button" className="rounded-md p-2 hover:bg-muted" onClick={() => setSelected((items) => items.filter((_, itemIndex) => itemIndex !== index))} aria-label={`Remove ${file.name}`}><X className="h-4 w-4" /></button>
              </div>
            ))}
            <div className="flex justify-end">
              <button type="button" disabled={busy} onClick={() => void upload()} className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-60">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}
                {busy ? "Reading and filing…" : `Upload ${selected.length} contract${selected.length === 1 ? "" : "s"}`}
              </button>
            </div>
          </div>
        )}

        {error && <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900">{error}</div>}
      </section>

      {results.length > 0 && (
        <section className="rounded-2xl border bg-card p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="font-semibold">Latest intake results</h2>
            <div className="text-xs text-muted-foreground">Filed {resultCounts.filed} · Review {resultCounts.review} · Duplicate {resultCounts.duplicate} · Rejected {resultCounts.rejected}</div>
          </div>
          <div className="mt-3 grid gap-3 lg:grid-cols-2">
            {results.map((result, index) => (
              <div key={`${result.original_name}-${index}`} className={`rounded-xl border p-4 ${statusClass(result.status)}`}>
                <div className="flex items-start gap-3"><FileCheck2 className="mt-0.5 h-5 w-5 shrink-0" /><div className="min-w-0"><div className="truncate font-semibold">{result.original_name}</div><div className="mt-1 text-sm">{result.detail}</div>{result.client_name && <div className="mt-1 text-sm font-medium">Client: {result.client_name} · Signed Contracts</div>}{result.evidence_types?.length > 0 && <div className="mt-1 text-xs opacity-75">Matched by: {result.evidence_types.join(", ")}</div>}</div></div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="rounded-2xl border bg-card p-5 shadow-sm">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div><h2 className="flex items-center gap-2 font-semibold"><FileSearch className="h-5 w-5" /> Needs review</h2><p className="mt-1 text-sm text-muted-foreground">Unreadable scans, missing identifiers and conflicting identifiers stay here until a staff member verifies the client.</p></div>
          <button type="button" onClick={() => void loadReview()} disabled={reviewBusy} className="rounded-lg border px-3 py-2 text-sm">{reviewBusy ? "Refreshing…" : "Refresh queue"}</button>
        </div>

        {review.length > 0 && (
          <div className="mt-4 flex flex-col gap-2 md:flex-row">
            <input value={clientSearch} onChange={(event) => setClientSearch(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void searchClients(); }} placeholder="Search client by name, ID or account reference" className="h-10 flex-1 rounded-lg border bg-background px-3 text-sm" />
            <button type="button" onClick={() => void searchClients()} disabled={clientSearchBusy} className="h-10 rounded-lg border px-4 text-sm font-medium">{clientSearchBusy ? "Searching…" : "Search clients"}</button>
          </div>
        )}

        <div className="mt-4 space-y-3">
          {!reviewBusy && review.length === 0 && <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">No signed contracts need manual review.</div>}
          {review.map((item) => (
            <div key={item.file_id} className="rounded-xl border p-4">
              <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                <div className="min-w-0"><div className="truncate font-medium">{item.original_name}</div><div className="mt-1 text-xs text-muted-foreground">{readableSize(item.size_bytes)} · {item.reference}</div><div className="mt-2 text-sm text-amber-800">{item.description || "Manual verification required"}</div></div>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                  <button type="button" onClick={() => void openManagedFile(item.file_id)} className="rounded-lg border px-3 py-2 text-sm">Open scan</button>
                  <select value={assignment[item.file_id] || ""} onChange={(event) => setAssignment((current) => ({ ...current, [item.file_id]: event.target.value }))} className="h-10 min-w-64 rounded-lg border bg-background px-3 text-sm">
                    <option value="">Select verified client…</option>
                    {clients.map((client) => <option key={client.id} value={client.id}>{client.full_name} · {client.account_reference}</option>)}
                  </select>
                  <button type="button" disabled={!assignment[item.file_id] || assigning === item.file_id} onClick={() => void fileManually(item)} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground disabled:opacity-50">{assigning === item.file_id && <Loader2 className="h-4 w-4 animate-spin" />}File under Signed Contracts</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
