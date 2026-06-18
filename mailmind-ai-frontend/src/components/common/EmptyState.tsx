import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-white/50 px-8 py-16 text-center",
        className,
      )}
    >
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-green-soft">
        <Icon className="h-6 w-6 text-brand-green" />
      </div>
      <h3 className="text-lg font-semibold text-brand-text">{title}</h3>
      <p className="mt-2 max-w-sm text-body">{description}</p>
      {action ? <div className="mt-6">{action}</div> : null}
    </div>
  );
}
