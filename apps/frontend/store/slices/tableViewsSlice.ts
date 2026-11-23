import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import { logout, logoutUser } from "./authSlice";

// View preferences only. Never store payment credentials, financial edits or
// unsubmitted form values in this slice.
type TableViewsState = { byScope: Record<string, Record<string, unknown>> };
const initialState: TableViewsState = { byScope: {} };

const tableViewsSlice = createSlice({
    name: "tableViews",
    initialState,
    reducers: {
        tableViewFieldSet(
            state,
            action: PayloadAction<{ scope: string; field: string; value: unknown }>,
        ) {
            const { scope, field, value } = action.payload;
            if (!state.byScope[scope]) state.byScope[scope] = {};
            state.byScope[scope][field] = value;
        },
        tableViewScopeCleared(state, action: PayloadAction<string>) {
            delete state.byScope[action.payload];
        },
        tableViewsCleared(state) {
            state.byScope = {};
        },
    },
    extraReducers: (builder) => {
        // Wipe all table preferences when the user logs out. The scope key
        // prevents cross-tenant reuse while authenticated, but not keeping
        // another user's filters in memory is an additional safety barrier.
        builder.addCase(logout, (state) => { state.byScope = {}; });
        builder.addCase(logoutUser.fulfilled, (state) => { state.byScope = {}; });
    },
});

export const { tableViewFieldSet, tableViewScopeCleared, tableViewsCleared } =
    tableViewsSlice.actions;
export default tableViewsSlice.reducer;
