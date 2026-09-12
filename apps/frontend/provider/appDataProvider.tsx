"use client";

import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useRef,
    useState,
    type ReactNode,
} from "react";

import {
    cancelSubscription as cancelSubscriptionRequest,
    checkoutSubscription as checkoutSubscriptionRequest,
    createSubscriptionPlan as createSubscriptionPlanRequest,
    deleteSubscriptionPlan as deleteSubscriptionPlanRequest,
    getCurrentSubscription,
    listAdminSubscriptionPlans,
    listSubscriptionPlans,
    listSubscriptions,
    updateSubscriptionPlan as updateSubscriptionPlanRequest,
} from "@/api/billing";
import {
    acceptLoanOffer as acceptLoanOfferRequest,
    createLoanRequest as createLoanRequestRequest,
    listAllLoanRequests,
    listMyLoanRequests,
} from "@/api/loanRequests";
import {
    createLoanOffer as createLoanOfferRequest,
    listOffersByRequest,
} from "@/api/loanOffers";
import { listLoans } from "@/api/loans";
import {
    getMarketplaceRequest,
    listMarketplaceRequests,
    unlockMarketplaceRequest as unlockMarketplaceRequestApi,
} from "@/api/marketplace";
import { listPayments } from "@/api/payments";
import {
    createLoanProduct as createLoanProductRequest,
    deleteLoanProduct as deleteLoanProductRequest,
    listLoanProducts,
    listPublicLoanProducts,
    setLoanProductActive as setLoanProductActiveRequest,
    updateLoanProduct as updateLoanProductRequest,
} from "@/api/loanProducts";
import { api } from "@/lib/api";
import { useTenant } from "@/provider/tenantProvider";
import { fetchBranchesThunk } from "@/store/features/thunks/branchThunks";
import { fetchCompanyStaff } from "@/store/features/thunks/companyUserThunk";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { cacheScopeInvalidated } from "@/store/features/slices/httpCacheSlice";
import {
    fetchCompanies,
    type LoanCompany,
} from "@/store/slices/companiesSlice";
import type {
    CompanySubscription,
    SubscriptionCheckoutPayload,
    SubscriptionCheckoutResponse,
    SubscriptionPlan,
    SubscriptionPlanCreatePayload,
    SubscriptionPlanUpdatePayload,
} from "@/types/billing";
import type { Borrower } from "@/types/borrower";
import type { Branch } from "@/types/branch";
import type { CompanyStaff } from "@/types/companyStuff";
import {
    hasRole,
    isCompanyRole,
    isPlatformRole,
    PLATFORM_FINANCE_ROLES,
    LENDING_ROLES,
    type AuthUser,
} from "@/types/auth";
import type { Loan } from "@/types/loan";
import type { LoanOffer, LoanOfferCreatePayload } from "@/types/loan_offer";
import type {
    LoanProduct,
    LoanProductCreatePayload,
    LoanProductUpdatePayload,
} from "@/types/loanProduct";
import { LoanRequestStatus, type LoanRequest, type LoanRequestCreatePayload } from "@/types/loanRequest";
import type {
    MarketplaceRequestCard,
    MarketplaceRequestDetail,
    MarketplaceUnlock,
    UnlockMarketplacePayload,
} from "@/types/marketplace";
import type { PaymentTransaction } from "@/types/payment";
import { getErrorMessage } from "@/utils/apiError";

type AppDataErrors = {
    companies: string | null;
    companyStaff: string | null;
    branches: string | null;
    borrowers: string | null;
    loanRequests: string | null;
    loanOffers: string | null;
    marketplace: string | null;
    loans: string | null;
    payments: string | null;
    billing: string | null;
    loanProducts: string | null;
};

type LoadingState = {
    borrowers: boolean;
    loanRequests: boolean;
    loanOffers: boolean;
    marketplace: boolean;
    loans: boolean;
    payments: boolean;
    billing: boolean;
    loanProducts: boolean;
};

