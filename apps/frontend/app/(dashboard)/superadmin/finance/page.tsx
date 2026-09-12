"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import {
  BadgePercent,
  Banknote,
  CheckCircle2,
  FileCheck2,
  Pencil,
  Plus,
  ReceiptText,
  RefreshCcw,
  Scale,
} from "lucide-react";

import {
  createChargeClaim,
  listAccountOpeningFees,
  listBorrowerRequestFees,
  listChargeClaims,
  listChargeLedger,
  listTransactionAgreements,
  makeOwnerAgreementDecision,
  saveAccountOpeningFee,
  saveBorrowerRequestFee,
  saveTransactionAgreement,
  type AccountOpeningFee,
  type AccountOpeningFeeWrite,
  type BorrowerRequestFee,
  type BorrowerRequestFeeWrite,
  type ChargeClaim,
  type ChargeLedgerEntry,
  type FeeType,
  type TransactionAgreement,
  type TransactionAgreementWrite,
} from "@/api/finance";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { CustomDialog } from "@/components/ui/custom-dialog";
import { DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { PageLoader } from "@/components/ui/page-loader";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { formatDate, formatDateTime, formatMoney, titleCase } from "@/lib/format";
import { useAppData } from "@/provider/appDataProvider";
import { toast } from "@/utils/toast";

const GLOBAL_VALUE = "global";
const NONE_VALUE = "none";

const borrowerFeeDefault: BorrowerRequestFeeWrite = {
  company_id: null,
  name: "Borrow request service fee",
  fee_type: "flat",
  flat_amount: 20,
  percentage: 0,
  minimum_amount: null,
  maximum_amount: null,
  currency: "LSL",
  required_before_submission: true,
  refundable: false,
  effective_from: null,
  effective_to: null,
  is_active: true,
};

const openingFeeDefault: AccountOpeningFeeWrite = {
  company_id: null,
  name: "Assisted borrower account opening fee",
  fee_type: "flat",
  flat_amount: 0,
  percentage: 0,
  minimum_amount: null,
  maximum_amount: null,
  currency: "LSL",
  effective_from: null,
  effective_to: null,
  is_active: false,
};

function agreementDefault(companyId = ""): TransactionAgreementWrite {
  const today = new Date().toISOString().slice(0, 10);
  return {
    company_id: companyId,
    name: "Platform cash transaction charge agreement",
    inbound_percentage: 0.005,
    outbound_percentage: 0.005,
    inbound_flat_fee: 0,
    outbound_flat_fee: 0,
    minimum_charge: null,
    maximum_charge: null,
    currency: "LSL",
    settlement_frequency: "monthly",
    settlement_day: 1,
    effective_from: today,
    effective_to: null,
    terms: null,
  };
}

export default function PlatformFinanceConfigurationPage() {
  const { companies, getCompanyName } = useAppData();
  const [borrowerFees, setBorrowerFees] = useState<BorrowerRequestFee[]>([]);
  const [openingFees, setOpeningFees] = useState<AccountOpeningFee[]>([]);
  const [agreements, setAgreements] = useState<TransactionAgreement[]>([]);
  const [ledger, setLedger] = useState<ChargeLedgerEntry[]>([]);
  const [claims, setClaims] = useState<ChargeClaim[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [borrowerDialog, setBorrowerDialog] = useState(false);
  const [openingDialog, setOpeningDialog] = useState(false);
  const [agreementDialog, setAgreementDialog] = useState(false);
  const [claimDialog, setClaimDialog] = useState(false);
  const [borrowerEditId, setBorrowerEditId] = useState<string | undefined>();
  const [openingEditId, setOpeningEditId] = useState<string | undefined>();
  const [agreementEditId, setAgreementEditId] = useState<string | undefined>();
  const [borrowerForm, setBorrowerForm] = useState<BorrowerRequestFeeWrite>(borrowerFeeDefault);
  const [openingForm, setOpeningForm] = useState<AccountOpeningFeeWrite>(openingFeeDefault);
  const [agreementForm, setAgreementForm] = useState<TransactionAgreementWrite>(agreementDefault());
  const [claimForm, setClaimForm] = useState({ company_id: "", period_start: new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().slice(0, 10), period_end: new Date().toISOString().slice(0, 10), due_days: 14, notes: "" });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [borrowerRows, openingRows, agreementRows, ledgerRows, claimRows] = await Promise.all([
        listBorrowerRequestFees(),
        listAccountOpeningFees(),
        listTransactionAgreements(),
        listChargeLedger(),
        listChargeClaims(),
      ]);
      setBorrowerFees(borrowerRows);
      setOpeningFees(openingRows);
      setAgreements(agreementRows);
      setLedger(ledgerRows);
      setClaims(claimRows);
    } catch (error) {
      toast.error(error, { description: "Platform finance configuration could not be loaded." });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const activeBorrowerFee = useMemo(() => borrowerFees.find((item) => item.is_active && item.company_id === null) ?? null, [borrowerFees]);
  const totalCharges = useMemo(() => ledger.reduce((sum, item) => sum + Number(item.charge_amount || 0), 0), [ledger]);
  const openClaims = useMemo(() => claims.filter((item) => item.status !== "paid" && item.status !== "settled").reduce((sum, item) => sum + Number(item.amount || 0), 0), [claims]);

  function openBorrowerFee(item?: BorrowerRequestFee) {
    setBorrowerEditId(item?.id);
    setBorrowerForm(item ? stripBorrowerRead(item) : borrowerFeeDefault);
    setBorrowerDialog(true);
  }

  function openOpeningFee(item?: AccountOpeningFee) {
    setOpeningEditId(item?.id);
    setOpeningForm(item ? stripOpeningRead(item) : openingFeeDefault);
    setOpeningDialog(true);
  }

  function openAgreement(item?: TransactionAgreement) {
    setAgreementEditId(item?.id);
    setAgreementForm(item ? stripAgreementRead(item) : agreementDefault(companies[0]?.id ?? ""));
    setAgreementDialog(true);
  }

  async function submitBorrowerFee(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    try {
      await saveBorrowerRequestFee(normalizeBorrowerFee(borrowerForm), borrowerEditId);
      setBorrowerDialog(false);
      toast.success("Borrower request fee saved");
      await load();
    } catch (error) {
      toast.error(error, { description: "The borrower fee configuration was not saved." });
    } finally { setSaving(false); }
  }

  async function submitOpeningFee(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    try {
      await saveAccountOpeningFee(normalizeOpeningFee(openingForm), openingEditId);
      setOpeningDialog(false);
      toast.success("Assisted account-opening charge saved");
      await load();
    } catch (error) {
      toast.error(error, { description: "The account-opening charge was not saved." });
    } finally { setSaving(false); }
  }

  async function submitAgreement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    try {
      await saveTransactionAgreement(normalizeAgreement(agreementForm), agreementEditId);
      setAgreementDialog(false);
      toast.success("Transaction agreement saved", { description: "The percentages are stored as percentages. Entering 0.005 means 0.005%, not 0.5%." });
      await load();
    } catch (error) {
      toast.error(error, { description: "The agreement was not saved." });
    } finally { setSaving(false); }
  }

  async function acceptAgreement(item: TransactionAgreement) {
    setSaving(true);
    try {
      await makeOwnerAgreementDecision(item.id, true);
      toast.success("Owner acceptance recorded");
      await load();
    } catch (error) { toast.error(error); } finally { setSaving(false); }
  }

  async function submitClaim(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    try {
      await createChargeClaim({ ...claimForm, notes: claimForm.notes.trim() || null });
      setClaimDialog(false);
      toast.success("Charge claim created");
      await load();
    } catch (error) { toast.error(error, { description: "The claim could not be created." }); } finally { setSaving(false); }
  }

  if (loading) return <PageLoader rows={8} />;

  return (
    <div className="loanhub-page">
      <section className="loanhub-hero flex flex-col justify-between gap-5 p-6 lg:flex-row lg:items-end">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.24em] text-primary">Platform owner finance rules</p>
          <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Fees, agreements and claims</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">Configure the cash amount charged to a borrower for an online request, the company charge for assisted client account opening, and separate inbound/outbound transaction percentages agreed with each tenant company.</p>
        </div>
        <Button variant="outline" onClick={() => void load()}><RefreshCcw className="h-4 w-4" />Refresh finance</Button>
      </section>

      <div className="grid gap-4 md:grid-cols-4">
        <Metric icon={Banknote} label="Active request fee" value={activeBorrowerFee ? feeDescription(activeBorrowerFee) : "Not configured"} />
        <Metric icon={Scale} label="Agreements" value={String(agreements.length)} />
        <Metric icon={BadgePercent} label="Accrued charges" value={formatMoney(totalCharges)} />
        <Metric icon={ReceiptText} label="Open claims" value={formatMoney(openClaims)} />
      </div>

      <Alert>
        <Scale className="h-4 w-4" />
        <AlertTitle>Percentage entry rule</AlertTitle>
        <AlertDescription>Enter <strong>0.005</strong> to charge <strong>0.005%</strong>. A cash movement of M10,000 at that rate creates a platform charge of M0.50: 10,000 × 0.005 ÷ 100.</AlertDescription>
      </Alert>

      <Tabs defaultValue="fees" className="space-y-5">
        <TabsList className="grid h-auto w-full grid-cols-2 rounded-2xl p-1 sm:grid-cols-4"><TabsTrigger value="fees" className="rounded-xl py-2.5">Service fees</TabsTrigger><TabsTrigger value="agreements" className="rounded-xl py-2.5">Agreements</TabsTrigger><TabsTrigger value="ledger" className="rounded-xl py-2.5">Charge ledger</TabsTrigger><TabsTrigger value="claims" className="rounded-xl py-2.5">Claims</TabsTrigger></TabsList>

        <TabsContent value="fees" className="grid gap-6 xl:grid-cols-2">
          <FeeTable title="Borrower loan-request fee" description="Cash paid by a borrower to the platform owner before an online request is broadcast." items={borrowerFees} companies={companies} onAdd={() => openBorrowerFee()} onEdit={openBorrowerFee} />
          <OpeningFeeTable items={openingFees} companies={companies} onAdd={() => openOpeningFee()} onEdit={openOpeningFee} />
        </TabsContent>

        <TabsContent value="agreements">
          <Card className="loanhub-panel overflow-hidden">
            <CardHeader className="border-b bg-muted/20"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center"><div><CardTitle>Company cash transaction agreements</CardTitle><CardDescription>Version-controlled inbound and outbound charges. Active financial agreements cannot be silently edited.</CardDescription></div><Button onClick={() => openAgreement()} disabled={companies.length === 0}><Plus className="h-4 w-4" />New agreement</Button></div></CardHeader>
            <CardContent className="p-0"><div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>Agreement</TableHead><TableHead>Company</TableHead><TableHead>Money in</TableHead><TableHead>Money out</TableHead><TableHead>Settlement</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Action</TableHead></TableRow></TableHeader><TableBody>{agreements.length === 0 ? <TableRow><TableCell colSpan={7} className="h-40 text-center text-muted-foreground">No company transaction agreements exist.</TableCell></TableRow> : agreements.map((item) => <TableRow key={item.id}><TableCell><p className="font-black">{item.name}</p><p className="font-mono text-xs text-muted-foreground">{item.agreement_number}</p></TableCell><TableCell>{getCompanyName(item.company_id)}</TableCell><TableCell><p className="font-black">{item.inbound_percentage}%</p><p className="text-xs text-muted-foreground">+ {formatMoney(item.inbound_flat_fee)}</p></TableCell><TableCell><p className="font-black">{item.outbound_percentage}%</p><p className="text-xs text-muted-foreground">+ {formatMoney(item.outbound_flat_fee)}</p></TableCell><TableCell>{titleCase(item.settlement_frequency)}{item.settlement_day ? ` · day ${item.settlement_day}` : ""}</TableCell><TableCell><Badge variant={item.status === "active" ? "default" : "secondary"}>{titleCase(item.status)}</Badge></TableCell><TableCell><div className="flex justify-end gap-2">{item.status !== "active" && <Button size="sm" variant="outline" onClick={() => openAgreement(item)}><Pencil className="h-4 w-4" />Edit</Button>}{!item.owner_accepted_at && <LoadingButton size="sm" loading={saving} onClick={() => void acceptAgreement(item)}><CheckCircle2 className="h-4 w-4" />Owner accept</LoadingButton>}</div></TableCell></TableRow>)}</TableBody></Table></div></CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="ledger">
          <Card className="loanhub-panel overflow-hidden"><CardHeader><CardTitle>Automatic transaction-charge ledger</CardTitle><CardDescription>Every eligible successful money-in or money-out movement stores the agreement snapshot, percentage, flat fee and resulting charge.</CardDescription></CardHeader><CardContent className="p-0"><div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>Accrued</TableHead><TableHead>Company</TableHead><TableHead>Direction</TableHead><TableHead>Purpose</TableHead><TableHead>Gross movement</TableHead><TableHead>Rate</TableHead><TableHead>Charge</TableHead><TableHead>Status</TableHead></TableRow></TableHeader><TableBody>{ledger.length === 0 ? <TableRow><TableCell colSpan={8} className="h-40 text-center text-muted-foreground">No eligible transaction charges have accrued.</TableCell></TableRow> : ledger.map((item) => <TableRow key={item.id}><TableCell>{formatDateTime(item.accrued_at)}</TableCell><TableCell>{getCompanyName(item.company_id)}</TableCell><TableCell><Badge variant="outline">{item.direction === "inbound" ? "Money in" : "Money out"}</Badge></TableCell><TableCell>{titleCase(item.payment_purpose)}</TableCell><TableCell>{formatMoney(item.gross_amount, item.currency)}</TableCell><TableCell>{item.percentage_rate}% + {formatMoney(item.flat_fee, item.currency)}</TableCell><TableCell className="font-black">{formatMoney(item.charge_amount, item.currency)}</TableCell><TableCell><Badge variant="secondary">{titleCase(item.status)}</Badge></TableCell></TableRow>)}</TableBody></Table></div></CardContent></Card>
        </TabsContent>

        <TabsContent value="claims">
          <Card className="loanhub-panel overflow-hidden"><CardHeader className="border-b bg-muted/20"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center"><div><CardTitle>Period claims</CardTitle><CardDescription>Create a claim from eligible, unclaimed ledger rows for the agreed period.</CardDescription></div><Button onClick={() => setClaimDialog(true)} disabled={companies.length === 0}><Plus className="h-4 w-4" />Create claim</Button></div></CardHeader><CardContent className="p-0"><div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>Claim</TableHead><TableHead>Company</TableHead><TableHead>Period</TableHead><TableHead>Transactions</TableHead><TableHead>Gross value</TableHead><TableHead>Claim amount</TableHead><TableHead>Status</TableHead></TableRow></TableHeader><TableBody>{claims.length === 0 ? <TableRow><TableCell colSpan={7} className="h-40 text-center text-muted-foreground">No platform charge claims exist.</TableCell></TableRow> : claims.map((item) => <TableRow key={item.id}><TableCell><p className="font-mono text-xs font-black text-primary">{item.claim_number}</p><p className="text-xs text-muted-foreground">Due {formatDate(item.due_at)}</p></TableCell><TableCell>{getCompanyName(item.company_id)}</TableCell><TableCell>{formatDate(item.period_start)} – {formatDate(item.period_end)}</TableCell><TableCell>{item.transaction_count}</TableCell><TableCell>{formatMoney(item.gross_transaction_value, item.currency)}</TableCell><TableCell className="font-black">{formatMoney(item.amount, item.currency)}</TableCell><TableCell><Badge variant={item.status === "paid" ? "default" : "secondary"}>{titleCase(item.status)}</Badge></TableCell></TableRow>)}</TableBody></Table></div></CardContent></Card>
        </TabsContent>
      </Tabs>

      <FeeDialog open={borrowerDialog} onOpenChange={setBorrowerDialog} title="Borrower request service fee" description="Configure the fee required before an online loan request is broadcast. Platform finance may verify any recognised payment channel." form={borrowerForm} setForm={setBorrowerForm} companies={companies} saving={saving} onSubmit={submitBorrowerFee} showRequestControls />
      <FeeDialog open={openingDialog} onOpenChange={setOpeningDialog} title="Assisted account-opening charge" description="Accrue this amount to the tenant company when its loan officer opens a borrower account on behalf of a customer." form={openingForm} setForm={setOpeningForm} companies={companies} saving={saving} onSubmit={submitOpeningFee} />

      <CustomDialog open={agreementDialog} onOpenChange={(open) => !saving && setAgreementDialog(open)} title="Company cash transaction agreement" description="Configure separate incoming and outgoing charges. Percentages are manually editable until the agreement becomes active." contentClassName="sm:max-w-3xl">
        <form onSubmit={submitAgreement} className="space-y-6 p-6 sm:p-8"><div className="grid gap-4 md:grid-cols-2"><Field label="Tenant company"><Select value={agreementForm.company_id} onValueChange={(value) => setAgreementForm((current) => ({ ...current, company_id: value }))}><SelectTrigger><SelectValue placeholder="Select company" /></SelectTrigger><SelectContent>{companies.map((company) => <SelectItem key={company.id} value={company.id}>{company.name}</SelectItem>)}</SelectContent></Select></Field><Field label="Agreement name"><Input required value={agreementForm.name} onChange={(event) => setAgreementForm((current) => ({ ...current, name: event.target.value }))} /></Field><Field label="Incoming transaction rate (%)"><Input type="number" min="0" max="100" step="0.000001" required value={agreementForm.inbound_percentage} onChange={(event) => setAgreementForm((current) => ({ ...current, inbound_percentage: Number(event.target.value) }))} /></Field><Field label="Outgoing transaction rate (%)"><Input type="number" min="0" max="100" step="0.000001" required value={agreementForm.outbound_percentage} onChange={(event) => setAgreementForm((current) => ({ ...current, outbound_percentage: Number(event.target.value) }))} /></Field><Field label="Incoming flat fee"><Input type="number" min="0" step="0.01" value={agreementForm.inbound_flat_fee} onChange={(event) => setAgreementForm((current) => ({ ...current, inbound_flat_fee: Number(event.target.value) }))} /></Field><Field label="Outgoing flat fee"><Input type="number" min="0" step="0.01" value={agreementForm.outbound_flat_fee} onChange={(event) => setAgreementForm((current) => ({ ...current, outbound_flat_fee: Number(event.target.value) }))} /></Field><Field label="Minimum charge"><Input type="number" min="0" step="0.01" value={agreementForm.minimum_charge ?? ""} onChange={(event) => setAgreementForm((current) => ({ ...current, minimum_charge: nullableNumber(event.target.value) }))} /></Field><Field label="Maximum charge"><Input type="number" min="0" step="0.01" value={agreementForm.maximum_charge ?? ""} onChange={(event) => setAgreementForm((current) => ({ ...current, maximum_charge: nullableNumber(event.target.value) }))} /></Field><Field label="Settlement frequency"><Select value={agreementForm.settlement_frequency} onValueChange={(value) => setAgreementForm((current) => ({ ...current, settlement_frequency: value as TransactionAgreementWrite["settlement_frequency"] }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{["daily","weekly","monthly","quarterly","custom"].map((value) => <SelectItem key={value} value={value}>{titleCase(value)}</SelectItem>)}</SelectContent></Select></Field><Field label="Settlement day"><Input type="number" min="1" max="31" value={agreementForm.settlement_day ?? ""} onChange={(event) => setAgreementForm((current) => ({ ...current, settlement_day: nullableNumber(event.target.value) }))} /></Field><Field label="Effective from"><Input type="date" required value={agreementForm.effective_from.slice(0, 10)} onChange={(event) => setAgreementForm((current) => ({ ...current, effective_from: event.target.value }))} /></Field><Field label="Effective to"><Input type="date" value={agreementForm.effective_to?.slice(0, 10) ?? ""} onChange={(event) => setAgreementForm((current) => ({ ...current, effective_to: event.target.value || null }))} /></Field><div className="md:col-span-2"><Field label="Terms and settlement notes"><Textarea rows={5} value={agreementForm.terms ?? ""} onChange={(event) => setAgreementForm((current) => ({ ...current, terms: event.target.value || null }))} /></Field></div><Alert className="md:col-span-2"><BadgePercent className="h-4 w-4" /><AlertTitle>Example at the current rate</AlertTitle><AlertDescription>M10,000 money in at {agreementForm.inbound_percentage}% produces {formatMoney(10000 * Number(agreementForm.inbound_percentage) / 100 + Number(agreementForm.inbound_flat_fee))}. M10,000 money out at {agreementForm.outbound_percentage}% produces {formatMoney(10000 * Number(agreementForm.outbound_percentage) / 100 + Number(agreementForm.outbound_flat_fee))} before minimum/maximum rules.</AlertDescription></Alert></div><DialogFooter className="mx-0 mb-0"><Button type="button" variant="outline" onClick={() => setAgreementDialog(false)} disabled={saving}>Cancel</Button><LoadingButton type="submit" loading={saving} loadingText="Saving..." disabled={!agreementForm.company_id}><FileCheck2 className="h-4 w-4" />Save agreement</LoadingButton></DialogFooter></form>
      </CustomDialog>

      <CustomDialog open={claimDialog} onOpenChange={(open) => !saving && setClaimDialog(open)} title="Create a period charge claim" description="Only eligible unclaimed cash-transaction ledger entries within the selected period are included." contentClassName="sm:max-w-lg"><form onSubmit={submitClaim} className="space-y-6 p-6 sm:p-8"><div className="space-y-4"><Field label="Tenant company"><Select value={claimForm.company_id} onValueChange={(value) => setClaimForm((current) => ({ ...current, company_id: value }))}><SelectTrigger><SelectValue placeholder="Select company" /></SelectTrigger><SelectContent>{companies.map((company) => <SelectItem key={company.id} value={company.id}>{company.name}</SelectItem>)}</SelectContent></Select></Field><div className="grid grid-cols-2 gap-4"><Field label="Period start"><Input type="date" required value={claimForm.period_start} onChange={(event) => setClaimForm((current) => ({ ...current, period_start: event.target.value }))} /></Field><Field label="Period end"><Input type="date" required value={claimForm.period_end} onChange={(event) => setClaimForm((current) => ({ ...current, period_end: event.target.value }))} /></Field></div><Field label="Payment due after days"><Input type="number" min="0" max="365" required value={claimForm.due_days} onChange={(event) => setClaimForm((current) => ({ ...current, due_days: Number(event.target.value) }))} /></Field><Field label="Notes"><Textarea value={claimForm.notes} onChange={(event) => setClaimForm((current) => ({ ...current, notes: event.target.value }))} /></Field></div><DialogFooter className="mx-0 mb-0"><Button type="button" variant="outline" onClick={() => setClaimDialog(false)} disabled={saving}>Cancel</Button><LoadingButton type="submit" loading={saving} loadingText="Creating..." disabled={!claimForm.company_id}><ReceiptText className="h-4 w-4" />Create claim</LoadingButton></DialogFooter></form></CustomDialog>
    </div>
  );
}

function Metric({ icon: Icon, label, value }: { icon: typeof Banknote; label: string; value: string }) { return <div className="loanhub-stat"><div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/12 text-primary"><Icon className="h-5 w-5" /></div><p className="mt-4 text-xs font-black uppercase tracking-[0.14em] text-muted-foreground">{label}</p><p className="mt-1 text-xl font-black">{value}</p></div>; }
function Field({ label, children }: { label: string; children: ReactNode }) { return <div className="space-y-2"><Label>{label}</Label>{children}</div>; }

function FeeTable({ title, description, items, companies, onAdd, onEdit }: { title: string; description: string; items: BorrowerRequestFee[]; companies: { id: string; name: string }[]; onAdd: () => void; onEdit: (item: BorrowerRequestFee) => void }) {
  const companyName = (id: string | null) => id ? companies.find((item) => item.id === id)?.name ?? "Unknown company" : "Global default";
  return <Card className="loanhub-panel overflow-hidden"><CardHeader className="border-b bg-muted/20"><div className="flex items-start justify-between gap-4"><div><CardTitle>{title}</CardTitle><CardDescription>{description}</CardDescription></div><Button size="sm" onClick={onAdd}><Plus className="h-4 w-4" />Add</Button></div></CardHeader><CardContent className="p-0"><Table><TableHeader><TableRow><TableHead>Scope</TableHead><TableHead>Charge</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Action</TableHead></TableRow></TableHeader><TableBody>{items.length === 0 ? <TableRow><TableCell colSpan={4} className="h-36 text-center text-muted-foreground">No borrower request fee configured.</TableCell></TableRow> : items.map((item) => <TableRow key={item.id}><TableCell><p className="font-black">{companyName(item.company_id)}</p><p className="text-xs text-muted-foreground">{item.name}</p></TableCell><TableCell>{feeDescription(item)}</TableCell><TableCell><Badge variant={item.is_active ? "default" : "secondary"}>{item.is_active ? "Active" : "Inactive"}</Badge></TableCell><TableCell className="text-right"><Button size="sm" variant="outline" onClick={() => onEdit(item)}><Pencil className="h-4 w-4" />Edit</Button></TableCell></TableRow>)}</TableBody></Table></CardContent></Card>;
}

function OpeningFeeTable({ items, companies, onAdd, onEdit }: { items: AccountOpeningFee[]; companies: { id: string; name: string }[]; onAdd: () => void; onEdit: (item: AccountOpeningFee) => void }) {
  const companyName = (id: string | null) => id ? companies.find((item) => item.id === id)?.name ?? "Unknown company" : "Global default";
  return <Card className="loanhub-panel overflow-hidden"><CardHeader className="border-b bg-muted/20"><div className="flex items-start justify-between gap-4"><div><CardTitle>Assisted borrower account-opening charge</CardTitle><CardDescription>Accrued to the tenant company when a loan officer opens a customer account.</CardDescription></div><Button size="sm" onClick={onAdd}><Plus className="h-4 w-4" />Add</Button></div></CardHeader><CardContent className="p-0"><Table><TableHeader><TableRow><TableHead>Scope</TableHead><TableHead>Charge</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Action</TableHead></TableRow></TableHeader><TableBody>{items.length === 0 ? <TableRow><TableCell colSpan={4} className="h-36 text-center text-muted-foreground">No account-opening charge configured.</TableCell></TableRow> : items.map((item) => <TableRow key={item.id}><TableCell><p className="font-black">{companyName(item.company_id)}</p><p className="text-xs text-muted-foreground">{item.name}</p></TableCell><TableCell>{feeDescription(item)}</TableCell><TableCell><Badge variant={item.is_active ? "default" : "secondary"}>{item.is_active ? "Active" : "Inactive"}</Badge></TableCell><TableCell className="text-right"><Button size="sm" variant="outline" onClick={() => onEdit(item)}><Pencil className="h-4 w-4" />Edit</Button></TableCell></TableRow>)}</TableBody></Table></CardContent></Card>;
}

type FeeForm = BorrowerRequestFeeWrite | AccountOpeningFeeWrite;
function FeeDialog<T extends FeeForm>({ open, onOpenChange, title, description, form, setForm, companies, saving, onSubmit, showRequestControls = false }: { open: boolean; onOpenChange: (open: boolean) => void; title: string; description: string; form: T; setForm: React.Dispatch<React.SetStateAction<T>>; companies: { id: string; name: string }[]; saving: boolean; onSubmit: (event: FormEvent<HTMLFormElement>) => void; showRequestControls?: boolean }) {
  return (
    <CustomDialog open={open} onOpenChange={(value) => !saving && onOpenChange(value)} title={title} description={description} contentClassName="sm:max-w-2xl">
      <form onSubmit={onSubmit} className="space-y-6 p-6 sm:p-8">
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Scope"><Select value={form.company_id ?? GLOBAL_VALUE} onValueChange={(value) => setForm((current) => ({ ...current, company_id: value === GLOBAL_VALUE ? null : value }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value={GLOBAL_VALUE}>Global default</SelectItem>{companies.map((company) => <SelectItem key={company.id} value={company.id}>{company.name}</SelectItem>)}</SelectContent></Select></Field>
          <Field label="Configuration name"><Input required value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} /></Field>
          <Field label="Fee method"><Select value={form.fee_type} onValueChange={(value) => setForm((current) => ({ ...current, fee_type: value as FeeType }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="flat">Flat cash amount</SelectItem><SelectItem value="percentage">Percentage</SelectItem><SelectItem value="hybrid">Flat plus percentage</SelectItem></SelectContent></Select></Field>
          <Field label="Flat amount"><Input type="number" min="0" step="0.01" value={form.flat_amount} onChange={(event) => setForm((current) => ({ ...current, flat_amount: Number(event.target.value) }))} /></Field>
          <Field label="Percentage (%)"><Input type="number" min="0" max="100" step="0.000001" value={form.percentage} onChange={(event) => setForm((current) => ({ ...current, percentage: Number(event.target.value) }))} /></Field>
          <Field label="Currency"><Input required maxLength={3} value={form.currency} onChange={(event) => setForm((current) => ({ ...current, currency: event.target.value.toUpperCase() }))} /></Field>
          <Field label="Minimum amount"><Input type="number" min="0" step="0.01" value={form.minimum_amount ?? ""} onChange={(event) => setForm((current) => ({ ...current, minimum_amount: nullableNumber(event.target.value) }))} /></Field>
          <Field label="Maximum amount"><Input type="number" min="0" step="0.01" value={form.maximum_amount ?? ""} onChange={(event) => setForm((current) => ({ ...current, maximum_amount: nullableNumber(event.target.value) }))} /></Field>
          <Field label="Effective from"><Input type="datetime-local" value={toLocalDateTime(form.effective_from)} onChange={(event) => setForm((current) => ({ ...current, effective_from: event.target.value ? new Date(event.target.value).toISOString() : null }))} /></Field>
          <Field label="Effective to"><Input type="datetime-local" value={toLocalDateTime(form.effective_to)} onChange={(event) => setForm((current) => ({ ...current, effective_to: event.target.value ? new Date(event.target.value).toISOString() : null }))} /></Field>
          <label className="flex items-center gap-3 rounded-2xl border p-4 md:col-span-2"><Checkbox checked={form.is_active} onCheckedChange={(checked) => setForm((current) => ({ ...current, is_active: checked === true }))} /><span className="text-sm font-black">Active configuration</span></label>
          {showRequestControls && "required_before_submission" in form && <><label className="flex items-center gap-3 rounded-2xl border p-4"><Checkbox checked={form.required_before_submission} onCheckedChange={(checked) => setForm((current) => ({ ...current, required_before_submission: checked === true }))} /><span className="text-sm font-black">Require before broadcast</span></label><label className="flex items-center gap-3 rounded-2xl border p-4"><Checkbox checked={form.refundable} onCheckedChange={(checked) => setForm((current) => ({ ...current, refundable: checked === true }))} /><span className="text-sm font-black">Refundable</span></label></>}
        </div>
        <DialogFooter className="mx-0 mb-0"><Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>Cancel</Button><LoadingButton type="submit" loading={saving} loadingText="Saving..."><CheckCircle2 className="h-4 w-4" />Save configuration</LoadingButton></DialogFooter>
      </form>
    </CustomDialog>
  );
}

function feeDescription(item: Pick<BorrowerRequestFee, "fee_type" | "flat_amount" | "percentage" | "currency"> | Pick<AccountOpeningFee, "fee_type" | "flat_amount" | "percentage" | "currency">): string {
  if (item.fee_type === "flat") return formatMoney(item.flat_amount, item.currency);
  if (item.fee_type === "percentage") return `${item.percentage}%`;
  return `${formatMoney(item.flat_amount, item.currency)} + ${item.percentage}%`;
}
function nullableNumber(value: string): number | null { return value.trim() === "" ? null : Number(value); }
function toLocalDateTime(value: string | null): string { if (!value) return ""; const date = new Date(value); if (Number.isNaN(date.getTime())) return ""; const offset = date.getTimezoneOffset(); return new Date(date.getTime() - offset * 60000).toISOString().slice(0, 16); }
function stripBorrowerRead(item: BorrowerRequestFee): BorrowerRequestFeeWrite { const { id: _id, created_by_user_id: _createdBy, created_at: _created, updated_at: _updated, ...write } = item; return write; }
function stripOpeningRead(item: AccountOpeningFee): AccountOpeningFeeWrite { const { id: _id, created_by_user_id: _createdBy, created_at: _created, updated_at: _updated, ...write } = item; return write; }
function stripAgreementRead(item: TransactionAgreement): TransactionAgreementWrite { const { id: _id, agreement_number: _number, status: _status, owner_accepted_by_user_id: _ownerBy, company_accepted_by_user_id: _companyBy, owner_accepted_at: _ownerAt, company_accepted_at: _companyAt, activated_at: _activated, suspended_at: _suspended, created_at: _created, updated_at: _updated, ...write } = item; return write; }
function normalizeBorrowerFee(form: BorrowerRequestFeeWrite): BorrowerRequestFeeWrite { return { ...form, flat_amount: Number(form.flat_amount || 0), percentage: Number(form.percentage || 0) }; }
function normalizeOpeningFee(form: AccountOpeningFeeWrite): AccountOpeningFeeWrite { return { ...form, flat_amount: Number(form.flat_amount || 0), percentage: Number(form.percentage || 0) }; }
function normalizeAgreement(form: TransactionAgreementWrite): TransactionAgreementWrite { return { ...form, inbound_percentage: Number(form.inbound_percentage || 0), outbound_percentage: Number(form.outbound_percentage || 0), inbound_flat_fee: Number(form.inbound_flat_fee || 0), outbound_flat_fee: Number(form.outbound_flat_fee || 0) }; }
