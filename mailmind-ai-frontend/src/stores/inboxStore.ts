import { create } from "zustand";

export type InboxViewFilter = "all" | "unread" | "read" | "important";

export type EmailCategoryFilter =
  | "all"
  | "important"
  | "work"
  | "personal"
  | "finance"
  | "promotions"
  | "social"
  | "updates";

interface InboxState {
  page: number;
  pageSize: number;
  viewFilter: InboxViewFilter;
  category: EmailCategoryFilter;
  search: string;
  setPage: (page: number) => void;
  setViewFilter: (filter: InboxViewFilter) => void;
  setCategory: (category: EmailCategoryFilter) => void;
  setSearch: (search: string) => void;
}

export const useInboxStore = create<InboxState>((set) => ({
  page: 1,
  pageSize: 20,
  viewFilter: "all",
  category: "all",
  search: "",
  setPage: (page) => set({ page }),
  setViewFilter: (viewFilter) => set({ viewFilter, page: 1 }),
  setCategory: (category) => set({ category, page: 1 }),
  setSearch: (search) => set({ search, page: 1 }),
}));
