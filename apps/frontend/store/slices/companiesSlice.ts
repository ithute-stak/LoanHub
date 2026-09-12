import {
    createAsyncThunk,
    createSlice,
    PayloadAction,
} from "@reduxjs/toolkit";

import { api } from "@/lib/api";

export type CompanyStatus =
    | "pending"
    | "approved"
    | "rejected"
    | string;

export type InstitutionType =
    | "loan_company"
    | "commercial_bank"
    | "microfinance_institution"
    | "financial_cooperative"
    | "development_finance_institution"
    | "government_lending_program";

export interface LoanCompany {
    id: string;
    name: string;
    institution_type?: InstitutionType;
    registration_number: string;
    license_number: string;
    phone: string;
    email: string;
    website: string;
    address: string;
    district: string;
    status: CompanyStatus;
    is_active: boolean;
    created_at: string;
}

export interface LoanCompanyPayload {
    name: string;
    institution_type?: InstitutionType;
    registration_number: string;
    license_number: string;
    phone: string;
    email: string;
    website: string;
    address: string;
    district: string;
    status?: CompanyStatus;
    is_active?: boolean;
}

interface CompaniesState {
    companies: LoanCompany[];
    loading: boolean;
    actionLoadingId: string | null;
    error: string | null;
    selectedCompany: LoanCompany | null;
}

const initialState: CompaniesState = {
    companies: [],
    loading: false,
    actionLoadingId: null,
    error: null,
    selectedCompany: null,
};

function getErrorMessage(
    error: unknown,
    fallback: string,
): string {
    if (
        typeof error === "object" &&
        error !== null &&
        "response" in error
    ) {
        const responseError = error as {
            response?: {
                data?: {
                    detail?: string;
                };
            };
        };

        return responseError.response?.data?.detail ?? fallback;
    }

    if (error instanceof Error) {
        return error.message;
    }

    return fallback;
}

function replaceCompany(
    companies: LoanCompany[],
    updatedCompany: LoanCompany,
) {
    const index = companies.findIndex(
        (company) => company.id === updatedCompany.id,
    );

    if (index !== -1) {
        companies[index] = updatedCompany;
    }
}

export const fetchCompanies = createAsyncThunk<
    LoanCompany[],
    void,
    { rejectValue: string }
>("companies/fetchCompanies", async (_, thunkAPI) => {
    try {
        const response = await api.get<LoanCompany[]>("/companies/");
        return response.data;
    } catch (error: unknown) {
        return thunkAPI.rejectWithValue(
            getErrorMessage(error, "Failed to load companies"),
        );
    }
});

export const createCompany = createAsyncThunk<
    LoanCompany,
    LoanCompanyPayload,
    { rejectValue: string }
>("companies/createCompany", async (payload, thunkAPI) => {
    try {
        const response = await api.post<LoanCompany>(
            "/companies/",
            payload,
        );

        return response.data;
    } catch (error: unknown) {
        return thunkAPI.rejectWithValue(
            getErrorMessage(error, "Failed to create company"),
        );
    }
});

export const updateCompany = createAsyncThunk<
    LoanCompany,
    {
        id: string;
        payload: Partial<LoanCompanyPayload>;
    },
    { rejectValue: string }
>("companies/updateCompany", async ({ id, payload }, thunkAPI) => {
    try {
        const response = await api.put<LoanCompany>(
            `/companies/${id}`,
            payload,
        );

        return response.data;
    } catch (error: unknown) {
        return thunkAPI.rejectWithValue(
            getErrorMessage(error, "Failed to update company"),
        );
    }
});

export const deleteCompany = createAsyncThunk<
    string,
    string,
    { rejectValue: string }
>("companies/deleteCompany", async (id, thunkAPI) => {
    try {
        await api.delete(`/companies/${id}`);
        return id;
    } catch (error: unknown) {
        return thunkAPI.rejectWithValue(
            getErrorMessage(error, "Failed to delete company"),
        );
    }
});

export const approveCompany = createAsyncThunk<
    LoanCompany,
    string,
    { rejectValue: string }
>("companies/approveCompany", async (companyId, thunkAPI) => {
    try {
        const response = await api.patch<LoanCompany>(
            `/companies/${companyId}/approve`,
        );

        return response.data;
    } catch (error: unknown) {
        return thunkAPI.rejectWithValue(
            getErrorMessage(error, "Failed to approve company"),
        );
    }
});

export const rejectCompany = createAsyncThunk<
    LoanCompany,
    string,
    { rejectValue: string }
>("companies/rejectCompany", async (companyId, thunkAPI) => {
    try {
        const response = await api.patch<LoanCompany>(
            `/companies/${companyId}/reject`,
        );

        return response.data;
    } catch (error: unknown) {
        return thunkAPI.rejectWithValue(
            getErrorMessage(error, "Failed to reject company"),
        );
    }
});

