import { createAsyncThunk, createSlice, type PayloadAction } from "@reduxjs/toolkit";

import {
  getBalanceSheet,
  getProfitAndLoss,
  getTrialBalance,
  listAccountingAccounts,
  listJournalEntries,
} from "@/api/accounting";
import { expenseManagementApi } from "@/api/expenseManagement";
import { listReports } from "@/api/reports";
import type { AccountingAccount, FinancialStatement, JournalEntry, TrialBalance } from "@/types/accounting";
import type {
  BranchDailyLedger,
  BranchDailySubmission,
  BranchFundingTransfer,
  ExpenseCategory,
  FinancialIntegrityReport,
  PaymentMethodOption,
  TreasuryDashboard,
  TreasurySettings,
  TreasuryStatement,
} from "@/types/expenseManagement";
import type { GeneratedReport } from "@/types/reporting";
import { getErrorMessage } from "@/utils/apiError";

export type FinancialWorkspaceRequest = {
  businessDate: string;
  branchId?: string | null;
  statementFrom?: string;
  statementTo?: string;
  includeAccounting?: boolean;
  includeReports?: boolean;
};

type AccountingWorkspaceData = [
  AccountingAccount[],
  JournalEntry[],
  TrialBalance | null,
  FinancialStatement | null,
  FinancialStatement | null,
];

type FinancialOperationsState = {
  status: "idle" | "loading" | "succeeded" | "failed";
  refreshing: boolean;
  error: string | null;
  businessDate: string;
  selectedBranchId: string | null;
  methods: PaymentMethodOption[];
  settings: TreasurySettings | null;
  categories: ExpenseCategory[];
  dashboard: TreasuryDashboard | null;
  ledger: BranchDailyLedger | null;
  transfers: BranchFundingTransfer[];
  submissions: BranchDailySubmission[];
  submissionTotal: number;
  statement: TreasuryStatement | null;
  accounts: AccountingAccount[];
  journals: JournalEntry[];
  trialBalance: TrialBalance | null;
  profitAndLoss: FinancialStatement | null;
  balanceSheet: FinancialStatement | null;
  reports: GeneratedReport[];
  integrity: FinancialIntegrityReport | null;
};

const currentDate = () => {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
};

const initialState: FinancialOperationsState = {
  status: "idle",
  refreshing: false,
  error: null,
  businessDate: currentDate(),
  selectedBranchId: null,
  methods: [],
  settings: null,
  categories: [],
  dashboard: null,
  ledger: null,
  transfers: [],
  submissions: [],
  submissionTotal: 0,
  statement: null,
  accounts: [],
  journals: [],
  trialBalance: null,
  profitAndLoss: null,
  balanceSheet: null,
  reports: [],
  integrity: null,
};

export const loadFinancialWorkspace = createAsyncThunk(
  "financialOperations/loadWorkspace",
  async (request: FinancialWorkspaceRequest, { rejectWithValue }) => {
    try {
      const fromDate = request.statementFrom ?? `${request.businessDate.slice(0, 8)}01`;
      const toDate = request.statementTo ?? request.businessDate;
      const branchWasSpecified = Object.prototype.hasOwnProperty.call(request, "branchId");
      const requestedBranchId = branchWasSpecified ? (request.branchId ?? null) : undefined;
      const [methods, settings, categories] = await Promise.all([
        expenseManagementApi.paymentMethods(),
        expenseManagementApi.settings(),
        expenseManagementApi.categories(),
      ]);
      const selectedBranchId = requestedBranchId === undefined
        ? (settings.headquarters_branch_id ?? null)
        : requestedBranchId;
      const [dashboard, transfers, integrity, ledger] = await Promise.all([
        expenseManagementApi.dashboard(request.businessDate, selectedBranchId),
        expenseManagementApi.transfers(request.businessDate, request.businessDate),
        expenseManagementApi.integrity(request.businessDate, selectedBranchId),
        selectedBranchId
          ? expenseManagementApi.currentDay(selectedBranchId, request.businessDate)
          : Promise.resolve(null),
      ]);

      const accountingPromise: Promise<AccountingWorkspaceData> = request.includeAccounting
        ? Promise.all([
            listAccountingAccounts(),
            listJournalEntries({ fromDate, toDate, branchId: selectedBranchId, limit: 200 }),
            getTrialBalance({ fromDate, toDate, branchId: selectedBranchId }),
            getProfitAndLoss({ fromDate, toDate, branchId: selectedBranchId }),
            getBalanceSheet({ toDate, branchId: selectedBranchId }),
          ])
        : Promise.resolve([[], [], null, null, null]);

      const [accountingData, submissions, reports] = await Promise.all([
        accountingPromise,
        expenseManagementApi.submissions({ dateFrom: fromDate, dateTo: toDate, branchId: request.branchId, limit: 200 }),
        request.includeReports ? listReports() : Promise.resolve([]),
      ]);
      const [accounts, journals, trialBalance, profitAndLoss, balanceSheet] = accountingData;

      return {
        businessDate: request.businessDate,
        selectedBranchId,
        methods,
        settings,
        categories,
        dashboard,
        ledger,
        transfers,
        accounts,
        journals,
        trialBalance,
        profitAndLoss,
        balanceSheet,
        submissions: submissions.items,
        submissionTotal: submissions.total,
        reports,
        integrity,
      };
    } catch (error: unknown) {
      return rejectWithValue(getErrorMessage(error, "The accounting and expense workspace could not be loaded"));
    }
  },
);

const financialOperationsSlice = createSlice({
  name: "financialOperations",
  initialState,
  reducers: {
    setFinancialBusinessDate(state, action: PayloadAction<string>) {
      state.businessDate = action.payload;
    },
    setFinancialBranch(state, action: PayloadAction<string | null>) {
      state.selectedBranchId = action.payload;
    },
    setFinancialStatement(state, action: PayloadAction<TreasuryStatement | null>) {
      state.statement = action.payload;
    },
    upsertSubmission(state, action: PayloadAction<BranchDailySubmission>) {
      const index = state.submissions.findIndex((item) => item.id === action.payload.id);
      if (index >= 0) state.submissions[index] = action.payload;
      else state.submissions.unshift(action.payload);
    },
    upsertJournal(state, action: PayloadAction<JournalEntry>) {
      const index = state.journals.findIndex((item) => item.id === action.payload.id);
      if (index >= 0) state.journals[index] = action.payload;
      else state.journals.unshift(action.payload);
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(loadFinancialWorkspace.pending, (state) => {
        state.refreshing = state.status === "succeeded";
        state.status = state.status === "idle" ? "loading" : state.status;
        state.error = null;
      })
      .addCase(loadFinancialWorkspace.fulfilled, (state, action) => {
        state.status = "succeeded";
        state.refreshing = false;
        state.error = null;
        Object.assign(state, action.payload);
      })
      .addCase(loadFinancialWorkspace.rejected, (state, action) => {
        state.status = "failed";
        state.refreshing = false;
        state.error = String(action.payload ?? action.error.message ?? "Unknown error");
      });
  },
});

export const {
  setFinancialBusinessDate,
  setFinancialBranch,
  setFinancialStatement,
  upsertSubmission,
  upsertJournal,
} = financialOperationsSlice.actions;

export default financialOperationsSlice.reducer;