type AppDataContextType = {
    user: AuthUser | null;
    currentStaffAssignment: CompanyStaff | null;
    currentCompany: LoanCompany | null;
    currentBranch: Branch | null;
    currentBorrower: Borrower | null;

    companies: LoanCompany[];
    companyStaff: CompanyStaff[];
    branches: Branch[];
    borrowers: Borrower[];
    loanRequests: LoanRequest[];
    openLoanRequests: LoanRequest[];
    myLoanRequests: LoanRequest[];
    loanOffers: LoanOffer[];
    marketplaceRequests: MarketplaceRequestCard[];
    selectedMarketplaceRequest: MarketplaceRequestDetail | null;
    loans: Loan[];
    payments: PaymentTransaction[];
    subscriptionPlans: SubscriptionPlan[];
    subscriptions: CompanySubscription[];
    currentSubscription: CompanySubscription | null;
    loanProducts: LoanProduct[];

    companiesCount: number;
    approvedCompaniesCount: number;
    pendingCompaniesCount: number;
    activeCompaniesCount: number;
    companyStaffCount: number;
    activeStaffCount: number;
    branchesCount: number;
    activeBranchesCount: number;
    borrowersCount: number;
    loanRequestsCount: number;
    openLoanRequestsCount: number;
    approvedLoanRequestsCount: number;
    rejectedLoanRequestsCount: number;
    requestedAmountTotal: number;
    loanOffersCount: number;
    acceptedLoanOffersCount: number;
    activeLoansCount: number;
    overdueLoansCount: number;
    outstandingBalanceTotal: number;
    successfulPaymentsTotal: number;
    loanProductsCount: number;
    activeLoanProductsCount: number;

    isLoading: boolean;
    isCompaniesLoading: boolean;
    isCompanyStaffLoading: boolean;
    isBranchesLoading: boolean;
    isBorrowersLoading: boolean;
    isLoanRequestsLoading: boolean;
    isLoanOffersLoading: boolean;
    isMarketplaceLoading: boolean;
    isLoansLoading: boolean;
    isPaymentsLoading: boolean;
    isBillingLoading: boolean;
    isLoanProductsLoading: boolean;
    errors: AppDataErrors;
    hasError: boolean;

    getCompanyById: (companyId: string | null | undefined) => LoanCompany | null;
    getCompanyName: (companyId: string | null | undefined) => string;
    getBranchById: (branchId: string | null | undefined) => Branch | null;
    getBorrowerById: (borrowerId: string | null | undefined) => Borrower | null;

    refreshAllData: () => Promise<void>;
    refreshBilling: () => Promise<void>;
    createSubscriptionPlan: (
        payload: SubscriptionPlanCreatePayload,
    ) => Promise<SubscriptionPlan>;
    updateSubscriptionPlan: (
        planId: string,
        payload: SubscriptionPlanUpdatePayload,
    ) => Promise<SubscriptionPlan>;
    deleteSubscriptionPlan: (planId: string) => Promise<void>;
    loadOffersForRequest: (loanRequestId: string) => Promise<LoanOffer[]>;
    clearLoadedOffers: () => void;
    loadMarketplaceRequest: (requestId: string) => Promise<MarketplaceRequestDetail>;
    unlockMarketplaceRequest: (
        requestId: string,
        payload: UnlockMarketplacePayload,
    ) => Promise<MarketplaceUnlock>;
    submitLoanOffer: (payload: LoanOfferCreatePayload) => Promise<LoanOffer>;
    createLoanRequest: (payload: LoanRequestCreatePayload) => Promise<LoanRequest>;
    acceptLoanOffer: (requestId: string, offerId: string) => Promise<Loan>;
    checkoutSubscription: (
        payload: SubscriptionCheckoutPayload,
    ) => Promise<SubscriptionCheckoutResponse>;
    cancelSubscription: (subscriptionId: string) => Promise<CompanySubscription>;
    createLoanProduct: (payload: LoanProductCreatePayload) => Promise<LoanProduct>;
    updateLoanProduct: (productId: string, payload: LoanProductUpdatePayload) => Promise<LoanProduct>;
    setLoanProductActive: (productId: string, active: boolean) => Promise<LoanProduct>;
    deleteLoanProduct: (productId: string) => Promise<void>;
};

