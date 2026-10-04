type LoanPreviewExports = WebAssembly.Exports & {
  affordability_headroom_cents?: (
    incomeCents: bigint,
    commitmentsCents: bigint,
    proposedInstallmentCents: bigint,
  ) => bigint;
  simple_interest_total_cents?: (
    principalCents: bigint,
    rateMilliPercent: bigint,
    months: number,
    processingFeeCents: bigint,
  ) => bigint;
};

let modulePromise: Promise<LoanPreviewExports | null> | null = null;

async function loadLoanComputeWasm(): Promise<LoanPreviewExports | null> {
  if (typeof window === "undefined" || typeof WebAssembly === "undefined") return null;
  if (!modulePromise) {
    modulePromise = fetch("/wasm/loanhub_compute_wasm.wasm", { cache: "force-cache" })
      .then(async (response) => {
        if (!response.ok) return null;
        const bytes = await response.arrayBuffer();
        const instance = await WebAssembly.instantiate(bytes, {});
        return instance.instance.exports as LoanPreviewExports;
      })
      .catch(() => null);
  }
  return modulePromise;
}

function moneyToCents(value: number): bigint | null {
  if (!Number.isFinite(value)) return null;
  return BigInt(Math.round(value * 100));
}

function rateToMilliPercent(value: number): bigint | null {
  if (!Number.isFinite(value)) return null;
  return BigInt(Math.round(value * 1000));
}

export async function simpleInterestBrowserPreview(input: {
  principal: number;
  ratePercent: number;
  months: number;
  processingFee?: number;
}): Promise<number | null> {
  const wasmExports = await loadLoanComputeWasm();
  const fn = wasmExports?.simple_interest_total_cents;
  const principalCents = moneyToCents(input.principal);
  const feeCents = moneyToCents(input.processingFee ?? 0);
  const rateMilliPercent = rateToMilliPercent(input.ratePercent);
  if (!fn || principalCents === null || feeCents === null || rateMilliPercent === null) {
    return null;
  }

  try {
    const result = fn(
      principalCents,
      rateMilliPercent,
      Math.trunc(input.months),
      feeCents,
    );
    if (result < BigInt(0)) return null;
    return Number(result) / 100;
  } catch {
    return null;
  }
}

export async function affordabilityCashflowHeadroomPreview(input: {
  income: number;
  commitments: number;
  proposedInstallment: number;
}): Promise<number | null> {
  const wasmExports = await loadLoanComputeWasm();
  const fn = wasmExports?.affordability_headroom_cents;
  const income = moneyToCents(input.income);
  const commitments = moneyToCents(input.commitments);
  const proposed = moneyToCents(input.proposedInstallment);
  if (!fn || income === null || commitments === null || proposed === null) return null;

  try {
    return Number(fn(income, commitments, proposed)) / 100;
  } catch {
    return null;
  }
}
