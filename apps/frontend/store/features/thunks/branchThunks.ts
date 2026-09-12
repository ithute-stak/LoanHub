import {
    createAsyncThunk,
} from "@reduxjs/toolkit";

import {
    branchApi,
} from "@/api/branch";

import type {
    Branch,
    BranchCreatePayload,
    BranchUpdatePayload,
} from "@/types/branch";

import {
    getErrorMessage,
} from "@/utils/apiError";

export const fetchBranchesThunk =
    createAsyncThunk<
        Branch[],
        void,
        {
            rejectValue: string;
        }
    >(
        "branches/fetchAll",
        async (_, thunkAPI) => {
            try {
                const response =
                    await branchApi.getAll();

                return response.data;
            } catch (error: unknown) {
                return thunkAPI.rejectWithValue(
                    getErrorMessage(
                        error,
                        "Failed to fetch branches",
                    ),
                );
            }
        },
    );

export const fetchCompanyBranchesThunk =
    createAsyncThunk<
        Branch[],
        string,
        {
            rejectValue: string;
        }
    >(
        "branches/fetchByCompany",
        async (
            companyId,
            thunkAPI,
        ) => {
            try {
                const response =
                    await branchApi.getByCompany(
                        companyId,
                    );

                return response.data;
            } catch (error: unknown) {
                return thunkAPI.rejectWithValue(
                    getErrorMessage(
                        error,
                        "Failed to fetch company branches",
                    ),
                );
            }
        },
    );

export const fetchBranchByIdThunk =
    createAsyncThunk<
        Branch,
        string,
        {
            rejectValue: string;
        }
    >(
        "branches/fetchById",
        async (
            branchId,
            thunkAPI,
        ) => {
            try {
                const response =
                    await branchApi.getOne(
                        branchId,
                    );

                return response.data;
            } catch (error: unknown) {
                return thunkAPI.rejectWithValue(
                    getErrorMessage(
                        error,
                        "Failed to fetch branch",
                    ),
                );
            }
        },
    );

export const createBranchThunk =
    createAsyncThunk<
        Branch,
        BranchCreatePayload,
        {
            rejectValue: string;
        }
    >(
        "branches/create",
        async (
            payload,
            thunkAPI,
        ) => {
            try {
                const response =
                    await branchApi.create(
                        payload,
                    );

                return response.data;
            } catch (error: unknown) {
                return thunkAPI.rejectWithValue(
                    getErrorMessage(
                        error,
                        "Failed to create branch",
                    ),
                );
            }
        },
    );

export const updateBranchThunk =
    createAsyncThunk<
        Branch,
        {
            id: string;
            data: BranchUpdatePayload;
        },
        {
            rejectValue: string;
        }
    >(
        "branches/update",
        async (
            {
                id,
                data,
            },
            thunkAPI,
        ) => {
            try {
                const response =
                    await branchApi.update(
                        id,
                        data,
                    );

                return response.data;
            } catch (error: unknown) {
                return thunkAPI.rejectWithValue(
                    getErrorMessage(
                        error,
                        "Failed to update branch",
                    ),
                );
            }
        },
    );

export const deleteBranchThunk =
    createAsyncThunk<
        string,
        string,
        {
            rejectValue: string;
        }
    >(
        "branches/delete",
        async (
            branchId,
            thunkAPI,
        ) => {
            try {
                await branchApi.delete(
                    branchId,
                );

                return branchId;
            } catch (error: unknown) {
                return thunkAPI.rejectWithValue(
                    getErrorMessage(
                        error,
                        "Failed to delete branch",
                    ),
                );
            }
        },
    );

export const activateBranchThunk =
    createAsyncThunk<
        string,
        string,
        {
            rejectValue: string;
        }
    >(
        "branches/activate",
        async (
            branchId,
            thunkAPI,
        ) => {
            try {
                await branchApi.activate(
                    branchId,
                );

                return branchId;
            } catch (error: unknown) {
                return thunkAPI.rejectWithValue(
                    getErrorMessage(
                        error,
                        "Failed to activate branch",
                    ),
                );
            }
        },
    );

export const deactivateBranchThunk =
    createAsyncThunk<
        string,
        string,
        {
            rejectValue: string;
        }
    >(
        "branches/deactivate",
        async (
            branchId,
            thunkAPI,
        ) => {
            try {
                await branchApi.deactivate(
                    branchId,
                );

                return branchId;
            } catch (error: unknown) {
                return thunkAPI.rejectWithValue(
                    getErrorMessage(
                        error,
                        "Failed to deactivate branch",
                    ),
                );
            }
        },
    );
