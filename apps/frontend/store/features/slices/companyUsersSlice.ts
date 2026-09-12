import {
    createSlice,
    PayloadAction,
} from "@reduxjs/toolkit";

import {
    CompanyStaff,
} from "@/types/companyStuff";

import {
    createCompanyStaff,
    fetchCompanyStaff,
    fetchCompanyStaffById,
    updateCompanyStaff,
    deleteCompanyStaff,
} from "@/store/features/thunks/companyUserThunk";

interface CompanyStaffState {
    staff: CompanyStaff[];
    loading: boolean;
    error: string | null;
    createdStaff: CompanyStaff | null;
    selectedStaff: CompanyStaff | null;
}

const initialState: CompanyStaffState = {
    staff: [],
    loading: false,
    error: null,
    createdStaff: null,
    selectedStaff: null,
};

const companyStaffSlice = createSlice({
    name: "companyStaff",
    initialState,

    reducers: {
        clearCompanyStaffError(state) {
            state.error = null;
        },

        setSelectedStaff(
            state,
            action: PayloadAction<CompanyStaff | null>
        ) {
            state.selectedStaff = action.payload;
        },
    },

    extraReducers: (builder) => {

        // ======================
        // FETCH ALL
        // ======================
        builder
            .addCase(fetchCompanyStaff.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchCompanyStaff.fulfilled, (state, action) => {
                state.loading = false;
                state.staff = action.payload;
            })
            .addCase(fetchCompanyStaff.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload ?? "Failed to fetch staff";
            });

        // ======================
        // CREATE
        // ======================
        builder
            .addCase(createCompanyStaff.pending, (state) => {
                state.loading = true;
            })
            .addCase(createCompanyStaff.fulfilled, (state, action) => {
                state.loading = false;
                state.createdStaff = action.payload;
                state.staff.unshift(action.payload);
            })
            .addCase(createCompanyStaff.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload ?? "Failed to create staff";
            });

        // ======================
        // UPDATE
        // ======================
        builder
            .addCase(updateCompanyStaff.fulfilled, (state, action) => {
                const index = state.staff.findIndex(
                    (s) => s.id === action.payload.id
                );

                if (index !== -1) {
                    state.staff[index] = action.payload;
                }
            });

        // ======================
        // DELETE
        // ======================
        builder
            .addCase(deleteCompanyStaff.fulfilled, (state, action) => {
                state.staff = state.staff.filter(
                    (s) => s.id !== action.payload
                );
            });

        // ======================
        // FETCH ONE
        // ======================
        builder
            .addCase(fetchCompanyStaffById.fulfilled, (state, action) => {
                state.selectedStaff = action.payload;
            });
    },
});

export const {
    clearCompanyStaffError,
    setSelectedStaff,
} = companyStaffSlice.actions;

export default companyStaffSlice.reducer;