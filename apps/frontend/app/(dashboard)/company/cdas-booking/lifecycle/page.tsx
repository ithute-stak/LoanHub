import { CdasLoanLifecyclePanel } from "../CdasLoanLifecyclePanel";

export default function CdasLifecyclePage() {
  return (
    <main className="space-y-6 pb-10">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Official CDAS Loan Lifecycle</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          Register a real LoanHub loan in CDAS, then control its review, approval, activation, modification, reconciliation and settlement from one loan-linked audit trail.
        </p>
      </div>
      <CdasLoanLifecyclePanel />
    </main>
  );
}
