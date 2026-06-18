export const APP_NAME = "MailMind AI";

export const ROUTES = {
  LOGIN: "/login",
  AUTH_CALLBACK: "/auth/callback",
  DASHBOARD: "/dashboard",
  INBOX: "/inbox",
  EMAIL: "/email",
  ASSISTANT: "/assistant",
  SEARCH: "/search",
  SETTINGS: "/settings",
} as const;

export const NAV_ITEMS = [
  { label: "Dashboard", href: ROUTES.DASHBOARD, icon: "LayoutDashboard" },
  { label: "Inbox", href: ROUTES.INBOX, icon: "Inbox" },
  { label: "Assistant", href: ROUTES.ASSISTANT, icon: "MessageSquare" },
  { label: "Search", href: ROUTES.SEARCH, icon: "Search" },
  { label: "Settings", href: ROUTES.SETTINGS, icon: "Settings" },
] as const;

export const ROUTE_META: Record<string, { title: string; description?: string }> = {
  [ROUTES.DASHBOARD]: { title: "Dashboard", description: "Overview of your inbox activity" },
  [ROUTES.INBOX]: { title: "Inbox", description: "All your emails in one place" },
  [ROUTES.EMAIL]: { title: "Email", description: "Read and respond with AI" },
  [ROUTES.ASSISTANT]: { title: "Assistant", description: "Chat with your inbox" },
  [ROUTES.SEARCH]: { title: "Search", description: "Find emails with natural language" },
  [ROUTES.SETTINGS]: { title: "Settings", description: "Manage your account and preferences" },
};
