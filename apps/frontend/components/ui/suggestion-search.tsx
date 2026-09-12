"use client";

import * as React from "react";
import { Search, X } from "lucide-react";

import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverAnchor,
  PopoverContent,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export type SearchSuggestion =
  | string
  | {
      value: string;
      label?: string;
      description?: string;
      keywords?: readonly string[];
    };

type SuggestionSearchProps = Omit<
  React.ComponentProps<typeof Input>,
  "value" | "defaultValue" | "onChange"
> & {
  value: string;
  onValueChange: (value: string) => void;
  suggestions?: readonly SearchSuggestion[];
  emptyMessage?: string;
  suggestionLabel?: string;
  maxSuggestions?: number;
  minimumCharacters?: number;
  showSuggestionsOnFocus?: boolean;
  clearable?: boolean;
  wrapperClassName?: string;
  onSuggestionSelect?: (suggestion: {
    value: string;
    label: string;
    description?: string;
  }) => void;
};

type NormalizedSuggestion = {
  value: string;
  label: string;
  description?: string;
  searchText: string;
};

export function normalizeSearchText(value: string): string {
  return value.trim().toLocaleLowerCase();
}

function compactSearchText(value: string): string {
  return normalizeSearchText(value).replace(/[^a-z0-9]+/g, "");
}

/**
 * Lower scores are better. This intentionally supports partial fragments such as
 * `si-90` matching `Koetlisi-9088`, while still ranking exact and prefix matches first.
 */
export function fuzzySearchScore(query: string, candidate: string): number {
  const normalizedQuery = normalizeSearchText(query);
  const normalizedCandidate = normalizeSearchText(candidate);

  if (!normalizedQuery) return 0;
  if (!normalizedCandidate) return Number.POSITIVE_INFINITY;
  if (normalizedCandidate === normalizedQuery) return 0;
  if (normalizedCandidate.startsWith(normalizedQuery)) return 1;
  if (normalizedCandidate.includes(normalizedQuery)) return 2;

  const compactQuery = compactSearchText(normalizedQuery);
  const compactCandidate = compactSearchText(normalizedCandidate);
  if (!compactQuery) return Number.POSITIVE_INFINITY;
  if (compactCandidate.startsWith(compactQuery)) return 3;
  if (compactCandidate.includes(compactQuery)) return 4;

  const tokens = normalizedQuery.split(/\s+/).filter(Boolean);
  if (tokens.length > 1 && tokens.every((token) => normalizedCandidate.includes(token))) {
    return 5;
  }

  // Last-resort ordered-character matching for slightly incomplete typing.
  let cursor = 0;
  for (const character of compactCandidate) {
    if (character === compactQuery[cursor]) cursor += 1;
    if (cursor === compactQuery.length) return 6;
  }

  return Number.POSITIVE_INFINITY;
}

export function fuzzySearchMatches(query: string, candidate: string): boolean {
  return Number.isFinite(fuzzySearchScore(query, candidate));
}

function normalizeSuggestion(
  suggestion: SearchSuggestion,
): NormalizedSuggestion | null {
  if (typeof suggestion === "string") {
    const value = suggestion.trim();
    if (!value) return null;
    return {
      value,
      label: value,
      searchText: normalizeSearchText(value),
    };
  }

  const value = suggestion.value.trim();
  const label = (suggestion.label ?? suggestion.value).trim();
  if (!value || !label) return null;

  return {
    value,
    label,
    description: suggestion.description?.trim() || undefined,
    searchText: normalizeSearchText(
      [
        value,
        label,
        suggestion.description,
        ...(suggestion.keywords ?? []),
      ]
        .filter(Boolean)
        .join(" "),
    ),
  };
}

