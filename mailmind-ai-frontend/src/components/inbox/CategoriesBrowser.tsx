import { Tags } from "lucide-react";

import { EmailList } from "@/components/inbox/EmailList";
import { EmptyState } from "@/components/common/EmptyState";
import { Skeleton } from "@/components/ui/skeleton";
import { useDashboard } from "@/hooks/useDashboard";
import { CATEGORY_BADGE_STYLES, EMAIL_CATEGORY_OPTIONS } from "@/lib/emailCategories";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { EmailCategoryFilter } from "@/stores/inboxStore";
import type { EmailListResponse } from "@/types/email";

const CATEGORY_TILE_COLORS: Record<string, string> = {
  important: "from-emerald-100 to-green-50 border-emerald-200",
  work: "from-teal-100 to-emerald-50 border-teal-200",
  personal: "from-violet-100 to-purple-50 border-violet-200",
  finance: "from-cyan-100 to-teal-50 border-cyan-200",
  promotions: "from-slate-100 to-gray-50 border-slate-200",
  social: "from-indigo-100 to-violet-50 border-indigo-200",
  updates: "from-amber-100 to-yellow-50 border-amber-200",
};

interface CategoriesBrowserProps {
  data: EmailListResponse | undefined;
  isLoading: boolean;
  isFetching: boolean;
  isError: boolean;
  onRetry: () => void;
  onSync?: () => void;
  isSyncing?: boolean;
  page: number;
  onPageChange: (page: number) => void;
  selectedCategory: EmailCategoryFilter;
  onSelectCategory: (category: EmailCategoryFilter) => void;
}

export function CategoriesBrowser({
  data,
  isLoading,
  isFetching,
  isError,
  onRetry,
  onSync,
  isSyncing,
  page,
  onPageChange,
  selectedCategory,
  onSelectCategory,
}: CategoriesBrowserProps) {
  const { data: dashboard, isLoading: dashboardLoading } = useDashboard();

  const categoryCounts = new Map(
    (dashboard?.categories ?? []).map((item) => [item.category, item.count]),
  );

  const selectableCategories = EMAIL_CATEGORY_OPTIONS.filter((option) => option.value !== "all");

  return (
    <div className="space-y-6">
      <div>
        <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-brand-muted">
          Pick a category
        </p>
        {dashboardLoading ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={index} className="h-20 rounded-2xl" />
            ))}
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <button
              type="button"
              onClick={() => onSelectCategory("all")}
              className={cn(
                "rounded-2xl border bg-gradient-to-br p-4 text-left transition-all",
                "from-white to-brand-green-soft/40 border-border",
                selectedCategory === "all" && "ring-2 ring-brand-green/40 shadow-soft",
              )}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-brand-text">All categories</span>
                <Tags className="h-4 w-4 text-brand-green" />
              </div>
              <p className="mt-1 text-2xl font-bold tabular-nums text-brand-text">
                {formatNumber(dashboard?.stats.total_emails ?? 0)}
              </p>
            </button>

            {selectableCategories.map((option) => {
              const count = categoryCounts.get(option.value) ?? 0;
              const active = selectedCategory === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => onSelectCategory(option.value)}
                  className={cn(
                    "rounded-2xl border bg-gradient-to-br p-4 text-left transition-all",
                    CATEGORY_TILE_COLORS[option.value] ?? "from-white to-muted border-border",
                    active && "ring-2 ring-brand-green/40 shadow-soft",
                    count === 0 && "opacity-60",
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-semibold text-brand-text">{option.label}</span>
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-[10px] font-bold uppercase",
                        CATEGORY_BADGE_STYLES[option.value] ?? "bg-accent text-brand-text",
                      )}
                    >
                      {option.label}
                    </span>
                  </div>
                  <p className="mt-1 text-2xl font-bold tabular-nums text-brand-text">
                    {formatNumber(count)}
                  </p>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {selectedCategory === "all" ? (
        <EmptyState
          icon={Tags}
          title="Select a category"
          description="Choose a category tile above to browse emails in that group."
        />
      ) : (
        <div>
          <p className="mb-3 text-sm font-medium text-brand-muted">
            Showing{" "}
            <span className="font-semibold text-brand-text">
              {EMAIL_CATEGORY_OPTIONS.find((o) => o.value === selectedCategory)?.label}
            </span>{" "}
            emails
          </p>
          <EmailList
            data={data}
            isLoading={isLoading}
            isFetching={isFetching}
            isError={isError}
            onRetry={onRetry}
            onSync={onSync}
            isSyncing={isSyncing}
            page={page}
            onPageChange={onPageChange}
          />
        </div>
      )}
    </div>
  );
}
