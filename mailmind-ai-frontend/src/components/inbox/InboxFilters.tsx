import { Search, X } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EMAIL_CATEGORY_OPTIONS } from "@/lib/emailCategories";
import { cn } from "@/lib/utils";
import { useInboxStore, type InboxViewFilter } from "@/stores/inboxStore";

const VIEW_FILTERS: { value: InboxViewFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "unread", label: "Unread" },
  { value: "read", label: "Read" },
  { value: "important", label: "Important" },
];

export function InboxFilters() {
  const { viewFilter, category, search, setViewFilter, setCategory, setSearch } = useInboxStore();
  const [searchInput, setSearchInput] = useState(search);

  useEffect(() => {
    setSearchInput(search);
  }, [search]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (searchInput !== search) {
        setSearch(searchInput);
      }
    }, 300);

    return () => window.clearTimeout(timer);
  }, [searchInput, search, setSearch]);

  const hasActiveFilters =
    viewFilter !== "all" || category !== "all" || search.trim().length > 0;

  function clearFilters() {
    setSearchInput("");
    setSearch("");
    setViewFilter("all");
    setCategory("all");
  }

  return (
    <div className="space-y-4">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-brand-muted" />
        <Input
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
          placeholder="Search subject, sender, or preview…"
          className="pl-9 pr-9"
        />
        {searchInput ? (
          <button
            type="button"
            onClick={() => {
              setSearchInput("");
              setSearch("");
            }}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-brand-muted hover:text-brand-text"
            aria-label="Clear search"
          >
            <X className="h-4 w-4" />
          </button>
        ) : null}
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-2">
          {VIEW_FILTERS.map((filter) => (
            <Button
              key={filter.value}
              type="button"
              size="sm"
              variant={viewFilter === filter.value ? "default" : "outline"}
              onClick={() => setViewFilter(filter.value)}
              className={cn(
                "rounded-full",
                viewFilter !== filter.value && "bg-white hover:bg-accent",
              )}
            >
              {filter.label}
            </Button>
          ))}
        </div>

        <select
          value={category}
          onChange={(event) => setCategory(event.target.value as typeof category)}
          className="h-9 rounded-xl border border-input bg-white px-3 text-sm text-brand-text shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label="Filter by category"
        >
          {EMAIL_CATEGORY_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {hasActiveFilters ? (
        <div className="flex items-center justify-between text-sm text-brand-muted">
          <span>Filters applied</span>
          <Button type="button" variant="ghost" size="sm" onClick={clearFilters}>
            Clear all
          </Button>
        </div>
      ) : null}
    </div>
  );
}
