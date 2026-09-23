"use client";

import Link from "next/link";
import { useState } from "react";
import { BadgeCheck, ShieldCheck, UserCheck } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/utils/apiError";

type VerificationResult = {
  borrower_id: string;
  account_id: string;
  account_reference: string;
  national_id_masked: string;
  employee_no: string;
  verified: boolean;
  identity_basis: string;
  provider_national_id_present: boolean;
  verification_reference: string;
  verified_at: string | null;
  employee: {
    employee_no: string | null;
    name: string | null;
    surname: string | null;
    dob: string | null;
    department: string | null;
    joining_date: string | null;
    termination_date: string | null;
  };
};

export default function VerifyCdasEmployeePage() {
  const [nationalId, setNationalId] = useState("");
  const [employeeNo, setEmployeeNo] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<VerificationResult | null>(null);

  async function verify() {
    const id = nationalId.trim();
    const employee = employeeNo.trim();
    if (!id || !employee) {
      setError("Enter both the LoanHub client National ID and the CDAS employee number.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);
    try {
      const response = await api.post<VerificationResult>("/cdas/verify-employee", {
        national_id: id,
        employee_no: employee,
      });
      setResult(response.data);
    } catch (requestError: unknown) {
      setError(getErrorMessage(requestError, "CDAS employee verification failed."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6 pb-10">
      <div>
        <div className="flex items-center gap-2">
          <UserCheck className="h-6 w-6" />
          <h1 className="text-2xl font-semibold tracking-tight">Verify CDAS Employee</h1>
        </div>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          Link a CDAS employee number to exactly one active LoanHub client using the client&apos;s National ID.
        </p>
      </div>

      <Alert>
        <ShieldCheck className="h-4 w-4" />
        <AlertTitle>Exact-ID policy</AlertTitle>
        <AlertDescription>
          LoanHub matches the National ID exactly after removing harmless formatting such as spaces and hyphens, then requires CDAS to return the exact employee number searched. Names and date of birth are display information only and are never used as a fuzzy identity fallback. CDAS v1.5 does not document National ID in Employee Details; if the provider supplies one, it must also match exactly.
        </AlertDescription>
      </Alert>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Verification failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>National ID and employee number</CardTitle>
          <CardDescription>
            No LoanHub borrower UUID is required. Use the National ID already recorded on the client profile and the employee number used by CDAS.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="national-id">LoanHub client National ID</Label>
              <Input
                id="national-id"
                value={nationalId}
                onChange={(event) => setNationalId(event.target.value)}
                placeholder="National ID"
                autoComplete="off"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="employee-no">CDAS employee number</Label>
              <Input
                id="employee-no"
                value={employeeNo}
                onChange={(event) => setEmployeeNo(event.target.value)}
                placeholder="EmployeeNo"
                autoComplete="off"
              />
            </div>
          </div>
          <LoadingButton loading={loading} loadingText="Verifying exact identifiers..." onClick={verify}>
            <UserCheck className="h-4 w-4" />Verify exact link
          </LoadingButton>
        </CardContent>
      </Card>

      {result?.verified && (
        <Card className="border-emerald-500/40">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BadgeCheck className="h-5 w-5" />Exact employee link verified
            </CardTitle>
            <CardDescription>
              LoanHub account {result.account_reference} · National ID {result.national_id_masked} · CDAS employee {result.employee_no}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div><div className="text-muted-foreground">Name from CDAS</div><div className="font-medium">{result.employee.name || "—"}</div></div>
              <div><div className="text-muted-foreground">Surname from CDAS</div><div className="font-medium">{result.employee.surname || "—"}</div></div>
              <div><div className="text-muted-foreground">Department</div><div className="font-medium">{result.employee.department || "—"}</div></div>
              <div><div className="text-muted-foreground">Provider National ID</div><div className="font-medium">{result.provider_national_id_present ? "Returned and matched" : "Not returned by documented v1.5 response"}</div></div>
            </div>
            <Button asChild>
              <Link href="/company/cdas-booking/intelligence">Continue to Borrower Intelligence</Link>
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
