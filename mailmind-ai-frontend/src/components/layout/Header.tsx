import { LogOut } from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useAuth } from "@/hooks/useAuth";

interface HeaderProps {
  title: string;
  description?: string;
  descriptionTone?: "error";
}

export function Header({ title, description, descriptionTone }: HeaderProps) {
  const { user, logout } = useAuth();

  const initials = user?.full_name
    ?.split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase() ?? "MM";

  return (
    <header className="surface-chrome sticky top-0 z-40 border-b px-4 py-4 sm:px-8">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <h1 className="heading-page truncate">{title}</h1>
          {description ? (
            <p
              className={`mt-0.5 truncate text-sm ${
                descriptionTone === "error" ? "font-medium text-destructive" : "text-body"
              }`}
            >
              {description}
            </p>
          ) : null}
        </div>

        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          <div className="hidden text-right sm:block">
            <p className="text-sm font-medium text-brand-text">{user?.full_name ?? user?.email}</p>
            <p className="text-xs text-brand-muted">{user?.email}</p>
          </div>
          <Separator orientation="vertical" className="hidden h-8 sm:block" />
          <Avatar className="h-10 w-10 border-2 border-border shadow-sm">
            <AvatarImage src={user?.avatar_url ?? undefined} alt={user?.full_name ?? "User"} />
            <AvatarFallback className="bg-brand-green-soft text-brand-text">{initials}</AvatarFallback>
          </Avatar>
          <Button
            variant="ghost"
            size="icon"
            className="rounded-xl text-brand-muted hover:bg-brand-green-soft hover:text-brand-text"
            onClick={() => void logout()}
            aria-label="Log out"
          >
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </header>
  );
}
