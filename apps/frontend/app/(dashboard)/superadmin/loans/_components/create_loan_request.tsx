"use client";


import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import React, { useState } from "react";
import { useDispatch } from "react-redux";
import { AppDispatch } from "@/store"; // Adjust import to point to your main store setup
import { createLoanRequest } from "@/store/features/thunks/loanRequestThunks";
import { toast } from "@/utils/toast";
import { Calendar, FileText, Send, Loader2 } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";

interface CreateRequestFormProps {
    onSuccess: () => void;
}

export default function CreateRequestForm({ onSuccess }: CreateRequestFormProps) {
    const dispatch = useDispatch<AppDispatch>();
    const [loading, setLoading] = useState(false);
    const [formData, setFormData] = useState({
        requested_amount: "",
        preferred_term_months: "",
        loan_purpose: "",
        visible_to_lenders: true,
        allow_lenders_to_call: true,
    });

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);

        try {
            const payload = {
                requested_amount: parseFloat(formData.requested_amount),
                preferred_term_months: formData.preferred_term_months ? parseInt(formData.preferred_term_months) : null,
                loan_purpose: formData.loan_purpose || null,
                visible_to_lenders: formData.visible_to_lenders,
                allow_lenders_to_call: formData.allow_lenders_to_call,
            };

            // Dispatch Redux action instead of standard fetch pipeline
            await dispatch(createLoanRequest(payload)).unwrap();

            toast.success("Loan request has been dispatched successfully.");

            // Reset Form State Safely
            setFormData({
                requested_amount: "",
                preferred_term_months: "",
                loan_purpose: "",
                visible_to_lenders: true,
                allow_lenders_to_call: true,
            });
            onSuccess();
        } catch (error: any) {
            toast.error(error || "Submission rejected by platform constraints.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="rounded-[1.75rem] border border-border bg-card p-6 shadow-sm">
            <h2 className="text-xl font-black tracking-tight text-card-foreground mb-1">Create Loan Request</h2>
            <p className="text-xs text-muted-foreground mb-6">Submit your capital requirements to approved marketplace lenders.</p>

            <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2">Requested Amount (LSL / M)</label>
                    <div className="relative">
                        <span className="absolute left-4 top-1/2 -translate-y-1/2 font-bold text-primary">M</span>
                        <Input
                            type="number"
                            step="0.01"
                            required
                            value={formData.requested_amount}
                            onChange={(e) => setFormData({ ...formData, requested_amount: e.target.value })}
                            placeholder="0.00"
                            className="w-full rounded-xl border border-border bg-background py-3 pl-9 pr-4 text-sm font-semibold text-foreground shadow-inner focus:border-primary focus:outline-none"
                        />
                    </div>
                </div>

                <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2">Preferred Term (Months)</label>
                    <div className="relative">
                        <Calendar className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <Input
                            type="number"
                            value={formData.preferred_term_months}
                            onChange={(e) => setFormData({ ...formData, preferred_term_months: e.target.value })}
                            placeholder="e.g. 12"
                            className="w-full rounded-xl border border-border bg-background py-3 pl-11 pr-4 text-sm font-semibold text-foreground shadow-inner focus:border-primary focus:outline-none"
                        />
                    </div>
                </div>

                <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2">Loan Purpose</label>
                    <div className="relative">
                        <FileText className="absolute left-4 top-3 h-4 w-4 text-muted-foreground" />
                        <Textarea
                            rows={3}
                            value={formData.loan_purpose}
                            onChange={(e) => setFormData({ ...formData, loan_purpose: e.target.value })}
                            placeholder="Describe the usage of funds..."
                            className="w-full rounded-xl border border-border bg-background py-3 pl-11 pr-4 text-sm font-semibold text-foreground shadow-inner focus:border-primary focus:outline-none"
                        />
                    </div>
                </div>

                <div className="space-y-3 pt-2">
                    <div className="flex items-center gap-3 select-none">
                        <Checkbox
                            id="visible_to_lenders"
                            checked={formData.visible_to_lenders}
                            onCheckedChange={(checked) => setFormData({ ...formData, visible_to_lenders: !!checked })}
                        />
                        <label htmlFor="visible_to_lenders" className="text-xs font-semibold text-card-foreground cursor-pointer">
                            Broadcast & make visible to licensed lenders
                        </label>
                    </div>

                    <div className="flex items-center gap-3 select-none">
                        <Checkbox
                            id="allow_lenders_to_call"
                            checked={formData.allow_lenders_to_call}
                            onCheckedChange={(checked) => setFormData({ ...formData, allow_lenders_to_call: !!checked })}
                        />
                        <label htmlFor="allow_lenders_to_call" className="text-xs font-semibold text-card-foreground cursor-pointer">
                            Allow matching underwriters to contact me directly
                        </label>
                    </div>
                </div>

                <button
                    type="submit"
                    disabled={loading}
                    className="mt-2 w-full flex items-center justify-center gap-2 cursor-pointer rounded-xl bg-primary py-3 text-sm font-bold text-primary-foreground transition-all duration-200 hover:opacity-95 active:scale-[0.99] disabled:opacity-50"
                >
                    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                    Dispatch Loan Request
                </button>
            </form>
        </div>
    );
}