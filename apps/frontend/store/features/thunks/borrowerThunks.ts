import { createAsyncThunk } from "@reduxjs/toolkit";
import { api } from "@/lib/api";

import {
    Borrower,
    CreateBorrowerPayload,
    BorrowerCreateResponse,
    UpdateBorrowerPayload
} from "@/types/borrower";

import { getErrorMessage } from "@/utils/apiError";
import {UpdatePersonPayload} from "@/types/person";
type UpdateBorrowerProfilePayload = {
    borrowerId: string;
    personId: string;
    borrower: UpdateBorrowerPayload;
    person: UpdatePersonPayload;
};

export const updateBorrowerProfile = createAsyncThunk<
    Borrower,
    UpdateBorrowerProfilePayload,
    { rejectValue: string }
>(
    "borrowers/updateProfile",
    async (
        {
            borrowerId,
            personId,
            borrower,
            person,
        },
        thunkAPI,
    ) => {
        try {
            await Promise.all([
                api.put(
                    `/people/${personId}`,
                    person,
                ),
                api.put(
                    `/borrowers/${borrowerId}`,
                    borrower,
                ),
            ]);

            const response =
                await api.get<Borrower>(
                    `/borrowers/${borrowerId}`,
                );

            return response.data;
        } catch (error: unknown) {
            return thunkAPI.rejectWithValue(
                getErrorMessage(
                    error,
                    "Failed to update borrower profile",
                ),
            );
        }
    },
);


// GET ALL
export const fetchBorrowers = createAsyncThunk<
    Borrower[],
    void,
    { rejectValue: string }
>(
    "borrowers/fetchAll",
    async (_, thunkAPI) => {
        try {
            const res =
                await api.get<Borrower[]>(
                    "/borrowers/"
                );

            return res.data;

        } catch (error: unknown) {

            return thunkAPI.rejectWithValue(
                getErrorMessage(
                    error,
                    "Failed to fetch borrowers"
                )
            );
        }
    }
);


// GET ONE
export const fetchBorrowerById =
    createAsyncThunk<
        Borrower,
        string,
        { rejectValue: string }
    >(
        "borrowers/fetchById",
        async (id, thunkAPI) => {

            try {

                const res =
                    await api.get<Borrower>(
                        `/borrowers/${id}`
                    );

                return res.data;

            } catch (error: unknown) {

                return thunkAPI.rejectWithValue(
                    getErrorMessage(
                        error,
                        "Failed to fetch borrower"
                    )
                );
            }
        }
    );


// CREATE
export const createBorrower =
    createAsyncThunk<
        BorrowerCreateResponse,
        CreateBorrowerPayload,
        { rejectValue: string }
    >(
        "borrowers/create",
        async (payload, thunkAPI) => {

            try {

                const res =
                    await api.post<BorrowerCreateResponse>(
                        "/borrower-registration/",
                        payload
                    );

                return res.data;

            } catch (error: unknown) {

                return thunkAPI.rejectWithValue(
                    getErrorMessage(
                        error,
                        "Failed to create borrower"
                    )
                );
            }
        }
    );


// UPDATE
export const updateBorrower =
    createAsyncThunk<
        Borrower,
        {
            id:string;
            payload:UpdateBorrowerPayload;
        },
        { rejectValue:string }
    >(
        "borrowers/update",
        async (
            {id,payload},
            thunkAPI
        ) => {

            try {

                const res =
                    await api.put<Borrower>(
                        `/borrowers/${id}`,
                        payload
                    );

                return res.data;

            } catch(error:unknown){

                return thunkAPI.rejectWithValue(
                    getErrorMessage(
                        error,
                        "Failed to update borrower"
                    )
                );
            }
        }
    );


// DELETE
export const deleteBorrower =
    createAsyncThunk<
        string,
        string,
        { rejectValue:string }
    >(
        "borrowers/delete",
        async(id,thunkAPI)=>{

            try{

                await api.delete(
                    `/borrowers/${id}`
                );

                return id;

            }catch(error:unknown){

                return thunkAPI.rejectWithValue(
                    getErrorMessage(
                        error,
                        "Failed to delete borrower"
                    )
                );
            }
        }
    );