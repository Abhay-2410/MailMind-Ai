import { Link, useLocation } from "react-router-dom";
import { Inbox, LayoutDashboard, MessageSquare, Search, Settings } from "lucide-react";

import { cn } from "@/lib/utils";
import { NAV_ITEMS } from "@/lib/constants";

const ICONS = {
  LayoutDashboard,
  Inbox,
  MessageSquare,
  Search,
  Settings,
} as const;

export function MobileNav() {
  const location = useLocation();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 border-t border-white/60 bg-white/90 px-2 py-2 backdrop-blur-xl lg:hidden">
      <ul className="flex items-center justify-around">
        {NAV_ITEMS.map((item) => {
          const Icon = ICONS[item.icon as keyof typeof ICONS];
          const active = location.pathname.startsWith(item.href);
          return (
            <li key={item.href}>
              <Link
                to={item.href}
                className={cn(
                  "flex flex-col items-center gap-0.5 rounded-xl px-2.5 py-1.5 text-[10px] font-semibold transition-colors duration-200",
                  active ? "text-brand-green" : "text-brand-muted",
                )}
              >
                <span
                  className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-xl transition-colors",
                    active && "bg-brand-green-soft",
                  )}
                >
                  <Icon className="h-4 w-4" />
                </span>
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