export function SuggestionSearch({
  value,
  onValueChange,
  suggestions = [],
  emptyMessage = "No matching suggestions.",
  suggestionLabel = "Suggestions",
  maxSuggestions = 8,
  minimumCharacters = 0,
  showSuggestionsOnFocus = true,
  clearable = true,
  wrapperClassName,
  className,
  disabled,
  onFocus,
  onKeyDown,
  onSuggestionSelect,
  ...inputProps
}: SuggestionSearchProps) {
  const anchorRef = React.useRef<HTMLDivElement>(null);
  const [open, setOpen] = React.useState(false);
  const [activeIndex, setActiveIndex] = React.useState(0);
  const [contentWidth, setContentWidth] = React.useState<number | undefined>();

  const normalizedSuggestions = React.useMemo(() => {
    const unique = new Map<string, NormalizedSuggestion>();

    suggestions.forEach((suggestion) => {
      const normalized = normalizeSuggestion(suggestion);
      if (!normalized) return;
      const key = normalizeSearchText(
        [normalized.value, normalized.label, normalized.description]
          .filter(Boolean)
          .join(" "),
      );
      if (!unique.has(key)) unique.set(key, normalized);
    });

    return Array.from(unique.values());
  }, [suggestions]);

  const visibleSuggestions = React.useMemo(() => {
    const query = normalizeSearchText(value);
    if (query.length < minimumCharacters) {
      return showSuggestionsOnFocus
        ? normalizedSuggestions.slice(0, maxSuggestions)
        : [];
    }

    return normalizedSuggestions
      .map((suggestion, index) => ({
        suggestion,
        index,
        score: fuzzySearchScore(query, suggestion.searchText),
      }))
      .filter((item) => Number.isFinite(item.score))
      .sort((left, right) => left.score - right.score || left.index - right.index)
      .slice(0, maxSuggestions)
      .map((item) => item.suggestion);
  }, [
    maxSuggestions,
    minimumCharacters,
    normalizedSuggestions,
    showSuggestionsOnFocus,
    value,
  ]);

  React.useEffect(() => {
    setActiveIndex(0);
  }, [value, visibleSuggestions.length]);

  React.useEffect(() => {
    const anchor = anchorRef.current;
    if (!anchor) return;

    const updateWidth = () => setContentWidth(anchor.getBoundingClientRect().width);
    updateWidth();

    const observer = new ResizeObserver(updateWidth);
    observer.observe(anchor);
    return () => observer.disconnect();
  }, []);

  function selectSuggestion(suggestion: NormalizedSuggestion) {
    onValueChange(suggestion.value);
    onSuggestionSelect?.({
      value: suggestion.value,
      label: suggestion.label,
      description: suggestion.description,
    });
    setOpen(false);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    onKeyDown?.(event);
    if (event.defaultPrevented) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!open) {
        setOpen(true);
        setActiveIndex(0);
      } else {
        setActiveIndex((current) =>
          visibleSuggestions.length === 0
            ? 0
            : (current + 1) % visibleSuggestions.length,
        );
      }
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) {
        setOpen(true);
        setActiveIndex(Math.max(visibleSuggestions.length - 1, 0));
      } else {
        setActiveIndex((current) =>
          visibleSuggestions.length === 0
            ? 0
            : (current - 1 + visibleSuggestions.length) %
              visibleSuggestions.length,
        );
      }
      return;
    }

    if (event.key === "Enter" && open && visibleSuggestions[activeIndex]) {
      event.preventDefault();
      selectSuggestion(visibleSuggestions[activeIndex]);
      return;
    }

    if (event.key === "Escape") setOpen(false);
  }

  const shouldOpen =
    !disabled &&
    open &&
    (visibleSuggestions.length > 0 ||
      normalizeSearchText(value).length >= minimumCharacters);

  return (
    <Popover open={shouldOpen} onOpenChange={setOpen}>
      <PopoverAnchor asChild>
        <div
          ref={anchorRef}
          className={cn("relative w-full", wrapperClassName)}
        >
          <Search className="pointer-events-none absolute left-3 top-1/2 z-10 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            {...inputProps}
            type={inputProps.type ?? "search"}
            value={value}
            disabled={disabled}
            role="combobox"
            aria-autocomplete="list"
            aria-expanded={shouldOpen}
            autoComplete="off"
            onFocus={(event) => {
              onFocus?.(event);
              if (showSuggestionsOnFocus || value.trim()) setOpen(true);
            }}
            onChange={(event) => {
              onValueChange(event.target.value);
              setOpen(true);
            }}
            onKeyDown={handleKeyDown}
            className={cn(
              "h-11 rounded-xl border bg-background pl-10",
              clearable && value ? "pr-10" : "pr-3",
              className,
            )}
          />
          {clearable && value && !disabled ? (
            <button
              type="button"
              aria-label="Clear search"
              className="absolute right-2 top-1/2 z-10 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => {
                onValueChange("");
                setOpen(true);
              }}
            >
              <X className="h-4 w-4" />
            </button>
          ) : null}
        </div>
      </PopoverAnchor>

      <PopoverContent
        align="start"
        sideOffset={6}
        onOpenAutoFocus={(event) => event.preventDefault()}
        className="max-w-[calc(100vw-2rem)] p-1"
        style={{ width: contentWidth }}
      >
        <Command shouldFilter={false}>
          <CommandList>
            <CommandEmpty>{emptyMessage}</CommandEmpty>
            <CommandGroup heading={suggestionLabel}>
              {visibleSuggestions.map((suggestion, index) => (
                <CommandItem
                  key={`${suggestion.value}-${index}`}
                  value={suggestion.value}
                  data-selected={index === activeIndex ? "true" : undefined}
                  className={cn(
                    "items-start py-2.5",
                    index === activeIndex && "bg-muted text-foreground",
                  )}
                  onMouseDown={(event) => event.preventDefault()}
                  onMouseMove={() => setActiveIndex(index)}
                  onSelect={() => selectSuggestion(suggestion)}
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-semibold">
                      {suggestion.label}
                    </span>
                    {suggestion.description ? (
                      <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                        {suggestion.description}
                      </span>
                    ) : null}
                  </span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
