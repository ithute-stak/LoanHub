"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, RefreshCcw, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { getCompanyArrearsPolicy, saveCompanyArrearsPolicy, type ArrearsPolicy, type ArrearsRule } from "@/api/paymentEnginePolicies";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

const RULES: Array<{ value: ArrearsRule; title: string; detail: string }> = [
  { value: "simple_carry", title: "Simple arrears carry-forward", detail: "Add unpaid arrears to the next instalment without extra arrears interest." },
  { value: "fixed_schedule", title: "Fixed schedule with separate arrears", detail: "Keep scheduled instalments unchanged and show overdue amounts separately." },
  { value: "carry_with_interest", title: "Carry-forward with additional interest", detail: "Requires approved legal and contractual authorization; not selectable through this self-service screen." },
];

export function CompanyArrearsPolicySettings({ canManage }: { canManage: boolean }) {
  const [policy, setPolicy] = useState<ArrearsPolicy | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    setLoading(true);
    try {
      setPolicy(await getCompanyArrearsPolicy());
      setError(null);
    } catch (cause: unknown) {
      setError(getErrorMessage(cause, "Unable to load arrears policy."));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { void load(); }, [load]);
  const save = async () => {
    if (!canManage || !policy || policy.rule === "carry_with_interest") return;
    setSaving(true);
    try {
      const updated = await saveCompanyArrearsPolicy({
        rule: policy.rule, version: policy.version,
        periodic_arrears_rate_percent: 0, additional_interest_authorized: false,
      });
      setPolicy(updated);
      toast.success("Company arrears policy saved");
    } catch (cause: unknown) {
      toast.error(getErrorMessage(cause, "Unable to save arrears policy."));
    } finally {
      setSaving(false);
    }
  };
  return (
    <Card className="rounded-3xl">
      <CardHeader>
        <CardTitle>Repayment and arrears rules</CardTitle>
        <CardDescription>Company-wide default for future loans. Existing loans and live repayment calculations are not changed by this setting.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? <p className="text-sm text-muted-foreground">Loading arrears policy…</p> : error ? (
          <div className="space-y-2"><p role="alert" className="text-sm text-destructive">{error}</p><Button variant="outline" size="sm" onClick={() => void load()}><RefreshCcw className="mr-2 h-4 w-4" />Retry</Button></div>
        ) : policy ? <>
          <div role="radiogroup" aria-label="Default arrears rule" className="space-y-3">
            {RULES.map((rule) => (
              <Label key={rule.value} className="flex cursor-pointer items-start gap-3 rounded-xl border p-4">
                <input type="radio" name="company-arrears-rule" value={rule.value} checked={policy.rule === rule.value}
                  disabled={!canManage || rule.value === "carry_with_interest"}
                  onChange={() => setPolicy({ ...policy, rule: rule.value, periodic_arrears_rate_percent: 0, additional_interest_authorized: false })} />
                <span className="space-y-1"><span className="block font-semibold">{rule.title}</span><span className="block text-xs font-normal text-muted-foreground">{rule.detail}</span></span>
              </Label>
            ))}
          </div>
          <div className="flex items-start gap-2 rounded-lg border bg-muted/30 p-3 text-xs text-muted-foreground">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            Policy selection is stored for future integration. Additional interest requires separate legal review, and no live balances change here.
          </div>
          <Button onClick={() => void save()} disabled={!canManage || saving || policy.rule === "carry_with_interest"}>
            <Save className="mr-2 h-4 w-4" />{saving ? "Saving…" : "Save default arrears rule"}
          </Button>
        </> : null}
      </CardContent>
    </Card>
  );
}
