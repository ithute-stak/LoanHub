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
  employee_no: string;
  verified: boolean;
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
  const [borrowerId, setBorrowerId] = useState("");
  const [employeeNo, setEmployeeNo] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<VerificationResult | null>(null);

  async function verify() {
    const borrower = borrowerId.trim();
    const employee = employeeNo.trim();
    if (!borrower || !employee) {
      setError("Enter both the LoanHub borrower ID and the CDAS employee number.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);
    try {
      const response = await api.post<VerificationResult>(
        `/cdas/borrowers/${borrower}/verify-employee`,
        { employee_no: employee },
      );
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
          Bind a CDAS employee number to a known LoanHub borrower before branch-scoped affordability and deduction reads are allowed.
        </p>
      </div>

      <Alert>
        <ShieldCheck className="h-4 w-4" />
        <AlertTitle>Borrower-scoped verification</AlertTitle>
        <AlertDescription>
          LoanHub calls only the CDAS employee-details endpoint first. The employee number, name, surname and date of birth must match the selected borrower before the payroll profile is marked verified. This screen is not a general employee-directory search.
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
          <CardTitle>Borrower and employee</CardTitle>
          <CardDescription>
            Use the borrower ID from the LoanHub client/borrower record and the employee number supplied for CDAS payroll verification.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="borrower-id">LoanHub borrower ID</Label>
              <Input
                id="borrower-id"
                value={borrowerId}
                onChange={(event) => setBorrowerId(event.target.value)}
                placeholder="UUID"
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
          <LoadingButton loading={loading} loadingText="Verifying with CDAS..." onClick={verify}>
            <UserCheck className="h-4 w-4" />Verify employee
          </LoadingButton>
        </CardContent>
      </Card>

      {result?.verified && (
        <Card className="border-emerald-500/40">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BadgeCheck className="h-5 w-5" />Official identity verified
            </CardTitle>
            <CardDescription>
              This borrower may now use branch-scoped CDAS affordability, deduction and snapshot reads for employee {result.employee_no}.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div><div className="text-muted-foreground">Name</div><div className="font-medium">{result.employee.name || "—"}</div></div>
              <div><div className="text-muted-foreground">Surname</div><div className="font-medium">{result.employee.surname || "—"}</div></div>
              <div><div className="text-muted-foreground">Date of birth</div><div className="font-medium">{result.employee.dob || "—"}</div></div>
              <div><div className="text-muted-foreground">Department</div><div className="font-medium">{result.employee.department || "—"}</div></div>
            </div>
            <Button asChild>
              <Link href="/company/cdas-booking">Continue to Official CDAS reads</Link>
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
