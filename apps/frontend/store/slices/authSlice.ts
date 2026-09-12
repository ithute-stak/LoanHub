import {
    createAsyncThunk,
    createSlice,
    type PayloadAction,
} from "@reduxjs/toolkit";

import { api } from "@/lib/api";
import {
    StorageKeys,
    clearAuthStorage,
    getStoredJson,
    getStoredValue,
    setStoredJson,
    setStoredValue,
} from "@/lib/storage";
import type {
    AuthUser,
    LoginRequest,
    LoginResponse,
    RefreshResponse,
    UserRole,
} from "@/types/auth";
import { getErrorMessage } from "@/utils/apiError";

export type { AuthUser, LoginRequest, LoginResponse, UserRole };

type AuthState = {
    user: AuthUser | null;
    accessToken: string | null;
    isAuthenticated: boolean;
    initialized: boolean;
    loading: boolean;
    error: string | null;
};

const initialState: AuthState = {
    user: null,
    accessToken: null,
    isAuthenticated: false,
    initialized: false,
    loading: false,
    error: null,
};

function persistSession(accessToken: string, user: AuthUser): void {
    setStoredValue(StorageKeys.accessToken, accessToken);
    setStoredJson(StorageKeys.authUser, user);
}

export const loginUser = createAsyncThunk<
    LoginResponse,
    LoginRequest,
    { rejectValue: string }
>("auth/login", async (payload, thunkApi) => {
    try {
        const response = await api.post<LoginResponse>("/auth/login", payload);
        persistSession(response.data.access_token, response.data.user);
        return response.data;
    } catch (error: unknown) {
        return thunkApi.rejectWithValue(getErrorMessage(error, "Login failed"));
    }
});

export const fetchCurrentUser = createAsyncThunk<
    AuthUser,
    void,
    { rejectValue: string }
>("auth/fetchCurrentUser", async (_, thunkApi) => {
    try {
        const response = await api.get<AuthUser>("/auth/me");
        setStoredJson(StorageKeys.authUser, response.data);
        return response.data;
    } catch (error: unknown) {
        return thunkApi.rejectWithValue(
            getErrorMessage(error, "Could not load the current account"),
        );
    }
});

export const bootstrapAuth = createAsyncThunk<
    { accessToken: string; user: AuthUser } | null,
    void,
    { rejectValue: string }
>("auth/bootstrap", async (_, thunkApi) => {
    const storedToken = getStoredValue(StorageKeys.accessToken);
    const storedUser = getStoredJson<AuthUser>(StorageKeys.authUser);

    try {
        const accessToken: string = storedToken ?? (
            await api.post<RefreshResponse>("/auth/refresh")
        ).data.access_token;

        if (!storedToken) {
            setStoredValue(StorageKeys.accessToken, accessToken);
        }

        const meResponse = await api.get<AuthUser>("/auth/me");
        persistSession(accessToken, meResponse.data);
        return { accessToken, user: meResponse.data };
    } catch (error: unknown) {
        clearAuthStorage();
        if (!storedToken && !storedUser) {
            return null;
        }
        return thunkApi.rejectWithValue(
            getErrorMessage(error, "Your session has expired"),
        );
    }
});

export const logoutUser = createAsyncThunk<void, void>(
    "auth/logout",
    async () => {
        try {
            await api.post("/auth/logout");
        } finally {
            clearAuthStorage();
        }
    },
);

const authSlice = createSlice({
    name: "auth",
    initialState,
    reducers: {
        restoreAuth(state) {
            const token = getStoredValue(StorageKeys.accessToken);
            const user = getStoredJson<AuthUser>(StorageKeys.authUser);
            state.accessToken = token;
            state.user = user;
            state.isAuthenticated = Boolean(token && user);
        },
        logout(state) {
            clearAuthStorage();
            state.user = null;
            state.accessToken = null;
            state.isAuthenticated = false;
            state.initialized = true;
            state.loading = false;
            state.error = null;
        },
        clearAuthError(state) {
            state.error = null;
        },
        replaceAuthSession(
            state,
            action: PayloadAction<{ accessToken: string; user: AuthUser }>,
        ) {
            state.accessToken = action.payload.accessToken;
            state.user = action.payload.user;
            state.isAuthenticated = true;
            state.initialized = true;
            state.loading = false;
            state.error = null;
            persistSession(action.payload.accessToken, action.payload.user);
        },
        replaceAuthUser(state, action: PayloadAction<AuthUser>) {
            state.user = action.payload;
            state.isAuthenticated = Boolean(state.accessToken);
            setStoredJson(StorageKeys.authUser, action.payload);
        },
    },
    extraReducers: (builder) => {
        builder
            .addCase(loginUser.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(loginUser.fulfilled, (state, action) => {
                state.loading = false;
                state.initialized = true;
                state.accessToken = action.payload.access_token;
                state.user = action.payload.user;
                state.isAuthenticated = true;
            })
            .addCase(loginUser.rejected, (state, action) => {
                state.loading = false;
                state.initialized = true;
                state.error = action.payload ?? "Login failed";
            })
            .addCase(bootstrapAuth.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(bootstrapAuth.fulfilled, (state, action) => {
                state.loading = false;
                state.initialized = true;
                if (!action.payload) {
                    state.user = null;
                    state.accessToken = null;
                    state.isAuthenticated = false;
                    return;
                }
                state.accessToken = action.payload.accessToken;
                state.user = action.payload.user;
                state.isAuthenticated = true;
            })
            .addCase(bootstrapAuth.rejected, (state, action) => {
                state.loading = false;
                state.initialized = true;
                state.user = null;
                state.accessToken = null;
                state.isAuthenticated = false;
                state.error = action.payload ?? null;
            })
            .addCase(fetchCurrentUser.fulfilled, (state, action) => {
                state.user = action.payload;
                state.isAuthenticated = Boolean(state.accessToken);
            })
            .addCase(logoutUser.fulfilled, (state) => {
                state.user = null;
                state.accessToken = null;
                state.isAuthenticated = false;
                state.initialized = true;
                state.loading = false;
                state.error = null;
            });
    },
});

export const {
    restoreAuth,
    logout,
    clearAuthError,
    replaceAuthUser,
    replaceAuthSession,
} = authSlice.actions;

export default authSlice.reducer;
