"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2, ShieldCheck } from "lucide-react";

import { getGatewayPaymentMethods, type GatewayPaymentRail } from "@/api/lelefaPayGate";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { PaymentMethod, PaymentMethodOption } from "@/types/expenseManagement";

export type PaymentEvidence = {
  payment_method: PaymentMethod;
  gateway_provider: string;
  gateway_customer_phone: string;
  proof_reference: string;
  proof_url: string;
  proof_notes: string;
};

export const DEFAULT_PAYMENT_METHOD_OPTIONS: PaymentMethodOption[] = [
  {
    value: "lelefapaygate",
    label: "LelefaPayGate (secure electronic payment)",
    proof_recommended: false,
  },
  { value: "cash", label: "Cash", proof_recommended: false },
];

export const EMPTY_PAYMENT_EVIDENCE: PaymentEvidence = {
  payment_method: "cash",
  gateway_provider: "",
  gateway_customer_phone: "",
  proof_reference: "",
  proof_url: "",
  proof_notes: "",
};

type PaymentMethodFieldsProps = {
  methods: PaymentMethodOption[];
  value: PaymentEvidence;
  onChange: (value: PaymentEvidence) => void;
  disabled?: boolean;
  showNotes?: boolean;
  showGatewayRailPicker?: boolean;
};

export function PaymentMethodFields({
  methods,
  value,
  onChange,
  disabled = false,
  showNotes = true,
  showGatewayRailPicker = true,
}: PaymentMethodFieldsProps) {
  const [rails, setRails] = useState<GatewayPaymentRail[]>([]);
  const [railsLoading, setRailsLoading] = useState(false);
  const [railsError, setRailsError] = useState("");
  const [railsLoaded, setRailsLoaded] = useState(false);
  const isCash = value.payment_method === "cash";
  const isGateway = value.payment_method === "lelefapaygate";
  const methodOptions = DEFAULT_PAYMENT_METHOD_OPTIONS.map(
    fallback => methods.find(item => item.value === fallback.value) ?? fallback,
  );
  const directRails = useMemo(
    () => rails.filter(rail => rail.available && rail.flow === "phone_prompt"),
    [rails],
  );
  const hostedRails = useMemo(
    () => rails.filter(rail => rail.available && rail.flow === "hosted_checkout"),
    [rails],
  );
  const selectedRail = directRails.find(rail => rail.id === value.gateway_provider) ?? null;
  const phoneField = selectedRail?.fields.find(field => field.key === "phone");

  useEffect(() => {
    if (!isGateway || !showGatewayRailPicker || railsLoaded || railsLoading) return;
    setRailsLoading(true);
    setRailsError("");
    getGatewayPaymentMethods("LSL")
      .then(catalog => {
        const available = catalog.methods.filter(rail => rail.available);
        const direct = available.filter(rail => rail.flow === "phone_prompt");
        setRails(available);
        if (!direct.some(rail => rail.id === value.gateway_provider) && direct[0]) {
          onChange({
            ...value,
            gateway_provider: direct[0].id,
            gateway_customer_phone: "",
          });
        }
      })
      .catch(error => setRailsError(error instanceof Error ? error.message : "Payment methods could not be loaded"))
      .finally(() => {
        setRailsLoaded(true);
        setRailsLoading(false);
      });
  }, [isGateway, onChange, railsLoaded, railsLoading, showGatewayRailPicker, value]);

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Payment method</Label>
        <Select
          value={value.payment_method}
          disabled={disabled}
          onValueChange={(paymentMethod: PaymentMethod) =>
            onChange({
              ...value,
              payment_method: paymentMethod,
              gateway_provider: "",
              gateway_customer_phone: "",
              proof_reference: "",
              proof_url: "",
            })
          }
        >
          <SelectTrigger><SelectValue placeholder="Choose cash or LelefaPayGate" /></SelectTrigger>
          <SelectContent>
            {methodOptions.map(method => (
              <SelectItem key={method.value} value={method.value}>{method.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isGateway ? (
        <>
          <Alert>
            <ShieldCheck className="h-4 w-4" />
            <AlertTitle>Handled securely by LelefaPayGate</AlertTitle>
            <AlertDescription>
              Choose an enabled Lelefa rail below. LoanHub sends only the payment request from its protected backend. PINs, card data, API keys and provider credentials never reach this screen. Ledgers update only after a signed gateway confirmation.
            </AlertDescription>
          </Alert>

          {!showGatewayRailPicker ? (
            <p className="rounded-xl border bg-muted/30 p-3 text-xs text-muted-foreground">The payout provider is selected by LelefaPayGate’s protected server configuration.</p>
          ) : railsLoading ? (
            <div className="flex items-center gap-2 rounded-xl border p-3 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading enabled Lelefa payment providers…
            </div>
          ) : railsError ? (
            <Alert variant="destructive">
              <AlertTitle>Payment providers unavailable</AlertTitle>
              <AlertDescription>{railsError}</AlertDescription>
            </Alert>
          ) : directRails.length ? (
            <>
              <div className="space-y-2">
                <Label>LelefaPayGate provider</Label>
                <Select
                  value={value.gateway_provider}
                  disabled={disabled}
                  onValueChange={gatewayProvider => onChange({
                    ...value,
                    gateway_provider: gatewayProvider,
                    gateway_customer_phone: "",
                  })}
                >
                  <SelectTrigger><SelectValue placeholder="Choose M-Pesa, EcoCash or another enabled provider" /></SelectTrigger>
                  <SelectContent>
                    {directRails.map(rail => (
                      <SelectItem key={rail.id} value={rail.id}>{rail.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {selectedRail ? <p className="text-xs text-muted-foreground">{selectedRail.description}</p> : null}
              </div>

              {phoneField ? (
                <div className="space-y-2">
                  <Label htmlFor="gateway-customer-phone">{phoneField.label}</Label>
                  <Input
                    id="gateway-customer-phone"
                    type="tel"
                    autoComplete="tel"
                    disabled={disabled}
                    value={value.gateway_customer_phone}
                    onChange={event => onChange({ ...value, gateway_customer_phone: event.target.value })}
                    placeholder={phoneField.placeholder || "+266 5…"}
                    required={phoneField.required}
                  />
                  <p className="text-xs text-muted-foreground">The customer approves the request on this phone. Never ask for or record their PIN.</p>
                </div>
              ) : null}
            </>
          ) : (
            <Alert variant="destructive">
              <AlertTitle>No direct LSL collection provider is enabled</AlertTitle>
              <AlertDescription>Enable a compatible M-Pesa, EcoCash or bank collection rail in LelefaPayGate before collecting here.</AlertDescription>
            </Alert>
          )}

          {hostedRails.length ? (
            <p className="rounded-xl border bg-muted/30 p-3 text-xs text-muted-foreground">
              Borrowers can also pay online through LelefaPayGate using {hostedRails.map(rail => rail.label).join(", ")}. Card and PayPal details are entered only on the hosted gateway page.
            </p>
          ) : null}
        </>
      ) : null}

      {showNotes ? (
        <div className="space-y-2">
          <Label>{isCash ? "Cash verification notes" : "Internal notes (optional)"}</Label>
          <Textarea
            disabled={disabled}
            value={value.proof_notes}
            onChange={event => onChange({ ...value, proof_notes: event.target.value })}
            placeholder={
              isCash
                ? "Cash counted, borrower identified, receipt book reference"
                : "Internal note; do not enter card details, PINs or gateway credentials"
            }
          />
        </div>
      ) : null}
    </div>
  );
}
