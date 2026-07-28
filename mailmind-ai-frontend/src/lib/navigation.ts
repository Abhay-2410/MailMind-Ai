import type { Location } from "react-router-dom";

import { ROUTES } from "@/lib/constants";

export type SidebarNavItem = {
  id: string;
  label: string;
  href: string;
  isActive: (location: Location) => boolean;
};

function searchParams(location: Location) {
  return new URLSearchParams(location.search);
}

function inboxViewActive(location: Location, view?: string) {
  if (location.pathname !== ROUTES.INBOX) return false;
  const current = searchParams(location).get("view");
  if (!view) return !current;
  return current === view;
}

/** Desktop sidebar — each item has a unique active rule (no shared hrefs). */
export const SIDEBAR_NAV_ITEMS: SidebarNavItem[] = [
  {
    id: "dashboard",
    label: "Dashboard",
    href: ROUTES.DASHBOARD,
    isActive: (location) =>
      location.pathname === ROUTES.DASHBOARD &&
      searchParams(location).get("section") !== "insights",
  },
  {
    id: "inbox",
    label: "Inbox",
    href: ROUTES.INBOX,
    isActive: (location) => inboxViewActive(location),
  },
  {
    id: "summaries",
    label: "Summaries",
    href: `${ROUTES.INBOX}?view=summaries`,
    isActive: (location) => inboxViewActive(location, "summaries"),
  },
  {
    id: "insights",
    label: "Category Insights",
    href: `${ROUTES.DASHBOARD}?section=insights`,
    isActive: (location) =>
      location.pathname === ROUTES.DASHBOARD &&
      searchParams(location).get("section") === "insights",
  },
  {
    id: "settings",
    label: "Settings",
    href: ROUTES.SETTINGS,
    isActive: (location) => location.pathname === ROUTES.SETTINGS,
  },
];

export function formatSyncProgress(fetched: number, newCount: number): string {
  return `${fetched.toLocaleString()} imported · ${newCount.toLocaleString()} new`;
}

export const SYNC_BUTTON_LABEL = {
  idle: "Sync inbox",
  running: "Syncing…",
  categorizing: "Categorizing…",
} as const;
