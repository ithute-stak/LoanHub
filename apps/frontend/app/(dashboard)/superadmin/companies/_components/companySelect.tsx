"use client";

import * as React from "react";
import { Check, ChevronsUpDown } from "lucide-react";

import { cn } from "@/lib/utils";
import { useAppSelector } from "@/store/hooks";

import { Button } from "@/components/ui/button";
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover";

import {
    Command,
    CommandEmpty,
    CommandGroup,
    CommandInput,
    CommandItem,
    CommandList,
} from "@/components/ui/command";
import {LoanCompany} from "@/store/slices/companiesSlice";


type Props = {
    value: string;
    onChange: (companyId: string) => void;
};

export function CompanySelect({ value, onChange }: Props) {
    const { companies } = useAppSelector((s) => s.companies);

    const [open, setOpen] = React.useState(false);
    const [search, setSearch] = React.useState("");

    const selectedCompany = companies.find((c) => c.id === value);

    // ✅ safer filter
    const filtered = React.useMemo(() => {
        if (!search.trim()) return companies;

        const q = search.toLowerCase();

        return companies.filter((c) =>
            `${c.name} ${c.registration_number} ${c.license_number} ${c.district}`
                .toLowerCase()
                .includes(q)
        );
    }, [companies, search]);

    // ✅ UNIQUE LABEL (important fix)
    const formatLabel = (c: LoanCompany) =>
        `${c.name} (${c.registration_number}) - ${c.district}`;

    return (
        <div className="space-y-2">
            <label className="text-xs font-bold text-muted-foreground">
                Select Company
            </label>

            <Popover open={open} onOpenChange={setOpen}>
                <PopoverTrigger asChild>
                    <Button
                        variant="outline"
                        role="combobox"
                        className="w-full justify-between rounded-xl border-border bg-background font-semibold"
                    >
                        {selectedCompany
                            ? formatLabel(selectedCompany)
                            : "Select company..."}

                        <ChevronsUpDown className="ml-2 h-4 w-4 opacity-50" />
                    </Button>
                </PopoverTrigger>

                <PopoverContent className="w-full p-0">
                    <Command shouldFilter={false}>
                        {/* SEARCH INPUT */}
                        <CommandInput
                            placeholder="Search by name, reg no, district..."
                            value={search}
                            onValueChange={setSearch}
                        />

                        <CommandList>
                            {filtered.length === 0 ? (
                                <CommandEmpty>
                                    No companies found
                                </CommandEmpty>
                            ) : (
                                <CommandGroup>
                                    {filtered.map((company) => (
                                        <CommandItem
                                            key={company.id}
                                            value={company.id} // ✅ FIXED (use id, not name)
                                            onSelect={() => {
                                                onChange(company.id);
                                                setOpen(false);
                                                setSearch("");
                                            }}
                                        >
                                            <Check
                                                className={cn(
                                                    "mr-2 h-4 w-4",
                                                    value === company.id
                                                        ? "opacity-100"
                                                        : "opacity-0"
                                                )}
                                            />

                                            {formatLabel(company)}
                                        </CommandItem>
                                    ))}
                                </CommandGroup>
                            )}
                        </CommandList>
                    </Command>
                </PopoverContent>
            </Popover>
        </div>
    );
}