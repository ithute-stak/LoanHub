"use client";

import { ContactRound, Phone, RefreshCcw, Search, WalletCards } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { callsApi } from "@/api/calls";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { formatMoney, titleCase } from "@/lib/format";
import type { CallClient, CallClientDetail } from "@/types/calls";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

type PhoneBookCallContext = {
  borrowerId: string;
  phone: string;
  loanId?: string;
};

type CompanyPhoneBookPanelProps = {
  onStartCall: (context: PhoneBookCallContext) => void;
};

export function CompanyPhoneBookPanel({ onStartCall }: CompanyPhoneBookPanelProps) {
  const [clients, setClients] = useState<CallClient[]>([]);
  const [selectedClient, setSelectedClient] = useState<CallClientDetail | null>(null);
  const [search, setSearch] = useState("");
  const [loanFilter, setLoanFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [openingClientId, setOpeningClientId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setClients(await callsApi.listClients());
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The company phone book could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(() => {
    const token = search.trim().toLowerCase();
    return clients.filter((client) => {
      if (loanFilter === "has-loan" && client.loans.length === 0) return false;
      if (loanFilter === "overdue" && !client.loans.some((loan) => loan.is_overdue)) return false;
      if (!token) return true;
      return [client.name, client.phone, ...client.loans.map((loan) => loan.loan_reference)]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(token);
    });
  }, [clients, loanFilter, search]);

  async function openClient(client: CallClient) {
    setOpeningClientId(client.borrower_id);
    try {
      setSelectedClient(await callsApi.getClient(client.borrower_id));
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The borrower contacts could not be loaded."));
    } finally {
      setOpeningClientId(null);
    }
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-4 space-y-0">
          <div>
            <CardTitle className="flex items-center gap-2"><ContactRound className="h-5 w-5 text-primary" />Company phone book</CardTitle>
            <CardDescription className="mt-1">
              Call a borrower or an authorised alternative contact, then link the call to the relevant loan.
            </CardDescription>
          </div>
          <Button variant="outline" onClick={() => void load()} disabled={loading}>
            <RefreshCcw className={"mr-2 h-4 w-4 " + (loading ? "animate-spin" : "")} />
            Refresh
          </Button>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-[1fr_200px]">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search borrower, number or loan reference…" className="pl-9" />
          </div>
          <NativeSelect value={loanFilter} onChange={(event) => setLoanFilter(event.target.value)}>
            <option value="all">All borrowers</option>
            <option value="has-loan">Has a loan</option>
            <option value="overdue">Overdue loan</option>
          </NativeSelect>
        </CardContent>
      </Card>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card>
          <CardHeader>
            <CardTitle>Borrowers</CardTitle>
            <CardDescription>{filtered.length} people in your authorised company or branch scope.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 p-4 sm:grid-cols-2">
            {filtered.map((client) => (
              <div
                key={client.borrower_id}
                className={"rounded-2xl border p-4 text-left transition hover:border-primary/50 hover:bg-primary/5 " + (selectedClient?.borrower_id === client.borrower_id ? "border-primary bg-primary/5" : "")}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <Link
                      href={`/company/borrowers/${client.borrower_id}`}
                      className="font-black underline-offset-4 hover:text-primary hover:underline"
                    >
                      {client.name ?? "Borrower"}
                    </Link>
                    <p className="mt-1 text-sm text-muted-foreground">{client.phone ?? "No primary number"}</p>
                  </div>
                  <ContactRound className="h-5 w-5 shrink-0 text-primary" />
                </div>
                <div className="mt-3 flex items-center justify-between gap-3">
                  <p className="text-xs text-muted-foreground">{client.loans.length} linked loan{client.loans.length === 1 ? "" : "s"}</p>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={openingClientId === client.borrower_id}
                    onClick={() => void openClient(client)}
                  >
                    Contacts
                  </Button>
                </div>
              </div>
            ))}
            {!loading && filtered.length === 0 && <p className="col-span-full py-12 text-center text-sm text-muted-foreground">No borrower matches the current phone-book search.</p>}
          </CardContent>
        </Card>

        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Contacts & loans</CardTitle>
            <CardDescription>Only contacts explicitly marked as permitted can be called.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {selectedClient ? (
              <>
                <div>
                  <Link
                    href={`/company/borrowers/${selectedClient.borrower_id}`}
                    className="text-lg font-black underline-offset-4 hover:text-primary hover:underline"
                  >
                    {selectedClient.name ?? "Borrower"}
                  </Link>
                  <p className="text-sm text-muted-foreground">Choose the person to call, then optionally link the loan.</p>
                </div>
                <div className="space-y-2">
                  <Label>Authorised contacts</Label>
                  {selectedClient.contacts.map((contact) => (
                    <div key={contact.phone + contact.name} className="flex items-center justify-between gap-3 rounded-xl border p-3">
                      <div className="min-w-0">
                        <p className="truncate font-bold">{contact.name}{contact.is_primary ? " · Primary" : ""}</p>
                        <p className="text-xs text-muted-foreground">{contact.relationship} · {contact.phone}</p>
                      </div>
                      {contact.is_call_permitted ? (
                        <Button size="sm" onClick={() => onStartCall({ borrowerId: selectedClient.borrower_id, phone: contact.phone })}>
                          <Phone className="mr-1 h-4 w-4" />Call
                        </Button>
                      ) : <Badge variant="secondary">Not permitted</Badge>}
                    </div>
                  ))}
                  {selectedClient.contacts.length === 0 && <p className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">No calling contacts have been recorded.</p>}
                </div>
                <div className="space-y-2">
                  <Label>Call about a loan</Label>
                  {selectedClient.loans.map((loan) => {
                    const preferredContact = selectedClient.contacts.find((contact) => contact.is_call_permitted && contact.is_primary)
                      ?? selectedClient.contacts.find((contact) => contact.is_call_permitted);
                    return (
                      <div key={loan.id} className="flex items-center justify-between gap-3 rounded-xl bg-muted/40 p-3">
                        <div className="min-w-0">
                          <p className="font-bold">{loan.loan_reference}</p>
                          <p className="text-xs text-muted-foreground">{formatMoney(loan.balance)} · {titleCase(loan.status)}{loan.is_overdue ? " · overdue" : ""}</p>
                        </div>
                        {preferredContact ? (
                          <Button size="sm" variant="outline" onClick={() => onStartCall({ borrowerId: selectedClient.borrower_id, phone: preferredContact.phone, loanId: loan.id })}>
                            <WalletCards className="mr-1 h-4 w-4" />Call
                          </Button>
                        ) : <Badge variant="secondary">No permitted contact</Badge>}
                      </div>
                    );
                  })}
                </div>
              </>
            ) : <p className="py-16 text-center text-sm text-muted-foreground">{openingClientId ? "Loading borrower contacts…" : "Select a borrower to see contacts and loan-linked calls."}</p>}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
