import type { LucideIcon } from "lucide-react";

import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string | number;
  icon: LucideIcon;
  trend?: string;
  className?: string;
}

export function StatCard({ label, value, icon: Icon, trend, className }: StatCardProps) {
  return (
    <Card className={cn("surface-card overflow-hidden", className)}>
      <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
        <p className="text-sm font-medium text-brand-muted">{label}</p>
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-green-soft">
          <Icon className="h-4 w-4 text-brand-green" />
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-3xl font-bold tracking-tight text-brand-text">{value}</p>
        {trend ? <p className="mt-1 text-xs text-brand-muted">{trend}</p> : null}
      </CardContent>
    </Card>
  );
}
