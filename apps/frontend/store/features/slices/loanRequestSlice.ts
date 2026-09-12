import { createSlice } from "@reduxjs/toolkit";
import { LoanRequest, LoanRequestStatus } from "@/types/loanRequest";
import {
    createLoanRequest,
    deleteLoanRequest,
    fetchAllRequests,
    fetchMyRequests,
    fetchOpenRequests,
    fetchRequestById,
    updateLoanRequest
} from "@/store/features/thunks/loanRequestThunks";

interface LoanRequestState {
    allRequests: LoanRequest[];
    myRequests: LoanRequest[];
    openRequests: LoanRequest[];
    currentRequest: LoanRequest | null;
    loading: boolean;
    error: string | null;
}

const initialState: LoanRequestState = {
    allRequests: [],
    myRequests: [],
    openRequests: [],
    currentRequest: null,
    loading: false,
    error: null,
};

const loanRequestSlice = createSlice({
    name: "loanRequests",
    initialState,
    reducers: {
        clearCurrentRequest: (state) => {
            state.currentRequest = null;
        },
    },
    extraReducers: (builder) => {
        builder
            // 1. Specific Success Handlers
            .addCase(fetchAllRequests.fulfilled, (state, action) => {
                state.loading = false;
                state.allRequests = action.payload;
            })
            .addCase(fetchMyRequests.fulfilled, (state, action) => {
                state.loading = false;
                state.myRequests = action.payload;
            })
            .addCase(fetchOpenRequests.fulfilled, (state, action) => {
                state.loading = false;
                state.openRequests = action.payload;
            })
            .addCase(fetchRequestById.fulfilled, (state, action) => {
                state.loading = false;
                state.currentRequest = action.payload;
            })
            .addCase(createLoanRequest.fulfilled, (state, action) => {
                state.loading = false;
                state.myRequests.unshift(action.payload);
                state.allRequests.unshift(action.payload);
                if (action.payload.status === LoanRequestStatus.OPEN && action.payload.visible_to_lenders) {
                    state.openRequests.unshift(action.payload);
                }
            })
            .addCase(updateLoanRequest.fulfilled, (state, action) => {
                state.loading = false;
                const updated = action.payload;

                if (state.currentRequest?.id === updated.id) {
                    state.currentRequest = updated;
                }

                state.allRequests = state.allRequests.map(r => r.id === updated.id ? updated : r);
                state.myRequests = state.myRequests.map(r => r.id === updated.id ? updated : r);

                if (updated.status === LoanRequestStatus.OPEN && updated.visible_to_lenders) {
                    const exists = state.openRequests.some(r => r.id === updated.id);
                    state.openRequests = exists
                        ? state.openRequests.map(r => r.id === updated.id ? updated : r)
                        : [updated, ...state.openRequests];
                } else {
                    state.openRequests = state.openRequests.filter(r => r.id !== updated.id);
                }
            })
            .addCase(deleteLoanRequest.fulfilled, (state, action) => {
                state.loading = false;
                const deletedId = action.payload;
                if (state.currentRequest?.id === deletedId) {
                    state.currentRequest = null;
                }
                state.allRequests = state.allRequests.filter(r => r.id !== deletedId);
                state.myRequests = state.myRequests.filter(r => r.id !== deletedId);
                state.openRequests = state.openRequests.filter(r => r.id !== deletedId);
            })

            // 2. Intercept Global Pending States for loanRequests namespace
            .addMatcher(
                (action) => typeof action.type === "string" && action.type.endsWith("/pending") && action.type.startsWith("loanRequests/"),
                (state) => {
                    state.loading = true;
                    state.error = null;
                }
            )
            // 3. Intercept Global Rejected States (typed using an inline type guard check)
            .addMatcher(
                (action): action is { type: string; payload: string } =>
                    typeof action.type === "string" && action.type.endsWith("/rejected") && action.type.startsWith("loanRequests/"),
                (state, action) => {
                    state.loading = false;
                    state.error = action.payload || "An unexpected error occurred.";
                }
            );
    },
});

export const { clearCurrentRequest } = loanRequestSlice.actions;
export default loanRequestSlice.reducer;