import {
    configureStore,
} from "@reduxjs/toolkit";

import authReducer from "./slices/authSlice";
import companiesReducer from "./slices/companiesSlice";

import companyStaffReducer from "./features/slices/companyUsersSlice";
import branchReducer from "./features/slices/branchSlice";
import borrowersReducer from "./features/slices/borrowerSlice";
import loanRequestReducer from "./features/slices/loanRequestSlice";
import loanOffersReducer from "./features/slices/loanOfferSlice";
import financialOperationsReducer from "./features/slices/financialOperationsSlice";
import httpCacheReducer from "./features/slices/httpCacheSlice";

export const store = configureStore({
    reducer: {
        auth: authReducer,
        companies: companiesReducer,
        companyStaff:
        companyStaffReducer,

        branches: branchReducer,
        borrowers: borrowersReducer,

        loanRequests:
        loanRequestReducer,

        loanOffers:
        loanOffersReducer,

        financialOperations: financialOperationsReducer,
        httpCache: httpCacheReducer,
    },
});

export type RootState =
    ReturnType<typeof store.getState>;

export type AppDispatch =
    typeof store.dispatch;