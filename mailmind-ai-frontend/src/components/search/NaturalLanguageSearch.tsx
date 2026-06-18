import { AlertCircle, Clock, Loader2, Search, Sparkles } from "lucide-react";
import { useState } from "react";

import { EmailListItem } from "@/components/inbox/EmailListItem";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useExecuteSearch, useSearchHistory } from "@/hooks/useSearch";
import { formatDistanceToNow } from "@/lib/format";
import { SEARCH_SUGGESTIONS, type SearchResponse } from "@/types/search";

export function NaturalLanguageSearch() {
  const [query, setQuery] = useState("");
  const [lastResult, setLastResult] = useState<SearchResponse | null>(null);
  const searchMutation = useExecuteSearch();
  const { data: history, isLoading: historyLoading } = useSearchHistory();

  async function runSearch(searchQuery: string) {
    const trimmed = searchQuery.trim();
    if (!trimmed || searchMutation.isPending) return;

    setQuery(trimmed);
    try {
      const result = await searchMutation.mutateAsync(trimmed);
      setLastResult(result);
    } catch {
      setLastResult(null);
    }
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    void runSearch(query);
  }

  return (
    <div className="space-y-6">
      <Card className="surface-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Sparkles className="h-5 w-5 text-brand-green" />
            Natural Language Search
          </CardTitle>
          <CardDescription>
            Describe what you&apos;re looking for — AI converts it to Gmail search syntax and fetches
            matching emails.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={handleSubmit} className="flex flex-col gap-3 sm:flex-row">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-brand-muted" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder='Try "Show unread Amazon emails"'
                className="pl-9"
                disabled={searchMutation.isPending}
              />
            </div>
            <Button type="submit" disabled={!query.trim() || searchMutation.isPending}>
              {searchMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Searching…
                </>
              ) : (
                "Search"
              )}
            </Button>
          </form>

          <div className="flex flex-wrap gap-2">
            {SEARCH_SUGGESTIONS.map((suggestion) => (
              <Button
                key={suggestion}
                type="button"
                variant="outline"
                size="sm"
                className="rounded-full bg-white"
                onClick={() => void runSearch(suggestion)}
                disabled={searchMutation.isPending}
              >
                {suggestion}
              </Button>
            ))}
          </div>

          {searchMutation.isError ? (
            <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{searchMutation.error.message || "Search failed. Please try again."}</span>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {lastResult ? (
        <Card className="surface-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Gmail query</CardTitle>
            <CardDescription>{lastResult.explanation}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <code className="block rounded-xl border border-border bg-accent/50 px-4 py-3 text-sm text-brand-text">
              {lastResult.gmail_query}
            </code>
            <p className="text-sm text-brand-muted">
              {lastResult.total} result{lastResult.total === 1 ? "" : "s"} · via {lastResult.model_used}
            </p>
          </CardContent>
        </Card>
      ) : null}

      {searchMutation.isPending ? (
        <div className="space-y-3">
          <Skeleton className="h-20 rounded-2xl" />
          <Skeleton className="h-24 rounded-2xl" />
          <Skeleton className="h-24 rounded-2xl" />
        </div>
      ) : null}

      {lastResult && !searchMutation.isPending ? (
        lastResult.results.length > 0 ? (
          <div className="overflow-hidden rounded-2xl border border-border bg-white/80 shadow-sm">
            {lastResult.results.map((email) => (
              <EmailListItem key={email.id} email={email} />
            ))}
          </div>
        ) : (
          <Card className="surface-card border-dashed">
            <CardContent className="py-10 text-center">
              <p className="text-brand-text">No emails matched that search.</p>
              <p className="mt-2 text-sm text-brand-muted">
                Try a broader query or sync your inbox first.
              </p>
            </CardContent>
          </Card>
        )
      ) : null}

      <Card className="surface-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Clock className="h-4 w-4 text-brand-green" />
            Recent searches
          </CardTitle>
        </CardHeader>
        <CardContent>
          {historyLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : !history || history.length === 0 ? (
            <p className="text-sm text-brand-muted">Your recent searches will appear here.</p>
          ) : (
            <ul className="space-y-2">
              {history.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => void runSearch(item.natural_query)}
                    disabled={searchMutation.isPending}
                    className="flex w-full items-start justify-between gap-3 rounded-xl border border-border bg-white/70 px-4 py-3 text-left transition-colors hover:bg-accent/60 disabled:opacity-50"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-brand-text">{item.natural_query}</p>
                      <p className="truncate text-xs text-brand-muted">{item.gmail_query}</p>
                    </div>
                    <div className="shrink-0 text-right text-xs text-brand-muted">
                      <p>{item.results_count} results</p>
                      <p>{formatDistanceToNow(item.created_at)}</p>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
