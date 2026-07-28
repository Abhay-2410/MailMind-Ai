import { Link, useLocation, useNavigate } from "react-router-dom";
import { BarChart3, Inbox, LayoutDashboard, Settings, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { APP_NAME, ROUTES } from "@/lib/constants";
import { SIDEBAR_NAV_ITEMS } from "@/lib/navigation";
import { useAssistantStore } from "@/stores/assistantStore";
import { useAuthStore } from "@/stores/authStore";

const ICONS = {
  dashboard: LayoutDashboard,
  inbox: Inbox,
  summaries: Sparkles,
  insights: BarChart3,
  settings: Settings,
} as const;

export function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const clearMessages = useAssistantStore((s) => s.clearMessages);

  function handleNewConversation() {
    clearMessages();
    navigate(ROUTES.ASSISTANT, { replace: location.pathname === ROUTES.ASSISTANT });
  }

  return (
    <aside className="surface-chrome hidden h-screen w-[280px] shrink-0 flex-col border-r p-6 lg:sticky lg:top-0 lg:flex">
      <Link to={ROUTES.DASHBOARD} className="mb-8 flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl brand-icon-surface">
          <Sparkles className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm font-bold text-foreground">{APP_NAME}</p>
          <p className="text-xs font-medium text-muted-foreground">Gmail copilot</p>
        </div>
      </Link>

      <Button type="button" className="mb-8 h-11 rounded-2xl shadow-glow" onClick={handleNewConversation}>
        New conversation
      </Button>

      <nav className="flex flex-col gap-1">
        {SIDEBAR_NAV_ITEMS.map((item) => {
          const Icon = ICONS[item.id as keyof typeof ICONS] ?? Inbox;
          const active = item.isActive(location);
          return (
            <Link
              key={item.id}
              to={item.href}
              className={cn("nav-item", active ? "nav-item-active" : "nav-item-inactive")}
            >
              <Icon className={cn("h-4 w-4 shrink-0", active ? "text-primary" : "text-muted-foreground")} />
              <span className="whitespace-nowrap">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="surface-panel mt-auto p-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full brand-gradient text-sm font-bold text-primary-foreground shadow-soft">
            {(user?.full_name?.[0] ?? user?.email?.[0] ?? "M").toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-foreground">
              {user?.full_name ?? "MailMind User"}
            </p>
            <p className="truncate text-xs font-medium text-muted-foreground">{user?.email}</p>
          </div>
        </div>
        <div className="mt-3 flex items-center justify-between text-xs">
          <span className="font-medium text-muted-foreground">Gmail connected</span>
          <span className="badge-brand">Free</span>
        </div>
      </div>
    </aside>
  );
}
