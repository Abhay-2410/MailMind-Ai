import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "@/lib/api";
import type { SearchHistoryItem, SearchResponse } from "@/types/search";

export async function executeSearch(query: string, maxResults = 50): Promise<SearchResponse> {
  return apiRequest<SearchResponse>("/search", {
    method: "POST",
    body: JSON.stringify({ query, max_results: maxResults }),
  });
}

export async function fetchSearchHistory(limit = 10): Promise<SearchHistoryItem[]> {
  return apiRequest<SearchHistoryItem[]>(`/search/history?limit=${limit}`);
}

export function useSearchHistory() {
  return useQuery({
    queryKey: ["search-history"],
    queryFn: () => fetchSearchHistory(),
  });
}

export function useExecuteSearch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (query: string) => executeSearch(query),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["search-history"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["inbox"] });
    },
  });
}
