import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import {
    createLoanOffer,
    fetchOffersByRequest,
    updateLoanOffer,
    deleteLoanOffer
} from "../thunks/loanOfferThunks";
import {LoanOffer} from "@/types/loan_offer";

interface LoanOfferState {
    offers: LoanOffer[];
    loading: boolean;
    error: string | null;
}

const initialState: LoanOfferState = {
    offers: [],
    loading: false,
    error: null,
};

const loanOfferSlice = createSlice({
    name: "loanOffers",
    initialState,
    reducers: {
        clearOfferErrors: (state) => {
            state.error = null;
        },
        resetOfferState: (state) => {
            state.offers = [];
            state.loading = false;
            state.error = null;
        }
    },
    extraReducers: (builder) => {
        builder
            // ================= FETCH BY REQUEST =================
            .addCase(fetchOffersByRequest.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchOffersByRequest.fulfilled, (state, action: PayloadAction<LoanOffer[]>) => {
                state.loading = false;
                state.offers = action.payload;
            })
            .addCase(fetchOffersByRequest.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload || "An unexpected error occurred.";
            })

            // ================= CREATE OFFER =================
            .addCase(createLoanOffer.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(createLoanOffer.fulfilled, (state, action: PayloadAction<LoanOffer>) => {
                state.loading = false;
                state.offers.unshift(action.payload); // Add new entry to top of view list
            })
            .addCase(createLoanOffer.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload || "An unexpected error occurred.";
            })

            // ================= UPDATE OFFER =================
            .addCase(updateLoanOffer.fulfilled, (state, action: PayloadAction<LoanOffer>) => {
                const index = state.offers.findIndex((o) => o.id === action.payload.id);
                if (index !== -1) {
                    state.offers[index] = action.payload;
                }
            })

            // ================= DELETE OFFER =================
            .addCase(deleteLoanOffer.fulfilled, (state, action: PayloadAction<string>) => {
                state.offers = state.offers.filter((o) => o.id !== action.payload);
            });
    }
});

export const { clearOfferErrors, resetOfferState } = loanOfferSlice.actions;
export default loanOfferSlice.reducer;