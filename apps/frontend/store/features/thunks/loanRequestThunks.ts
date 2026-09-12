import { createAsyncThunk } from "@reduxjs/toolkit";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/utils/apiError";
import {
    LoanRequest,
    LoanRequestCreatePayload,
    LoanRequestUpdatePayload
} from "@/types/loanRequest";

// GET ALL
export const fetchAllRequests = createAsyncThunk<
    LoanRequest[],
    void,
    { rejectValue: string }
>(
    "loanRequests/fetchAll",
    async (_, thunkAPI) => {
        try {
            const res = await api.get<LoanRequest[]>("/loan_requests/");
            return res.data;
        } catch (error: unknown) {
            return thunkAPI.rejectWithValue(
                getErrorMessage(error, "Failed to fetch all loan requests")
            );
        }
    }
);

// GET MY REQUESTS
export const fetchMyRequests = createAsyncThunk<
    LoanRequest[],
    void,
    { rejectValue: string }
>(
    "loanRequests/fetchMy",
    async (_, thunkAPI) => {
        try {
            const res = await api.get<LoanRequest[]>("/loan_requests/my");
            return res.data;
        } catch (error: unknown) {
            return thunkAPI.rejectWithValue(
                getErrorMessage(error, "Failed to fetch your loan requests")
            );
        }
    }
);

// GET OPEN REQUESTS
export const fetchOpenRequests = createAsyncThunk<
    LoanRequest[],
    void,
    { rejectValue: string }
>(
    "loanRequests/fetchOpen",
    async (_, thunkAPI) => {
        try {
            const res = await api.get<LoanRequest[]>("/loan_requests/open");
            return res.data;
        } catch (error: unknown) {
            return thunkAPI.rejectWithValue(
                getErrorMessage(error, "Failed to fetch open marketplace requests")
            );
        }
    }
);

// GET ONE BY ID
export const fetchRequestById = createAsyncThunk<
    LoanRequest,
    string,
    { rejectValue: string }
>(
    "loanRequests/fetchById",
    async (id, thunkAPI) => {
        try {
            const res = await api.get<LoanRequest>(`/loan_requests/${id}`);
            return res.data;
        } catch (error: unknown) {
            return thunkAPI.rejectWithValue(
                getErrorMessage(error, "Failed to fetch loan request")
            );
        }
    }
);

// CREATE
export const createLoanRequest = createAsyncThunk<
    LoanRequest,
    LoanRequestCreatePayload,
    { rejectValue: string }
>(
    "loanRequests/create",
    async (payload, thunkAPI) => {
        try {
            const res = await api.post<LoanRequest>("/loan_requests/", payload);
            return res.data;
        } catch (error: unknown) {
            return thunkAPI.rejectWithValue(
                getErrorMessage(error, "Failed to create loan request")
            );
        }
    }
);

// UPDATE (PATCH)
export const updateLoanRequest = createAsyncThunk<
    LoanRequest,
    { id: string; payload: LoanRequestUpdatePayload },
    { rejectValue: string }
>(
    "loanRequests/update",
    async ({ id, payload }, thunkAPI) => {
        try {
            const res = await api.patch<LoanRequest>(`/loan_requests/${id}`, payload);
            return res.data;
        } catch (error: unknown) {
            return thunkAPI.rejectWithValue(
                getErrorMessage(error, "Failed to update loan request")
            );
        }
    }
);

// DELETE
export const deleteLoanRequest = createAsyncThunk<
    string,
    string,
    { rejectValue: string }
>(
    "loanRequests/delete",
    async (id, thunkAPI) => {
        try {
            await api.delete(`/loan_requests/${id}`);
            return id;
        } catch (error: unknown) {
            return thunkAPI.rejectWithValue(
                getErrorMessage(error, "Failed to delete loan request")
            );
        }
    }
);