"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft, ArrowRight, CircleAlert, ClipboardList,
  LockKeyhole, RefreshCw, ShieldCheck,
} from "lucide-react";

import {
  getBatlokoaRegistrationAvailability,
  getBatlokoaRegistrationFormRequirements,
  type RegistrationAvailability,
  type RegistrationFormRequirements,
} from "@/api/batlokoaRegistration";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getErrorMessage } from "@/utils/apiError";
import { DisabledRegistrationField } from "@/components/clients/disabled-registration-field";
import { validateBatlokoaPreviewContract } from "@/lib/batlokoa-registration-preview-contract";

function fieldLabel(key: string): string {
  return key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

/**
 * Internal staff-facing PREVIEW of field requirements only.
 *
 * No field values are requested, persisted, cached, or sent.
 * Do not add a POST call or fall back to legacy /company-clients.
 */
export default function BatlokoaRegistrationPreviewPage() {
  const [availability, setAvailability] = useState<RegistrationAvailability | null>(null);
  const [requirements, setRequirements] = useState<RegistrationFormRequirements | null>(null);
  const [stepIndex, setStepIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    setLoading(true);
    setError(null);
    try {
      const [status, form] = await Promise.all([
        getBatlokoaRegistrationAvailability(),
        getBatlokoaRegistrationFormRequirements(),
      ]);
      validateBatlokoaPreviewContract(status, form);
      setAvailability(status);
      setRequirements(form);
      setStepIndex(0);
    } catch (err) {
      setAvailability(null);
      setRequirements(null);
      setError(getErrorMessage(err, "Registration preview could not be loaded."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // Authenticated requests use LoanHub's existing API client.
    void reload();
  }, []);

  const sections = requirements?.sections ?? [];
  const active = sections[stepIndex];
  const fieldDetails = useMemo(
    () => new Map(requirements?.field_details.map((detail) => [detail.key, detail]) ?? []),
    [requirements],
  );

  return (
    <main className="mx-auto w-full max-w-5xl space-y-5 pb-12">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link href="/company/clients" className="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
          Back to clients
        </Link>
        <Badge variant="secondary" className="gap-2">
          <LockKeyhole className="h-3.5 w-3.5" />
          Read-only preparation
        </Badge>
      </div>

      <section className="rounded-2xl border bg-card p-6 shadow-sm">
        <div className="mb-3 flex items-center gap-3">
          <span className="rounded-xl bg-primary/10 p-3 text-primary">
            <ClipboardList className="h-6 w-6" />
          </span>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Batlokoa client registration
            </h1>
            <p className="text-sm text-muted-foreground">
              Staff workflow preparation — review the required screens before launch.
            </p>
          </div>
        </div>
        <Alert>
          <ShieldCheck className="h-4 w-4" />
          <AlertTitle>Client registration is not yet released</AlertTitle>
          <AlertDescription>
            Identity database migration and independent security approvals are
            required. This preview does not accept personal information and
            cannot create a client or loan.
          </AlertDescription>
        </Alert>
      </section>

      {loading ? (
        <Card>
          <CardContent className="flex items-center gap-3 p-8 text-sm text-muted-foreground">
            <RefreshCw className="h-5 w-5 animate-spin" />
            Checking authenticated registration requirements…
          </CardContent>
        </Card>
      ) : error ? (
        <Alert variant="destructive">
          <CircleAlert className="h-4 w-4" />
          <AlertTitle>Registration preview unavailable</AlertTitle>
          <AlertDescription>
            {error} Check your lending staff and company access before retrying.
          </AlertDescription>
          <div className="mt-3">
            <Button variant="outline" type="button" onClick={() => void reload()}>
              Retry
            </Button>
          </div>
        </Alert>
      ) : availability && requirements && active ? (
        <div className="grid gap-5 lg:grid-cols-[240px_minmax(0,1fr)]">
          <nav aria-label="Registration preparation steps" className="space-y-2">
            {sections.map((section, index) => (
              <Button
                key={section.id}
                type="button"
                variant={stepIndex === index ? "secondary" : "ghost"}
                className="h-auto w-full justify-start gap-3 whitespace-normal py-3 text-left"
                onClick={() => setStepIndex(index)}
              >
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-bold">
                  {index + 1}
                </span>
                <span>{section.title}</span>
              </Button>
            ))}
          </nav>
          <Card>
            <CardHeader>
              <CardDescription>
                Screen {stepIndex + 1} of {sections.length} · Schema v{requirements.schema_version}
              </CardDescription>
              <CardTitle>{active.title}</CardTitle>
              <CardDescription>
                Planned form fields. Entries are disabled until a separate production
                release has been approved.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {active.id === "identity" ? (
                <p className="rounded-lg border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
                  A national ID <strong>or</strong> passport is required. Both are
                  sensitive and must be checked against existing LoanHub and legacy records.
                </p>
              ) : null}
              <div className="grid gap-3 sm:grid-cols-2">
                {active.fields.map((field) => (
                  <div key={field} className="rounded-xl border bg-muted/20 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-sm font-medium">{fieldLabel(field)}</span>
                      {fieldDetails.get(field)?.deferred ? (
                        <Badge variant="outline">Future phase</Badge>
                      ) : fieldDetails.get(field)?.required ? (
                        <Badge variant="secondary">Required</Badge>
                      ) : (
                        <Badge variant="secondary">Optional</Badge>
                      )}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                      <span>Type: {fieldDetails.get(field)?.kind ?? "Unspecified"}</span>
                      {fieldDetails.get(field)?.sensitive ? (
                        <span>· Sensitive information</span>
                      ) : null}
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">
                      {fieldDetails.get(field)?.deferred
                        ? "Requires an independently verified capture workflow."
                        : "Planned; customer information cannot be entered here."}
                    </p>
                    {fieldDetails.get(field) ? (
                      <div className="mt-3">
                        <DisabledRegistrationField field={fieldDetails.get(field)!} />
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
              <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-4">
                <Button
                  type="button"
                  variant="outline"
                  disabled={stepIndex === 0}
                  onClick={() => setStepIndex((current) => Math.max(0, current - 1))}
                >
                  <ArrowLeft className="mr-2 h-4 w-4" /> Previous
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  disabled={stepIndex === sections.length - 1}
                  onClick={() => setStepIndex((current) => Math.min(sections.length - 1, current + 1))}
                >
                  Next screen <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </div>
              {active.id === "consent" ? (
                <section aria-label="Loan application handoff readiness" className="space-y-3 rounded-xl border bg-muted/20 p-4">
                  <h3 className="font-semibold">After registration: loan application</h3>
                  <p className="text-sm text-muted-foreground">
                    A completed, tenant-scoped new-only registration must be
                    verified before any future loan application is considered.
                    LoanHub will separately require borrower identity review,
                    affordability and credit approval.
                  </p>
                  <div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
                    <span>Registration provenance — pending release</span>
                    <span>Identity and KYC — required</span>
                    <span>Affordability assessment — required</span>
                    <span>Credit approval — required</span>
                  </div>
                  <Button type="button" disabled aria-disabled="true" className="w-full">
                    <LockKeyhole className="mr-2 h-4 w-4" />
                    Start loan application — unavailable
                  </Button>
                  <p className="text-xs text-muted-foreground">
                    No client lookup, loan calculator call, loan draft or
                    financial record is created by this preview.
                  </p>
                </section>
              ) : null}
              <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
                <LockKeyhole className="mr-2 inline h-4 w-4" />
                Submission disabled. No client details are collected by this page.
              </div>
            </CardContent>
          </Card>
        </div>
      ) : (
        <Alert variant="destructive">
          <CircleAlert className="h-4 w-4" />
          <AlertTitle>Incomplete registration specification</AlertTitle>
          <AlertDescription>Cannot show the new-only registration preview.</AlertDescription>
        </Alert>
      )}
    </main>
  );
}