const EMPTY_ERRORS: AppDataErrors = {
    companies: null,
    companyStaff: null,
    branches: null,
    borrowers: null,
    loanRequests: null,
    loanOffers: null,
    marketplace: null,
    loans: null,
    payments: null,
    billing: null,
    loanProducts: null,
};

const INITIAL_LOADING: LoadingState = {
    borrowers: false,
    loanRequests: false,
    loanOffers: false,
    marketplace: false,
    loans: false,
    payments: false,
    billing: false,
    loanProducts: false,
};

const AppDataContext = createContext<AppDataContextType | null>(null);

function statusEquals(value: unknown, expected: string): boolean {
    return String(value ?? "").toLowerCase() === expected.toLowerCase();
}

function sumNumbers(values: Array<number | string | null | undefined>): number {
    return values.reduce<number>((sum, value) => sum + Number(value ?? 0), 0);
}

export function AppDataProvider({ children }: { children: ReactNode }) {
    const dispatch = useAppDispatch();
    const { activeCompanyId, activeMembership } = useTenant();
    const user = useAppSelector((state) => state.auth.user);
    const authInitialized = useAppSelector((state) => state.auth.initialized);

    const {
        companies,
        loading: companiesLoading,
        error: companiesError,
    } = useAppSelector((state) => state.companies);
    const {
        staff: companyStaff,
        loading: companyStaffLoading,
        error: companyStaffError,
    } = useAppSelector((state) => state.companyStaff);
    const {
        branches,
        loading: branchesLoading,
        error: branchesError,
    } = useAppSelector((state) => state.branches);

    const [borrowers, setBorrowers] = useState<Borrower[]>([]);
    const [loanRequests, setLoanRequests] = useState<LoanRequest[]>([]);
    const [loanOffers, setLoanOffers] = useState<LoanOffer[]>([]);
    const [marketplaceRequests, setMarketplaceRequests] = useState<MarketplaceRequestCard[]>([]);
    const [selectedMarketplaceRequest, setSelectedMarketplaceRequest] =
        useState<MarketplaceRequestDetail | null>(null);
    const [loans, setLoans] = useState<Loan[]>([]);
    const [payments, setPayments] = useState<PaymentTransaction[]>([]);
    const [subscriptionPlans, setSubscriptionPlans] = useState<SubscriptionPlan[]>([]);
    const [subscriptions, setSubscriptions] = useState<CompanySubscription[]>([]);
    const [currentSubscription, setCurrentSubscription] =
        useState<CompanySubscription | null>(null);
    const [loanProducts, setLoanProducts] = useState<LoanProduct[]>([]);
    const [localLoading, setLocalLoading] = useState<LoadingState>(INITIAL_LOADING);
    const [localErrors, setLocalErrors] = useState<AppDataErrors>(EMPTY_ERRORS);
    const loadedScopeRef = useRef<string | null>(null);

    const setResourceLoading = useCallback((key: keyof LoadingState, value: boolean) => {
        setLocalLoading((current) => ({ ...current, [key]: value }));
    }, []);

    const setResourceError = useCallback((key: keyof AppDataErrors, value: string | null) => {
        setLocalErrors((current) => ({ ...current, [key]: value }));
    }, []);

    const loadBorrowers = useCallback(async () => {
        if (!user || isCompanyRole(user.role) || (isPlatformRole(user.role) && user.role !== "superadmin")) {
            setBorrowers([]);
            return;
        }
        setResourceLoading("borrowers", true);
        setResourceError("borrowers", null);
        try {
            if (user.role === "superadmin") {
                const response = await api.get<Borrower[]>("/borrowers/");
                setBorrowers(response.data);
            } else {
                const response = await api.get<Borrower>("/borrowers/me");
                setBorrowers([{ ...response.data, person: user.person }]);
            }
        } catch (error: unknown) {
            setBorrowers([]);
            setResourceError("borrowers", getErrorMessage(error, "Failed to load borrowers"));
        } finally {
            setResourceLoading("borrowers", false);
        }
    }, [setResourceError, setResourceLoading, user]);

    const loadLoanRequests = useCallback(async () => {
        if (!user || isCompanyRole(user.role) || (isPlatformRole(user.role) && user.role !== "superadmin")) {
            setLoanRequests([]);
            return;
        }
        setResourceLoading("loanRequests", true);
        setResourceError("loanRequests", null);
        try {
            const data =
                user.role === "superadmin"
                    ? await listAllLoanRequests()
                    : await listMyLoanRequests();
            setLoanRequests(data);
        } catch (error: unknown) {
            setLoanRequests([]);
            setResourceError(
                "loanRequests",
                getErrorMessage(error, "Failed to load loan requests"),
            );
        } finally {
            setResourceLoading("loanRequests", false);
        }
    }, [setResourceError, setResourceLoading, user]);

    const loadMarketplace = useCallback(async () => {
        const activeRole = activeMembership?.role ?? user?.role;
        const canViewMarketplace =
            user?.role === "superadmin" ||
            Boolean(activeRole && hasRole(activeRole, LENDING_ROLES));

        if (!canViewMarketplace) {
            setMarketplaceRequests([]);
            return;
        }
        setResourceLoading("marketplace", true);
        setResourceError("marketplace", null);
        try {
            setMarketplaceRequests(await listMarketplaceRequests());
        } catch (error: unknown) {
            setMarketplaceRequests([]);
            setResourceError(
                "marketplace",
                getErrorMessage(error, "Failed to load the loan marketplace"),
            );
        } finally {
            setResourceLoading("marketplace", false);
        }
    }, [activeMembership?.role, setResourceError, setResourceLoading, user?.role]);

    const loadLoansData = useCallback(async () => {
        if (!user || (isPlatformRole(user.role) && user.role !== "superadmin")) {
            setLoans([]);
            return;
        }
        setResourceLoading("loans", true);
        setResourceError("loans", null);
        try {
            setLoans(await listLoans());
        } catch (error: unknown) {
            setLoans([]);
            setResourceError("loans", getErrorMessage(error, "Failed to load loans"));
        } finally {
            setResourceLoading("loans", false);
        }
    }, [setResourceError, setResourceLoading, user]);

    const loadPaymentsData = useCallback(async () => {
        if (!user || (isPlatformRole(user.role) && !PLATFORM_FINANCE_ROLES.includes(user.role))) {
            setPayments([]);
            return;
        }
        setResourceLoading("payments", true);
        setResourceError("payments", null);
        try {
            setPayments(await listPayments());
        } catch (error: unknown) {
            setPayments([]);
            setResourceError("payments", getErrorMessage(error, "Failed to load payments"));
        } finally {
            setResourceLoading("payments", false);
        }
    }, [setResourceError, setResourceLoading, user]);

    const loadLoanProducts = useCallback(async () => {
        if (!user || (isPlatformRole(user.role) && user.role !== "superadmin")) {
            setLoanProducts([]);
            return;
        }

        setResourceLoading("loanProducts", true);
        setResourceError("loanProducts", null);
        try {
            const products =
                user.role === "borrower"
                    ? await listPublicLoanProducts()
                    : await listLoanProducts();
            setLoanProducts(products);
        } catch (error: unknown) {
            setLoanProducts([]);
            setResourceError(
                "loanProducts",
                getErrorMessage(error, "Failed to load loan products"),
            );
        } finally {
            setResourceLoading("loanProducts", false);
        }
    }, [setResourceError, setResourceLoading, user]);

    const loadBilling = useCallback(async () => {
        if (user && isPlatformRole(user.role) && user.role !== "superadmin") {
            setSubscriptionPlans([]);
            setSubscriptions([]);
            setCurrentSubscription(null);
            return;
        }
        setResourceLoading("billing", true);
        setResourceError("billing", null);
        try {
            const plans = user?.role === "superadmin"
                ? await listAdminSubscriptionPlans()
                : await listSubscriptionPlans();
            setSubscriptionPlans(plans);
            if (!user) {
                setSubscriptions([]);
                setCurrentSubscription(null);
            } else if (user.role === "superadmin") {
                setSubscriptions(await listSubscriptions());
                setCurrentSubscription(null);
            } else if (isCompanyRole(user.role)) {
                const subscription = await getCurrentSubscription();
                setCurrentSubscription(subscription);
                setSubscriptions(subscription ? [subscription] : []);
            } else {
                setSubscriptions([]);
                setCurrentSubscription(null);
            }
        } catch (error: unknown) {
            setResourceError("billing", getErrorMessage(error, "Failed to load billing data"));
        } finally {
            setResourceLoading("billing", false);
        }
    }, [setResourceError, setResourceLoading, user]);

    const loadAllData = useCallback(async () => {
        if (!authInitialized || !user) {
            return;
        }
        if (isCompanyRole(user.role) && !activeCompanyId) {
            return;
        }

        setLocalErrors(EMPTY_ERRORS);
        const tasks: Promise<unknown>[] = [loadBilling()];
        if (user.role === "superadmin" || isCompanyRole(user.role) || user.role === "borrower") {
            tasks.push(dispatch(fetchCompanies()).unwrap());
        }

        if (user.role === "superadmin" || isCompanyRole(user.role)) {
            tasks.push(dispatch(fetchCompanyStaff()).unwrap());
            tasks.push(dispatch(fetchBranchesThunk()).unwrap());
        }

        tasks.push(loadBorrowers());
        tasks.push(loadLoanRequests());
        tasks.push(loadMarketplace());
        tasks.push(loadLoansData());
        tasks.push(loadPaymentsData());
        tasks.push(loadLoanProducts());

        const results = await Promise.allSettled(tasks);
        const reduxFailures = results.filter((result) => result.status === "rejected");
        if (reduxFailures.length > 0) {
            // Slice errors already contain the actionable server message.
        }
    }, [
        activeCompanyId,
        authInitialized,
        dispatch,
        loadBilling,
        loadBorrowers,
        loadLoanRequests,
        loadLoansData,
        loadMarketplace,
        loadPaymentsData,
        loadLoanProducts,
        user,
    ]);

    const refreshAllData = useCallback(async () => {
        if (user) {
            dispatch(
                cacheScopeInvalidated({
                    scope: `${user.id}:${activeCompanyId ?? "platform"}:${activeMembership?.role ?? user.role}`,
                }),
            );
        }
        await loadAllData();
    }, [
        activeCompanyId,
        activeMembership?.role,
        dispatch,
        loadAllData,
        user,
    ]);

    useEffect(() => {
        if (!authInitialized || !user) {
            loadedScopeRef.current = null;
            return;
        }
        if (isCompanyRole(user.role) && !activeCompanyId) {
            return;
        }
        const scope = `${user.id}:${activeCompanyId ?? "platform"}:${activeMembership?.role ?? user.role}`;
        if (loadedScopeRef.current === scope) {
            return;
        }
        loadedScopeRef.current = scope;
        const timer = window.setTimeout(() => {
            setLoanOffers([]);
            setSelectedMarketplaceRequest(null);
            void loadAllData();
        }, 0);
        return () => window.clearTimeout(timer);
    }, [activeCompanyId, activeMembership?.role, authInitialized, loadAllData, user]);

    const companyMap = useMemo(
        () => new Map(companies.map((company) => [company.id, company])),
        [companies],
    );
    const branchMap = useMemo(
        () => new Map(branches.map((branch) => [branch.id, branch])),
        [branches],
    );
    const borrowerMap = useMemo(
        () => new Map(borrowers.map((borrower) => [borrower.id, borrower])),
        [borrowers],
    );

    const currentCompany = activeCompanyId
        ? companyMap.get(activeCompanyId) ?? null
        : null;
    const currentStaffAssignment = activeMembership
        ? companyStaff.find((staff) => staff.id === activeMembership.id) ?? null
        : null;
    const currentBranch = activeMembership?.branch_id
        ? branchMap.get(activeMembership.branch_id) ?? null
        : null;
    const currentBorrower = user?.role === "borrower" ? borrowers[0] ?? null : null;

    const loadOffersForRequest = useCallback(
        async (requestId: string) => {
            setResourceLoading("loanOffers", true);
            setResourceError("loanOffers", null);
            try {
                const offers = await listOffersByRequest(requestId);
                setLoanOffers(offers);
                return offers;
            } catch (error: unknown) {
                setResourceError("loanOffers", getErrorMessage(error, "Failed to load offers"));
                throw error;
            } finally {
                setResourceLoading("loanOffers", false);
            }
        },
        [setResourceError, setResourceLoading],
    );

    const loadMarketplaceRequest = useCallback(
        async (requestId: string) => {
            setResourceLoading("marketplace", true);
            setResourceError("marketplace", null);
            try {
                const detail = await getMarketplaceRequest(requestId);
                setSelectedMarketplaceRequest(detail);
                return detail;
            } catch (error: unknown) {
                setResourceError(
                    "marketplace",
                    getErrorMessage(error, "Failed to load marketplace request"),
                );
                throw error;
            } finally {
                setResourceLoading("marketplace", false);
            }
        },
        [setResourceError, setResourceLoading],
    );

    const unlockMarketplaceRequest = useCallback(
        async (requestId: string, payload: UnlockMarketplacePayload) => {
            const unlock = await unlockMarketplaceRequestApi(requestId, payload);
            await Promise.all([loadMarketplace(), loadMarketplaceRequest(requestId), loadPaymentsData()]);
            return unlock;
        },
        [loadMarketplace, loadMarketplaceRequest, loadPaymentsData],
    );

    const submitLoanOffer = useCallback(
        async (payload: LoanOfferCreatePayload) => {
            const offer = await createLoanOfferRequest(payload);
            setLoanOffers((current) => [offer, ...current.filter((item) => item.id !== offer.id)]);
            await loadMarketplace();
            return offer;
        },
        [loadMarketplace],
    );

    const createLoanRequest = useCallback(
        async (payload: LoanRequestCreatePayload) => {
            const request = await createLoanRequestRequest(payload);
            setLoanRequests((current) => [request, ...current]);
            return request;
        },
        [],
    );

    const acceptLoanOffer = useCallback(
        async (requestId: string, offerId: string) => {
            const loan = await acceptLoanOfferRequest(requestId, offerId);
            setLoans((current) => [loan, ...current.filter((item) => item.id !== loan.id)]);
            await Promise.all([loadLoanRequests(), loadOffersForRequest(requestId)]);
            return loan;
        },
        [loadLoanRequests, loadOffersForRequest],
    );

    const checkoutSubscription = useCallback(
        async (
            payload: SubscriptionCheckoutPayload,
        ): Promise<SubscriptionCheckoutResponse> => {
            const result = await checkoutSubscriptionRequest(payload);

            setCurrentSubscription(result.subscription);
            setSubscriptions((current) => [
                result.subscription,
                ...current.filter(
                    (item) => item.id !== result.subscription.id,
                ),
            ]);

            if (result.payment) {
                setPayments((current) => [
                    result.payment!,
                    ...current.filter(
                        (payment) => payment.id !== result.payment!.id,
                    ),
                ]);
            }

            return result;
        },
        [],
    );

    const cancelSubscription = useCallback(async (subscriptionId: string) => {
        const subscription = await cancelSubscriptionRequest(subscriptionId);
        setCurrentSubscription((current) =>
            current?.id === subscription.id ? subscription : current,
        );
        setSubscriptions((current) =>
            current.map((item) => (item.id === subscription.id ? subscription : item)),
        );
        return subscription;
    }, []);

    const createSubscriptionPlan = useCallback(
        async (payload: SubscriptionPlanCreatePayload) => {
            const plan = await createSubscriptionPlanRequest(payload);
            setSubscriptionPlans((current) => [
                plan,
                ...current.filter((item) => item.id !== plan.id),
            ]);
            return plan;
        },
        [],
    );

    const updateSubscriptionPlan = useCallback(
        async (planId: string, payload: SubscriptionPlanUpdatePayload) => {
            const plan = await updateSubscriptionPlanRequest(planId, payload);
            setSubscriptionPlans((current) =>
                current.map((item) => (item.id === plan.id ? plan : item)),
            );
            setSubscriptions((current) =>
                current.map((subscription) =>
                    subscription.plan_id === plan.id
                        ? { ...subscription, plan, plan_name: plan.name }
                        : subscription,
                ),
            );
            return plan;
        },
        [],
    );

    const deleteSubscriptionPlan = useCallback(async (planId: string) => {
        await deleteSubscriptionPlanRequest(planId);
        setSubscriptionPlans((current) => current.filter((item) => item.id !== planId));
    }, []);

    const createLoanProduct = useCallback(
        async (payload: LoanProductCreatePayload) => {
            const product = await createLoanProductRequest(payload);
            setLoanProducts((current) => [
                product,
                ...current.filter((item) => item.id !== product.id),
            ]);
            return product;
        },
        [],
    );

    const updateLoanProduct = useCallback(
        async (productId: string, payload: LoanProductUpdatePayload) => {
            const product = await updateLoanProductRequest(productId, payload);
            setLoanProducts((current) =>
                current.map((item) => (item.id === product.id ? product : item)),
            );
            return product;
        },
        [],
    );

    const setLoanProductActive = useCallback(
        async (productId: string, active: boolean) => {
            const product = await setLoanProductActiveRequest(productId, active);
            setLoanProducts((current) =>
                current.map((item) => (item.id === product.id ? product : item)),
            );
            return product;
        },
        [],
    );

    const deleteLoanProduct = useCallback(async (productId: string) => {
        await deleteLoanProductRequest(productId);
        setLoanProducts((current) => current.filter((item) => item.id !== productId));
    }, []);

    const errors = useMemo<AppDataErrors>(
        () => ({
            ...localErrors,
            companies: companiesError ?? localErrors.companies,
            companyStaff: companyStaffError ?? localErrors.companyStaff,
            branches: branchesError ?? localErrors.branches,
        }),
        [branchesError, companiesError, companyStaffError, localErrors],
    );

    const openLoanRequests = useMemo(
        () =>
            loanRequests.filter(
                (request) =>
                    (request.status === LoanRequestStatus.OPEN ||
                        request.status === LoanRequestStatus.OFFERED) &&
                    request.visible_to_lenders,
            ),
        [loanRequests],
    );

    const value = useMemo<AppDataContextType>(() => {
        const approvedCompaniesCount = companies.filter((company) =>
            statusEquals(company.status, "approved"),
        ).length;
        const pendingCompaniesCount = companies.filter((company) =>
            statusEquals(company.status, "pending"),
        ).length;
        const activeLoans = loans.filter((loan) => loan.status === "active");
        const successfulPayments = payments.filter((payment) => payment.status === "succeeded");
        const isLoading =
            companiesLoading ||
            companyStaffLoading ||
            branchesLoading ||
            Object.values(localLoading).some(Boolean);

        return {
            user,
            currentStaffAssignment,
            currentCompany,
            currentBranch,
            currentBorrower,
            companies,
            companyStaff,
            branches,
            borrowers,
            loanRequests,
            openLoanRequests,
            myLoanRequests: user?.role === "borrower" ? loanRequests : [],
            loanOffers,
            marketplaceRequests,
            selectedMarketplaceRequest,
            loans,
            payments,
            subscriptionPlans,
            subscriptions,
            currentSubscription,
            loanProducts,

            companiesCount: companies.length,
            approvedCompaniesCount,
            pendingCompaniesCount,
            activeCompaniesCount: companies.filter((company) => company.is_active).length,
            companyStaffCount: companyStaff.length,
            activeStaffCount: companyStaff.filter((staff) => staff.is_active).length,
            branchesCount: branches.length,
            activeBranchesCount: branches.filter((branch) => branch.is_active).length,
            borrowersCount: borrowers.length,
            loanRequestsCount: loanRequests.length,
            openLoanRequestsCount: openLoanRequests.length,
            approvedLoanRequestsCount: loanRequests.filter((request) => request.status === LoanRequestStatus.ACCEPTED).length,
            rejectedLoanRequestsCount: loanRequests.filter((request) => request.status === LoanRequestStatus.CANCELLED || request.status === LoanRequestStatus.EXPIRED).length,
            requestedAmountTotal: sumNumbers(loanRequests.map((request) => request.requested_amount)),
            loanOffersCount: loanOffers.length,
            acceptedLoanOffersCount: loanOffers.filter((offer) => offer.status === "accepted").length,
            activeLoansCount: activeLoans.length,
            overdueLoansCount: loans.filter((loan) => loan.is_overdue).length,
            outstandingBalanceTotal: sumNumbers(loans.map((loan) => loan.balance)),
            successfulPaymentsTotal: sumNumbers(successfulPayments.map((payment) => payment.amount)),
            loanProductsCount: loanProducts.length,
            activeLoanProductsCount: loanProducts.filter((product) => product.is_active).length,

            isLoading,
            isCompaniesLoading: companiesLoading,
            isCompanyStaffLoading: companyStaffLoading,
            isBranchesLoading: branchesLoading,
            isBorrowersLoading: localLoading.borrowers,
            isLoanRequestsLoading: localLoading.loanRequests,
            isLoanOffersLoading: localLoading.loanOffers,
            isMarketplaceLoading: localLoading.marketplace,
            isLoansLoading: localLoading.loans,
            isPaymentsLoading: localLoading.payments,
            isBillingLoading: localLoading.billing,
            isLoanProductsLoading: localLoading.loanProducts,
            errors,
            hasError: Object.values(errors).some(Boolean),

            getCompanyById: (companyId) =>
                companyId ? companyMap.get(companyId) ?? null : null,
            getCompanyName: (companyId) =>
                companyId ? companyMap.get(companyId)?.name ?? "Unknown company" : "No company",
            getBranchById: (branchId) =>
                branchId ? branchMap.get(branchId) ?? null : null,
            getBorrowerById: (borrowerId) =>
                borrowerId ? borrowerMap.get(borrowerId) ?? null : null,

            refreshAllData,
            refreshBilling: loadBilling,
            createSubscriptionPlan,
            updateSubscriptionPlan,
            deleteSubscriptionPlan,
            loadOffersForRequest,
            clearLoadedOffers: () => setLoanOffers([]),
            loadMarketplaceRequest,
            unlockMarketplaceRequest,
            submitLoanOffer,
            createLoanRequest,
            acceptLoanOffer,
            checkoutSubscription,
            cancelSubscription,
            createLoanProduct,
            updateLoanProduct,
            setLoanProductActive,
            deleteLoanProduct,
        };
    }, [
        acceptLoanOffer,
        branchMap,
        branches,
        branchesLoading,
        borrowers,
        borrowerMap,
        cancelSubscription,
        checkoutSubscription,
        createLoanProduct,
        createSubscriptionPlan,
        deleteLoanProduct,
        deleteSubscriptionPlan,
        companies,
        companiesLoading,
        companyMap,
        companyStaff,
        companyStaffLoading,
        createLoanRequest,
        currentBorrower,
        currentBranch,
        currentCompany,
        currentStaffAssignment,
        currentSubscription,
        errors,
        loadBilling,
        loadMarketplaceRequest,
        loadOffersForRequest,
        loanOffers,
        loanProducts,
        loanRequests,
        loans,
        localLoading,
        marketplaceRequests,
        openLoanRequests,
        payments,
        refreshAllData,
        selectedMarketplaceRequest,
        submitLoanOffer,
        setLoanProductActive,
        subscriptionPlans,
        subscriptions,
        unlockMarketplaceRequest,
        updateLoanProduct,
        updateSubscriptionPlan,
        user,
    ]);

    return <AppDataContext.Provider value={value}>{children}</AppDataContext.Provider>;
}

export function useAppData(): AppDataContextType {
    const context = useContext(AppDataContext);
    if (!context) {
        throw new Error("useAppData must be used inside AppDataProvider");
    }
    return context;
}
