import { Link, useLocation } from "react-router-dom";
import {
  Inbox,
  LayoutDashboard,
  MessageSquare,
  Search,
  Settings,
  Sparkles,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { APP_NAME, NAV_ITEMS, ROUTES } from "@/lib/constants";

const ICONS = {
  LayoutDashboard,
  Inbox,
  MessageSquare,
  Search,
  Settings,
} as const;

export function Sidebar() {
  const location = useLocation();

  return (
    <aside className="hidden h-screen w-64 shrink-0 flex-col border-r border-white/60 bg-white/60 p-6 backdrop-blur-xl lg:sticky lg:top-0 lg:flex">
      <Link to={ROUTES.DASHBOARD} className="mb-10 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-brand-green-soft shadow-glow">
          <Sparkles className="h-5 w-5 text-brand-green" />
        </div>
        <div>
          <p className="text-sm font-bold text-brand-text">{APP_NAME}</p>
          <p className="text-xs text-brand-muted">Gmail copilot</p>
        </div>
      </Link>

      <nav className="flex flex-1 flex-col gap-1">
        {NAV_ITEMS.map((item) => {
          const Icon = ICONS[item.icon as keyof typeof ICONS];
          const active = location.pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              to={item.href}
              className={cn("nav-item", active ? "nav-item-active" : "nav-item-inactive")}
            >
              <Icon className={cn("h-4 w-4", active && "text-brand-green")} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto rounded-2xl bg-brand-green-soft/60 p-4">
        <p className="text-xs font-semibold text-brand-text">AI-powered inbox</p>
        <p className="mt-1 text-xs text-brand-muted">Summarize, reply, and search smarter.</p>
      </div>
    </aside>
  );
}
