"use client";


import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import React, { useEffect, useState } from "react";
import { toast } from "@/utils/toast";
import { DollarSign, Percent, Clock, Send, ShieldCheck, MessageSquare } from "lucide-react";
import {useDispatch} from "react-redux";
import {AppDispatch} from "@/store";
import {createLoanOffer} from "@/store/features/thunks/loanOfferThunks";
import { INTEREST_METHOD_OPTIONS, interestMethodOption } from "@/lib/interest-methods";
import { InstallmentDueDateFields, installmentDueDatesComplete, resizeInstallmentDueDates } from "@/components/loans/installment-due-date-fields";
import type { InterestMethod } from "@/types/loan";

// 1. Updated props to accept the required database IDs
type CounterOfferFormProps = {
    loanRequestId: string;
    branchId: string;
    requestedAmount: number;
    preferredTermMonths?: number;
    onSuccess: (payload: any) => void; // Pass payload back to your API handler/Thunk
    onCancel: () => void;
};

export function LoanCounterOfferForm({
                                         loanRequestId,
                                         branchId,
                                         requestedAmount,
                                         preferredTermMonths,
                                         onSuccess,
                                         onCancel
                                     }: CounterOfferFormProps) {
    // 2. State elements explicitly matching your API schema names
    const [approvedAmount, setApprovedAmount] = useState("");
    const [termMonths, setTermMonths] = useState("");
    const [installmentDueDates, setInstallmentDueDates] = useState<string[]>([]);
    const [interestRatePercent, setInterestRatePercent] = useState("");
    const [interestMethod, setInterestMethod] = useState<InterestMethod>("daily_accrual_reducing");
    const [processingFee, setProcessingFee] = useState("");
    const [notes, setNotes] = useState("");
    const dispatch = useDispatch<AppDispatch>();

    useEffect(() => {
        setInstallmentDueDates((current) => resizeInstallmentDueDates(current, Number(termMonths || 0)));
    }, [termMonths]);

    const handleSendOffer = (e: React.FormEvent) => {
        e.preventDefault();

        // Basic validation for required numerical metrics
        if (!approvedAmount || !termMonths || !interestRatePercent || !processingFee) {
            toast.error("Please fill out all parameter metrics before submission.");
            return;
        }
        if (!installmentDueDatesComplete(installmentDueDates, Number(termMonths))) {
            toast.error(`Enter all ${Number(termMonths)} installment due dates before submission.`);
            return;
        }

        // 3. Construct the exact JSON request body payload
        const requestBody = {
            approved_amount: Number(approvedAmount),
            term_months: Number(termMonths),
            interest_rate_percent: Number(interestRatePercent),
            processing_fee: Number(processingFee),
            notes: notes || "",
            loan_request_id: loanRequestId,
            branch_id: branchId,
            calculation_method: interestMethod,
            installment_due_dates: installmentDueDates,
        };



        // Pass the body out to your parent handler (Axios/Fetch/RTK Query)
        dispatch(createLoanOffer(requestBody));
        onSuccess(requestBody);

        toast.success(`Financial counter-offer of M${approvedAmount} successfully dispatched!`);

        // Clear states
        setApprovedAmount("");
        setTermMonths("");
        setInstallmentDueDates([]);
        setInterestRatePercent("");
        setProcessingFee("");
        setNotes("");
    };

    return (
        <form onSubmit={handleSendOffer} className="space-y-4">
            {/* Approved Amount */}
            <div>
                <label className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground block mb-1">
                    Approved Amount (M)
                </label>
                <div className="relative">
                    <DollarSign className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                        type="number"
                        value={approvedAmount}
                        onChange={(e) => setApprovedAmount(e.target.value)}
                        placeholder={requestedAmount.toString()}
                        className="w-full bg-background border border-border rounded-xl pl-9 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                    />
                </div>
            </div>


            <div>
                <label className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground block mb-1">
                    Interest Method
                </label>
                <select
                    value={interestMethod}
                    onChange={(event) => setInterestMethod(event.target.value as InterestMethod)}
                    className="h-10 w-full rounded-xl border border-border bg-background px-3 text-sm"
                >
                    {INTEREST_METHOD_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                </select>
                <p className="mt-1 text-xs text-muted-foreground">{interestMethodOption(interestMethod).description}</p>
            </div>

            {/* Interest Rate Percent */}
            <div>
                <label className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground block mb-1">
                    {interestMethodOption(interestMethod).rateLabel}
                </label>
                <div className="relative">
                    <Percent className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                        type="number"
                        step="0.01"
                        value={interestRatePercent}
                        onChange={(e) => setInterestRatePercent(e.target.value)}
                        placeholder="12.5"
                        className="w-full bg-background border border-border rounded-xl pl-9 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                    />
                </div>
            </div>

            {/* Term Months */}
            <div>
                <label className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground block mb-1">
                    Term Duration (Months)
                </label>
                <div className="relative">
                    <Clock className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                        type="number"
                        value={termMonths}
                        onChange={(e) => setTermMonths(e.target.value)}
                        placeholder={preferredTermMonths?.toString() || "12"}
                        className="w-full bg-background border border-border rounded-xl pl-9 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                    />
                </div>
            </div>

            <InstallmentDueDateFields
                count={Number(termMonths || 0)}
                value={installmentDueDates}
                onChange={setInstallmentDueDates}
            />

            {/* Processing Fee */}
            <div>
                <label className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground block mb-1">
                    Processing Fee (M)
                </label>
                <div className="relative">
                    <ShieldCheck className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                        type="number"
                        step="0.01"
                        value={processingFee}
                        onChange={(e) => setProcessingFee(e.target.value)}
                        placeholder="150.00"
                        className="w-full bg-background border border-border rounded-xl pl-9 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                    />
                </div>
            </div>

            {/* Notes */}
            <div>
                <label className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground block mb-1">
                    Notes
                </label>
                <div className="relative">
                    <MessageSquare className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Textarea
                        value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                        placeholder="Add specific conditions or remarks..."
                        rows={3}
                        className="w-full bg-background border border-border rounded-xl pl-9 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 resize-none"
                    />
                </div>
            </div>

            <div className="flex gap-3 justify-end pt-2">
                <button
                    type="button"
                    onClick={onCancel}
                    className="px-4 py-2 text-xs font-bold uppercase tracking-wider border border-border rounded-xl hover:bg-muted transition cursor-pointer"
                >
                    Cancel
                </button>
                <button
                    type="submit"
                    className="flex items-center gap-2 px-4 py-2 text-xs font-bold uppercase tracking-wider bg-primary text-primary-foreground rounded-xl hover:opacity-90 transition cursor-pointer"
                >
                    <Send className="h-3 w-3" />
                    Dispatch Offer
                </button>
            </div>
        </form>
    );
}