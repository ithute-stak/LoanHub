"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Lightbulb, RefreshCcw, Send } from "lucide-react";

import { professionalApi } from "@/api/professional";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { PageLoader } from "@/components/ui/page-loader";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { formatDate, titleCase } from "@/lib/format";
import type { PlatformSuggestion, PlatformSuggestionCreate } from "@/types/professional";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

const initialForm: PlatformSuggestionCreate = {
  title: "",
  category: "feature_request",
  description: "",
  priority: "normal",
};

export default function SuggestionsPage() {
  const [rows, setRows] = useState<PlatformSuggestion[]>([]);
  const [form, setForm] = useState<PlatformSuggestionCreate>(initialForm);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await professionalApi.suggestions());
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Suggestions could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    try {
      const created = await professionalApi.suggest(form);
      setRows((current) => [created, ...current]);
      setForm(initialForm);
      toast.success("Suggestion sent to the platform owner");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The suggestion could not be submitted."));
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <PageLoader rows={6} />;

  return (
    <main className="loanhub-page space-y-6 p-4 sm:p-6">
      <section className="loanhub-hero flex flex-col justify-between gap-4 p-6 md:flex-row md:items-end">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.22em] text-primary">Product improvement</p>
          <h1 className="mt-2 text-3xl font-black">Suggestion box</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">Submit a traceable feature request or operational improvement to the platform owner.</p>
        </div>
        <Button variant="outline" onClick={() => void load()}><RefreshCcw className="h-4 w-4" />Refresh</Button>
      </section>

      <div className="grid gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
        <Card className="rounded-3xl border-border/70 shadow-sm">
          <CardHeader><CardTitle>New suggestion</CardTitle><CardDescription>All fields are validated by the form and FastAPI schema.</CardDescription></CardHeader>
          <CardContent>
            <form onSubmit={submit} className="space-y-4">
              <div className="space-y-2"><Label htmlFor="suggestion-title">Title</Label><Input id="suggestion-title" required minLength={4} maxLength={200} value={form.title} onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))} /></div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2"><Label>Category</Label><Select value={form.category ?? "feature_request"} onValueChange={(value) => setForm((current) => ({ ...current, category: value as NonNullable<PlatformSuggestionCreate["category"]> }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="feature_request">Feature request</SelectItem><SelectItem value="support_query">Support query</SelectItem></SelectContent></Select></div>
                <div className="space-y-2"><Label>Priority</Label><Select value={form.priority ?? "normal"} onValueChange={(value) => setForm((current) => ({ ...current, priority: value as NonNullable<PlatformSuggestionCreate["priority"]> }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{["low", "normal", "high", "urgent"].map((value) => <SelectItem key={value} value={value}>{titleCase(value)}</SelectItem>)}</SelectContent></Select></div>
              </div>
              <div className="space-y-2"><Label htmlFor="suggestion-description">Description</Label><Textarea id="suggestion-description" required minLength={10} maxLength={10000} value={form.description} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} className="min-h-36" /></div>
              <LoadingButton type="submit" loading={submitting} loadingText="Sending suggestion..." className="w-full"><Send className="h-4 w-4" />Send suggestion</LoadingButton>
            </form>
          </CardContent>
        </Card>

        <Card className="rounded-3xl border-border/70 shadow-sm">
          <CardHeader><CardTitle>Submitted items</CardTitle><CardDescription>{rows.length} traceable item(s)</CardDescription></CardHeader>
          <CardContent className="space-y-3">
            {rows.length === 0 ? <div className="rounded-2xl border border-dashed p-10 text-center text-sm text-muted-foreground"><Lightbulb className="mx-auto mb-3 h-8 w-8" />No suggestions have been submitted.</div> : rows.map((row) => (
              <article key={row.id} className="rounded-2xl border bg-gradient-to-br from-card to-primary/5 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-black">{row.reference} · {row.title}</p><p className="mt-1 text-xs text-muted-foreground">{formatDate(row.created_at)} · {titleCase(row.category)}</p></div><Badge variant="secondary">{titleCase(row.status)}</Badge></div>
                <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{row.description}</p>
                {row.platform_response && <div className="mt-3 rounded-xl bg-muted/50 p-3 text-sm"><span className="font-black">Platform response:</span> {row.platform_response}</div>}
              </article>
            ))}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
