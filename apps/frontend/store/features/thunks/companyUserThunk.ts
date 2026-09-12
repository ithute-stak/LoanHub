import { createAsyncThunk } from "@reduxjs/toolkit";

import { api } from "@/lib/api";

import {
    CompanyStaff,
    CreateCompanyStaffPayload,
    UpdateCompanyStaffPayload,
} from "@/types/companyStuff";

import { getErrorMessage } from "@/utils/apiError";


// GET ALL
export const fetchCompanyStaff = createAsyncThunk<
    CompanyStaff[],
    void,
    { rejectValue: string }
>(
    "companyStaff/fetchAll",
    async (_, thunkAPI) => {
        try {
            const res = await api.get<CompanyStaff[]>(
                "/company-staff/"
            );
            return res.data;
        } catch (error: unknown) {
            return thunkAPI.rejectWithValue(
                getErrorMessage(
                    error,
                    "Failed to fetch staff"
                )
            );
        }
    }
);


// GET ONE
export const fetchCompanyStaffById = createAsyncThunk<
    CompanyStaff,
    string,
    { rejectValue: string }
>(
    "companyStaff/fetchById",
    async (id, thunkAPI) => {
        try {
            const res = await api.get<CompanyStaff>(
                `/company-staff/${id}`
            );

            return res.data;
        } catch (error: unknown) {
            return thunkAPI.rejectWithValue(
                getErrorMessage(
                    error,
                    "Failed to fetch staff"
                )
            );
        }
    }
);


// CREATE
export const createCompanyStaff = createAsyncThunk<
    CompanyStaff,
    CreateCompanyStaffPayload,
    { rejectValue: string }
>(
    "companyStaff/create",
    async (payload, thunkAPI) => {
        try {
            const res = await api.post<CompanyStaff>(
                "/company-staff/",
                payload
            );

            return res.data;
        } catch (error: unknown) {
            return thunkAPI.rejectWithValue(
                getErrorMessage(
                    error,
                    "Failed to create staff"
                )
            );
        }
    }
);


// UPDATE
export const updateCompanyStaff = createAsyncThunk<
    CompanyStaff,
    {
        id: string;
        payload: UpdateCompanyStaffPayload;
    },
    { rejectValue: string }
>(
    "companyStaff/update",
    async ({ id, payload }, thunkAPI) => {
        try {
            const res = await api.put<CompanyStaff>(
                `/company-staff/${id}`,
                payload
            );

            return res.data;
        } catch (error: unknown) {
            return thunkAPI.rejectWithValue(
                getErrorMessage(
                    error,
                    "Failed to update staff"
                )
            );
        }
    }
);


// DELETE
export const deleteCompanyStaff = createAsyncThunk<
    string,
    string,
    { rejectValue: string }
>(
    "companyStaff/delete",
    async (id, thunkAPI) => {
        try {
            await api.delete(
                `/company-staff/${id}`
            );

            return id;
        } catch (error: unknown) {
            return thunkAPI.rejectWithValue(
                getErrorMessage(
                    error,
                    "Failed to delete staff"
                )
            );
        }
    }
);