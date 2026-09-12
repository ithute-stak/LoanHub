import { createAsyncThunk } from "@reduxjs/toolkit";
import {LoanOffer, LoanOfferCreatePayload, LoanOfferUpdatePayload} from "@/types/loan_offer";
import {api} from "@/lib/api";

// Create a new offer
export const createLoanOffer = createAsyncThunk<
    LoanOffer,
    LoanOfferCreatePayload,
    { rejectValue: string }
>("loanOffers/createLoanOffer", async (payload, { rejectWithValue }) => {
    try {
        const response = await api.post<LoanOffer>("/loan-offers/", payload);
        return response.data;
    } catch (error: any) {
        return rejectWithValue(
            error.response?.data?.detail || "Failed to create loan offer parameters."
        );
    }
});

// Fetch all offers assigned to a specific loan request
export const fetchOffersByRequest = createAsyncThunk<
    LoanOffer[],
    string,
    { rejectValue: string }
>("loanOffers/fetchOffersByRequest", async (loanRequestId, { rejectWithValue }) => {
    try {
        const response = await api.get<LoanOffer[]>(`/loan-offers/request/${loanRequestId}`);
        return response.data;
    } catch (error: any) {
        return rejectWithValue(
            error.response?.data?.detail || "Failed to retrieve matching application offer files."
        );
    }
});

// Update an existing offer
export const updateLoanOffer = createAsyncThunk<
    LoanOffer,
    LoanOfferUpdatePayload,
    { rejectValue: string }
>("loanOffers/updateLoanOffer", async ({ id, ...payload }, { rejectWithValue }) => {
    try {
        const response = await api.patch<LoanOffer>(`/loan-offers/${id}`, payload);
        return response.data;
    } catch (error: any) {
        return rejectWithValue(
            error.response?.data?.detail || "Failed to update financial configuration metrics."
        );
    }
});

// Remove/Delete an offer
export const deleteLoanOffer = createAsyncThunk<
    string,
    string,
    { rejectValue: string }
>("loanOffers/deleteLoanOffer", async (offerId, { rejectWithValue }) => {
    try {
        await api.delete(`/loan-offers/${offerId}`);
        return offerId;
    } catch (error: any) {
        return rejectWithValue(
            error.response?.data?.detail || "Failed to purge targeted database records."
        );
    }
});