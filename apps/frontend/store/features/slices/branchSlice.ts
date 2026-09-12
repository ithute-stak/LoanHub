import {
    createSlice,
    type PayloadAction,
} from "@reduxjs/toolkit";

import type {
    Branch,
} from "@/types/branch";

import {
    activateBranchThunk,
    createBranchThunk,
    deactivateBranchThunk,
    deleteBranchThunk,
    fetchBranchByIdThunk,
    fetchBranchesThunk,
    fetchCompanyBranchesThunk,
    updateBranchThunk,
} from "@/store/features/thunks/branchThunks";

type BranchState = {
    branches: Branch[];
    selectedBranch: Branch | null;

    loading: boolean;
    actionLoadingId: string | null;

    error: string | null;
};

const initialState: BranchState = {
    branches: [],
    selectedBranch: null,

    loading: false,
    actionLoadingId: null,

    error: null,
};

function replaceBranch(
    branches: Branch[],
    updatedBranch: Branch,
) {
    const index = branches.findIndex(
        (branch) =>
            branch.id ===
            updatedBranch.id,
    );

    if (index !== -1) {
        branches[index] =
            updatedBranch;
    }
}

const branchSlice = createSlice({
    name: "branches",
    initialState,

    reducers: {
        clearBranchError(state) {
            state.error = null;
        },

        setSelectedBranch(
            state,
            action: PayloadAction<
                Branch | null
            >,
        ) {
            state.selectedBranch =
                action.payload;
        },
    },

    extraReducers: (builder) => {
        builder
            .addCase(
                fetchBranchesThunk.pending,
                (state) => {
                    state.loading = true;
                    state.error = null;
                },
            )

            .addCase(
                fetchBranchesThunk.fulfilled,
                (
                    state,
                    action,
                ) => {
                    state.loading = false;
                    state.branches =
                        action.payload;
                },
            )

            .addCase(
                fetchBranchesThunk.rejected,
                (
                    state,
                    action,
                ) => {
                    state.loading = false;
                    state.error =
                        action.payload ??
                        "Failed to fetch branches";
                },
            )

            .addCase(
                fetchCompanyBranchesThunk.pending,
                (state) => {
                    state.loading = true;
                    state.error = null;
                },
            )

            .addCase(
                fetchCompanyBranchesThunk.fulfilled,
                (
                    state,
                    action,
                ) => {
                    state.loading = false;
                    state.branches =
                        action.payload;
                },
            )

            .addCase(
                fetchCompanyBranchesThunk.rejected,
                (
                    state,
                    action,
                ) => {
                    state.loading = false;
                    state.error =
                        action.payload ??
                        "Failed to fetch company branches";
                },
            )

            .addCase(
                fetchBranchByIdThunk.fulfilled,
                (
                    state,
                    action,
                ) => {
                    state.selectedBranch =
                        action.payload;
                },
            )

            .addCase(
                createBranchThunk.pending,
                (state) => {
                    state.actionLoadingId =
                        "create";
                    state.error = null;
                },
            )

            .addCase(
                createBranchThunk.fulfilled,
                (
                    state,
                    action,
                ) => {
                    state.actionLoadingId =
                        null;

                    state.branches.unshift(
                        action.payload,
                    );
                },
            )

            .addCase(
                createBranchThunk.rejected,
                (
                    state,
                    action,
                ) => {
                    state.actionLoadingId =
                        null;

                    state.error =
                        action.payload ??
                        "Failed to create branch";
                },
            )

            .addCase(
                updateBranchThunk.pending,
                (
                    state,
                    action,
                ) => {
                    state.actionLoadingId =
                        action.meta.arg.id;

                    state.error = null;
                },
            )

            .addCase(
                updateBranchThunk.fulfilled,
                (
                    state,
                    action,
                ) => {
                    state.actionLoadingId =
                        null;

                    replaceBranch(
                        state.branches,
                        action.payload,
                    );

                    if (
                        state.selectedBranch
                            ?.id ===
                        action.payload.id
                    ) {
                        state.selectedBranch =
                            action.payload;
                    }
                },
            )

            .addCase(
                updateBranchThunk.rejected,
                (
                    state,
                    action,
                ) => {
                    state.actionLoadingId =
                        null;

                    state.error =
                        action.payload ??
                        "Failed to update branch";
                },
            )

            .addCase(
                deleteBranchThunk.pending,
                (
                    state,
                    action,
                ) => {
                    state.actionLoadingId =
                        action.meta.arg;

                    state.error = null;
                },
            )

            .addCase(
                deleteBranchThunk.fulfilled,
                (
                    state,
                    action,
                ) => {
                    state.actionLoadingId =
                        null;

                    state.branches =
                        state.branches.filter(
                            (branch) =>
                                branch.id !==
                                action.payload,
                        );

                    if (
                        state.selectedBranch
                            ?.id ===
                        action.payload
                    ) {
                        state.selectedBranch =
                            null;
                    }
                },
            )

            .addCase(
                deleteBranchThunk.rejected,
                (
                    state,
                    action,
                ) => {
                    state.actionLoadingId =
                        null;

                    state.error =
                        action.payload ??
                        "Failed to delete branch";
                },
            )

            .addCase(
                activateBranchThunk.pending,
                (
                    state,
                    action,
                ) => {
                    state.actionLoadingId =
                        action.meta.arg;

                    state.error = null;
                },
            )

            .addCase(
                activateBranchThunk.fulfilled,
                (
                    state,
                    action,
                ) => {
                    state.actionLoadingId =
                        null;

                    const branch =
                        state.branches.find(
                            (item) =>
                                item.id ===
                                action.payload,
                        );

                    if (branch) {
                        branch.is_active = true;
                    }
                },
            )

            .addCase(
                activateBranchThunk.rejected,
                (
                    state,
                    action,
                ) => {
                    state.actionLoadingId =
                        null;

                    state.error =
                        action.payload ??
                        "Failed to activate branch";
                },
            )

            .addCase(
                deactivateBranchThunk.pending,
                (
                    state,
                    action,
                ) => {
                    state.actionLoadingId =
                        action.meta.arg;

                    state.error = null;
                },
            )

            .addCase(
                deactivateBranchThunk.fulfilled,
                (
                    state,
                    action,
                ) => {
                    state.actionLoadingId =
                        null;

                    const branch =
                        state.branches.find(
                            (item) =>
                                item.id ===
                                action.payload,
                        );

                    if (branch) {
                        branch.is_active = false;
                    }
                },
            )

            .addCase(
                deactivateBranchThunk.rejected,
                (
                    state,
                    action,
                ) => {
                    state.actionLoadingId =
                        null;

                    state.error =
                        action.payload ??
                        "Failed to deactivate branch";
                },
            );
    },
});

export const {
    clearBranchError,
    setSelectedBranch,
} = branchSlice.actions;

export default branchSlice.reducer;
