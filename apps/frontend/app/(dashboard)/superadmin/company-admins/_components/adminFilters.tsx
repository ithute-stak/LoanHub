import { SuggestionSearch, type SearchSuggestion } from "@/components/ui/suggestion-search";
import { Dispatch, SetStateAction } from "react";

type StatusFilter = "all" | "active" | "inactive";

type Props = {
    search: string;
    setSearch: Dispatch<SetStateAction<string>>;

    companyId: string;
    setCompanyId: Dispatch<SetStateAction<string>>;

    status: StatusFilter;
    setStatus: Dispatch<SetStateAction<StatusFilter>>;
    suggestions?: readonly SearchSuggestion[];
};

export function CompanyAdminFilters({
                                        search,
                                        setSearch,
                                        companyId,
                                        setCompanyId,
                                        status,
                                        setStatus,
                                        suggestions = [],
                                    }: Props) {
    return (
        <div className="flex flex-col md:flex-row gap-3 justify-between">

            <SuggestionSearch
                value={search}
                onValueChange={setSearch}
                suggestions={suggestions}
                placeholder="Type a user, company, phone or email..."
                suggestionLabel="Company administrators"
                emptyMessage="No administrator matches that text."
                wrapperClassName="w-full md:w-96"
            />

            <div className="flex gap-2">
                {(["all", "active", "inactive"] as const).map((s) => (
                    <button
                        key={s}
                        onClick={() => setStatus(s)}
                        className={`px-4 py-2 rounded-xl text-sm font-bold border ${
                            status === s
                                ? "bg-primary text-white"
                                : "bg-background"
                        }`}
                    >
                        {s.toUpperCase()}
                    </button>
                ))}
            </div>
        </div>
    );
}