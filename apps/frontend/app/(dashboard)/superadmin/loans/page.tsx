"use client";


import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { SuggestionSearch } from "@/components/ui/suggestion-search";
import { StickyFilterBar } from "@/components/ui/sticky-filter-bar";
import { useEffect, useCallback, useState, useMemo } from "react";
import { useDispatch, useSelector } from "react-redux";
import { useRouter } from "next/navigation";
import { AppDispatch, RootState } from "@/store";
import { fetchAllRequests } from "@/store/features/thunks/loanRequestThunks";
import AnalyticsOverview from "@/app/(dashboard)/superadmin/loans/_components/overview";
import CreateRequestForm from "@/app/(dashboard)/superadmin/loans/_components/create_loan_request";
import { toast } from "@/utils/toast";
import {
    Search,
    Filter,
    ArrowUpDown,
    RefreshCw,
    Eye,
    Trash2,
    SlidersHorizontal
} from "lucide-react";

export default function LoanRequestsDashboard() {
    const dispatch = useDispatch<AppDispatch>();
    const router = useRouter();

    // Redux Selectors
    const requests = useSelector((state: RootState) => state.loanRequests.allRequests);
    const loading = useSelector((state: RootState) => state.loanRequests.loading);
    const error = useSelector((state: RootState) => state.loanRequests.error);

    // Filter & Sorting State Variables
    const [searchTerm, setSearchTerm] = useState("");
    const [statusFilter, setStatusFilter] = useState("ALL");
    const [minAmount, setMinAmount] = useState("");
    const [maxAmount, setMaxAmount] = useState("");
    const [sortField, setSortField] = useState<"created_at" | "requested_amount">("created_at");
    const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");

    const syncDataGrid = useCallback(async () => {
        try {
            await dispatch(fetchAllRequests()).unwrap();
        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : String(err);
            toast.error(errorMessage || "Failed fetching state registry logs.");
        }
    }, [dispatch]);

    useEffect(() => {
        const timer = window.setTimeout(() => syncDataGrid(), 0);
        return () => window.clearTimeout(timer);
    }, [syncDataGrid]);

    useEffect(() => {
        if (error) {
            toast.error(error);
        }
    }, [error]);

    // Handle Header Column Toggles for sorting
    const handleSort = (field: "created_at" | "requested_amount") => {
        if (sortField === field) {
            setSortDirection(sortDirection === "asc" ? "desc" : "asc");
        } else {
            setSortField(field);
            setSortDirection("desc");
        }
    };

    // Filter, Search, and Sort Computing Pipeline
    const filteredAndSortedRequests = useMemo(() => {
        let results = [...requests];

        // 1. Text Search Filter (Matches against UUID or purpose string)
        if (searchTerm.trim() !== "") {
            const term = searchTerm.toLowerCase();
            results = results.filter(
                (item) =>
                    item.id.toLowerCase().includes(term) ||
                    (item.loan_purpose && item.loan_purpose.toLowerCase().includes(term))
            );
        }

        // 2. Status Match Enum Filter
        if (statusFilter !== "ALL") {
            results = results.filter(
                (item) => item.status?.toLowerCase() === statusFilter.toLowerCase()
            );
        }

        // 3. Numeric Ranges Filter
        if (minAmount !== "") {
            results = results.filter((item) => Number(item.requested_amount) >= Number(minAmount));
        }
        if (maxAmount !== "") {
            results = results.filter((item) => Number(item.requested_amount) <= Number(maxAmount));
        }

        // 4. Sorting Evaluation
        results.sort((a, b) => {
            const valA = sortField === "requested_amount" ? Number(a[sortField]) : new Date(a[sortField]).getTime();
            const valB = sortField === "requested_amount" ? Number(b[sortField]) : new Date(b[sortField]).getTime();

            if (valA < valB) return sortDirection === "asc" ? -1 : 1;
            if (valA > valB) return sortDirection === "asc" ? 1 : -1;
            return 0;
        });

        return results;
    }, [requests, searchTerm, statusFilter, minAmount, maxAmount, sortField, sortDirection]);

    // Helper method to resolve dynamic Tailwind color styling blocks for modern Status tags
    const getStatusStyles = (status: string) => {
        const normalization = status?.toLowerCase();
        switch (normalization) {
            case "submitted":
            case "open":
                return "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20";
            case "under_review":
                return "bg-amber-500/10 text-amber-500 border border-amber-500/20";
            case "draft":
                return "bg-slate-500/10 text-slate-400 border border-slate-500/20";
            case "accepted":
            case "offered":
                return "bg-cyan-500/10 text-cyan-500 border border-cyan-500/20";
            default:
                return "bg-muted text-muted-foreground border border-border";
        }
    };

    return (
        <main className="min-h-screen bg-background text-foreground p-6 md:p-10">
            <div className="mx-auto space-y-8">

                {/* HEADER SECTION */}
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                        <h1 className="text-3xl font-black tracking-tight md:text-4xl">Portfolio Analytics Dashboard</h1>
                        <p className="text-sm text-muted-foreground mt-1">
                            Real-time management dashboard tracking financial requests across Lesotho marketplace.
                        </p>
                    </div>
                    <button
                        onClick={syncDataGrid}
                        disabled={loading}
                        className="flex items-center gap-2 self-start sm:self-center px-4 py-2 text-xs font-bold uppercase tracking-wider border border-border bg-card rounded-xl hover:bg-muted/50 transition cursor-pointer disabled:opacity-50"
                    >
                        <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
                        Sync Registry
                    </button>
                </div>

                {/* ANALYTICS HIGHLIGHTS */}
                <AnalyticsOverview data={requests} />

                {/* WORKSPACE CONTENT GRID */}
                <div className="grid gap-8 lg:grid-cols-3">

                    {/* CONTROL APPLICATION SUBMISSION PANEL */}
                    <div className="lg:col-span-1">
                        <CreateRequestForm onSuccess={syncDataGrid} />
                    </div>

                    {/* ASSET INVENTORY INTERACTIVE REGISTRY DATATABLE */}
                    <div className="lg:col-span-2 rounded-[1.75rem] border border-border bg-card p-6 shadow-sm flex flex-col justify-between">
                        <div>
                            <div className="flex flex-col gap-4 mb-6 sm:flex-row sm:items-center sm:justify-between">
                                <h2 className="text-xl font-black tracking-tight text-card-foreground">Active Market Placement Portfolio</h2>
                                <span className="text-xs font-bold bg-muted px-2.5 py-1 rounded-md text-muted-foreground">
                                    Found: {filteredAndSortedRequests.length} rows
                                </span>
                            </div>

                            {/* DYNAMIC FILTER TOOLBAR CONTROL BAR */}
                            <StickyFilterBar
                                ariaLabel="Platform loan request search and filters"
                                className="mb-6 rounded-2xl data-[floating=true]:border"
                            >
                            <div className="space-y-4 rounded-[inherit] border border-border/60 bg-card/95 p-3 backdrop-blur">
                                <div className="grid gap-3 sm:grid-cols-3">
                                    {/* Search Input */}
                                    <SuggestionSearch
                                        value={searchTerm}
                                        onValueChange={setSearchTerm}
                                        suggestions={requests.map((request) => ({
                                            value: request.loan_purpose?.trim() || request.id,
                                            label: request.loan_purpose?.trim() || `Request ${request.id.slice(0, 8)}`,
                                            description: `${String(request.status).replaceAll("_", " ")} · ${Number(request.requested_amount).toLocaleString()}`,
                                            keywords: [request.id, request.borrower_id, request.status, request.origination_channel],
                                        }))}
                                        placeholder="Type a request ID, purpose, borrower or status..."
                                        suggestionLabel="Loan requests"
                                        emptyMessage="No loan request matches that text."
                                        wrapperClassName="sm:col-span-2"
                                    />
                                    {/* Status Filter */}
                                    <div className="relative">
                                        <Filter className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <NativeSelect
                                            value={statusFilter}
                                            onChange={(e) => setStatusFilter(e.target.value)}
                                            className="w-full pl-9 pr-4 py-2 text-sm bg-background border border-border rounded-xl focus:outline-none appearance-none cursor-pointer"
                                        >
                                            <option value="ALL">All Statuses</option>
                                            <option value="DRAFT">Draft</option>
                                            <option value="SUBMITTED">Submitted</option>
                                            <option value="UNDER_REVIEW">Under Review</option>
                                            <option value="OFFERED">Offered</option>
                                            <option value="accepted">Accepted</option>
                                            <option value="cancelled">Cancelled</option>
                                        </NativeSelect>
                                    </div>
                                </div>

                                {/* Advanced Min/Max Range Filters Toggle Row */}
                                <div className="flex flex-wrap items-center gap-3 p-3 border border-border/60 bg-muted/20 rounded-xl text-xs">
                                    <div className="flex items-center gap-2">
                                        <SlidersHorizontal className="h-3.5 w-3.5 text-muted-foreground" />
                                        <span className="font-bold text-muted-foreground uppercase tracking-wider">Amount Range:</span>
                                    </div>
                                    <Input
                                        type="number"
                                        placeholder="Min (M)"
                                        value={minAmount}
                                        onChange={(e) => setMinAmount(e.target.value)}
                                        className="w-24 px-2 py-1 bg-background border border-border rounded-md focus:outline-none"
                                    />
                                    <span className="text-muted-foreground">to</span>
                                    <Input
                                        type="number"
                                        placeholder="Max (M)"
                                        value={maxAmount}
                                        onChange={(e) => setMaxAmount(e.target.value)}
                                        className="w-24 px-2 py-1 bg-background border border-border rounded-md focus:outline-none"
                                    />
                                    {(minAmount || maxAmount || statusFilter !== "ALL" || searchTerm) && (
                                        <button
                                            onClick={() => {
                                                setSearchTerm("");
                                                setStatusFilter("ALL");
                                                setMinAmount("");
                                                setMaxAmount("");
                                            }}
                                            className="ml-auto text-primary font-bold hover:underline cursor-pointer"
                                        >
                                            Clear Filters
                                        </button>
                                    )}
                                </div>
                            </div>
                            </StickyFilterBar>

                            {/* CORE DATATABLE GRID STRUCTURE */}
                            <div className="overflow-x-auto">
                                <table className="w-full text-left text-sm border-collapse">
                                    <thead>
                                    <tr className="border-b border-border bg-muted/30">
                                        <th className="p-4 text-xs font-bold uppercase tracking-wider text-muted-foreground">#</th>
                                        <th
                                            onClick={() => handleSort("requested_amount")}
                                            className="p-4 text-xs font-bold uppercase tracking-wider text-muted-foreground cursor-pointer hover:bg-muted/50 transition group select-none"
                                        >
                                            <div className="flex items-center gap-1">
                                                Requested Amount
                                                <ArrowUpDown className="h-3 w-3 text-muted-foreground group-hover:text-foreground transition" />
                                            </div>
                                        </th>
                                        <th className="p-4 text-xs font-bold uppercase tracking-wider text-muted-foreground">Term</th>
                                        <th className="p-4 text-xs font-bold uppercase tracking-wider text-muted-foreground">Status</th>
                                        <th
                                            onClick={() => handleSort("created_at")}
                                            className="p-4 text-xs font-bold uppercase tracking-wider text-muted-foreground cursor-pointer hover:bg-muted/50 transition group select-none"
                                        >
                                            <div className="flex items-center gap-1">
                                                Placement Date
                                                <ArrowUpDown className="h-3 w-3 text-muted-foreground group-hover:text-foreground transition" />
                                            </div>
                                        </th>
                                        <th className="p-4 text-xs font-bold uppercase tracking-wider text-muted-foreground text-right">Actions</th>
                                    </tr>
                                    </thead>
                                    <tbody>
                                    {loading && filteredAndSortedRequests.length === 0 ? (
                                        <tr>
                                            <td colSpan={6} className="p-8 text-center text-muted-foreground">Syncing live server parameters...</td>
                                        </tr>
                                    ) : filteredAndSortedRequests.length === 0 ? (
                                        <tr>
                                            <td colSpan={6} className="p-8 text-center text-muted-foreground">No matching asset records found matching active filter configurations.</td>
                                        </tr>
                                    ) : (
                                        filteredAndSortedRequests.map((item, index) => (
                                            <tr key={item.id} className="border-b border-border transition-colors hover:bg-muted/20">
                                                {/* DISPLAY INDEX RATHER THAN UUID STRING */}
                                                <td className="p-4 font-mono text-xs font-bold text-muted-foreground">
                                                    {index + 1}
                                                </td>
                                                <td className="p-4 font-bold text-foreground">
                                                    M{Number(item.requested_amount).toFixed(2)}
                                                </td>
                                                <td className="p-4 text-sm font-medium">
                                                    {item.preferred_term_months ? `${item.preferred_term_months} Mos` : "N/A"}
                                                </td>
                                                <td className="p-4">
                                                        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] uppercase font-bold tracking-wider ${getStatusStyles(item.status)}`}>
                                                            {item.status || "Unknown"}
                                                        </span>
                                                </td>
                                                <td className="p-4 text-xs font-semibold text-muted-foreground">
                                                    {new Date(item.created_at).toLocaleDateString("en-US", { year: 'numeric', month: 'short', day: 'numeric' })}
                                                </td>
                                                {/* ROW ACTION HOOKS BUTTONS GROUP */}
                                                <td className="p-4 text-right">
                                                    <div className="flex items-center justify-end gap-2">
                                                        <button
                                                            onClick={() => router.push(`/superadmin/loans/${item.id}`)}
                                                            className="p-1.5 border border-border bg-background rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition cursor-pointer"
                                                            title="View Details"
                                                        >
                                                            <Eye className="h-3.5 w-3.5" />
                                                        </button>
                                                        <button
                                                            onClick={() => toast.warning("Delete pipelines must be triggered via secure authorization roles.")}
                                                            className="p-1.5 border border-border bg-background rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition cursor-pointer"
                                                            title="Delete Request"
                                                        >
                                                            <Trash2 className="h-3.5 w-3.5" />
                                                        </button>
                                                    </div>
                                                </td>
                                            </tr>
                                        ))
                                    )}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>

                </div>
            </div>
        </main>
    );
}