export const activateCompany = createAsyncThunk<
    LoanCompany,
    string,
    { rejectValue: string }
>("companies/activateCompany", async (companyId, thunkAPI) => {
    try {
        const response = await api.patch<LoanCompany>(
            `/companies/${companyId}/activate`,
        );

        return response.data;
    } catch (error: unknown) {
        return thunkAPI.rejectWithValue(
            getErrorMessage(error, "Failed to activate company"),
        );
    }
});

export const deactivateCompany = createAsyncThunk<
    LoanCompany,
    string,
    { rejectValue: string }
>("companies/deactivateCompany", async (companyId, thunkAPI) => {
    try {
        const response = await api.patch<LoanCompany>(
            `/companies/${companyId}/deactivate`,
        );

        return response.data;
    } catch (error: unknown) {
        return thunkAPI.rejectWithValue(
            getErrorMessage(error, "Failed to deactivate company"),
        );
    }
});

const companiesSlice = createSlice({
    name: "companies",
    initialState,
    reducers: {
        clearCompaniesError(state) {
            state.error = null;
        },

        selectCompany(
            state,
            action: PayloadAction<LoanCompany | null>,
        ) {
            state.selectedCompany = action.payload;
        },
    },
    extraReducers: (builder) => {
        builder
            .addCase(fetchCompanies.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchCompanies.fulfilled, (state, action) => {
                state.loading = false;
                state.companies = action.payload;
            })
            .addCase(fetchCompanies.rejected, (state, action) => {
                state.loading = false;
                state.error =
                    action.payload ?? "Failed to load companies";
            })

            .addCase(createCompany.fulfilled, (state, action) => {
                state.companies.unshift(action.payload);
            })

            .addCase(updateCompany.pending, (state, action) => {
                state.error = null;
                state.actionLoadingId = action.meta.arg.id;
            })
            .addCase(updateCompany.fulfilled, (state, action) => {
                state.actionLoadingId = null;
                replaceCompany(state.companies, action.payload);
            })
            .addCase(updateCompany.rejected, (state, action) => {
                state.actionLoadingId = null;
                state.error =
                    action.payload ?? "Failed to update company";
            })

            .addCase(deleteCompany.pending, (state, action) => {
                state.error = null;
                state.actionLoadingId = action.meta.arg;
            })
            .addCase(deleteCompany.fulfilled, (state, action) => {
                state.actionLoadingId = null;
                state.companies = state.companies.filter(
                    (company) => company.id !== action.payload,
                );
            })
            .addCase(deleteCompany.rejected, (state, action) => {
                state.actionLoadingId = null;
                state.error =
                    action.payload ?? "Failed to delete company";
            })

            .addCase(approveCompany.pending, (state, action) => {
                state.error = null;
                state.actionLoadingId = action.meta.arg;
            })
            .addCase(approveCompany.fulfilled, (state, action) => {
                state.actionLoadingId = null;
                replaceCompany(state.companies, action.payload);
            })
            .addCase(approveCompany.rejected, (state, action) => {
                state.actionLoadingId = null;
                state.error =
                    action.payload ?? "Failed to approve company";
            })

            .addCase(rejectCompany.pending, (state, action) => {
                state.error = null;
                state.actionLoadingId = action.meta.arg;
            })
            .addCase(rejectCompany.fulfilled, (state, action) => {
                state.actionLoadingId = null;
                replaceCompany(state.companies, action.payload);
            })
            .addCase(rejectCompany.rejected, (state, action) => {
                state.actionLoadingId = null;
                state.error =
                    action.payload ?? "Failed to reject company";
            })

            .addCase(activateCompany.pending, (state, action) => {
                state.error = null;
                state.actionLoadingId = action.meta.arg;
            })
            .addCase(activateCompany.fulfilled, (state, action) => {
                state.actionLoadingId = null;
                replaceCompany(state.companies, action.payload);
            })
            .addCase(activateCompany.rejected, (state, action) => {
                state.actionLoadingId = null;
                state.error =
                    action.payload ?? "Failed to activate company";
            })

            .addCase(deactivateCompany.pending, (state, action) => {
                state.error = null;
                state.actionLoadingId = action.meta.arg;
            })
            .addCase(deactivateCompany.fulfilled, (state, action) => {
                state.actionLoadingId = null;
                replaceCompany(state.companies, action.payload);
            })
            .addCase(deactivateCompany.rejected, (state, action) => {
                state.actionLoadingId = null;
                state.error =
                    action.payload ?? "Failed to deactivate company";
            });
    },
});

export const {
    clearCompaniesError,
    selectCompany,
} = companiesSlice.actions;

export default companiesSlice.reducer;