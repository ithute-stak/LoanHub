import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

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
});

export const { tableViewFieldSet, tableViewScopeCleared, tableViewsCleared } =
    tableViewsSlice.actions;
export default tableViewsSlice.reducer;
