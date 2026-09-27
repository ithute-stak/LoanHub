import Link from "next/link";
import { Activity, BrainCircuit, Calculator, ChartNoAxesCombined } from "lucide-react";

import { CompanyOperatingSystemCentre } from "@/components/company/company-operating-system-centre";

export default function CompanyCommandCentrePage() {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap justify-end gap-2">
        <Link
          href="/company/credit-loss-provisioning"
          className="inline-flex items-center gap-2 rounded-xl border bg-card px-4 py-2 text-sm font-black text-primary shadow-sm transition hover:bg-primary/5"
        >
          <Calculator className="h-4 w-4" /> Credit Loss Provisioning
        </Link>
        <Link
          href="/company/predictive-intelligence"
          className="inline-flex items-center gap-2 rounded-xl border bg-card px-4 py-2 text-sm font-black text-primary shadow-sm transition hover:bg-primary/5"
        >
          <Activity className="h-4 w-4" /> Predictive Intelligence
        </Link>
        <Link
          href="/company/ai-intelligence"
          className="inline-flex items-center gap-2 rounded-xl border bg-card px-4 py-2 text-sm font-black text-primary shadow-sm transition hover:bg-primary/5"
        >
          <BrainCircuit className="h-4 w-4" /> AI Intelligence
        </Link>
        <Link
          href="/company/portfolio-risk"
          className="inline-flex items-center gap-2 rounded-xl border bg-card px-4 py-2 text-sm font-black text-primary shadow-sm transition hover:bg-primary/5"
        >
          <ChartNoAxesCombined className="h-4 w-4" /> Portfolio Risk Intelligence
        </Link>
      </div>
      <CompanyOperatingSystemCentre />
    </div>
  );
}